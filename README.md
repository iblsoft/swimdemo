<img width="200" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logoslogan_new.png"/> <img width="170" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logo_swimweather.png"/>

# IBL SWIM Demonstration - Client examples

This is a repository of example scripts for interaction with AMQP and EDR services on swim.iblsoft.com.

## AMQP 1.0 client

[amqp_client_example.py](https://github.com/iblsoft/swimdemo/blob/main/amqp_client_example.py) is an AMQP 1.0 client based on [Apache Qpid Proton](https://github.com/apache/qpid-proton) (AMQP messaging client).

For details regarding the AMQP message and application properties please [read our documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/AMQP-Data-Subscriptions/) on the AMQP subscription details.

The example client behaves like this:

- Connects to `amqp.swim.iblsoft.com:5672`
- The client subscribes to a wildcard topic `weather.aviation.*` to receive METAR, SPECI, TAF, SIGMET
- When an AMQP message is received, the script:
  - Displays the AMQP message properties and the custom application properties
  - If an IWXXM payload is present (with or without gzip compression), it will uncompress the payload, extract the basic issue time, observation time, validity, airspace and aerodrome information from the report. This is mostly to show how to access the XML and verify that the values from the XML match the AMQP application properties correctly.
  - The uncompressed IWXXM payloads are stored into `received_data` subfolder. The file name is created using:
    - A combination of the message subject and application properties `properties.icao_location_identifier`,
    `properties.report_status` and `properties.issue_datetime`, if all are present.
    - Otherwise, the filename is based on the message subject, if present.
    - Otheriwse, a timestamp is used to name the file.

### Dependencies



The only package that needs to be installed on top of what is provided in the Python standard library is `python-qpid-proton`. Before installing the package, make sure you have `openssl-devel`, `libffi-devel`, and `python3-devel` packages installed (these are names of the packages on RHEL and its derivatives). They are necessary for bulding the Qpid Proton "wheel".

```bash
python -m pip install python-qpid-proton
```

On Ubuntu Linux you should install from your distribution using:

```bash
sudo apt install python3-qpid-proton
```

### Command line options

You can override the default AMQP URL, topic, CA certificate, output folder, authentication, and subscription settings through the command line interface:

| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message and exit |
| `-o, --output-folder` | Folder to store received message data (default: `received_data`) |
| `-u, --url` | AMQP(S) URL to connect to. Use `amqps://` for SSL connections or `amqp://` for unencrypted connections (default: `amqps://amqp.swim.iblsoft.com:5672`) |
| `-t, --topic` | AMQP topic/queue to subscribe to (default is the wildcard topic for all OPMET data: `weather.aviation.*`) |
| `-n, --num-connections` | Number of parallel AMQP connections to create (default: 1) |
| `-c, --ca-cert` | Path to the CA certificate file to override the default HARICA staging root certificate. On Windows, the certificate must be added to 'Trusted Root Certification Authorities' using certmgr.msc |
| `--client-cert` | Optional. Path to the client certificate file for mutual TLS authentication. If not provided, only the server's authenticity will be verified |
| `--client-key` | Optional. Path to the client private key file for mutual TLS authentication. If not provided, only the server's authenticity will be verified |
| `--client-cert-password` | Optional. Password for the client certificate file (e.g., .p12 file) used for mutual TLS authentication |
| `--username` | Optional. Username for AMQP SASL authentication. If provided, password should also be provided |
| `--password` | Optional. Password for AMQP SASL authentication. If provided, username should also be provided |
| `--durable` | Enable durable subscription mode. Messages sent while the client is disconnected will be queued and delivered when the client reconnects. Requires the broker to support durable subscriptions |
| `--subscription-name` | Optional. Custom name for the durable subscription. If not provided, an auto-generated name based on the client ID will be used. This is only relevant when `--durable` is enabled |

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

- Topic `weather.aviation.metar` creates subscription `sub-weather.aviation.metar`
- Topic `weather.aviation.taf` creates subscription `sub-weather.aviation.taf`

This ensures that you can run multiple durable subscriptions to different topics without conflicts.

You can also specify a custom subscription name:

```bash
python amqp_client_example.py --durable --subscription-name "my-custom-subscription"
```

Durable subscriptions are identified by the combination of your client's container ID (based on hostname and username) and the subscription name. To receive queued messages after reconnection, you must use the same container ID and subscription name.

#### Parallel Connections

Create multiple parallel connections for load testing purposes:

```bash
python amqp_client_example.py --num-connections 10
```

### Example output

```text
Message properties:
  Subject: weather.aviation.taf
  Content-Type: application/xml
  Content-Encoding: gzip
  Absolute-Expiry-Time: 1763187377.0
  Creation-Time: 1763144177.0
  Address: weather.aviation.taf
  Priority: 5
Application properties:
  conformsTo: https://eur-registry.swim.aero/services/eurocontrol-iwxxm-taf-subscription-and-request-service-10
  geometry.coordinate.latitude: 50.83
  geometry.coordinate.longitude: -0.28
  geometry.type: Point
  links[0].href: https://localhost/weather.aviation.taf_918.xml
  links[0].rel: update
  links[0].type: application/xml
  links[1].href: https://localhost/collections/iwxxm-taf/locations/icao:EGKA?datetime=2025-11-14T15:00:00Z/2025-11-14T20:00:00Z
  links[1].rel: item
  links[1].type: application/zip
  properties.end_datetime: 2025-11-14T20:00:00Z
  properties.icao_location_identifier: EGKA
  properties.icao_location_type: AD
  properties.integrity.method: sha512
  properties.integrity.value: a492152aea00829d9bdd6865689895435a842744d117cc2c5c0518a2a76efb5e2babf163191df1891d2a8fccaefb7c8918846e781f39d6089486416ad0ed040c
  properties.issue_datetime: 2025-11-14T18:11:00Z
  properties.report_status: AMENDMENT
  properties.start_datetime: 2025-11-14T15:00:00Z
  topic: weather.aviation.taf
Payload saved to received_data/weather.aviation.taf_EGKA_AMENDMENT_2025-11-14T18:11:00Z.xml
Extracted IWXXM Report Information: Found 1 report(s)
  Report 1:
    report_type: TAF
    iwxxm_version: 2023-1
    gml_id: uuid.31d6dff3-0577-4352-9091-137011414cca
    report_status: AMENDMENT
    aerodrome_designator: EGKA
    issue_time: 2025-11-14T18:11:00Z
    cnl_start_datetime: 2025-11-14T15:00:00Z
    cnl_end_datetime: 2025-11-14T20:00:00Z
```

### Verifying the server's certificate

*Note:* Normally the AMQP port 5672 is reserved for unencrypted communications. The *Artemis ActiveMQ* broker supports unencrypted connections, but we have chosen to disable this option and only allow SSL connections. The connection to 5672 thus requires SSL, but does not strictly require verification of the server's certificate.

The client will attempt to verify the server's authenticity using the HARICA staging root certificate.

- On Windows 11 you will need to add the HARICA staging root certificate using Windows built-in *certmgr* tool as explained [in the documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/Working-with-Certificates/Importing-HARICA-root-certificate-on-Windows/). This is because the Windows build of Qpid Proton uses the Windows system's TLS library SChannel, rather than OpenSSL.
- For Linux and other non-Windows platforms where Qpid Proton is using OpenSSL the HARICA certificate is provided in a .pem file.
- If the verification of the server's certificate fails for any reason, the client will disable the verification and reconnect.
