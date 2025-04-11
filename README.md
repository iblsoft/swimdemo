<img width="200" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logoslogan_new.png"/> <img width="170" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logo_swimweather.png"/>

# IBL SWIM Demonstration - Client examples
This is a repository of example scripts for interaction with AMQP and EDR services on swim.iblsoft.com.

## AMQP 1.0 client

[amqp_client_example.py](https://github.com/iblsoft/swimdemo/blob/main/amqp_client_example.py) is a simple AMQP 1.0 client based on [Apache Qpid Proton](https://github.com/apache/qpid-proton) (AMQP messaging client) which does the following:
- Connects to amqp.swim.iblsoft.com:5672
- Subscribes to topic `origin.a.wis2.com-ibl.data.core.weather.aviation.metar`
- Listens for incoming AMQP notification messages
- When a message is received, the script:
  - Displays the AMQP message properties and the custom appliaction properties
  - If an IWXXM payload is present as (can be with or without gzip compression applied), it will extract the basic issue time, observation time, validity, airspace and aerodrome information from the report. This is mostly to show how to access the XML and verify that the values from the XML match the AMQP application properties correctly.
 
Example output:
```
C:\Python312\python.exe amqp_client_example.py
Received a message:
Message properties:
  Subject: SPECI_LETO_NORMAL_20250411095200
  Content-Type: application/xml
  Content-Encoding: gzip
  Address: origin.a.wis2.com-ibl.data.core.weather.aviation.metar
  Priority: 4
Application properties:
  _AMQ_DUPL_ID: 59e4133560aa52d23d3eca981b17426195765268114b5ff81fc2c13901e17b6a33dd4001ad87637098ed7709d71d9bf346e5f4df90e14c5edad7faea8afa92da
  geometry.coordinates.latitude: 40.48
  geometry.coordinates.longitude: -3.45
  geometry.type: Point
  links[0].href: https://swim.iblsoft.com/filedb/SPECI_LETO_NORMAL_20250411095200_3.xml
  links[0].rel: canonical
  links[0].type: application/xml
  properties.datetime: 2025-04-11T09:52:00Z
  properties.icao_location_identifier: LETO
  properties.icao_location_type: AD
  properties.integrity.method: sha512
  properties.integrity.value: 59e4133560aa52d23d3eca981b17426195765268114b5ff81fc2c13901e17b6a33dd4001ad87637098ed7709d71d9bf346e5f4df90e14c5edad7faea8afa92da
  properties.pubtime: 2025-04-11T09:52:00Z
  topic: origin.a.wis2.com-ibl.data.core.weather.aviation.metar
Extracted IWXXM Report Information:
  report_type: SPECI
  iwxxm_version: 2021-2
  aerodrome_designator: LETO
  issue_time: 2025-04-11T09:52:00Z
  observation_time: 2025-04-11T09:52:00Z
```
