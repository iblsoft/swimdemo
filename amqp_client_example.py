import sys
import gzip
from proton import ConnectionException
from proton.handlers import MessagingHandler
from proton.reactor import Container
from iwxxm_utils import extractReportInformation

class AMQPClient(MessagingHandler):
    def __init__(self, url):
        super(AMQPClient, self).__init__()
        self.url = url

    def on_start(self, event):
        try:
            # Create a receiver to listen on the specified URL
            self.receiver = event.container.create_receiver(self.url)
            print("Receiver created on:", self.url)
        except Exception as e:
            print("Error creating receiver:", e)
            # Close connection if receiver creation fails
            event.connection.close()

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
        event.connection.close()

    def on_connection_open_failed(self, event):
        print("Connection open failed:", event.connection.condition)
        event.connection.close()

    def on_connection_error(self, event):
        print("Connection error:", event.connection.condition)
        event.connection.close()

if __name__ == '__main__':
    # Set the AMQP URL to connect to the server with one of the topics
    url = "amqp://amqp.swim.iblsoft.com:5672/origin.a.wis2.com-ibl.data.core.weather.aviation.metar"
    try:
        Container(AMQPClient(url)).run()
    except Exception as e:
        print("Error during container run:", e)
        sys.exit(1)