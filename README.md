<img width="200" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logoslogan_new.png"/> <img width="170" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logo_swimweather.png"/>

# IBL SWIM Demonstration - Client examples

This is a repository of example scripts for interaction with AMQP and EDR services on swim.iblsoft.com.

## AMQP 1.0 client

[amqp_client_example.py](https://github.com/iblsoft/swimdemo/blob/main/amqp_client_example.py) is a simple AMQP 1.0 client based on [Apache Qpid Proton](https://github.com/apache/qpid-proton) (AMQP messaging client).

For details regarding the AMQP message and application properties please [read our documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/AMQP-Data-Subscriptions/) on the AMQP subscription details.

The example client behaves like this:

- Connects to `amqp.swim.iblsoft.com:5672`
- The client subscribes to a wildcard topic `origin.a.wis2.com-ibl.data.core.weather.aviation.*` to receive METAR, SPECI, TAF, SIGMET
- When an AMQP message is received, the script:
  - Displays the AMQP message properties and the custom application properties
  - If an IWXXM payload is present (with or without gzip compression), it will uncompress the payload, extract the basic issue time, observation time, validity, airspace and aerodrome information from the report. This is mostly to show how to access the XML and verify that the values from the XML match the AMQP application properties correctly.
  - The uncompressed IWXXM payloads are stored into `received_data` subfolder with the AMQP message's subject as the file name.

### Dependencies

The only package that needs to be installed on top of what is provided in the Python standard library is `python-qpid-proton`:

```bash
python -m pip install python-qpid-proton
```

On Ubuntu Linux you should install from your distribution using:

```bash
sudo apt install python3-qpid-proton
```

### Command line options

You can override the default AMQP URL, topic, CA certificate, output folder, authentication, and subscription settings through the command line interface:

```text
c:\Python312\python.exe amqp_client_example.py --help
usage: amqp_client_example.py [-h] [--output-folder OUTPUT_FOLDER] [--url URL] [--topic TOPIC]
                              [--num-connections NUM_CONNECTIONS] [--ca-cert CA_CERT]
                              [--client-cert CLIENT_CERT] [--client-key CLIENT_KEY]
                              [--client-cert-password CLIENT_CERT_PASSWORD] [--username USERNAME]
                              [--password PASSWORD] [--durable] [--subscription-name SUBSCRIPTION_NAME]

IBL MET-SWIM AMQP Client Example

options:
  -h, --help            show this help message and exit
  --output-folder OUTPUT_FOLDER, -o OUTPUT_FOLDER
                        Folder to store received message data (default: 'received_data')
  --url URL, -u URL     AMQP(S) URL to connect to. Use 'amqps://' for SSL connections or 'amqp://' for unencrypted
                        connections (default: 'amqps://amqp.swim.iblsoft.com:5672').
  --topic TOPIC, -t TOPIC
                        AMQP topic/queue to subscribe to (default is the wildcard topic for all OPMET data:
                        'origin.a.wis2.com-ibl.data.core.weather.aviation.*')
  --num-connections NUM_CONNECTIONS, -n NUM_CONNECTIONS
                        Number of parallel AMQP connections to create (default: 1)
  --ca-cert CA_CERT, -c CA_CERT
                        Path to the CA certificate file to override the default HARICA staging root certificate
                        (default: 'c:\Projects\SWIM\swimdemo\HARICA-TLS-Root-2021-RSA.pem'). On Windows, the
                        certificate must be added to 'Trusted Root Certification Authorities' using certmgr.msc.
  --client-cert CLIENT_CERT
                        Optional. Path to the client certificate file for mutual TLS authentication. If not provided,
                        only the server's authenticity will be verified.
  --client-key CLIENT_KEY
                        Optional. Path to the client private key file for mutual TLS authentication. If not provided,
                        only the server's authenticity will be verified.
  --client-cert-password CLIENT_CERT_PASSWORD
                        Optional. Password for the client certificate file (e.g., .p12 file) used for mutual TLS
                        authentication.
  --username USERNAME   Optional. Username for AMQP SASL authentication. If provided, password should also be provided.
  --password PASSWORD   Optional. Password for AMQP SASL authentication. If provided, username should also be provided.
  --durable             Enable durable subscription mode. Messages sent while the client is disconnected will be queued
                        and delivered when the client reconnects. Requires the broker to support durable subscriptions.
  --subscription-name SUBSCRIPTION_NAME
                        Optional. Custom name for the durable subscription. If not provided, an auto-generated name
                        based on the client ID will be used. This is only relevant when --durable is enabled.
```

#### Authentication

The client supports AMQP SASL username/password authentication if the server requires it:

```bash
python amqp_client_example.py --username myuser --password mypass
```

#### Durable Subscriptions

Enable durable subscriptions to receive messages that were sent while the client was disconnected:

```bash
python amqp_client_example.py --durable
```

When using durable subscriptions, the client automatically generates a unique subscription name based on the topic. For example:

- Topic `origin.a.wis2.com-ibl.data.core.weather.aviation.metar` creates subscription `sub-weather.aviation.metar`
- Topic `origin.a.wis2.com-ibl.data.core.weather.aviation.taf` creates subscription `sub-weather.aviation.taf`

This ensures that you can run multiple durable subscriptions to different topics without conflicts.

You can also specify a custom subscription name:

```bash
python amqp_client_example.py --durable --subscription-name "my-custom-subscription"
```

Durable subscriptions are identified by the combination of your client's container ID (based on hostname and username) and the subscription name. To receive queued messages after reconnection, you must use the same container ID and subscription name.

#### Parallel Connections

Create multiple parallel connections to improve throughput:

```bash
python amqp_client_example.py --num-connections 3
```

### Example output

```text
Message properties:
  Subject: TAF_LPFL_NORMAL_20250415140000
  Content-Type: application/xml
  Content-Encoding: gzip
  Absolute-Expiry-Time: 1744769932.0
  Address: origin.a.wis2.com-ibl.data.core.weather.aviation.taf
  Priority: 5
Application properties:
  _AMQ_DUPL_ID: aedecccebe39e01ec62ae3091381a0e3d34c3fb8d83041e3b152af6d62c71f7bdfa4a331b7c7d56a542df296e868298af52f112b60cae5a68829351a4feaf7e1
  conformsTo: https://eur-registry.swim.aero/services/eurocontrol-iwxxm-taf-subscription-and-request-service-10
  geometry.coordinates.latitude: 39.45
  geometry.coordinates.longitude: -31.13
  geometry.type: Point
  links[0].href: https://swim.iblsoft.com/filedb/TAF_LPFL_NORMAL_20250415140000.xml
  links[0].rel: canonical
  links[0].type: application/xml
  links[1].href: https://edr.swim.iblsoft.com/edr/collections/iwxxm-taf/locations/icao:LPFL?datetime=2025-04-15T15:00:00Z/2025-04-16T00:00:00Z
  links[1].rel: item
  links[1].type: application/zip
  properties.end_datetime: 2025-04-16T00:00:00Z
  properties.icao_location_identifier: LPFL
  properties.icao_location_type: AD
  properties.integrity.method: sha512
  properties.integrity.value: aedecccebe39e01ec62ae3091381a0e3d34c3fb8d83041e3b152af6d62c71f7bdfa4a331b7c7d56a542df296e868298af52f112b60cae5a68829351a4feaf7e1
  properties.pubtime: 2025-04-15T14:00:00Z
  properties.start_datetime: 2025-04-15T15:00:00Z
  topic: origin.a.wis2.com-ibl.data.core.weather.aviation.taf
Payload saved to received_data\TAF_LPFL_NORMAL_20250415140000.xml
Extracted IWXXM Report Information:
  report_type: TAF
  iwxxm_version: 3.0
  aerodrome_designator: LPFL
  issue_time: 2025-04-15T14:00:00Z
```

### Verifying the server's certificate

*Note:* Normally the AMQP port 5672 is reserved for unencrypted communications. The *Artemis ActiveMQ* broker supports unencrypted connections, but we have chosen to disable this option and only allow SSL connections. The connection to 5672 thus requires SSL, but does not strictly require verification of the server's certificate.

The client will attempt to verify the server's authenticity using the HARICA staging root certificate.

- On Windows 11 you will need to add the HARICA staging root certificate using Windows built-in *certmgr* tool as explained [in the documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/Working-with-Certificates/Importing-HARICA-root-certificate-on-Windows/). This is because the Windows build of Qpid Proton uses the Windows system's TLS library SChannel, rather than OpenSSL.
- For Linux and other non-Windows platforms where Qpid Proton is using OpenSSL the HARICA certificate is provided in a .pem file.
- If the verification of the server's certificate fails for any reason, the client will disable the verification and reconnect.
