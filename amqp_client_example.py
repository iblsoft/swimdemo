#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Copyright (C) 2025, IBL Software Engineering spol. s r. o.
# Authors: Boris Burger
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.
#

import sys
import gzip
import getpass
import traceback
import os, os.path
import platform
import socket
import argparse
import ssl  # Import to check the SSL backend
from datetime import datetime, timezone
from proton import ConnectionException, SSLDomain, SASL
from proton.handlers import MessagingHandler
from proton.reactor import Container, DurableSubscription, AtLeastOnce
from iwxxm_utils import extractReportInformation

class AMQPClient(MessagingHandler):
    def __init__(self, url, topic, num_connections=1, base_client_id=None, outputFolderPath=None, ca_cert_path=None, client_cert_path=None, client_key_path=None, client_cert_password=None, username=None, password=None, durable=False, subscription_name=None, insecure=False):
        super(AMQPClient, self).__init__()
        self.url = url
        self.topic = topic
        self.num_connections = num_connections
        self.base_client_id = base_client_id
        self.outputFolderPath = outputFolderPath
        self.ca_cert_path = ca_cert_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        self.client_cert_password = client_cert_password
        self.username = username
        self.password = password
        self.durable = durable
        self.subscription_name = subscription_name
        self.insecure = insecure
        self.using_schannel = self.is_using_schannel()
        self.connections = {}  # Map connection to connection number
        self.receivers = []  # List of all receivers
        
        if self.using_schannel:
            print("Qpid Proton SSL backend: SChannel (Windows). Certificates must be imported into the Windows Certificate Store!")
        else:
            print("Qpid Proton SSL backend: OpenSSL.")
        
        if self.durable:
            print("Durable subscription mode: ENABLED. Messages will be queued while disconnected.")
        else:
            print("Durable subscription mode: DISABLED. Messages sent while disconnected will be lost.")
        
        if self.insecure:
            print("WARNING: SSL certificate verification is DISABLED. Use only for testing!")
        
        if not os.path.exists(self.outputFolderPath):
            os.makedirs(self.outputFolderPath)

    def is_using_schannel(self):
        """Check if Qpid Proton is using SChannel as the SSL backend."""
        if platform.system() == "Windows":
            try:
                # Attempt to create an SSLDomain and set a trusted CA database
                ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
                ssl_domain.set_trusted_ca_db("dummy_path")
                return False  # If no exception, OpenSSL is being used
            except Exception as e:
                if "SSL" in str(e) or "not supported" in str(e):
                    return True  # SChannel is being used
        return False  # Default to OpenSSL for non-Windows platforms

    def clean_topic_name(self, topic):
        """Clean and shorten the topic name for use in subscription names.
        Removes the 'origin.a.wis2.com-ibl.data.core.' prefix if present."""
        prefix = "origin.a.wis2.com-ibl.data.core."
        if topic.startswith(prefix):
            return topic[len(prefix):]
        return topic

    def on_start(self, event):
        try:
            # Validate certificate files exist before attempting connection
            if self.url.startswith("amqps") and not self.using_schannel and not self.insecure:
                if self.ca_cert_path:
                    if not os.path.exists(self.ca_cert_path):
                        abs_path = os.path.abspath(self.ca_cert_path)
                        print(f"ERROR: CA certificate file not found: {self.ca_cert_path}")
                        print(f"  Absolute path checked: {abs_path}")
                        print(f"  Current working directory: {os.getcwd()}")
                        sys.exit(1)
                    else:
                        abs_path = os.path.abspath(self.ca_cert_path)
                        print(f"Using CA certificate: {abs_path}")
                
                if self.client_cert_path:
                    if not os.path.exists(self.client_cert_path):
                        abs_path = os.path.abspath(self.client_cert_path)
                        print(f"ERROR: Client certificate file not found: {self.client_cert_path}")
                        print(f"  Absolute path checked: {abs_path}")
                        sys.exit(1)
                
                if self.client_key_path:
                    if not os.path.exists(self.client_key_path):
                        abs_path = os.path.abspath(self.client_key_path)
                        print(f"ERROR: Client key file not found: {self.client_key_path}")
                        print(f"  Absolute path checked: {abs_path}")
                        sys.exit(1)
            
            print(f"\nCreating {self.num_connections} parallel connection(s)...")
            
            for i in range(self.num_connections):
                if self.url.startswith("amqps"):
                    try:
                        ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
                    except Exception as e:
                        print(f"ERROR: Failed to create SSL domain: {e}")
                        print("This might indicate Qpid Proton was not compiled with SSL support.")
                        raise

                    if not self.using_schannel:
                        # OpenSSL is being used, set the certificate details if provided
                        if self.insecure:
                            # Insecure mode - try minimal SSL configuration
                            try:
                                # Some Qpid Proton versions require setting peer auth even for anonymous
                                ssl_domain.set_peer_authentication(SSLDomain.ANONYMOUS_PEER)
                            except Exception as e:
                                print(f"Warning: Could not set anonymous peer authentication: {e}")
                                print("Attempting connection without peer authentication setting...")
                                # Continue without setting peer authentication
                        else:
                            # Normal mode with certificate validation
                            ca_set = False
                            if self.ca_cert_path:
                                try:
                                    # Try to set the CA cert - might be a file or directory
                                    ssl_domain.set_trusted_ca_db(self.ca_cert_path)
                                    ca_set = True
                                except Exception as e:
                                    print(f"Warning: Failed to set CA certificate from {self.ca_cert_path}: {e}")
                            
                            if not ca_set:
                                # Try system defaults
                                print("Attempting to use system default CA certificates...")
                                for ca_path in ["/etc/ssl/certs", "/etc/pki/tls/certs", "/usr/share/ca-certificates"]:
                                    if os.path.exists(ca_path):
                                        try:
                                            ssl_domain.set_trusted_ca_db(ca_path)
                                            print(f"Using system CA certificates from {ca_path}")
                                            ca_set = True
                                            break
                                        except Exception as e:
                                            print(f"Failed to use {ca_path}: {e}")
                                
                                if not ca_set and not self.insecure:
                                    print("ERROR: Could not set any CA certificates for verification!")
                                    raise Exception("No valid CA certificate path found")
                            
                            if self.client_cert_path:
                                ssl_domain.set_credentials(self.client_cert_path, self.client_key_path, self.client_cert_password)
                            
                            # Set peer authentication after CA configuration
                            try:
                                ssl_domain.set_peer_authentication(SSLDomain.VERIFY_PEER_NAME)
                            except Exception as e:
                                print(f"ERROR: Failed to set peer authentication: {e}")
                                raise
                    else:
                        # Windows/SChannel
                        if self.insecure:
                            ssl_domain.set_peer_authentication(SSLDomain.ANONYMOUS_PEER)
                        else:
                            ssl_domain.set_peer_authentication(SSLDomain.VERIFY_PEER_NAME)
                else:
                    ssl_domain = None  # No SSL for plain AMQP connections

                # Create a unique connection name for each connection
                connection_name = f"{self.base_client_id}-{i + 1}" if self.base_client_id else f"connection-{i + 1}"
                
                connection = event.container.connect(
                    self.url,
                    ssl_domain=ssl_domain,
                    user=self.username,
                    password=self.password,
                )
                # Set unique container-id for this connection (this is what the broker sees)
                connection.container = connection_name
                
                self.connections[connection] = i + 1  # Store connection number (1-indexed)
                
                # Create receiver with durability options if requested
                if self.durable:
                    # Create a unique subscription name for each connection
                    if self.subscription_name:
                        sub_name = f"{self.subscription_name}-{i + 1}"
                    else:
                        # Auto-generate subscription name including the cleaned topic
                        # Note: The broker will prefix this with the container ID automatically
                        cleaned_topic = self.clean_topic_name(self.topic)
                        sub_name = f"sub-{cleaned_topic}"
                    receiver = event.container.create_receiver(
                        connection, 
                        source=self.topic,
                        name=sub_name,
                        options=DurableSubscription()
                    )
                    print(f"  Connection {i + 1}/{self.num_connections}: Durable receiver '{connection_name}' (subscription: '{sub_name}') created on {self.url}")
                else:
                    receiver = event.container.create_receiver(connection, source=self.topic)
                    print(f"  Connection {i + 1}/{self.num_connections}: Receiver '{connection_name}' created on {self.url}")
                
                self.receivers.append(receiver)
            
            print(f"\nAll {self.num_connections} connection(s) created.")
            print("You should see connections being opened below...")
        except Exception as e:
            print("Error creating receivers:", e)
            traceback.print_exc()
            if event.connection:
                event.connection.close()
            sys.exit(1)

    def on_message(self, event):
        msg = event.message
        # Identify which connection received this message
        connection = event.connection
        conn_num = self.connections.get(connection, "?")
        
        # For connections other than the first, just print a brief notification
        if conn_num != 1:
            subject_info = f" (Subject: {msg.subject})" if msg.subject else ""
            print(f"\n[Connection {conn_num}] Received a message{subject_info}")
            return
        
        # For the first connection, show full details
        print(f"\n[Connection {conn_num}] Received a message:")
        
        # Display message properties
        print("Message properties:")
        if msg.subject:
            print(f"  Subject: {msg.subject}")
        if msg.content_type:
            print(f"  Content-Type: {msg.content_type}")
        if msg.content_encoding:
            print(f"  Content-Encoding: {msg.content_encoding}")
        if msg.expiry_time:
            print(f"  Absolute-Expiry-Time: {msg.expiry_time}")
        if msg.creation_time:
            print(f"  Creation-Time: {msg.creation_time}")
        if msg.address:
            print(f"  Address: {msg.address}")
        if msg.ttl:
            print(f"  TTL: {msg.ttl}")
        if msg.priority:
            print(f"  Priority: {msg.priority}")
        
        # Display application properties
        if msg.properties:
            print("Application properties:")
            for key, value in msg.properties.items():
                print(f"  {key}: {value}")
        else:
            print("No application properties found in the message.")
        
        # Check if the message has a payload
        if msg.body:
            # Convert memoryview to bytes if necessary
            if isinstance(msg.body, memoryview):
                payload = msg.body.tobytes()
            elif isinstance(msg.body, (bytes, bytearray)):
                payload = bytes(msg.body)
            else:
                payload = str(msg.body).encode()
            
            decompressed_payload = payload
            # Detect if the payload is gzipped
            try:
                if msg.content_encoding == "gzip":
                    if payload[:2] == b'\x1f\x8b':  # GZIP magic number
                        decompressed_payload = gzip.decompress(payload)
                        decoded_payload = decompressed_payload.decode('utf-8')
                    else:
                        print("Payload does not appear to be gzipped, but content encoding is set to gzip!")
                        decoded_payload = payload.decode('utf-8')
                else:
                    decoded_payload = payload.decode('utf-8')

                # If output folder path is provided, save the payload to a file
                if self.outputFolderPath:
                    # Detect extension from content type
                    if msg.content_type:
                        extension = msg.content_type.split('/')[-1]
                    else:
                        extension = "unknown"
                    # Create output file path from the folder, message subject, and the extension
                    if msg.subject:
                        filePath = os.path.join(self.outputFolderPath, f"{msg.subject}.{extension}")
                    else:
                        # If no subject provided, create a file name based on the current UTC time
                        # and the extension
                        current_time = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        filePath = os.path.join(self.outputFolderPath, f"{current_time}.{extension}")
                        # If such a file already exists, append a number to the file name
                        counter = 1
                        while os.path.exists(filePath):
                            filePath = os.path.join(self.outputFolderPath, f"{current_time}_{counter}.{extension}")
                            counter += 1
                    # Save the payload to the file
                    with open(filePath, 'wb') as f:
                        f.write(decompressed_payload)
                    print(f"Payload saved to {filePath}")
                
                # Use the helper function to extract report information
                if self.outputFolderPath:
                    context = f"AMQP message saved to '{filePath}'"
                else:
                    context = f"AMQP message with subject '{msg.subject}'" if msg.subject else "AMQP message"
                extracted_info_list = extractReportInformation(decoded_payload, context)
                print(f"Extracted IWXXM Report Information: Found {len(extracted_info_list)} report(s)")
                for i, extracted_info in enumerate(extracted_info_list, 1):
                    print(f"  Report {i}:")
                    for key, value in extracted_info.items():
                        print(f"    {key}: {value}")
            except Exception as e:
                print("Error decoding payload:", e)
        else:
            print("No payload found in the message.")

    def on_connection_opened(self, event):
        conn_num = self.connections.get(event.connection, "?")
        print(f"[Connection {conn_num}] Connection successfully opened.")

    def on_connection_closed(self, event):
        conn_num = self.connections.get(event.connection, "?")
        print(f"[Connection {conn_num}] Connection closed by the server.")
        # Check if all connections are closed
        # For simplicity, we'll exit when any connection closes
        sys.exit(0)

    def on_transport_error(self, event):
        conn_num = self.connections.get(event.connection, "?")
        print(f"[Connection {conn_num}] Transport error:", event.transport.condition)
        if "TLS certificate verification error" in str(event.transport.condition):
            print("TLS certificate verification failed.")
            if platform.system() == "Windows":
                print("On Windows, ensure the HARICA root certificate is imported into certmgr.msc.")
            else:
                print("Ensure the HARICA certificate provided in the .pem file is correct.")
            
            try:
                # Close the existing connection if it exists
                if event.connection:
                    print(f"[Connection {conn_num}] Closing the connection due to transport error.")
                    event.connection.close()

                # Create a unique connection name for the reconnection
                connection_name = f"{self.base_client_id}-{conn_num}" if self.base_client_id else f"connection-{conn_num}"
                
                # Retry with peer verification disabled
                ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
                
                if not self.using_schannel:
                    # Set CA cert before peer authentication if available
                    if self.ca_cert_path:
                        ssl_domain.set_trusted_ca_db(self.ca_cert_path)
                    if self.client_cert_path:
                        ssl_domain.set_credentials(self.client_cert_path, self.client_key_path, self.client_cert_password)
                
                ssl_domain.set_peer_authentication(SSLDomain.ANONYMOUS_PEER)
                connection = event.container.connect(
                    self.url,
                    ssl_domain=ssl_domain,
                    user=self.username,
                    password=self.password,
                )
                # Set unique container-id for this connection (this is what the broker sees)
                connection.container = connection_name
                
                self.connections[connection] = conn_num  # Reuse the same connection number
                
                # Create receiver with the same durability options
                if self.durable:
                    if self.subscription_name:
                        sub_name = f"{self.subscription_name}-{conn_num}"
                    else:
                        # Auto-generate subscription name including the cleaned topic
                        # Note: The broker will prefix this with the container ID automatically
                        cleaned_topic = self.clean_topic_name(self.topic)
                        sub_name = f"sub-{cleaned_topic}"
                    receiver = event.container.create_receiver(
                        connection, 
                        source=self.topic,
                        name=sub_name,
                        options=DurableSubscription()
                    )
                else:
                    receiver = event.container.create_receiver(connection, source=self.topic)
                
                # Update the receiver in the list
                for i, r in enumerate(self.receivers):
                    if r.connection == event.connection:
                        self.receivers[i] = receiver
                        break
                print(f"[Connection {conn_num}] Reconnected with peer verification disabled on:", self.url)
            except Exception as e:
                print(f"[Connection {conn_num}] Error reconnecting with peer verification disabled:", e)
                traceback.print_exc()
                if event.connection:
                    event.connection.close()
        else:
            if event.connection:
                event.connection.close()

    def on_connection_open_failed(self, event):
        conn_num = self.connections.get(event.connection, "?")
        print(f"[Connection {conn_num}] Connection open failed:", event.connection.condition)
        event.connection.close()

    def on_connection_error(self, event):
        conn_num = self.connections.get(event.connection, "?")
        print(f"[Connection {conn_num}] Connection error:", event.connection.condition)
        event.connection.close()

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="IBL MET-SWIM AMQP Client Example")
    parser.add_argument(
        '--output-folder', '-o', 
        default="received_data", 
        help="Folder to store received message data (default: 'received_data')"
    )
    parser.add_argument(
        '--url', '-u', 
        default="amqps://amqp.swim.iblsoft.com:5672", 
        help="AMQP(S) URL to connect to. Use 'amqps://' for SSL connections or 'amqp://' for unencrypted "
         "connections (default: 'amqps://amqp.swim.iblsoft.com:5672')."
    )
    parser.add_argument(
        '--topic', '-t', 
        default="origin.a.wis2.com-ibl.data.core.weather.aviation.*", 
        help="AMQP topic/queue to subscribe to (default is the wildcard topic for all OPMET data: 'origin.a.wis2.com-ibl.data.core.weather.aviation.*')"
    )
    parser.add_argument(
        '--num-connections', '-n',
        type=int,
        default=1,
        help="Number of parallel AMQP connections to create (default: 1)"
    )
    default_ca_cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HARICA-TLS-Root-2021-RSA.pem")
    parser.add_argument(
        '--ca-cert', '-c', 
        default=default_ca_cert_path,
        help=f"Path to the CA certificate file to override the default HARICA staging root certificate (default: '{default_ca_cert_path}'). "
             "On Windows, the certificate must be added to 'Trusted Root Certification Authorities' "
             "using certmgr.msc."
    )
    parser.add_argument(
        '--client-cert', 
        help="Optional. Path to the client certificate file for mutual TLS authentication. "
        "If not provided, only the server's authenticity will be verified."
    )
    parser.add_argument(
        '--client-key', 
        help="Optional. Path to the client private key file for mutual TLS authentication. "
        "If not provided, only the server's authenticity will be verified."
    )
    parser.add_argument(
        '--client-cert-password', 
        help="Optional. Password for the client certificate file (e.g., .p12 file) used for mutual TLS authentication."
    )
    parser.add_argument(
        '--username', 
        help="Optional. Username for AMQP SASL authentication. If provided, password should also be provided."
    )
    parser.add_argument(
        '--password', 
        help="Optional. Password for AMQP SASL authentication. If provided, username should also be provided."
    )
    parser.add_argument(
        '--durable', 
        action='store_true',
        help="Enable durable subscription mode. Messages sent while the client is disconnected will be queued "
             "and delivered when the client reconnects. Requires the broker to support durable subscriptions."
    )
    parser.add_argument(
        '--subscription-name', 
        help="Optional. Custom name for the durable subscription. If not provided, an auto-generated name based "
             "on the client ID will be used. This is only relevant when --durable is enabled."
    )
    parser.add_argument(
        '--insecure', '-k',
        action='store_true',
        help="INSECURE: Disable SSL certificate verification. Use only for testing with self-signed certificates."
    )
    args = parser.parse_args()

    # Use parsed arguments
    s_outputFolderPath = args.output_folder
    url = args.url
    topic = args.topic
    num_connections = args.num_connections
    ca_cert_path = args.ca_cert
    client_cert_path = args.client_cert
    client_key_path = args.client_key
    client_cert_password = args.client_cert_password
    username = args.username
    password = args.password
    durable = args.durable
    subscription_name = args.subscription_name
    insecure = args.insecure
    hostname = socket.gethostname()  # Get the hostname of the computer
    usernameOS = getpass.getuser()  # Get the current user's name
    base_client_id = f"Python-Client-{hostname}-{usernameOS}"  # Base client ID
    container_id = f"{base_client_id}-container"  # Container ID
    try:
        # Enable frame-level tracing by setting trace=1
        Container(
            AMQPClient(
                url, topic, 
                num_connections=num_connections,
                base_client_id=base_client_id,
                outputFolderPath=s_outputFolderPath, 
                ca_cert_path=ca_cert_path, 
                client_cert_path=client_cert_path, 
                client_key_path=client_key_path, 
                client_cert_password=client_cert_password,
                username=username,
                password=password,
                durable=durable,
                subscription_name=subscription_name,
                insecure=insecure
            ), 
            container_id=container_id, 
            trace=1
        ).run()
    except Exception as e:
        print("Error during container run:", e)
        sys.exit(1)