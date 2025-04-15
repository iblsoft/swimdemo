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
import argparse
from datetime import datetime, timezone
from proton import ConnectionException, SSLDomain, SASL
from proton.handlers import MessagingHandler
from proton.reactor import Container
from iwxxm_utils import extractReportInformation

class AMQPClient(MessagingHandler):
    def __init__(self, url, topic, outputFolderPath=None, ca_cert_path=None):
        super(AMQPClient, self).__init__()
        self.url = url
        self.topic = topic
        self.outputFolderPath = outputFolderPath
        self.ca_cert_path = ca_cert_path
        if not os.path.exists(self.outputFolderPath):
            os.makedirs(self.outputFolderPath)

    def on_start(self, event):
        # Configure SSL for the connection
        try:
            ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
            # Enable peer authentication (verify the broker's certificate)
            ssl_domain.set_peer_authentication(SSLDomain.VERIFY_PEER_NAME)
            if platform.system() != "Windows":
                # Use the provided CA certificate path or default to the HARICA root certificate
                ssl_domain.set_trusted_ca_db(self.ca_cert_path)
            else:
                # On Windows, rely on the certificate imported into the Windows certificate store
                # Users need to import the HARICA root certificate into certmgr.msc
                pass
        except:
            print(f"Could not create SSL domain, is Qpid Proton compiled with SSL support?: {e}")
            traceback.print_exc()
            sys.exit(1)

        try:
            # First try with peer verification enabled
            ssl_domain.set_peer_authentication(SSLDomain.VERIFY_PEER_NAME)
            #ssl_domain.set_peer_authentication(SSLDomain.ANONYMOUS_PEER)
            connection = event.container.connect(
                self.url,
                ssl_domain=ssl_domain,
            )
            self.receiver = event.container.create_receiver(connection, source=self.topic)
            print("Receiver created on:", self.url)
        except Exception as e:
            print("Error creating receiver:", e)
            traceback.print_exc()
            if event.connection:
                event.connection.close()
            sys.exit(1)

    def on_message(self, event):
        msg = event.message
        print("\nReceived a message:")
        
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
                extracted_info = extractReportInformation(decoded_payload)
                print("Extracted IWXXM Report Information:")
                for key, value in extracted_info.items():
                    print(f"  {key}: {value}")
            except Exception as e:
                print("Error decoding payload:", e)
        else:
            print("No payload found in the message.")

    def on_transport_error(self, event):
        print("Transport error:", event.transport.condition)
        if "TLS certificate verification error" in str(event.transport.condition):
            print("TLS certificate verification failed.")
            if platform.system() == "Windows":
                print("On Windows, ensure the HARICA root certificate is imported into certmgr.msc.")
            else:
                print("Ensure the HARICA certificate provided in the .pem file is correct.")
            
            try:
                # Close the existing connection if it exists
                if event.connection:
                    print("Closing the previous connection due to transport error.")
                    event.connection.close()

                # Retry with peer verification disabled
                ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
                ssl_domain.set_peer_authentication(SSLDomain.ANONYMOUS_PEER)
                connection = event.container.connect(
                    self.url,
                    ssl_domain=ssl_domain,
                )
                self.receiver = event.container.create_receiver(connection, source=self.topic)
                print("Reconnected with peer verification disabled on:", self.url)
            except Exception as e:
                print("Error reconnecting with peer verification disabled:", e)
                traceback.print_exc()
                if event.connection:
                    event.connection.close()
        else:
            if event.connection:
                event.connection.close()

    def on_connection_open_failed(self, event):
        print("Connection open failed:", event.connection.condition)
        event.connection.close()

    def on_connection_error(self, event):
        print("Connection error:", event.connection.condition)
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
        help="AMQPS URL to connect to (default: 'amqps://amqp.swim.iblsoft.com:5672')"
    )
    parser.add_argument(
        '--topic', '-t', 
        default="origin.a.wis2.com-ibl.data.core.weather.aviation.*", 
        help="AMQP topic/queue to subscribe to (default is the wildcard topic for all OPMET data: 'origin.a.wis2.com-ibl.data.core.weather.aviation.*')"
    )
    default_ca_cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HARICA-TLS-Root-2021-RSA.pem")
    parser.add_argument(
        '--ca-cert', '-c', 
        default=default_ca_cert_path,
        help=f"Path to the CA certificate file to override the default HARICA staging root certificate (default: '{default_ca_cert_path}')."
    )
    args = parser.parse_args()

    # Use parsed arguments
    s_outputFolderPath = args.output_folder
    url = args.url
    topic = args.topic
    ca_cert_path = args.ca_cert
    username = getpass.getuser()  # Get the current user's name
    client_id = f"swimdemo-amqp-client-example-{username}"  # Append username to client ID
    try:
        # Enable frame-level tracing by setting trace=1
        Container(
            AMQPClient(url, topic, outputFolderPath=s_outputFolderPath, ca_cert_path=ca_cert_path), 
            container_id=client_id, 
            trace=1
        ).run()
    except Exception as e:
        print("Error during container run:", e)
        sys.exit(1)