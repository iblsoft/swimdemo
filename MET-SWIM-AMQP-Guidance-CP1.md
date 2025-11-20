# AMQP Message Structure in MET-SWIM (CP1)

In August 2025, the AMQP guidance was split into two parts: _CP1_ and _Next_

- The original working copy of this document is maintained in Markdown syntax: [MET-SWIM-AMQP-Guidance-CP1.md](https://github.com/iblsoft/swimdemo/blob/main/MET-SWIM-AMQP-Guidance-CP1.md).
- Properties that go beyond the CP1 MET-SWIM Service Definitions are maintained separately in [MET-SWIM-AMQP-Guidance-Next.md](https://github.com/iblsoft/swimdemo/blob/main/MET-SWIM-AMQP-Guidance-Next.md).
- The .docx version is generated using Pandoc, specifically the “vscode-pandoc” extension for the Microsoft Visual Studio Code, or the Cursor editor.

Members of the EUROCONTROL MET3SG Task Team on Service Architecture can submit pull requests towards the Markdown documents or comment on the .DOCX version on MET3SG SharePoint.

## Version History

### 1.0-draft1 (2025-06)

Initial draft for collecting feedback.

### 1.0-draft2 (2025-08-14)

1. Separated into guidance for CP1 (this document), and a "Next" document that contains the preparations for further extensions beyond CP1.
2. Removed content not directly relevant for CP1:
   1. External URL links for download of alternative formats (IWXXM will be passed in the message payload)
   2. Content type `application/url-list`
   3. Geometry properties (aerodrome coordinates, SIGMET bounding boxes)
   4. Payload integrity properties that were based on WIS 2.0 WNM, and SWIM TI Yellow Profile 2.0 mandates the se of S/MIME 4.0 for this purpose.
   5. Technical messages
3. The only way to send IWXXM is now embedding the data in the AMQP message payload with the content type `application/xml`. All mentions of `links` and `url-list` have been removed.
4. Discarded `subject` strings of type `DATA_METAR_LOWS_CORRECTION_2025040106450` because they create duplicity to the AMQP application properties, which are a much better filtering mechanism compared to application of wildcard patterns to a subject string (suggestion by Dario di Crescenzo).
5. The "subject" string now contains `aviation.weather.metar`.
6. Dropped all `properties.` prefixes, e.g. `properties.start_datetime`. The `properties` object is used in the WIS 2.0 Notification Message (WNM) standard because the WNM notifications conform to the GeoJSON structure. The GeoJSON specification mandates that all custom properties must be placed in a separate `properties` sub-object. In AMQP, however, the application properties concept is the direct equivalent of the GeoJSON properties - it is a list of application-defined data. So, there is no strict need to use prefixes.
7. New application property `properties.report_status` with values _NORMAL_, _AMENDMENT_, _CORRECTION_.
8. The new application property `issue_datetime` replaces the previous `properties.pubtime`. The publication time in WIS 2.0 WNM is the creation time of the notification message, so using this terminology for METAR, TAF, or SIGMET issue time was incorrect. In AMQP, the direct equivalent of `properties.pubtime` is the AMQP transport header property `creation-time`.
9. Added AMQP transport header property `creation-time`.
10. Rewritten section on `absolute-expiry-time`. The original idea of specifying expiration of 3h for METAR, 12h for TAF, 24h for SIGMET was incorrect.
11. The guidance for the priority field in AMQP transport header just states that certain message types should have higher priorities than others. For example, a TAF AMD should have higher priority than a regular TAF.
12. Added mention of _AMQP Messaging with Message Security_ using S/MIME 4.0 as defined in SWIM TI Yellow Profile 2.0, but without further implementation guidance. This section needs to be fleshed out.

### 1.0-draft3 (2025-08-20)

1. Renamed `issue_time` to `issue_datetime` for consistency with other temporal application properties.
2. Explanation why `absolute-expiry-time` and `creation-time` are handled differently - they are AMQP 1.0 built-in transport headers using the Unix time_t UTC timestamp in milliseconds, and they are not a part of the application headers.
3. `properties.icao_location_type` turned from _mandatory_ to _optional_, to be included only when disambiguation is needed. Explained motivation using `LECB BARCELONA FIR` vs. `BARCELONA UIR`.
4. Removed references to IWXXM 2.1, because the guidance related to property extraction does not work for versions older than IWXXM 3.0 (year 2018). IWXXM 3.0 significantly changed structure of IWXXM and abandoned the use of OM (Observation Model) schema.

### 1.0-draft4 (2025-08-21)

Rolled back the abandonment of `properties.<name>` prefixes for application properties. This is based on a discussion with Tom Kralidis (Meteorological Service of Canada, <https://github.com/tomkralidis>) who is the original author of the WIS 2.0 Notification Messages structure (WNM):

1. I the **"-Next"** proposals (beyond CP1) we have `geometry` and `links` prefixes, so leaving out the `property` prefix creates inconsistency with the JSON structure of the WNM messages we take inspiration from.
2. Using the `property.<name>` prefixes allows for easier interoperability between WIS 2.0 and MET-SWIM.
3. The WNM structure is based on [STAC (SpatioTemporal Assets Catalogs)](https://stacspec.org) specification.
4. The JSON structure of WNM notification metadata is based on [STAC Items](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md). STAC was created to introduce a standardised way of exposing collections of spatial temporal data, setting up some base guidelines to insure better interoperability (and searching in catalogues).
5. The STAC Item specification originated the [datetime](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#datetime), [start_datetime](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md#date-and-time-range) (and `end_datetime`) terminology.
  
## Introduction

This document defines the message structure and properties for AMQP 1.0 messages used in the MET-SWIM (Meteorological System Wide Information Management) implementation of the European Union Common Project Regulation (CP1). It provides guidance for developers and organisations implementing meteorological OPMET data distribution using AMQP 1.0 protocol in line with the SWIM Service definitions.

The guidance is maintained by the EUROCONTROL MET3SG Task Team on Service Architecture.

### Objectives

- Ensure interoperability between different MET-SWIM implementations
- Standardise AMQP message properties for meteorological data exchange
- Enable efficient filtering of messages
- Enable routing of messages to downstream systems based on typical information like report type or aerodrome/FIR code.
- Provide forward compatibility for future meteorological data types beyond CP1

### Scope (for CP1)

This specification currently covers the following meteorological report types that are covered by CP1 SWIM Service Definitions in IWXXM format:

- METAR
- SPECI
- TAF
- SIGMET

### WMO WIS 2.0 Notification Messages Relationship

This specification takes inspiration from the [WMO WIS 2.0 Notification Message Standard](https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-STABLE.html) while being tailored to the AMQP property syntax and specific requirements of MET-SWIM and the aviation meteorological community.

The WNM notification specification also guided the design of the notification messages in [OGC API - Environmental Data Retrieval (EDR) Part 2: Publish-Subscribe workflow](https://docs.ogc.org/is/23-057r1/23-057r1.html), which is used, for example, by the UK Met Office's QVA API (Quantitative Volcanic Ash) and is planned to be used by the SADIS API.

The notification metadata in WNM and OGC EDR publish/subscribe is in turn based on [STAC (SpatioTemporal Assets Catalogs)](https://stacspec.org) specification. The JSON structure and property terminology is based on so-called [STAC Items](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md).

### Authors

Editors:

- Boris Burger (IBL)

Contributions and feedback:

- Michal Weis (IBL)
- Dario di Crescenzo (EUROCONTROL)
- Michael Pichler (Austro Control)
- Tiaan Wessels (Netsys)
- Jürgen Schulze (met.no)
- Florian Dobener (DWD)

## References

- [EU Common Project Regulation (CP1)](https://eur-lex.europa.eu/eli/reg_impl/2021/116/oj/eng)
- [IWXXM METAR-SPECI Subscription and Request Service 1.0](https://eur-registry.swim.aero/services/eurocontrol-iwxxm-metar-speci-subscription-and-request-service-10)
- [IWXXM SIGMET Subscription and Request Service 1.0](https://eur-registry.swim.aero/services/eurocontrol-iwxxm-sigmet-subscription-and-request-service-10)
- [IWXXM TAF Subscription and Request Service 1.0](https://eur-registry.swim.aero/services/eurocontrol-iwxxm-taf-subscription-and-request-service-10)
- [OASIS AMQP 1.0 Specification, Part 3: Messaging](https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html)
- [OGC API - Environmental Data Retrieval (EDR)](https://ogcapi.ogc.org/edr/)
- [OGC API - Environmental Data Retrieval (EDR) Part 2: Publish-Subscribe workflow](https://docs.ogc.org/is/23-057r1/23-057r1.html)
- [AMQP Filter Expressions 1.0](https://docs.oasis-open.org/amqp/filtex/v1.0/filtex-v1.0.html)
- [WMO WIS 2.0 Overview](https://community.wmo.int/en/activity-areas/wis/WIS2-overview)
- [WMO WIS 2.0 Notification Message Standard](https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-STABLE.html)
- [STAC (SpatioTemporal Assets Catalogs)](https://stacspec.org)
- [STAC Item](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)
- [RFC 3339 - Date and Time on the Internet](https://www.rfc-editor.org/rfc/rfc3339.html)
- [ICAO Annex 3 - Meteorological Service for International Air Navigation](https://store.icao.int/en/annex-3-meteorological-service-for-international-air-navigation)

## AMQP 1.0 Message Structure

An AMQP message in the MET-SWIM context consists of the following components:

1. **Message Addressing** - Destination address using a hierarchical structure
2. **Message Transport Header** - Priority settings, expiration.
3. **Message Properties** - Standard AMQP properties including subject, content-type, etc.
4. **Application Properties** - Custom properties for meteorological data identification and filtering
5. **Message Payload** - The actual data (IWXXM XML).

## Message Addressing

### Address Structure

MET-SWIM uses a simplified three-level hierarchical structure for message addresses, inspired by  the [WIS 2 Topic Hierarchy](https://wmo-im.github.io/wis2-topic-hierarchy/standard/wis2-topic-hierarchy-STABLE.html).

For meteorological data, the address structure is:

```text
weather.aviation.<report-type>
```

Where `<report-type>` is one of:

- `metar` - for METAR and SPECI reports
- `taf` - for TAF reports
- `sigmet` - for SIGMET reports

### Examples

```text
weather.aviation.metar
weather.aviation.taf
weather.aviation.sigmet
```

### Wildcard Addresses in Subscriptions

Consumers can subscribe using wildcards to receive messages from multiple related addresses only if the AMQP broker supports wildcard functionality. **Wildcard support is not part of the AMQP 1.0 specification** - it is implemented as a broker-specific extension. Wildcard support is available in the popular AMQP brokers, but is not generally guaranteed.

**Common Wildcard Characters:**

- `*` - matches exactly one level in the hierarchy
- `#` - matches zero or more levels from that point onwards

**Wildcard Examples:**

```text
weather.aviation.*    # Subscribe to all aviation weather types
weather.#             # Subscribe to all weather data
#.metar               # Subscribe to METAR and SPECI
```

#### Broker Compatibility

Different AMQP 1.0 brokers implement wildcard support with varying levels of compatibility:

##### Apache ActiveMQ Artemis

- Full wildcard support using `*` and `#` characters
- Wildcards work with both queues and topics

##### Apache Qpid Proton

- Supports both `*` and `#` wildcards

##### RabbitMQ (with AMQP 1.0 plugin)

- There is some support for `*` and `#`
- RabbitMQ supports wildcards for routing from topic exchanges to queues. It does not, however, allow for automatic creation of queues from a topic. The users would need to create a queue and its binding themselves.

## AMQP Transport Header

### Priority

The `priority` field (0-9, where 9 is highest) SHALL be set according to the operational importance. For this version of the specification the exact priorities are not defined, however:

- SPECI should have higher priority than METAR
- TAF amendments should have higher priority than TAF
- SIGMET should have the highest priority

Example priorities:

| Report Type | Priority | Rationale |
|------------|----------|-----------|
| SIGMET | 7 | Highest priority for safety-critical information |
| SPECI | 6 | Special reports indicating significant changes |
| TAF AMD | 6 | Significant change to the original forecast |
| TAF | 5 | Forecast information with medium priority |
| METAR | 4 | Routine observations |

## AMQP Message Properties

The subsequent section define the AMQP 1.0 message properties used in MET-SWIM implementations. For detailed technical specifications, refer to the [OASIS AMQP 1.0 Specification, Part 3: Messaging](https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html).

- The documentation for the AMQP headers specifically is in [OASIS AMQP 1.0 specification, Part 3: Messaging - Section 3.2.5 - Header](https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html#type-header).
- See also [AMQP 1.0 specification, Part 3: Messaging, Section 3.2.6 - Properties](https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html#type-properties) for more details.

### subject (MANDATORY)

The `subject` SHALL represent the type of data transmitted, analogously to the WMO WIS 2.0 concept of topics and equal to the _source address_. This is useful for disambiguating data when using wildcard source address subscriptions.

Example:

```text
weather.aviation.metar
```

**Note:** In earlier versions of this specification, it was proposed that the `subject` string should hold the report type (METAR, SPECI, TAF, SIGMET), aerodrome or airspace ICAO code, issue time of the report, and so on. However, this created a duplicate identification and filtering mechanism competing with the application properties. Application properties, along with the SQL-like filter expressions, are much better suited for filtering purposes compared to wildcard patterns applied to subject strings.

### content-type (MANDATORY)

Indicates the MIME type of the payload and SHALL be set to `application/xml` for the IWXXM XML data.

### content-encoding (CONDITIONAL)

By default, payloads are not compressed, and in this case, the `content-encoding` property can be left out. However, when compression is applied to the payload, the `content-encoding` is mandatory.

The MET-SWIM service AMQP implementations and clients SHALL support the following content-encodings from [IANA HTTP Content Coding Registry|https://www.iana.org/assignments/http-parameters/http-parameters.xhtml]:

- `gzip` - for compressed data. This is the most widely supported compressed `content-encoding` in HTTP.
- `identity` - for uncompressed data (default if omitted).

### absolute-expiry-time (OPTIONAL)

Unix-like UTC timestamp in milliseconds, indicating when the message should expire in the broker and from the durable queues. Please see also the definition of the [timestamp](http://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-types-v1.0-os.html#type-timestamp)) type in the AMQP specification:

> Represents an approximate point in time using the Unix time_t [IEEE1003] encoding of UTC, but with a precision of milliseconds. For example, 1311704463521 represents the moment 2011-07-26T18:21:03.521Z

The `absolute-expiry-time` tells the broker when it should discard a message. On the other hand, the `ttl` field in the AMQP transport header (relative number in milliseconds) is typically calculated using a difference between the `absolute-expiry-time` and the time when the message was created. The `absolute-expiry-time` stays constant during the message's lifetime, whereas `ttl` can be progressively decreased by AMQP intermediaries.

When `absolute expiry time` is not set, the message will "live" in durable queues until a client receives it. Brokers usually have some pre-configured threshold of maximum `ttl` to avoid resource exhaustion if clients do not pick up messages from durable queues.

If a MET-SWIM AMQP implementation sets the absolute-expiry-time, it SHOULD set it high enough to:

- Give the clients a chance to receive the messages during shorter communication outages or client maintenance periods.
- Keep the messages long enough to survive the AMQP server maintenance windows or outages.

**Example:** AMQP message creation + 12 hours

Note: Originally, it was proposed to set the absolute-expiry-time depending on the report type, e.g. 3h for METAR, 12h for TAF, 24h for SIGMET. However, in general, there can be varying purposes for why the client needs to be subscribed to the data:

- One client might be interested only in the latest operationally useful data.
- Another client might be a climatological database that needs all the reports regardless of age. In this case loosing observations due to a 3h communication outage does not seem reasonable.

### creation-time (OPTIONAL)

This is the Unix UTC timestamp (in milliseconds since the epoch) indicating when the AMQP message was initially created. It mostly serves an informational purpose in AMQP and is used in the `ttl` calculation in some brokers.

## AMQP Application Properties

The application properties are the most flexible mechanism for identifying the data sent using AMQP and enabling server-side filtering using [AMQP Filter Expressions 1.0](https://docs.oasis-open.org/amqp/filtex/v1.0/filtex-v1.0.html). The AMQP specification does not regulate [AMQP application property](https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html#type-application-properties) names and meanings. They are custom-defined by individual services that use AMQP as their notification layer. 

Properties in the sections below are divided into categories based on their usage requirements:

- _mandatory_: need to be present at all times,
- _conditional_: are mandatory under stated conditions,
- _optional_: their presence is left to the implementation, but when included, they SHALL adhere to this specification.

### Examples of AMQP Filter Expressions applied to Application Properties

```sql
-- Filter by specific airports
properties.icao_location_identifier IN ('EBBR', 'EDDF')

-- Filter by country prefix
properties.icao_location_identifier LIKE 'EB%'

-- Filter by location and type
properties.icao_location_identifier LIKE 'EB%' 
  AND properties.icao_location_type IN ('CTA', 'FIR', 'AD')

-- Filter by topic pattern
subject LIKE 'weather.aviation.%'
```

### Mandatory Application Properties

These properties MUST be present in all meteorological data messages.

#### properties.report_status (mandatory)

One of the following values:

- `NORMAL` - Regular report
- `AMENDMENT` - Amendment of a previous report
- `CORRECTION` - Correction of a previous report

This is directly based on the IWXXM `reportStatus` attribute.

#### properties.icao_location_identifier (mandatory)

ICAO identifier of the location. Mandatory for reports that are issued for an aerodrome or an airspace that a 4-letter ICAO location designator can identify.

```text
properties.icao_location_identifier: "EBBR"
```

#### properties.icao_location_type (optional)

Type of location identifier. Can be optionally used for disambiguation when the location referred to by the `properties.icao_location_identifier` is not clear.

**Motivation:** Some countries use the same ICAO code to refer to both the lower FIR and the upper UIR airspace. For example, there are SIGMETs issued for `LECB BARCELONA FIR`, `LECB BARCELONA UIR`, and `LECB BARCELONA FIR/UIR`, depending on which vertical portion of the airspace is affected by the hazard. Including the airspace type information can help users subscribe to the lower (or upper) airspace only.

Values:

- `AD` - Aerodrome (for METAR/TAF)
  - From AIXM [AirportHeliportType](https://aixm.aero/sites/default/files/imce/AIXM51HTML/AIXM/DataType_CodeAirportHeliportType.html)
- `FIR` - Flight Information Region (for SIGMET)
  - From AIXM [AirspaceType](https://aixm.aero/sites/default/files/imce/AIXM511HTML/AIXM/DataType_CodeAirspaceType.html)
- `UIR` - Upper Information Region
  - From AIXM [AirspaceType](https://aixm.aero/sites/default/files/imce/AIXM511HTML/AIXM/DataType_CodeAirspaceType.html)
- `CTA` - Control Area
  - From AIXM [AirspaceType](https://aixm.aero/sites/default/files/imce/AIXM511HTML/AIXM/DataType_CodeAirspaceType.html)
- `OTHER:FIR_UIR` - Combined FIR/UIR
  - This is the FIR/UIR encoding used in `aixm:type` in <https://schemas.wmo.int/iwxxm/2025-2RC1/examples/sigmet-A6-1a-TS.xml>

#### conformsTo (conditional)

If there is a service definition the data conforms to (e.g. the CP1 compliant SWIM Service Definitions), this field SHOULD link to the service definition. The field identifies the specification version and the corresponding SWIM service definition.

```text
conformsTo: "https://eur-registry.swim.aero/services/eurocontrol-iwxxm-[service-type]-10"
```

Example values:

- `https://eur-registry.swim.aero/services/eurocontrol-iwxxm-metar-speci-subscription-and-request-service-10`
- `https://eur-registry.swim.aero/services/eurocontrol-iwxxm-taf-subscription-and-request-service-10`
- `https://eur-registry.swim.aero/services/eurocontrol-iwxxm-sigmet-subscription-and-request-service-10`

### Temporal Application Properties

These properties contain date and time information extracted from the IWXXM document.

#### properties.issue_datetime (mandatory)

[RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) formatted publication/issue time extracted from `iwxxm:issueTime`:

```yaml
properties.issue_datetime: "2025-04-15T14:10:00Z"
```

This property is mandatory for all the CP1 message types.

**Note:** In previous proposals, this was called `properties.pubtime` in reference to WIS 2.0 WNP publication time (`properties.pubtime`). However, the publication time in WNM refers to when the notification message was sent, rather than time of issuing of the meteorological report itself. Time of sending of the notification message is better represented by the `creation-time` in the AMQP transport header.

#### properties.datetime (conditional)

For METAR/SPECI only - observation time in [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) format from `iwxxm:observationTime`:

```yaml
properties.datetime: "2025-03-31T03:00:00Z"
```

**Note:** Corresponds to `properties.datetime` in WIS 2.0 Notification Messages, see [Properties / Temporal description](https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-STABLE.html#_1_12_properties_temporal_description) in the WNM specification.

#### properties.start_datetime (conditional)

For TAF/SIGMET - start of validity period in [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) format from `iwxxm:validPeriod`:

```yaml
properties.start_datetime: "2025-04-15T14:30:00Z"
```

**Note:** `properties.start_datetime` and `properties.end_datetime` correspond to the equivalently named properties in the WIS 2.0 Notification Messages. See [Properties / Temporal description](https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-STABLE.html#_1_12_properties_temporal_description) in the WNM specification.

#### properties.end_datetime (conditional)

For TAF/SIGMET - end of validity period in [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) format:

```yaml
properties.end_datetime: "2025-04-15T18:00:00Z"
```

### AMQP with Message Security

SWIM TI Yellow Profile 2.0 section 3.1.1.12 defines Service Interface Binding of type "AMQP Messaging with Message Security" that enables detection of data corruption during transmission and ensures data authenticity. This is by leveraging the [S/MIME 4.0 (RFC 8551)](https://datatracker.ietf.org/doc/html/rfc8551) standard used in emails.

**Note:** Our previous proposal was to adopt integrity methods from WIS 2.0 WNM specification, but since Yellow Profile 2.0 endorses S/MIME 4.0 there is no need to copy the integrity mechanisms from WIS 2.0.

> **TODO:** Provide more guidance on using S/MIME 4.0.

## Message Payload

For IWXXM XML documents, the payload SHALL contain the complete IWXXM XML document representing one METAR, SPECI, TAF or SIGMET report. XML documents using 

- The message property `content-type` must be set to `application/xml`.
- The payload can be optionally compressed using gzip; in this case, the `content-encoding` message property SHALL be set to `gzip`.

## Broker and Client Library Compatibility

### AMQP 1.0 Brokers Successfully Used in MET-SWIM Implementations

The following AMQP 1.0 brokers have been successfully used in MET-SWIM implementations:

| Broker | Wildcard Support | Filter Expressions | Notes |
|--------|------------------|--------------------|-------|
| Apache ActiveMQ Artemis | ✓ | ✓ | Full support for SQL-like filtering |
| RabbitMQ | partial | ✓ | Requires AMQP 1.0 plugin enabled |
| Apache Qpid Broker-J | ✓ | ✓ | Apache's AMQP 1.0 broker implementation |

### AMQP 1.0 Client Libraries Known to Work in MET-SWIM Context

The following client libraries have been successfully used with AMQP 1.0 brokers in real implementations:

**Note:** This section needs to be expanded based on the experience of a wider range of organisations. Qpid Proton C++ and Python APIs are known to work correctly.

#### JavaScript/Node.js

- **Rhea** - A fully compliant AMQP 1.0 library that is actively maintained. This is the JavaScript library for AMQP 1.0 connections that has been confirmed to work. Available at [https://github.com/amqp/rhea](https://github.com/amqp/rhea).

#### Python

- **Qpid Proton Python API** - Part of [Apache Qpid Proton](https://qpid.apache.org/proton/index.html), this is a mature and well-tested library with full AMQP 1.0 support. Successfully used with ActiveMQ Artemis, RabbitMQ, and other AMQP 1.0 brokers.

#### C++

- **Qpid Proton C++** - Part of [Apache Qpid Proton](https://qpid.apache.org/proton/index.html), verified to work properly with AMQP 1.0 brokers. Provides a portable C implementation with C++ bindings.

#### Java

- **Apache Qpid Proton-J** is a Java implementation from [apache Qpid Proton] (https://qpid.apache.org/proton/index.html). While not directly tested in MET-SWIM implementations, it is expected to work reliably based on the proven track record of other Qpid Proton language implementations.

#### DotNet

- **Qpid Proton DotNet** - .NET implementation from [Apache Qpid Proton](https://qpid.apache.org/proton/index.html), part of the same proven toolkit.

**Note**: At the time of writing, evidence of successful AMQP 1.0 implementations in other programming languages (such as Go, Ruby, PHP, or Rust) is limited. Organisations implementing MET-SWIM in these languages should verify compatibility with their chosen broker before deployment.

## AMQP Message Examples

### METAR Message Example

```yaml
# Message Addressing
address: weather.aviation.metar

# Header
priority: 4

# Message Properties
subject: "weather.aviation.metar"
content-type: "application/xml"
content-encoding: "gzip"
absolute-expiry-time: 1744823400

# Application Properties
conformsTo: "https://eur-registry.swim.aero/services/eurocontrol-iwxxm-metar-speci-subscription-and-request-service-10"
properties.issue_datetime: "2025-04-15T12:02:00Z"
properties.datetime: "2025-04-15T12:00:00Z"
properties.icao_location_identifier: "EBBR"
properties.icao_location_type: "AD"
properties.report_status: "NORMAL"

# Payload
# [Gzipped IWXXM XML content]
```

### TAF Amendment Example

```yaml
# Message Addressing
address: weather.aviation.taf

# Header
priority: 5

# Message Properties
subject: "weather.aviation.taf"
content-type: "application/xml"
content-encoding: "gzip"

# Application Properties
conformsTo: "https://eur-registry.swim.aero/services/eurocontrol-iwxxm-taf-subscription-and-request-service-10"
properties.issue_datetime: "2025-04-01T06:45:00Z"
properties.start_datetime: "2025-04-01T06:00:00Z"
properties.end_datetime: "2025-04-02T06:00:00Z"
properties.icao_location_identifier: "LOWS"
properties.icao_location_type: "AD"
properties.report_status: "AMENDMENT"
```

### SIGMET Example

```yaml
# Message Addressing
address: weather.aviation.sigmet

# Header
priority: 7

# Message Properties
subject: "weather.aviation.sigmet"
content-type: "application/xml"
content-encoding: "gzip"
absolute-expiry-time: 1744813130

# Application Properties
conformsTo: "https://eur-registry.swim.aero/services/eurocontrol-iwxxm-sigmet-subscription-and-request-service-10"
properties.issue_datetime: "2025-04-15T14:10:00Z"
properties.start_datetime: "2025-04-15T14:30:00Z"
properties.end_datetime: "2025-04-15T18:00:00Z"
properties.icao_location_identifier: "UDDD"
properties.icao_location_type: "FIR"
properties.report_status: "NORMAL"

# Payload
# [Gzipped IWXXM XML content]
```

## Appendices

### Appendix A: Property Extraction from IWXXM

This appendix provides comprehensive guidance for extracting AMQP application properties from IWXXM XML documents. IWXXM (ICAO Meteorological Information Exchange Model) documents follow a structured format defined by XML schemas that include multiple namespaces.

#### Required XML Namespaces

When processing IWXXM documents, XML namespaces must be properly detected and handled. **IWXXM versions and their namespace URIs change over time**, so implementations should use **version-agnostic namespace detection** rather than hardcoded URIs.

**Current IWXXM Schema Location**: [https://schemas.wmo.int/iwxxm/2023-1/](https://schemas.wmo.int/iwxxm/2023-1/)

**Dynamic Namespace Detection**:

Instead of hardcoding specific version URIs, detect namespaces dynamically by their common prefixes:

| Namespace Family | Common Prefix Pattern | Purpose |
|------------------|----------------------|---------|
| IWXXM | `http://icao.int/iwxxm/` or `https://schemas.wmo.int/iwxxm/` | IWXXM meteorological reports |
| AIXM | `http://www.aixm.aero/schema/` | Aeronautical information (airports, airspace) |
| GML | `http://www.opengis.net/gml/` | Geographic markup language |

**Implementation Approach for Namespace Detection**:

1. **Parse the XML document** and access the root element
2. **Extract all namespace declarations** from the document (typically available through the XML parser's namespace map or similar functionality)
3. **Iterate through namespace URIs** and match them against the common prefix patterns shown in the table above
4. **Build a namespace mapping** that maps logical prefixes (`iwxxm`, `aixm`, `gml`, etc.) to the actual namespace URIs found in the document
5. **Use this mapping** when constructing XPath expressions for data extraction

**Python Implementation**: The [IBL swimdemo iwxxm_utils.py](https://github.com/iblsoft/swimdemo/blob/main/iwxxm_utils.py) provides a working example of this approach.

**Older vs. Current Namespace Examples**:

```xml
<!-- Legacy IWXXM -->
xmlns:iwxxm="http://icao.int/iwxxm/3.0"
xmlns:aixm="http://www.aixm.aero/schema/5.1.1"
xmlns:gml="http://www.opengis.net/gml/3.2"

<!-- Current IWXXM -->
xmlns:iwxxm="https://schemas.wmo.int/iwxxm/2023-1"
xmlns:aixm="http://www.aixm.aero/schema/5.1.1"
xmlns:gml="http://www.opengis.net/gml/3.2"
```

> **Note**: Always detect namespaces dynamically from the actual XML document rather than assuming specific versions. This ensures compatibility with both legacy and current IWXXM implementations.

#### Document Structure Overview

IWXXM documents have different root elements depending on the report type:

- **METAR/SPECI**: `<iwxxm:METAR>`
- **TAF**: `<iwxxm:TAF>`
- **SIGMET**: `<iwxxm:SIGMET>`

Each document contains:

1. **Report metadata** (issue time, status, location references)
2. **Validity period** (for TAF and SIGMET)
3. **Observation time** (for METAR/SPECI)
4. **Location information** (aerodrome or airspace references)
5. **Meteorological content** (actual weather observations/forecasts)

#### Property Extraction Reference

The table below summarises which IWXXM XML elements or attributes contain the information necessary to populate the message and application properties in AMQP.

The guidance is compatible with IWXXM 3.0 and subsequent versions such as 2021-2 or 2023-1. It is not compatible with IWXXM 2.1 which had significantly different structure due to the usage of OM (Observation Model) schema. IWXXM 3.0 abandoned the Observation Model schema around 2018.

| AMQP Property | Report Types | XPath Expression | Description | Example Value |
|---------------|--------------|------------------|-------------|---------------|
| `properties.issue_datetime` | ALL | `/iwxxm:*/iwxxm:issueTime` | Issue/publication time from root element | `2025-04-15T14:10:00Z` |
| `properties.datetime` | METAR, SPECI | `/iwxxm:METAR/iwxxm:observationTime` | Observation time | `2025-03-31T03:00:00Z` |
| `properties.start_datetime` | TAF, SIGMET | `/iwxxm:*/iwxxm:validPeriod/gml:beginPosition` | Start of validity period | `2025-04-15T14:30:00Z` |
| `properties.end_datetime` | TAF, SIGMET | `/iwxxm:*/iwxxm:validPeriod/gml:endPosition` | End of validity period | `2025-04-15T18:00:00Z` |
| `properties.icao_location_identifier` | METAR, SPECI, TAF | `/iwxxm:*/iwxxm:aerodrome/aixm:AirportHeliport/aixm:locationIndicatorICAO` | Aerodrome ICAO code | `EBBR` |
| `properties.icao_location_identifier` | SIGMET | `/iwxxm:SIGMET/iwxxm:issuingAirTrafficServicesRegion/aixm:Airspace//aixm:designator` | Airspace designator | `UDDD` |
| `properties.icao_location_type` | METAR, SPECI, TAF | `"AD"` | Always "AD" for aerodrome reports | `AD` |
| `properties.icao_location_type` | SIGMET | `/iwxxm:SIGMET/iwxxm:issuingAirTrafficServicesRegion/aixm:Airspace/aixm:type` | Airspace type | `FIR`, `UIR`, `CTA`, `OTHER:FIR_UIR` |
