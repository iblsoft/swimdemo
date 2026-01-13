"""
EDR Client Load Testing Tool

Program for making EDR requests to a MET SWIM CP1 compliant EDR service.
Supports variable load generation with configurable request rates.

Example endpoint: https://swim.iblsoft.com:8444/edr
Example request: https://swim.iblsoft.com:8444/edr/collections/metar-all/locations/LZIB?datetime=2025-10-10T06:00

Requirements:
    pip install aiohttp numpy

Usage:
    python edr_load_test.py --rps 5
    python edr_load_test.py --rps 10 --duration 60
    python edr_load_test.py --rps 20 --endpoint https://swim.iblsoft.com:8444/edr --collection metar-all
"""

import argparse
import time
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import sys
import numpy as np
from urllib.parse import urljoin
import base64
from http import HTTPStatus
import platform

def get_http_status_description(status_code):
    """
    Get a human-readable description for HTTP status codes.
    
    Args:
        status_code: HTTP status code integer
        
    Returns:
        String description of the status code
    """
    # Handle special non-HTTP status codes
    if status_code == 0:
        return "Timeout"
    elif status_code == -1:
        return "Connection Error"
    
    # Use Python's built-in HTTPStatus enum for standard codes
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Unknown Status"


class EDRClient:
    """Client for making EDR requests with load testing capabilities."""
    
    def __init__(self, base_url='https://swim.iblsoft.com:8444/edr', collection='metar-all', username=None, password=None):
        """
        Initialize the EDR client.
        
        Args:
            base_url: Base URL of the EDR service
            collection: Collection name (e.g., 'metar-all')
            username: Optional username for HTTP Basic Authentication
            password: Optional password for HTTP Basic Authentication
        """
        self.base_url = base_url.rstrip('/')
        self.collection = collection
        self.username = username
        self.password = password
        self.auth_header = None
        
        # Prepare Basic Auth header if credentials provided
        if username and password:
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
            self.auth_header = f"Basic {encoded}"
        
        self.stats = defaultdict(int)
        self.response_times = []
        self.response_times_by_status = defaultdict(list)  # Track response times per status code
        self.session = None  # Will be created in async context
        self._stats_lock = asyncio.Lock()
        
    def get_random_datetime(self, max_hours_back=48):
        """
        Generate a random datetime within the last max_hours_back hours.
        
        Args:
            max_hours_back: Maximum number of hours to go back (default: 48 = 2 days)
            
        Returns:
            ISO formatted datetime string (YYYY-MM-DDTHH:MM)
        """
        now = datetime.now(timezone.utc)
        # Round to the nearest hour
        now = now.replace(minute=0, second=0, microsecond=0)
        
        # Generate random hours back
        hours_back = random.randint(1, max_hours_back)
        target_time = now - timedelta(hours=hours_back)
        
        return target_time.strftime('%Y-%m-%dT%H:%M')
    
    async def fetch_available_locations(self):
        """
        Query the EDR service for available locations in the collection.
        
        Returns:
            list: List of location IDs (ICAO codes), or None if request failed
        """
        url = f"{self.base_url}/collections/{self.collection}/locations"
        
        # Prepare headers with authentication if available
        headers = {}
        if self.auth_header:
            headers['Authorization'] = self.auth_header
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Parse GeoJSON FeatureCollection
                    if data.get('type') == 'FeatureCollection':
                        locations = []
                        for feature in data.get('features', []):
                            if 'properties' in feature and 'locationId' in feature['properties']:
                                location_id = feature['properties']['locationId']
                                locations.append(location_id)
                        
                        return locations if locations else None
                    else:
                        print(f"Warning: Unexpected response format from locations endpoint", file=sys.stderr)
                        return None
                else:
                    print(f"Warning: Failed to fetch locations (HTTP {response.status})", file=sys.stderr)
                    return None
                    
        except asyncio.TimeoutError:
            print("Warning: Timeout while fetching locations", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Warning: Error fetching locations: {e}", file=sys.stderr)
            return None
    
    async def get_metar(self, icao_code, datetime_str=None, time_mode='single'):
        """
        Request METAR data for a specific aerodrome and time.
        
        Args:
            icao_code: 4-letter ICAO airport code
            datetime_str: Optional datetime string (YYYY-MM-DDTHH:MM). If None, generates random.
            time_mode: Temporal query mode - 'single' or 'none'
            
        Returns:
            tuple: (success: bool, status_code: int, response_time: float, data: bytes or None, url: str)
        """
        # Build the request URL
        url = f"{self.base_url}/collections/{self.collection}/locations/{icao_code}"
        
        # Build params and path based on time mode
        if time_mode == 'none':
            params = {}
            request_path = f"/collections/{self.collection}/locations/{icao_code}"
        elif time_mode == 'single':
            if datetime_str is None:
                datetime_str = self.get_random_datetime()
            params = {'datetime': datetime_str}
            request_path = f"/collections/{self.collection}/locations/{icao_code}?datetime={datetime_str}"
        else:
            # Future time modes can be added here
            raise ValueError(f"Unsupported time_mode: {time_mode}")
        
        # Prepare headers with authentication if available
        headers = {}
        if self.auth_header:
            headers['Authorization'] = self.auth_header
        
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, params=params, headers=headers, timeout=timeout) as response:
                response_time = time.time() - start_time
                status_code = response.status
                
                # Read response data
                if status_code == 200:
                    data = await response.read()
                else:
                    data = None
                
                # Update stats (thread-safe)
                async with self._stats_lock:
                    self.stats['total_requests'] += 1
                    self.stats[f'status_{status_code}'] += 1
                    self.response_times.append(response_time)
                    self.response_times_by_status[status_code].append(response_time)
                    
                    if status_code == 200:
                        self.stats['successful_requests'] += 1
                        return True, status_code, response_time, data, request_path
                    else:
                        self.stats['failed_requests'] += 1
                        return False, status_code, response_time, None, request_path
                
        except asyncio.TimeoutError:
            response_time = 30.0
            async with self._stats_lock:
                self.stats['total_requests'] += 1
                self.stats['timeouts'] += 1
                self.stats['failed_requests'] += 1
                self.response_times.append(response_time)
                self.response_times_by_status[0].append(response_time)
            return False, 0, response_time, None, request_path
            
        except Exception as e:
            response_time = 0.0
            async with self._stats_lock:
                self.stats['total_requests'] += 1
                self.stats['errors'] += 1
                self.stats['failed_requests'] += 1
                self.response_times.append(response_time)
                self.response_times_by_status[-1].append(response_time)
            return False, -1, response_time, None, request_path
    
    async def get_trivial(self):
        """
        Make a trivial request to the base EDR endpoint (no subpaths or parameters).
        Useful for baseline performance testing.
        
        Returns:
            tuple: (success: bool, status_code: int, response_time: float, data: bytes or None, url: str)
        """
        # Request just the base URL
        url = self.base_url
        request_path = url.split('://', 1)[1].split('/', 1)[1] if '/' in url.split('://', 1)[1] else '/'
        
        # Prepare headers with authentication if available
        headers = {}
        if self.auth_header:
            headers['Authorization'] = self.auth_header
        
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                response_time = time.time() - start_time
                status_code = response.status
                
                # Read response data
                if status_code == 200:
                    data = await response.read()
                else:
                    data = None
                
                # Update stats (thread-safe)
                async with self._stats_lock:
                    self.stats['total_requests'] += 1
                    self.stats[f'status_{status_code}'] += 1
                    self.response_times.append(response_time)
                    self.response_times_by_status[status_code].append(response_time)
                    
                    if status_code == 200:
                        self.stats['successful_requests'] += 1
                        return True, status_code, response_time, data, f"/{request_path}"
                    else:
                        self.stats['failed_requests'] += 1
                        return False, status_code, response_time, None, f"/{request_path}"
                
        except asyncio.TimeoutError:
            response_time = 30.0
            async with self._stats_lock:
                self.stats['total_requests'] += 1
                self.stats['timeouts'] += 1
                self.stats['failed_requests'] += 1
                self.response_times.append(response_time)
                self.response_times_by_status[0].append(response_time)
            return False, 0, response_time, None, f"/{request_path}"
            
        except Exception as e:
            response_time = 0.0
            async with self._stats_lock:
                self.stats['total_requests'] += 1
                self.stats['errors'] += 1
                self.stats['failed_requests'] += 1
                self.response_times.append(response_time)
                self.response_times_by_status[-1].append(response_time)
            return False, -1, response_time, None, f"/{request_path}"
    
    def print_stats(self):
        """Print current statistics."""
        print("\n" + "="*60)
        print("EDR Client Statistics")
        print("="*60)
        
        total = self.stats['total_requests']
        successful = self.stats['successful_requests']
        failed = self.stats['failed_requests']
        
        print(f"Total Requests:      {total}")
        print(f"Successful:          {successful} ({100*successful/total if total > 0 else 0:.1f}%)")
        print(f"Failed:              {failed} ({100*failed/total if total > 0 else 0:.1f}%)")
        
        # Status code breakdown
        print("\nStatus Codes:")
        for key, value in sorted(self.stats.items()):
            if key.startswith('status_'):
                status_code = key.replace('status_', '')
                print(f"  {status_code}: {value}")
        
        # Error breakdown
        if self.stats['timeouts'] > 0:
            print(f"\nTimeouts:            {self.stats['timeouts']}")
        if self.stats['errors'] > 0:
            print(f"Connection Errors:   {self.stats['errors']}")
        
        # Overall response time statistics
        if self.response_times:
            print("\nOverall Response Times:")
            print(f"  Min:     {min(self.response_times):.3f}s")
            print(f"  Max:     {max(self.response_times):.3f}s")
            print(f"  Mean:    {np.mean(self.response_times):.3f}s")
            print(f"  Median:  {np.median(self.response_times):.3f}s")
            print(f"  95th %:  {np.percentile(self.response_times, 95):.3f}s")
        
        # Response time statistics by status code
        if self.response_times_by_status:
            print("\nResponse Times by Status Code:")
            for status_code in sorted(self.response_times_by_status.keys()):
                times = self.response_times_by_status[status_code]
                if times:
                    status_desc = get_http_status_description(status_code)
                    count = len(times)
                    print(f"\n  [{status_code} {status_desc}] ({count} requests):")
                    print(f"    Min:     {min(times):.3f}s")
                    print(f"    Max:     {max(times):.3f}s")
                    print(f"    Mean:    {np.mean(times):.3f}s")
                    print(f"    Median:  {np.median(times):.3f}s")
                    if count >= 20:  # Only show 95th percentile if enough samples
                        print(f"    95th %:  {np.percentile(times, 95):.3f}s")
        
        print("="*60 + "\n")


def generate_poisson_intervals(rate, duration, fluctuation=0.5):
    """
    Generate request intervals using Poisson distribution with variable rate.
    
    Args:
        rate: Average requests per second
        duration: Total duration in seconds
        fluctuation: How much the rate varies (0.0 = no variation, 1.0 = high variation)
                    Default 0.5 means rate can vary ±50% around the average
        
    Yields:
        Sleep time before next request
    """
    elapsed = 0
    while elapsed < duration:
        # Vary the instantaneous rate around the average
        # Use a log-normal distribution to ensure rate stays positive
        if fluctuation > 0:
            # Adjust the rate with random variation
            # fluctuation controls the standard deviation
            rate_multiplier = np.random.lognormal(0, fluctuation)
            current_rate = rate * rate_multiplier
            # Clamp to reasonable bounds (at least 0.1, at most 10x the average)
            current_rate = max(0.1, min(current_rate, rate * 10))
        else:
            current_rate = rate
        
        # Inter-arrival time for Poisson process with current rate
        interval = np.random.exponential(1.0 / current_rate)
        elapsed += interval
        if elapsed < duration:
            yield interval


async def run_load_test(client, avg_rps, duration, icao_codes=None, verbose=False, fluctuation=0.5, 
                        max_connections=10, force_close=False, time_mode='single', trivial=False, insecure=False):
    """
    Run a load test with variable request rates using async requests.
    
    Args:
        client: EDRClient instance
        avg_rps: Average requests per second
        duration: Duration of the test in seconds
        icao_codes: List of ICAO codes to use (not required for trivial mode)
        verbose: Print details for each request
        fluctuation: How much the rate varies (0.0 = no variation, 1.0+ = high variation)
        max_connections: Maximum concurrent connections to the server
        force_close: Force close connections after each request (disables keep-alive)
        time_mode: Temporal query mode ('single' or 'none')
        trivial: Make trivial requests to base endpoint only
        insecure: Skip SSL certificate verification
    """
    print(f"Starting EDR load test (ASYNC mode)...")
    print(f"Endpoint:        {client.base_url}")
    if not trivial:
        print(f"Collection:      {client.collection}")
    print(f"Average RPS:     {avg_rps}")
    print(f"Fluctuation:     {fluctuation:.2f} ({'low' if fluctuation < 0.3 else 'medium' if fluctuation < 0.7 else 'high'})")
    print(f"Duration:        {duration}s")
    if trivial:
        print(f"Mode:            Trivial (base endpoint only)")
    else:
        print(f"ICAO codes:      {len(icao_codes)} airports")
    print(f"Max connections: {max_connections}")
    print(f"Keep-alive:      {'disabled' if force_close else 'enabled'}")
    print(f"Expected total:  ~{int(avg_rps * duration)} requests")
    print("-" * 60)
    
    # Create aiohttp session with connection control
    connector = aiohttp.TCPConnector(
        limit=max_connections,           # Limit total connections
        limit_per_host=max_connections,  # Limit connections per host
        force_close=force_close,         # Force close connections if requested
        ssl=False if insecure else None  # Disable SSL verification if insecure
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        client.session = session
        
        start_time = time.time()
        last_status_time = start_time
        status_interval = 5  # Print status every 5 seconds
        
        # Task to schedule requests
        async def request_scheduler():
            tasks = []
            try:
                for interval in generate_poisson_intervals(avg_rps, duration, fluctuation):
                    # Sleep until next request
                    await asyncio.sleep(interval)
                    
                    # Schedule the request (don't wait for it)
                    if trivial:
                        task = asyncio.create_task(make_trivial_request())
                    else:
                        # Pick a random ICAO code
                        icao_code = random.choice(icao_codes)
                        task = asyncio.create_task(make_request(icao_code))
                    tasks.append(task)
                    
            except asyncio.CancelledError:
                pass
            
            # Wait for all pending requests to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # Task to make individual requests
        async def make_request(icao_code):
            success, status_code, response_time, data, request_path = await client.get_metar(icao_code, time_mode=time_mode)
            
            if verbose:
                status = "OK" if success else "FAIL"
                status_desc = get_http_status_description(status_code)
                print(f"[{status:4s}] {icao_code} [{status_code} {status_desc}] {response_time:.3f}s - {request_path}")
        
        # Task to make trivial requests
        async def make_trivial_request():
            success, status_code, response_time, data, request_path = await client.get_trivial()
            
            if verbose:
                status = "OK" if success else "FAIL"
                status_desc = get_http_status_description(status_code)
                print(f"[{status:4s}] TRIVIAL [{status_code} {status_desc}] {response_time:.3f}s - {request_path}")
        
        # Task to print periodic status updates
        async def status_reporter():
            last_report = start_time
            last_total_requests = 0
            last_response_times_count = 0
            
            try:
                while True:
                    await asyncio.sleep(1)
                    current_time = time.time()
                    if current_time - last_report >= status_interval:
                        elapsed = current_time - start_time
                        
                        # Get stats snapshot (thread-safe)
                        async with client._stats_lock:
                            total = client.stats['total_requests']
                            successful = client.stats['successful_requests']
                            
                            # Calculate interval statistics
                            interval_requests = total - last_total_requests
                            
                            # Get response times for this interval only
                            interval_response_times = client.response_times[last_response_times_count:]
                            last_response_times_count = len(client.response_times)
                        
                        if interval_requests > 0:
                            interval_rps = interval_requests / status_interval
                            success_rate = 100 * successful / total if total > 0 else 0
                            
                            # Calculate response time stats for interval
                            if interval_response_times:
                                min_time = min(interval_response_times)
                                max_time = max(interval_response_times)
                                mean_time = np.mean(interval_response_times)
                                print(f"[{elapsed:.0f}s] Requests: {interval_requests} | "
                                      f"RPS: {interval_rps:.2f} | "
                                      f"Success: {success_rate:.1f}% | "
                                      f"Response: min={min_time:.3f}s max={max_time:.3f}s mean={mean_time:.3f}s")
                            else:
                                print(f"[{elapsed:.0f}s] Requests: {interval_requests} | "
                                      f"RPS: {interval_rps:.2f} | "
                                      f"Success: {success_rate:.1f}%")
                        
                        last_total_requests = total
                        last_report = current_time
            except asyncio.CancelledError:
                pass
        
        try:
            # Run scheduler and status reporter concurrently
            reporter_task = asyncio.create_task(status_reporter())
            await request_scheduler()
            reporter_task.cancel()
            try:
                await reporter_task
            except asyncio.CancelledError:
                pass
                
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
        
        # Final statistics
        total_time = time.time() - start_time
        actual_rps = client.stats['total_requests'] / total_time if total_time > 0 else 0
        
        print(f"\nTest completed in {total_time:.1f}s")
        print(f"Actual average RPS: {actual_rps:.2f}")
        
        client.print_stats()


def main():
    """Main entry point for the EDR client."""
    # Fix for Windows: Use SelectorEventLoop instead of ProactorEventLoop
    # This prevents "ConnectionResetError: [WinError 10054]" when using force_close
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    parser = argparse.ArgumentParser(
        description='EDR Client Load Testing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic load test with default settings (5 RPS, 60 seconds)
  python edr_load_test.py --rps 5 --duration 60
  
  # Query latest METAR data (1 request per second to "metar" collection)
  # The "metar" collection represents latest METAR/SPECI data
  python edr_load_test.py --endpoint https://swim.iblsoft.com:8444/edr \\
    --username NAME --password "PASSWORD" --verbose --rps 1 \\
    --time-mode none --collection metar
  
  # Query historical METAR data with random datetime (5 RPS to "metar-all")
  python edr_load_test.py --endpoint https://swim.iblsoft.com:8444/edr \\
    --username NAME --password "PASSWORD" --verbose --rps 5 \\
    --collection metar-all
  
  # Test with high fluctuation (dramatic bursts)
  python edr_load_test.py --rps 20 --duration 120 --fluctuation 1.0
  
  # Test with minimal fluctuation (steady rate)
  python edr_load_test.py --rps 10 --duration 60 --fluctuation 0.1
  
  # Limit concurrent connections to avoid NGINX rate limiting
  python edr_load_test.py --rps 8 --max-connections 5
  
  # Test with self-signed SSL certificate (local development) which is not
  # signed by a trusted CA.
  python edr_load_test.py --endpoint https://localhost:38444/edr \\
    --username test --password test1234 --rps 5 --insecure
  
  # Baseline performance test (trivial requests to base endpoint only)
  python edr_load_test.py --rps 10 --trivial
  
  # Single request to specific location
  python edr_load_test.py --single LZIB --time-mode none
        '''
    )
    
    parser.add_argument(
        '--rps',
        type=float,
        default=5.0,
        help='Average requests per second (default: 5.0)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Duration of the test in seconds (default: 60)'
    )
    
    parser.add_argument(
        '--fluctuation',
        type=float,
        default=0.5,
        help='Request rate fluctuation (0.0=none, 0.5=medium, 1.0+=high, default: 0.5)'
    )
    
    parser.add_argument(
        '--endpoint',
        type=str,
        default='https://swim.iblsoft.com:8444/edr',
        help='EDR service endpoint URL (default: https://swim.iblsoft.com:8444/edr)'
    )
    
    parser.add_argument(
        '--collection',
        type=str,
        default='metar-all',
        help='Collection name (default: metar-all)'
    )
    
    parser.add_argument(
        '--icao',
        type=str,
        nargs='+',
        help='Specific ICAO codes to test (required if locations cannot be fetched from EDR service)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print details for each request'
    )
    
    parser.add_argument(
        '--single',
        type=str,
        metavar='ICAO',
        help='Make a single request for the specified ICAO code and exit'
    )
    
    parser.add_argument(
        '--username',
        type=str,
        help='Username for HTTP Basic Authentication'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        help='Password for HTTP Basic Authentication'
    )
    
    parser.add_argument(
        '--max-connections',
        type=int,
        default=10,
        help='Maximum concurrent HTTP connections (default: 10). Lower this if getting rate-limited.'
    )
    
    parser.add_argument(
        '--force-close',
        action='store_true',
        help='Force close connections after each request (disables keep-alive). Use if NGINX counts connections.'
    )
    
    parser.add_argument(
        '--time-mode',
        type=str,
        choices=['single', 'none'],
        default='single',
        help='Temporal query mode: "single" includes datetime parameter, "none" omits it (default: single)'
    )
    
    parser.add_argument(
        '--trivial',
        action='store_true',
        help='Make trivial requests to base endpoint only (no collections/locations). Useful for baseline performance testing.'
    )
    
    parser.add_argument(
        '--insecure',
        action='store_true',
        help='Skip SSL certificate verification (use for self-signed certificates). WARNING: Use only in testing!'
    )
    
    args = parser.parse_args()
    
    # Warn about insecure mode
    if args.insecure:
        print("WARNING: SSL certificate verification is disabled (--insecure)", file=sys.stderr)
        print("         Use this only in testing environments!", file=sys.stderr)
        print()
    
    # Validate arguments
    if args.rps <= 0:
        print("Error: RPS must be greater than 0", file=sys.stderr)
        return 1
    
    if args.duration <= 0:
        print("Error: Duration must be greater than 0", file=sys.stderr)
        return 1
    
    if args.fluctuation < 0:
        print("Error: Fluctuation must be non-negative", file=sys.stderr)
        return 1
    
    # Create client
    client = EDRClient(base_url=args.endpoint, collection=args.collection, 
                       username=args.username, password=args.password)
    
    # Single request mode
    if args.single:
        async def single_request():
            connector = aiohttp.TCPConnector(
                limit=1,
                ssl=False if args.insecure else None
            )
            async with aiohttp.ClientSession(connector=connector) as session:
                client.session = session
                print(f"Making single request for {args.single}...")
                print(f"Time mode: {args.time_mode}")
                
                if args.time_mode == 'single':
                    datetime_str = client.get_random_datetime()
                    print(f"Datetime: {datetime_str}")
                    success, status_code, response_time, data, request_path = await client.get_metar(
                        args.single, datetime_str, time_mode=args.time_mode
                    )
                else:
                    success, status_code, response_time, data, request_path = await client.get_metar(
                        args.single, time_mode=args.time_mode
                    )
                
                status_desc = get_http_status_description(status_code)
                print(f"\nStatus Code: {status_code} ({status_desc})")
                print(f"Response Time: {response_time:.3f}s")
                print(f"Success: {success}")
                print(f"Request Path: {request_path}")
                
                if data:
                    print(f"Data size: {len(data)} bytes")
                    print(f"\nFirst 500 bytes of response:")
                    print(data[:500])
        
        asyncio.run(single_request())
        return 0
    
    # Load test mode
    async def run_test_with_locations():
        """Fetch locations and run the load test."""
        # Use a simple session for fetching locations
        connector = aiohttp.TCPConnector(
            limit=5,
            ssl=False if args.insecure else None
        )
        async with aiohttp.ClientSession(connector=connector) as session:
            client.session = session
            
            # Skip location fetching in trivial mode
            if args.trivial:
                await run_load_test(
                    client=client,
                    avg_rps=args.rps,
                    duration=args.duration,
                    icao_codes=None,
                    verbose=args.verbose,
                    fluctuation=args.fluctuation,
                    max_connections=args.max_connections,
                    force_close=args.force_close,
                    time_mode=args.time_mode,
                    trivial=True,
                    insecure=args.insecure
                )
                return 0
            
            # Determine which ICAO codes to use
            icao_codes = None
            
            # If user specified ICAO codes, use those
            if args.icao:
                icao_codes = args.icao
                print(f"Using {len(icao_codes)} user-specified ICAO code(s)")
            else:
                # Try to fetch available locations from the EDR service
                print(f"Fetching available locations from {client.base_url}/collections/{client.collection}/locations...")
                icao_codes = await client.fetch_available_locations()
                
                if icao_codes:
                    print(f"Successfully retrieved {len(icao_codes)} location(s) from EDR service")
                    if len(icao_codes) <= 10:
                        print(f"Locations: {', '.join(icao_codes)}")
                    else:
                        print(f"Sample locations: {', '.join(icao_codes[:10])}...")
                else:
                    print("Error: Could not fetch locations from EDR service.", file=sys.stderr)
                    print("Please specify ICAO codes manually using the --icao option.", file=sys.stderr)
                    return 1
            
            if not icao_codes:
                print("Error: No ICAO codes available", file=sys.stderr)
                return 1
            
            await run_load_test(
                client=client,
                avg_rps=args.rps,
                duration=args.duration,
                icao_codes=icao_codes,
                verbose=args.verbose,
                fluctuation=args.fluctuation,
                max_connections=args.max_connections,
                force_close=args.force_close,
                time_mode=args.time_mode,
                trivial=False,
                insecure=args.insecure
            )
            return 0
    
    return asyncio.run(run_test_with_locations())


if __name__ == '__main__':
    sys.exit(main())
