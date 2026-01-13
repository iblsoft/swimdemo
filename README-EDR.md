# SWIM EDR Load Testing Tool

This is a load testing tool for EDR (Environmental Data Retrieval) services that follow the MET SWIM CP1 compliance standards.

[edr_load_test.py](https://github.com/iblsoft/swimdemo/blob/main/edr_load_test.py) is an asynchronous HTTP client based on [aiohttp](https://docs.aiohttp.org/) that can generate variable load patterns to test EDR service performance.

The tool supports:

- Variable request rates with configurable fluctuation
- Multiple concurrent connections
- HTTP Basic Authentication
- SSL/TLS with certificate verification
- Single requests for debugging
- Response time statistics and percentiles

## Installation & Dependencies

### Installing with pip

The EDR load testing tool requires Python 3.9 or later and two Python packages: `aiohttp` and `numpy`.

#### Option 1: Install into a Python virtual environment (recommended)

Create a virtual environment under a regular user account:

```bash
python -m venv ~/edr-test-env
~/edr-test-env/bin/pip install aiohttp numpy

# Verify that the script loads properly
~/edr-test-env/bin/python edr_load_test.py --help
```

Note: On Windows or with Python 3.10+, you may need to use `~/edr-test-env/Scripts/python` instead.

#### Option 2: Install system-wide

To install the dependencies system-wide:

```bash
pip install aiohttp numpy

# Verify that the script loads properly
python edr_load_test.py --help
```

## How to Run the Script

### Basic Usage

Run a load test with 5 requests per second for 60 seconds:

```bash
python edr_load_test.py --rps 5 --duration 60
```

### Common Use Cases

#### Query Latest METAR Data

Query the "metar" collection which represents the latest METAR/SPECI data:

```bash
python edr_load_test.py --endpoint https://swim.iblsoft.com:8444/edr \
  --username YOUR_USERNAME --password "YOUR_PASSWORD" \
  --rps 1 --time-mode none --collection metar --verbose
```

#### Query Historical METAR Data

Query the "metar-all" collection with random datetime parameters:

```bash
python edr_load_test.py --endpoint https://swim.iblsoft.com:8444/edr \
  --username YOUR_USERNAME --password "YOUR_PASSWORD" \
  --rps 5 --collection metar-all --verbose
```

#### Single Request for Debugging

Make a single request to a specific location:

```bash
python edr_load_test.py --single LZIB --time-mode none
```

#### Test with High Load and Fluctuation

Generate high load with dramatic bursts:

```bash
python edr_load_test.py --rps 20 --duration 120 --fluctuation 1.0
```

#### Test with Steady Rate

Generate a steady request rate with minimal fluctuation:

```bash
python edr_load_test.py --rps 10 --duration 60 --fluctuation 0.1
```

#### Limit Concurrent Connections

Limit concurrent connections to avoid server rate limiting:

```bash
python edr_load_test.py --rps 8 --max-connections 5
```

#### Test with Self-Signed Certificates

For local development with self-signed SSL certificates:

```bash
python edr_load_test.py --endpoint https://localhost:38444/edr \
  --username test --password test1234 \
  --rps 5 --insecure
```

**Warning:** Only use `--insecure` in testing environments!

#### Baseline Performance Test

Make trivial requests to the base endpoint only (no collections/locations):

```bash
python edr_load_test.py --rps 10 --trivial
```

#### Query Multiple Locations per Request

Request data for multiple locations in a single request (randomly selected without repetition):

```bash
python edr_load_test.py --rps 5 --num-locations 3 --verbose
```

#### Request Specific Format

Request data in a specific format (e.g., GeoJSON or OriginalInZip):

```bash
python edr_load_test.py --rps 5 --format GeoJSON --verbose
python edr_load_test.py --rps 5 --format OriginalInZip --verbose
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--rps` | Average requests per second (default: 5.0) |
| `--duration` | Duration of the test in seconds (default: 60) |
| `--fluctuation` | Request rate fluctuation: 0.0=none, 0.5=medium, 1.0+=high (default: 0.5) |
| `--endpoint` | EDR service endpoint URL (default: `https://swim.iblsoft.com:8444/edr`) |
| `--collection` | Collection name (default: `metar-all`) |
| `--icao` | Specific ICAO codes to test. If not provided, the tool will attempt to fetch available locations from the EDR service |
| `--num-locations` | Number of locations (ICAO codes) to include in each request, comma-delimited (default: 1) |
| `--format` | Response format to request (e.g., `GeoJSON`, `OriginalInZip`). If not specified, server default is used |
| `--verbose` | Print details for each request |
| `--single ICAO` | Make a single request for the specified ICAO code and exit |
| `--username` | Username for HTTP Basic Authentication |
| `--password` | Password for HTTP Basic Authentication |
| `--max-connections` | Maximum concurrent HTTP connections (default: 10). Lower this if getting rate-limited |
| `--force-close` | Force close connections after each request (disables keep-alive). Use if server counts connections |
| `--time-mode` | Temporal query mode: `single` includes datetime parameter, `none` omits it (default: `single`) |
| `--trivial` | Make trivial requests to base endpoint only (no collections/locations). Useful for baseline performance testing |
| `--insecure` | Skip SSL certificate verification (use for self-signed certificates). |

## Understanding the Output

The tool provides detailed statistics including:

- **Total/Successful/Failed Requests**: Overall request counts and success rate
- **Status Code Breakdown**: HTTP response codes received
- **Response Time Statistics**:
  - Overall statistics (min, max, mean, median, 95th percentile)
  - Per-status-code statistics
- **Real-time Progress**: During the test, periodic updates show requests per second and response times

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate verification errors and you're connecting to a server with a self-signed certificate or a certificate not signed by a trusted CA, you can use the `--insecure` flag:

```bash
python edr_load_test.py --insecure --rps 5
```

### Rate Limiting

If you're getting rate-limited by the server (receiving 429 or 503 status codes), try:

1. Reducing the requests per second: `--rps 2`
2. Limiting concurrent connections: `--max-connections 2`
3. Forcing closing of HTTP connections: `--force-close`
