#!/usr/bin/env python
"""
Convert CSV with embedded GPX trackpoints into valid GPX files.
Handles the specific format from hikr.org exports.
"""

import csv
import os
import re
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

def extract_gpx_from_cell(cell_content):
    """
    Extract GPX trackpoint data from a CSV cell.
    
    The data looks like:
    <trkpt lat="46.387..." lon="9.095...">
      <ele>2337.1</ele>
      <time>2013-09-13T12:59:08Z</time>
    </trkpt>
    """
    # The data is often truncated or split. We need to find all complete trkpt elements.
    # Pattern to match complete trackpoint elements
    pattern = r'<trkpt\s+lat="([^"]+)"\s+lon="([^"]+)"[^>]*>.*?</trkpt>'
    matches = re.findall(pattern, cell_content, re.DOTALL)
    
    if not matches:
        # Try alternate pattern if attributes are quoted with double quotes
        pattern2 = r'<trkpt\s+lat=""([^"]+)""\s+lon=""([^"]+)""[^>]*>.*?</trkpt>'
        matches = re.findall(pattern2, cell_content, re.DOTALL)
    
    return matches

def build_gpx_from_points(points, metadata):
    """
    Build a valid GPX XML string from extracted points.
    
    Args:
        points: list of (lat, lon, ele, time) tuples
        metadata: dict with name, description, etc.
    """
    if not points:
        return None
    
    # GPX header
    gpx = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="csv_to_gpx_converter" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{name}</name>
    <desc>{desc}</desc>
    <time>{time}</time>
  </metadata>
  <trk>
    <name>{name}</name>
    <desc>{desc}</desc>
    <trkseg>
'''.format(
    name=metadata.get('name', 'Converted Track'),
    desc=metadata.get('desc', ''),
    time=datetime.utcnow().isoformat() + 'Z'
)
    
    # Add trackpoints
    for lat, lon, ele, time in points:
        ele_str = f'<ele>{ele}</ele>' if ele else ''
        time_str = f'<time>{time}</time>' if time else ''
        gpx += f'      <trkpt lat="{lat}" lon="{lon}">\n'
        if ele_str:
            gpx += f'        {ele_str}\n'
        if time_str:
            gpx += f'        {time_str}\n'
        gpx += '      </trkpt>\n'
    
    # GPX footer
    gpx += '''    </trkseg>
  </trk>
</gpx>'''
    
    return gpx

def process_csv_to_gpx(csv_path, output_dir='data/raw'):
    """
    Main function: read CSV and convert each row to a GPX file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Read CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Try to detect delimiter
        sample = f.read(1024)
        f.seek(0)
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter
        
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader)  # Skip header row
        
        print(f"📋 CSV Header: {header}")
        print(f"🔍 Detected delimiter: '{delimiter}'")
        
        track_count = 0
        total_points = 0
        
        for row_idx, row in enumerate(reader):
            # Look for the column that contains GPX data
            # Usually it's the first column, but could be others
            gpx_content = None
            for col in row:
                if '<trkpt' in col:
                    gpx_content = col
                    break
            
            if not gpx_content:
                print(f"⚠️  Row {row_idx}: No GPX data found, skipping")
                continue
            
            # Extract points
            points = extract_gpx_from_cell(gpx_content)
            
            if not points:
                print(f"⚠️  Row {row_idx}: No valid trackpoints found")
                continue
            
            # Parse points with elevation and time if available
            parsed_points = []
            for lat, lon in points:
                # Extract elevation and time from the XML
                # Using regex to find ele and time within the trkpt
                ele_match = re.search(r'<ele>([^<]+)</ele>', gpx_content)
                time_match = re.search(r'<time>([^<]+)</time>', gpx_content)
                ele = ele_match.group(1) if ele_match else None
                time = time_match.group(1) if time_match else None
                parsed_points.append((lat, lon, ele, time))
            
            # Build metadata from other columns
            metadata = {
                'name': f'Track_{row_idx:04d}',
                'desc': 'Converted from CSV'
            }
            
            # Try to get a better name from other columns
            for col in row:
                if col and col not in gpx_content and len(col) < 100:
                    metadata['name'] = col[:50].strip()
                    break
            
            # Build and save GPX
            gpx_content = build_gpx_from_points(parsed_points, metadata)
            
            if gpx_content:
                # Clean filename
                safe_name = re.sub(r'[^\w\-_]', '_', metadata['name'])
                filename = f"{safe_name}_{row_idx:04d}.gpx"
                output_path = os.path.join(output_dir, filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(gpx_content)
                
                track_count += 1
                total_points += len(parsed_points)
                print(f"✅ Saved: {filename} ({len(parsed_points)} points)")
    
    print(f"\n📊 Conversion complete!")
    print(f"   - Tracks processed: {track_count}")
    print(f"   - Total points: {total_points}")
    print(f"   - Output directory: {output_dir}")

def combine_gpx_files(input_dir='data/raw', output_file='data/raw/combined.gpx'):
    """
    Optional: Combine all GPX files into a single GPX file.
    """
    import glob
    
    gpx_files = glob.glob(f"{input_dir}/*.gpx")
    if not gpx_files:
        print("No GPX files found to combine")
        return
    
    # Parse all files and combine
    combined = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="csv_to_gpx_converter" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Combined Tracks</name>
    <desc>All tracks combined for analysis</desc>
  </metadata>
'''
    
    for file_path in gpx_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract track segments
            seg_match = re.search(r'<trkseg>(.*?)</trkseg>', content, re.DOTALL)
            if seg_match:
                # Wrap each track in its own trk element
                combined += f'''  <trk>
    <name>{os.path.basename(file_path)}</name>
    <trkseg>
{seg_match.group(1)}
    </trkseg>
  </trk>
'''
    
    combined += '</gpx>'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined)
    
    print(f"✅ Combined GPX saved to: {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python csv_to_gpx.py <path_to_csv_file>")
        print("Example: python csv_to_gpx.py data/raw/gpx-tracks-from-hikr.org.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)
    
    # Convert
    process_csv_to_gpx(csv_path, output_dir='data/raw')
    
    # Optionally combine all GPX files
    combine = input("Combine all GPX files into one? (y/n): ").lower() == 'y'
    if combine:
        combine_gpx_files()