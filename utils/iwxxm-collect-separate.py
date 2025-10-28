#!/usr/bin/env python3
"""
Extract individual IWXXM reports from WMO collect:MeteorologicalBulletin files.

This script monitors an input folder for files and processes them:
- If the file uses WMO01 encapsulation, extracts messages and IWXXM reports from each
- If the file is a plain XML collect:MeteorologicalBulletin, extracts individual IWXXM reports
- If the file is already an individual IWXXM report, moves it to the output folder

WMO01 encapsulation format is detected by checking for the signature:
10 digits (last 2 are "01") + CR CR LF (0x0D 0x0D 0x0A)

Uses xml.dom.minidom to preserve comments, whitespace, and the exact XML structure.
Output files maintain the same format as input (WMO01 or plain XML).
"""

import argparse
import os
import sys
import time
import shutil
from pathlib import Path
from typing import List, Set, Tuple, Optional
from xml.dom import minidom
from xml.dom.minidom import Document, Element
import signal

# Add parent directory to path to allow imports from utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.WMOEncapsulation import WMO01Reader, WMO01Writer


class ReportExtractor:
    """Handles extraction of IWXXM reports from collect bulletins."""
    
    def __init__(self, input_folder: str, output_folder: str, poll_interval: float = 1.0, watch_mode: bool = False) -> None:
        """
        Initialize the report extractor.
        
        Args:
            input_folder: Path to folder to monitor for input files
            output_folder: Path to folder where output files will be placed
            poll_interval: Seconds between folder scans (default: 1.0)
            watch_mode: If True, continuously monitor folder; if False, process once and exit
        """
        self.input_folder: Path = Path(input_folder).resolve()
        self.output_folder: Path = Path(output_folder).resolve()
        self.poll_interval: float = poll_interval
        self.watch_mode: bool = watch_mode
        self.processed_files: Set[Tuple[str, float]] = set()
        self.running: bool = True
        
        # Validate folders
        if not self.input_folder.exists():
            raise ValueError(f"Input folder does not exist: {self.input_folder}")
        if not self.input_folder.is_dir():
            raise ValueError(f"Input path is not a folder: {self.input_folder}")
        
        # Create output folder if it doesn't exist
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"Input folder: {self.input_folder}")
        print(f"Output folder: {self.output_folder}")
        if self.watch_mode:
            print(f"Watch mode: enabled (poll interval: {self.poll_interval}s)")
            print("Press Ctrl+C to stop...")
        else:
            print(f"Watch mode: disabled (single pass)")
    
    def is_wmo01_encapsulated(self, file_path: Path) -> bool:
        """
        Check if file uses WMO01 encapsulation format.
        
        WMO01 format starts with: 10 digits (last 2 are "01") + CR CR LF
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file uses WMO01 encapsulation, False otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                # Read first 13 bytes (10 digits + 3 for CRCRLF)
                header = f.read(13)
                if len(header) < 13:
                    return False
                
                # Check if first 10 bytes are digits
                if not header[:10].isdigit():
                    return False
                
                # Check if bytes 8-10 (last 2 digits) are "01"
                if header[8:10] != b'01':
                    return False
                
                # Check if followed by CR CR LF (0x0D 0x0D 0x0A)
                if header[10:13] == b'\x0d\x0d\x0a':
                    return True
                
        except Exception:
            pass
        
        return False
    
    def is_xml_content(self, data: bytes) -> bool:
        """
        Check if data looks like XML content.
        
        Args:
            data: Bytes to check
            
        Returns:
            True if data appears to be XML, False otherwise
        """
        # Skip leading whitespace
        stripped = data.lstrip()
        if not stripped:
            return False
        
        # Check for XML declaration
        if stripped.startswith(b'<?xml'):
            return True
        
        # Check for XML tag (starts with < and has > within reasonable distance)
        if stripped.startswith(b'<') and b'>' in stripped[:200]:
            return True
        
        return False
    
    def is_collect_bulletin(self, doc: Document) -> bool:
        """
        Check if the XML document root is a collect:MeteorologicalBulletin.
        
        Args:
            doc: xml.dom.minidom Document object
            
        Returns:
            True if root element is collect:MeteorologicalBulletin, False otherwise
        """
        root = doc.documentElement
        
        # Check if root element local name is MeteorologicalBulletin
        if root.localName != "MeteorologicalBulletin":
            return False
        
        # Check if namespace starts with http://def.wmo.int/collect/
        namespace_uri = root.namespaceURI
        if namespace_uri and namespace_uri.startswith("http://def.wmo.int/collect/"):
            return True
        
        return False
    
    def is_iwxxm_report(self, doc: Document) -> bool:
        """
        Check if the XML document root is an IWXXM report.
        
        Args:
            doc: xml.dom.minidom Document object
            
        Returns:
            True if root element is an IWXXM report, False otherwise
        """
        root = doc.documentElement
        
        # Check if namespace starts with http://icao.int/iwxxm/
        if root.namespaceURI and root.namespaceURI.startswith("http://icao.int/iwxxm/"):
            return True
        
        return False
    
    def copy_namespace_declarations_except_collect(self, from_element: Element, to_element: Element) -> None:
        """
        Copy namespace declarations from one element to another.
        Only copies declarations that don't already exist on the target element.
        Skips the collect namespace as it's not needed in extracted IWXXM reports.
        
        Args:
            from_element: Source element (typically root)
            to_element: Target element (IWXXM report)
        """
        # Collect existing namespace declarations on target element
        existing_ns = set()
        if to_element.attributes:
            for i in range(to_element.attributes.length):
                attr = to_element.attributes.item(i)
                if attr.name.startswith('xmlns'):
                    existing_ns.add(attr.name)
        
        # Copy missing namespace declarations from source element
        if from_element.attributes:
            for i in range(from_element.attributes.length):
                attr = from_element.attributes.item(i)
                # Check if it's a namespace declaration and not already present
                if attr.name.startswith('xmlns') and attr.name not in existing_ns:
                    # Skip collect namespace - not needed in extracted IWXXM reports
                    if attr.value.startswith('http://def.wmo.int/collect/'):
                        continue
                    to_element.setAttribute(attr.name, attr.value)
    
    def extract_iwxxm_reports(self, doc: Document) -> List[Element]:
        """
        Extract IWXXM reports from collect:meteorologicalInformation elements.
        
        Args:
            doc: xml.dom.minidom Document object
            
        Returns:
            List of XML element nodes, one per IWXXM report
        """
        reports = []
        root = doc.documentElement
        
        # Find all meteorologicalInformation elements
        # They could be in any namespace starting with http://def.wmo.int/collect/
        for child in root.childNodes:
            if (child.nodeType == child.ELEMENT_NODE and 
                child.localName == "meteorologicalInformation" and
                child.namespaceURI and 
                child.namespaceURI.startswith("http://def.wmo.int/collect/")):
                
                # Find the IWXXM report inside (first element child with iwxxm namespace)
                for report_child in child.childNodes:
                    if (report_child.nodeType == report_child.ELEMENT_NODE and
                        report_child.namespaceURI and
                        report_child.namespaceURI.startswith("http://icao.int/iwxxm/")):
                        
                        # Copy namespace declarations from root to ensure standalone validity
                        self.copy_namespace_declarations_except_collect(root, report_child)
                        # Store reference to the (now enhanced) node
                        reports.append(report_child)
                        break  # Only one IWXXM report per meteorologicalInformation
        
        return reports
    
    def get_output_filename(self, base_filename: str, sequence_num: Optional[int] = None) -> str:
        """
        Generate output filename with optional sequence number.
        
        Args:
            base_filename: Original filename
            sequence_num: Optional sequence number to append
            
        Returns:
            New filename with sequence number if provided
        """
        stem = Path(base_filename).stem
        suffix = Path(base_filename).suffix
        
        if sequence_num is not None:
            return f"{stem}_{sequence_num:03d}{suffix}"
        else:
            return base_filename
    
    def extract_wmo_heading_and_body(self, message: bytes) -> Tuple[bytes, bytes]:
        """
        Extract WMO heading and XML body from a WMO message.
        
        The message format is: heading-CRCRLF-body
        where CRCRLF is 0x0D 0x0D 0x0A
        
        Args:
            message: Raw WMO message bytes
            
        Returns:
            Tuple of (heading, body) as bytes
        """
        crcrlf = b'\x0d\x0d\x0a'
        idx = message.find(crcrlf)
        
        if idx == -1:
            # No separator found - might be malformed or just body
            # Try to detect if this looks like XML without heading
            if self.is_xml_content(message):
                return b'', message
            # Otherwise treat entire message as heading (shouldn't happen)
            return message, b''
        
        heading = message[:idx]
        body = message[idx + len(crcrlf):]
        return heading, body
    
    def write_report_atomically(self, node: Element, output_filename: str) -> None:
        """
        Write XML node to file atomically using temporary file in input folder.
        Overwrites existing files in output folder if they exist.
        
        Args:
            node: xml.dom.minidom Element node
            output_filename: Target filename in output folder
        """
        # Create temporary file in input folder with dot prefix
        temp_filename = f".{output_filename}"
        temp_path = self.input_folder / temp_filename
        final_path = self.output_folder / output_filename
        
        try:
            # Write to temporary file
            with open(temp_path, 'w', encoding='utf-8') as f:
                # Write XML declaration
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                # Serialize the node directly to XML string
                f.write(node.toxml())
            
            # Atomically move/rename to output folder (overwrites if exists)
            shutil.move(str(temp_path), str(final_path))
            print(f"  Created: {output_filename}")
            
        except Exception as e:
            # Clean up temporary file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            raise e
    
    def write_wmo01_report_atomically(self, heading: bytes, body: bytes, output_filename: str) -> None:
        """
        Write WMO01 formatted report to file atomically.
        
        Args:
            heading: WMO heading bytes
            body: XML body bytes
            output_filename: Target filename in output folder
        """
        # Create temporary file in input folder with dot prefix
        temp_filename = f".{output_filename}"
        temp_path = self.input_folder / temp_filename
        final_path = self.output_folder / output_filename
        
        try:
            # Write using WMO01Writer
            writer = WMO01Writer(str(temp_path))
            writer.writeFromHeaderBody(heading, body)
            writer.close()
            
            # Atomically move/rename to output folder (overwrites if exists)
            shutil.move(str(temp_path), str(final_path))
            print(f"  Created: {output_filename}")
            
        except Exception as e:
            # Clean up temporary file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            raise e
    
    def process_wmo01_file(self, file_path: Path) -> None:
        """
        Process a file with WMO01 encapsulation.
        
        Args:
            file_path: Path object pointing to the WMO01 file to process
        """
        print(f"  Detected WMO01 encapsulation")
        
        message_count = 0
        reports_extracted = 0
        
        # Use WMO01Reader to read all messages
        with WMO01Reader(str(file_path), b_requireZeroTail=False) as reader:
            for message in reader:
                message_count += 1
                
                # Extract WMO heading and body
                heading, body = self.extract_wmo_heading_and_body(message)
                
                # Check if body is XML
                if not self.is_xml_content(body):
                    print(f"  Warning: Message {message_count} does not contain XML, skipping")
                    continue
                
                # Parse XML
                try:
                    doc = minidom.parseString(body)
                except Exception as e:
                    print(f"  Warning: Message {message_count} XML parsing failed: {e}")
                    continue
                
                # Extract IWXXM reports
                reports = []
                if self.is_collect_bulletin(doc):
                    # Extract all reports from collect bulletin
                    reports = self.extract_iwxxm_reports(doc)
                    print(f"  Message {message_count}: collect:MeteorologicalBulletin with {len(reports)} report(s)")
                elif self.is_iwxxm_report(doc):
                    # Single IWXXM report
                    reports = [doc.documentElement]
                    print(f"  Message {message_count}: Individual IWXXM report")
                else:
                    print(f"  Warning: Message {message_count} is not a collect bulletin or IWXXM report, skipping")
                    continue
                
                # Write each extracted report with WMO01 format
                for idx, report in enumerate(reports, start=1):
                    # Serialize report to XML string
                    xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + report.toxml()
                    xml_bytes = xml_str.encode('utf-8')
                    
                    # Generate output filename
                    if len(reports) > 1:
                        # Multiple reports: base_name_msgNNN_repNNN.ext
                        output_filename = self.get_output_filename(file_path.name, (message_count - 1) * 1000 + idx)
                    else:
                        # Single report: base_name_msgNNN.ext
                        output_filename = self.get_output_filename(file_path.name, message_count)
                    
                    # Write using WMO01 format
                    self.write_wmo01_report_atomically(heading, xml_bytes, output_filename)
                    reports_extracted += 1
        
        print(f"  Processed {message_count} WMO message(s), extracted {reports_extracted} report(s)")
        
        # Remove the original file
        file_path.unlink()
        print(f"  Removed original WMO01 file")
    
    def process_plain_xml_file(self, file_path: Path) -> None:
        """
        Process a plain XML file (not WMO01 encapsulated).
        
        Args:
            file_path: Path object pointing to the XML file to process
        """
        # Parse the XML file
        doc = minidom.parse(str(file_path))
        
        # Check if it's a collect bulletin
        if self.is_collect_bulletin(doc):
            print(f"  Detected collect:MeteorologicalBulletin")
            
            # Extract individual IWXXM reports
            reports = self.extract_iwxxm_reports(doc)
            print(f"  Found {len(reports)} IWXXM report(s)")
            
            if len(reports) == 0:
                print(f"  Warning: No IWXXM reports found in bulletin")
            else:
                # Extract all reports with sequence numbers
                for idx, report in enumerate(reports, start=1):
                    output_filename = self.get_output_filename(file_path.name, idx)
                    self.write_report_atomically(report, output_filename)
            
            # Remove the original collect bulletin file
            file_path.unlink()
            print(f"  Removed original bulletin file")
            
        else:
            # Not a collect bulletin - assume it's already an individual IWXXM report
            print(f"  Individual IWXXM report, moving to output folder")
            final_path = self.output_folder / file_path.name
            shutil.move(str(file_path), str(final_path))
            print(f"  Moved: {file_path.name}")
    
    def process_file(self, file_path: Path) -> None:
        """
        Process a single file (WMO01 encapsulated or plain XML).
        
        Args:
            file_path: Path object pointing to the file to process
        """
        try:
            print(f"Processing: {file_path.name}")
            
            # Check if file uses WMO01 encapsulation
            if self.is_wmo01_encapsulated(file_path):
                self.process_wmo01_file(file_path)
            else:
                # Check if it's XML content
                with open(file_path, 'rb') as f:
                    # Read first 1KB to check for XML
                    sample = f.read(1024)
                
                if not self.is_xml_content(sample):
                    print(f"  Warning: File does not appear to be XML or WMO01 format, skipping")
                    return
                
                self.process_plain_xml_file(file_path)
            
            print(f"Successfully processed: {file_path.name}")
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}", file=sys.stderr)
            # Don't mark as processed so it can be retried
            raise
    
    def scan_folder(self) -> None:
        """Scan input folder for new files to process."""
        try:
            # Get all files in input folder
            for entry in self.input_folder.iterdir():
                # Skip if not a file
                if not entry.is_file():
                    continue
                
                # Skip files starting with dot (temporary files)
                if entry.name.startswith('.'):
                    continue
                
                # Skip if already processed
                file_key = (entry.name, entry.stat().st_mtime)
                if file_key in self.processed_files:
                    continue
                
                # Process the file
                try:
                    self.process_file(entry)
                    # Mark as processed
                    self.processed_files.add(file_key)
                except Exception:
                    # Error already logged in process_file
                    pass
                    
        except Exception as e:
            print(f"Error scanning folder: {e}", file=sys.stderr)
    
    def run(self) -> None:
        """Run the extractor - either single pass or continuous watch mode."""
        if self.watch_mode:
            # Set up signal handler for graceful shutdown
            def signal_handler(sig, frame):
                print("\nShutting down gracefully...")
                self.running = False
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Continuous loop
            while self.running:
                self.scan_folder()
                time.sleep(self.poll_interval)
            
            print("Stopped.")
        else:
            # Single pass mode
            self.scan_folder()
            print("Processing complete.")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="""Extract individual IWXXM reports from WMO collect bulletins.

Supported input file formats:

1. Plain XML files containing either:
   - A single IWXXM report (passed through to output)
   - A collect:MeteorologicalBulletin (extracted into individual IWXXM reports)

2. WMO01 encapsulated files containing one or more messages:
   - Each message is extracted and saved to a new file
   - Messages containing collect:MeteorologicalBulletin are separated into individual IWXXM reports
   - Output files preserve WMO01 format with original WMO headings

In all cases, original file names are preserved with sequential counters appended
to differentiate individual extracted reports (e.g., filename_001.ext, filename_002.ext).""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single pass mode (process files once and exit)
  %(prog)s --input ./input --output ./output
  
  # Watch mode (continuously monitor folder)
  %(prog)s -i /data/input -o /data/output --watch --poll-interval 2.0
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input folder to monitor for XML files'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output folder where extracted reports will be placed'
    )
    
    parser.add_argument(
        '-w', '--watch',
        action='store_true',
        help='Watch mode: continuously monitor input folder for new files (default: process once and exit)'
    )
    
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=1.0,
        help='Seconds between folder scans in watch mode (default: 1.0)'
    )
    
    args = parser.parse_args()
    
    try:
        extractor = ReportExtractor(
            input_folder=args.input,
            output_folder=args.output,
            poll_interval=args.poll_interval,
            watch_mode=args.watch
        )
        extractor.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

