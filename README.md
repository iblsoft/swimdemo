<img width="200" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logoslogan_new.png"/> <img width="170" src="https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/attachments/ibl_logo_swimweather.png"/>

# IBL SWIM Demonstration - Client examples

This is a repository of example scripts for interaction with AMQP on `swim.iblsoft.com`, or on any other MET-SWIM AMQP server that follows the [EUROCONTROL MET3SG AMQP Message Guidance](https://swim-eurocontrol.atlassian.net/wiki/spaces/MSS/pages/638156804/AMQP+Message+Structure+in+MET-SWIM), for example, `swim.dwd.de`. 

## AMQP 1.0 client

[amqp_client_example.py](https://github.com/iblsoft/swimdemo/blob/main/amqp_client_example.py) is an AMQP 1.0 client based on [Apache Qpid Proton](https://github.com/apache/qpid-proton) (AMQP messaging client).

For details regarding the AMQP message and application properties, please [read our documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/AMQP-Data-Subscriptions/) on the AMQP subscription details.

The example client behaves like this:

- Connects to an AMQPS broker on URL that you provide (by default `amqp.swim.iblsoft.com:5672`).
- The client subscribes to a wildcard topic `weather.aviation.*` to receive METAR, SPECI, TAF, SIGMET
- When an AMQP message is received, the script:
  - Displays the AMQP message properties and the custom application properties
  - If an IWXXM payload is present (with or without gzip compression), it will uncompress the payload, extract the basic issue time, observation time, validity, airspace and aerodrome information from the report. This is mostly to show how to access the XML and verify that the values from the XML match the AMQP application properties correctly.
  - The uncompressed IWXXM payloads are stored in the `received_data` subfolder. The file name is created using:
    - A combination of the message subject and application properties `properties.icao_location_identifier`,
    `properties.report_status` and `properties.issue_datetime`, if all are present.
    - Otherwise, the filename is based on the message subject, if present.
    - Otherwise, a timestamp is used to name the file.

### Installation & Dependencies

#### Installing with pip into a Python virtual environment

The AMQP client requires Python 3.9 or later and the `python-qpid-proton` module, which can be installed using **pip**.

Before installing `python-qpid-proton`, make sure you have the following packages installed in your Linux distribution; otherwise, the installation will fail:
- `openssl-devel`,
- `libffi-devel`,
- `python3-devel`,
- `gcc`.

Create a virtual environment under a regular user account:

```bash
python -m venv ~/amqp-client-env
~/amqp-client-env/venv/bin/pip install python-qpid-proton

# Verify that the script loads properly
~/amqp-client-env/venv/bin/python amqp_client_example.py --help
```

Note that Python 3.10+ will likely skip the `venv` subfolder, so `~/amqp-client-env/bin/pip` and `~/amqp-client-env/bin/python` are used instead.

To install as root in your OS instead:
```bash
python -m pip install python-qpid-proton
```

We are mostly testing with the `python-qpid-proton` version 0.40.0, which is available through **pip**. 

#### Installing Qpid Proton from Linux Distribution

This is an example for Ubuntu 24.04, where the AMQP client will work with the system python and Qpid Proton installed from Ubuntu repositories.
```bash
# Install Qpid Proton module
sudo apt install python-qpid-proton

# Verify that the script loads properly
python amqp_client_example.py --help
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
| `-c, --ca-cert` | Path to the CA certificate .pem bundle, which contains, in the case of HARICA, all the relevant HARICA root and staging CA certs. On Windows, the certificate must be added to 'Trusted Root Certification Authorities' using certmgr.msc |
| `--client-cert` | Optional. Path to the client certificate file for mutual TLS authentication. If not provided, only the server's authenticity will be verified |
| `--client-key` | Optional. Path to the client private key file for mutual TLS authentication. If not provided, only the server's authenticity will be verified |
| `--client-cert-password` | Optional. Password for the client certificate file (e.g., .p12 file) used for mutual TLS authentication |
| `--username` | Optional. Username for AMQP SASL authentication. If provided, the password should also be provided |
| `--password` | Optional. Password for AMQP SASL authentication. If provided, username should also be provided |
| `--durable` | Enable durable subscription mode. Messages sent while the client is disconnected will be queued and delivered when the client reconnects. Requires the broker to support durable subscriptions |
| `--subscription-name` | Optional. Custom name for the durable subscription. If not provided, an auto-generated name based on the client ID will be used. This is only relevant when `--durable` is enabled |
| `--insecure` | Optional. Completely disable SSL certificate verification (both certificate chain and hostname). Client certificates will still be sent if provided. Use only for testing with self-signed certificates. |
| `--skip-hostname-verification` | Optional. Skip SSL hostname/domain verification but still verify the server's certificate chain. Use this when connecting via IP address or when the domain name doesn't match the certificate. The server certificate must still be signed by a trusted CA. Client certificates will still be sent and verified by the server. |

#### Authentication with Username and Password

The client supports AMQP SASL username/password authentication if the server requires it:

```bash
python amqp_client_example.py -u amqps://SERVER:5674 --username USERNAME --password 'PASSWORD' -t 'weather.aviation.*'
```

#### Authentication with Client Certificates (mTLS)

If the AMQP server requires mTLS with client certificates, you can run the script as follows:

```bash
~/amqp-client-env/venv/bin/python amqp_client_example.py \
-u amqps://SERVER:5671 \
-t weather.aviation.metar \
--user USERNAME --password 'PASSWORD' \
--client-cert CLIENT-CERT.crt \
--client-key CLIENT-KEY.key \
--ca-cert HARICA-bundle.pem
```

Notes:
- `-u amqps://SERVER:5671`: SERVER is the hostname of the server you are connecting to. Port 5671 is the standard AMQPS port for TLS connections; however, if the AMQP server exposes mTLS on a different network port, it should be replaced with a different port number.
- `--user USERNAME`: If the AMQP server requires a username to be provided, you can specify it using this option.
- `--password PASSWORD`: If the AMQP server requires a password to be provided, provide it using this option.
- `--client-cert CLIENT-CERT.crt`: This is the path to your client certificate.
- `--client-key CLIENT-KEY.key`: Your private key for the certificate.
- `--ca-cert HARICA-bundle.pem`: If the AMQP server is identifying itself with HARICA staging certificates, you can use the certificate bundle from this repository to verify them.

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
  properties.end_datetime: 2025-11-14T20:00:00Z
  properties.icao_location_identifier: EGKA
  properties.icao_location_type: AD
  properties.issue_datetime: 2025-11-14T18:11:00Z
  properties.report_status: AMENDMENT
  properties.start_datetime: 2025-11-14T15:00:00Z
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

*Note:* Normally the AMQP port 5672 is reserved for unencrypted communications. The *Artemis ActiveMQ* broker supports unencrypted connections, but we have chosen to disable this option on <swim.iblsoft.com> and only allow SSL connections. The connection to 5672 thus requires SSL, but does not strictly require verification of the server's certificate.

The client will attempt to verify the server's authenticity using the HARICA staging root certificate.

- On Windows 11 you will need to add the HARICA staging root certificate using Windows built-in *certmgr* tool as explained [in the documentation](https://swim.iblsoft.com/swimdemo/latest/SWIM-Weather-Public-Demonstration/Working-with-Certificates/Importing-HARICA-root-certificate-on-Windows/). This is because the Windows build of Qpid Proton uses the Windows system's TLS library SChannel, rather than OpenSSL.
- For Linux and other non-Windows platforms where Qpid Proton is using OpenSSL the HARICA certificate is provided in a .pem file.
- If the verification of the server's certificate fails for any reason, the client will disable the verification and reconnect.
