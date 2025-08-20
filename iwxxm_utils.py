from io import StringIO
import xml.etree.ElementTree as ET
import sys
import re
from WMOEncapsulation import WMOReader
from io import BytesIO
from typing import Union

WMO_HEADER_PATTERN = re.compile(br"^(\d{8})(00|01)\r\r\n", re.DOTALL)

def getIWXXMVersions(xml_string: str) -> set:
    # using ET.iterparse to avoid loading the entire document into memory
    # we will find all the namespace declarations and extract the IWXXM
    # version from those that start with "http://icao.int/iwxxm/"
    iwxxm_versions = set()
    base = "http://icao.int/iwxxm/"
    xml_io = StringIO(xml_string)
    for event, (prefix, uri) in ET.iterparse(xml_io, events=["start-ns"]):
        # Check if this namespace starts with http://icao.int/iwxxm/
        if uri.startswith(base):
            # Extract the portion after the final slash
            # For example, if uri == "http://icao.int/iwxxm/3.1", 
            # remainder will be "3.1"
            remainder = uri.rsplit('/', 1)[-1]
            iwxxm_versions.add(remainder)
    
    return iwxxm_versions

def getIWXXMReportTypes(xml_root: ET.Element) -> set:
    """
    Parse the given IWXXM XML (single or multiple reports).
    Return a list of the detected meteorological report types,
    for example ["SIGMET"] or ["AIRMET", "SIGMET"].
    """

    def local_name(tag):
        # Strip namespace, e.g. '{http://icao.int/iwxxm/3.0}SIGMET' -> 'SIGMET'
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    root_localname = local_name(xml_root.tag)

    # Case 1: The root itself is the IWXXM report (e.g. <iwxxm:SIGMET ...>)
    if root_localname != 'MeteorologicalBulletin':
        return [root_localname]

    # Case 2: The root is <collect:MeteorologicalBulletin>, which has
    #         <collect:meteorologicalInformation> children, each containing an IWXXM report.
    report_types = set()
    for child in xml_root:
        # We only care about immediate children named 'meteorologicalInformation'
        if local_name(child.tag) == 'meteorologicalInformation':
            # Each child under <collect:meteorologicalInformation> is typically one IWXXM report.
            for report in child:
                report_types.add(local_name(report.tag))

    return report_types

def extractReportInformation(data: Union[str, bytes], context: str = None):
    """
    Accepts data as either bytes or str. Detects WMO encapsulation using a bytes regex. 
    If WMO encapsulation is detected, processes each contained message as XML.
    Otherwise, decodes as UTF-8 and processes as XML.
    
    Args:
        data: The XML content as bytes or string
        context: Optional context information for error messages (e.g., filename, AMQP message ID, etc.)
    """
    # Ensure data is bytes for detection
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = data
    # WMO encapsulation detection
    if len(data_bytes) >= 13 and WMO_HEADER_PATTERN.match(data_bytes[:13]):
        # WMO encapsulation detected
        print(f"WMO encapsulation detected, processing {len(data_bytes)} bytes")
        with WMOReader(file=BytesIO(data_bytes), b_requireZeroTail=False) as reader:
            messages = reader.read()
        print(f"Extracted {len(messages)} messages from WMO encapsulation")
        all_reports = []
        total_msgs = len(messages)
        for i, msg_bytes in enumerate(messages, 1):
            try:
                msg_str = msg_bytes.decode('utf-8', errors='replace')
                xml_start_index = msg_str.find('\n') + 1
                xml_content = msg_str[xml_start_index:]
                # Process each extracted message as XML (skip WMO detection for individual messages)
                reports = _extractReportInformationFromXML(xml_content, context)
                all_reports.extend(reports)
            except Exception as e:
                print(f"Skipping message {i}/{total_msgs} due to XML error: {e}")
            # Progress update every 1000 messages (and at completion)
            if total_msgs >= 1000 and (i % 1000 == 0 or i == total_msgs):
                print(f"Processed {i}/{total_msgs} messages ({i/total_msgs*100:.1f}%)")
        return all_reports
    # Not WMO encapsulation, treat as XML
    if isinstance(data, bytes):
        s_xmlString = data.decode('utf-8', errors='replace')
    else:
        s_xmlString = data
    
    return _extractReportInformationFromXML(s_xmlString, context)

def _extractReportInformationFromXML(s_xmlString: str, context: str = None):
    """
    Internal function to extract IWXXM report information from an XML string.
    This contains the original XML processing logic.
    
    Args:
        s_xmlString: The XML content as string
        context: Optional context information for error messages (e.g., filename, AMQP message ID, etc.)
    """
    # Get the IWXXM version from the XML string
    set_iwxxmVersions = getIWXXMVersions(s_xmlString)

    if len(set_iwxxmVersions) == 0:
        print(f"No IWXXM version found!")
        return []
    elif len(set_iwxxmVersions) > 1:
        print(f"Multiple IWXXM versions found, will use the first one: {set_iwxxmVersions}")

    s_iwxxmVersion = set_iwxxmVersions.pop()

    xml_tree = ET.parse(StringIO(s_xmlString))
    xml_root = xml_tree.getroot()

    # Extract specific namespace URIs
    nsmap = {}
    xml_io = StringIO(s_xmlString)
    for event, (prefix, uri) in ET.iterparse(xml_io, events=["start-ns"]):
        nsmap[prefix] = uri

    # Find the required namespaces
    iwxxm_uri = next((uri for uri in nsmap.values() if uri.startswith("http://icao.int/iwxxm/")), None)
    aixm_uri = next((uri for uri in nsmap.values() if uri.startswith("http://www.aixm.aero/schema/")), None)
    gml_uri = next((uri for uri in nsmap.values() if uri.startswith("http://www.opengis.net/gml/")), None)
    collect_uri = next((uri for uri in nsmap.values() if uri.startswith("http://def.wmo.int/collect/")), None)
    xlink_uri = next((uri for uri in nsmap.values() if uri.startswith("http://www.w3.org/1999/xlink")), None)

    def local_name(tag):
        # Strip namespace, e.g. '{http://icao.int/iwxxm/3.0}SIGMET' -> 'SIGMET'
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    def extract_single_report_info(report_element):
        """Extract information from a single IWXXM report element."""
        d_extractedInfo = {}
        
        s_reportType = local_name(report_element.tag)
        
        # Store the report type and IWXXM version
        d_extractedInfo["report_type"] = s_reportType
        d_extractedInfo["iwxxm_version"] = s_iwxxmVersion
        
        # Extract the gml:id attribute if present
        if gml_uri:
            gml_id = report_element.get(f"{{{gml_uri}}}id")
            if gml_id:
                d_extractedInfo["gml_id"] = gml_id

        # If the report type is SIGMET or AIRMET, we need to find the ICAO code of the airspace
        if s_reportType == "SIGMET" or s_reportType == "AIRMET":
            # SIGMET report type
            xpath_designator = f"{{{iwxxm_uri}}}issuingAirTrafficServicesRegion//{{{aixm_uri}}}designator"
            xpath_type = f"{{{iwxxm_uri}}}issuingAirTrafficServicesRegion//{{{aixm_uri}}}type"
            # Find the first occurence of the designator element
            designator_elements = report_element.findall(xpath_designator, nsmap)
            type_elements = report_element.findall(xpath_type, nsmap)
            # Store the AIXM designator and type strings
            if designator_elements:
                designator = designator_elements[0].text
                d_extractedInfo["airspace_designator"] = designator
            else:
                gml_id = d_extractedInfo.get("gml_id", "N/A")
                context_info = f" in {context}" if context else ""
                print(f"No AIXM designator found{context_info}, gml:id: {gml_id}")
            if type_elements:
                type_ = type_elements[0].text
                d_extractedInfo["location_type"] = type_
            else:
                gml_id = d_extractedInfo.get("gml_id", "N/A")
                context_info = f" in {context}" if context else ""
                print(f"No AIXM type found{context_info}, gml:id: {gml_id}")

        # Extract the reportStatus attribute of the IWXXM report.
        reportStatus = report_element.get("reportStatus")
        d_extractedInfo["report_status"] = reportStatus

        # For SIGMET, AIRMET, and related reports, check for isCancelReport attribute
        if s_reportType in ["SIGMET", "AIRMET", "VolcanicAshSIGMET", "TropicalCycloneSIGMET"]:
            isCancelReport = report_element.get("isCancelReport")
            if isCancelReport is not None:
                # Convert string to boolean
                d_extractedInfo["is_cancel_report"] = isCancelReport.lower() == "true"
            else:
                d_extractedInfo["is_cancel_report"] = False

        # Check if this is a NIL report by examining iwxxm:baseForecast
        is_nil_report = False
        if s_reportType == "TAF":
            xpath_baseForecast = f"{{{iwxxm_uri}}}baseForecast"
            baseForecast_elements = report_element.findall(xpath_baseForecast, nsmap)
            if baseForecast_elements:
                baseForecast = baseForecast_elements[0]
                # Check if baseForecast has nilReason attribute and no child elements
                if baseForecast.get("nilReason") is not None and len(baseForecast) == 0:
                    is_nil_report = True
                    d_extractedInfo["NIL"] = True

        # If the report type is METAR, SPECI, or TAF, we need to find the ICAO code of the
        # reporting station. The ICAO code is located in aixm:AirportHeliport, where we need to search
        # for aixm:designator element (newer IWXXM) or aixm:locationIndicatorICAO (older IWXXM).
        if s_reportType in ["METAR", "SPECI", "TAF"]:
            # First try the standard aixm:designator
            xpath_designator = f"{{{iwxxm_uri}}}aerodrome//{{{aixm_uri}}}AirportHeliport//{{{aixm_uri}}}designator"
            designator_elements = report_element.findall(xpath_designator, nsmap)
            
            if designator_elements:
                designator = designator_elements[0].text
                d_extractedInfo["aerodrome_designator"] = designator
            else:
                # If not found, try aixm:locationIndicatorICAO (older IWXXM versions)
                xpath_location_icao = f"{{{iwxxm_uri}}}aerodrome//{{{aixm_uri}}}AirportHeliport//{{{aixm_uri}}}locationIndicatorICAO"
                location_icao_elements = report_element.findall(xpath_location_icao, nsmap)
                if location_icao_elements:
                    designator = location_icao_elements[0].text
                    d_extractedInfo["aerodrome_designator"] = designator

        # Now we need to find out the issueTime of the IWXXM report.
        xpath_issueTime = f"{{{iwxxm_uri}}}issueTime//{{{gml_uri}}}timePosition"
        issueTime_elements = report_element.findall(xpath_issueTime, nsmap)
        if issueTime_elements:
            issueTime = issueTime_elements[0].text
            d_extractedInfo["issue_time"] = issueTime

        # Some reports like METAR or SPECI will also have an iwxxm:observationTime element.
        observationTime = None
        xpath_observationTime = f"{{{iwxxm_uri}}}observationTime//{{{gml_uri}}}timePosition"
        observationTime_elements = report_element.findall(xpath_observationTime, nsmap)
        if observationTime_elements:
            observationTime = observationTime_elements[0].text
            d_extractedInfo["observation_time"] = observationTime
        elif xlink_uri is not None:
            # No observationTime found, check for xlink:href attribute
            xpath_observationTime_href = f"{{{iwxxm_uri}}}observationTime[@xlink:href]"

            observationTime_href_elements = report_element.findall(xpath_observationTime_href, nsmap)
            if observationTime_href_elements:
                # Get the xlink:href attribute value    
                href = observationTime_href_elements[0].get(f"{{{xlink_uri}}}href")
                # If the href starts with '#', it is a local reference to a gml:id in the same document, so remove it
                # and use the gml:id to find the gml:TimeInstant element.
                href = href.lstrip('#')
                # Find the gml:TimeInstant element with the given gml:id
                xpath_timeInstant = f".//{{{gml_uri}}}TimeInstant[@{{{gml_uri}}}id='{href}']"
                timeInstant_elements = xml_root.findall(xpath_timeInstant, nsmap)
                if timeInstant_elements:
                    # Get the gml:timePosition element from the TimeInstant element
                    timePosition_elements = timeInstant_elements[0].findall(f".//{{{gml_uri}}}timePosition", nsmap)
                    if timePosition_elements:
                        observationTime = timePosition_elements[0].text
                        d_extractedInfo["observation_time"] = observationTime
                    else:
                        print("No gml:timePosition found in the referenced gml:TimeInstant.")
                else:
                    print(f"No gml:TimeInstant found with gml:id '{href}'.")
        
        # For IWXXM reports that have an iwxxm:validPeriod element, we need to find the gml:beginPosition
        # and gml:endPosition elements. Skip this for NIL TAFs as they don't have validity periods.
        if not is_nil_report:
            # Extract validPeriod (main validity period of the report)
            xpath_validPeriod = f"{{{iwxxm_uri}}}validPeriod//{{{gml_uri}}}TimePeriod"
            validPeriod_elements = report_element.findall(xpath_validPeriod, nsmap)
            
            if validPeriod_elements:
                beginPosition = validPeriod_elements[0].find(f".//{{{gml_uri}}}beginPosition", nsmap)
                endPosition = validPeriod_elements[0].find(f".//{{{gml_uri}}}endPosition", nsmap)
                # if the beginPosition and endPosition elements are present, take their text values
                # and store them in the d_extractedInfo dictionary as start_datetime and end_datetime
                if beginPosition is not None and endPosition is not None:
                    d_extractedInfo["start_datetime"] = beginPosition.text
                    d_extractedInfo["end_datetime"] = endPosition.text
                else:
                    print("No gml:beginPosition or gml:endPosition found in the valid period element.")
            
            # Also extract cancelledReportValidPeriod if present (validity period of a cancelled report)
            xpath_cancelledValidPeriod = f"{{{iwxxm_uri}}}cancelledReportValidPeriod//{{{gml_uri}}}TimePeriod"
            cancelledValidPeriod_elements = report_element.findall(xpath_cancelledValidPeriod, nsmap)
            
            if cancelledValidPeriod_elements:
                cnl_beginPosition = cancelledValidPeriod_elements[0].find(f".//{{{gml_uri}}}beginPosition", nsmap)
                cnl_endPosition = cancelledValidPeriod_elements[0].find(f".//{{{gml_uri}}}endPosition", nsmap)
                # if the beginPosition and endPosition elements are present, take their text values
                # and store them in the d_extractedInfo dictionary as cnl_start_datetime and cnl_end_datetime
                if cnl_beginPosition is not None and cnl_endPosition is not None:
                    d_extractedInfo["cnl_start_datetime"] = cnl_beginPosition.text
                    d_extractedInfo["cnl_end_datetime"] = cnl_endPosition.text
                else:
                    print("No gml:beginPosition or gml:endPosition found in the cancelled report valid period element.")
        
        return d_extractedInfo

    root_localname = local_name(xml_root.tag)
    
    # Check if this is a collection (MeteorologicalBulletin) or a standalone report
    if root_localname == 'MeteorologicalBulletin':
        # This is a collection - process each meteorologicalInformation element
        reports_info = []
        for child in xml_root:
            if local_name(child.tag) == 'meteorologicalInformation':
                # Each meteorologicalInformation contains one IWXXM report
                for report_element in child:
                    if local_name(report_element.tag) in ['SIGMET', 'AIRMET', 'METAR', 'SPECI', 'TAF', 'TropicalCycloneAdvisory', 'VolcanicAshAdvisory', 'VolcanicAshSIGMET', 'TropicalCycloneSIGMET', 'SpaceWeatherAdvisory', 'SIGWXForecast']:
                        report_info = extract_single_report_info(report_element)
                        reports_info.append(report_info)
        return reports_info
    else:
        # This is a standalone report
        report_info = extract_single_report_info(xml_root)
        return [report_info]


if __name__ == '__main__':
    if len(sys.argv) == 2:
        # Read the XML file name from the command line
        xml_file = sys.argv[1]
        with open(xml_file, 'rb') as f:
            file_bytes = f.read()
        
        # Example usage of the functions
        extracted_info_list = extractReportInformation(file_bytes, f"file '{xml_file}'")
        print(f"Found {len(extracted_info_list)} report(s)")
        for i, extracted_info in enumerate(extracted_info_list, 1):
            print(f"Report {i}: {extracted_info}")
    else:
        # The user must provide a file on input, if not we need to exit
        print("Usage: python iwxxm_utils.py <xml_file>")
        print("For TAF early issuance analysis, use: python taf_stats_early_issue.py <directory_path>")
        sys.exit(1)


