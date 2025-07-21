from io import StringIO
import xml.etree.ElementTree as ET
import sys

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

def extractReportInformation(s_xmlString: str):
    """
    Extract information from IWXXM XML string.
    Returns a list of dictionaries - one per report found.
    For standalone reports, returns a single-item list.
    For collections, returns a list with one dictionary per report.
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
    xlink_uri = "http://www.w3.org/1999/xlink"

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
                print("No AIXM designator found.")
            if type_elements:
                type_ = type_elements[0].text
                d_extractedInfo["location_type"] = type_
            else:
                print("No AIXM type found.")

        # If the report type is METAR, SPECI, or TAF, we need to find the ICAO code of the
        # reporting station. The ICAO code is located in aixm:AirportHeliport, where we need to search
        # for aixm:designator element.
        if s_reportType in ["METAR", "SPECI", "TAF"]:
            xpath_designator = f"{{{iwxxm_uri}}}aerodrome//{{{aixm_uri}}}AirportHeliport//{{{aixm_uri}}}designator"
            designator_elements = report_element.findall(xpath_designator, nsmap)
            if designator_elements:
                designator = designator_elements[0].text
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
        else:
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
    s_xmlString = None
    xml_file = None
    if len(sys.argv) == 2:
        # Read the XML file name from the command line
        xml_file = sys.argv[1]
        with open(xml_file, 'r') as f:
            s_xmlString = f.read()
    else:
        # The user must provide a file on input, if not we need to exit
        print("Usage: python iwxxm_utils.py <xml_file>")
        sys.exit(1)

    # Example usage of the functions
    extracted_info_list = extractReportInformation(s_xmlString)
    print(f"Found {len(extracted_info_list)} report(s)")
    for i, extracted_info in enumerate(extracted_info_list, 1):
        print(f"Report {i}: {extracted_info}")


