#!/usr/bin/env python
"""
Extract GPX from CSV with a 'gpx' column.
Supports large GPX content (increased field size limit).
Optionally filters by bounding box using the 'bounds' column.
"""

import csv
import os
import re
import sys
import json
from pathlib import Path

# Increase CSV field size limit to handle large GPX columns
csv.field_size_limit(sys.maxsize)

def sanitize_filename(name):
    """Remove invalid characters for filenames."""
    return re.sub(r'[^\w\-_. ]', '_', str(name))

def parse_bounds(bounds_str):
    """
    Parse the 'bounds' column (JSON-like dict) to extract min/max lat/lon.
    Example:
    "{'min': {'type': 'Point', 'coordinates': [13.242523, 47.231143]}, 'max': ...}"
    Returns a dict with 'min_lat', 'max_lat', 'min_lon', 'max_lon' or None if parsing fails.
    """
    try:
        # Replace single quotes with double quotes for valid JSON
        bounds_str_fixed = bounds_str.replace("'", '"')
        bounds = json.loads(bounds_str_fixed)
        min_lon, min_lat = bounds['min']['coordinates']
        max_lon, max_lat = bounds['max']['coordinates']
        return {
            'min_lat': min_lat,
            'max_lat': max_lat,
            'min_lon': min_lon,
            'max_lon': max_lon
        }
    except Exception:
        return None

def track_in_area(bounds_info, area_bounds):
    """
    Check if track's bounding box intersects the area bounding box.
    area_bounds: dict with 'min_lat', 'max_lat', 'min_lon', 'max_lon'
    """
    if not bounds_info:
        return False
    # Check if the two bounding boxes overlap
    if bounds_info['max_lat'] < area_bounds['min_lat'] or bounds_info['min_lat'] > area_bounds['max_lat']:
        return False
    if bounds_info['max_lon'] < area_bounds['min_lon'] or bounds_info['min_lon'] > area_bounds['max_lon']:
        return False
    return True

def extract_gpx_from_csv(csv_path, output_dir='data/raw', max_rows=None, start_row=0,
                         area_bounds=None, filter_bounds=False):
    """
    Extract GPX from 'gpx' column and save as individual files.
    
    Args:
        csv_path: Path to CSV file
        output_dir: Where to save GPX files
        max_rows: Maximum number of rows to process (None = all)
        start_row: Row to start from (for resuming)
        area_bounds: dict with min_lat, max_lat, min_lon, max_lon for filtering
        filter_bounds: if True, use area_bounds to filter tracks
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # First, detect delimiter
    with open(csv_path, 'r', encoding='utf-8') as f:
        sample = f.read(1024)
        f.seek(0)
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter
        print(f"🔍 Detected delimiter: '{delimiter}'")
    
    # Count total rows quickly (with large field size)
    print("📊 Counting rows... (this may take a moment)")
    total_rows = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Use quoting=csv.QUOTE_MINIMAL to handle quoted fields with newlines
        reader = csv.reader(f, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        try:
            header = next(reader)  # skip header
        except StopIteration:
            print("CSV is empty")
            return
        for _ in reader:
            total_rows += 1
            if total_rows % 100000 == 0:
                print(f"   Counted {total_rows:,} rows...")
    print(f"📊 Total rows: {total_rows:,}")
    
    if max_rows:
        total_rows = min(total_rows, max_rows)
        print(f"📊 Processing only first {total_rows:,} rows")
    
    # Re-open for processing
    processed = 0
    skipped = 0
    errors = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        header = next(reader)
        
        # Find column indices
        try:
            gpx_idx = header.index('gpx')
        except ValueError:
            print("❌ 'gpx' column not found")
            return
        
        # Find bounds column if filtering
        bounds_idx = None
        if filter_bounds:
            try:
                bounds_idx = header.index('bounds')
                print(f"✅ Found 'bounds' column for filtering")
            except ValueError:
                print("⚠️ 'bounds' column not found, cannot filter")
                filter_bounds = False
        
        # Find name column
        name_idx = None
        for col in ['_id', 'name', 'url']:
            if col in header:
                name_idx = header.index(col)
                break
        if name_idx is not None:
            print(f"✅ Using column '{header[name_idx]}' for filename")
        
        row_num = 0
        for row in reader:
            row_num += 1
            
            if row_num <= start_row:
                continue
            if max_rows and row_num > max_rows + start_row:
                break
            
            # Filter by bounds if enabled
            if filter_bounds and bounds_idx is not None:
                bounds_str = row[bounds_idx].strip()
                bounds_info = parse_bounds(bounds_str)
                if not track_in_area(bounds_info, area_bounds):
                    skipped += 1
                    continue
            
            try:
                gpx_content = row[gpx_idx].strip()
                if not gpx_content:
                    skipped += 1
                    continue
                
                # Validate that it looks like GPX XML
                if not (gpx_content.startswith('<?xml') or gpx_content.startswith('<gpx')):
                    skipped += 1
                    continue
                
                # Generate filename
                if name_idx is not None and len(row) > name_idx:
                    base_name = row[name_idx].strip()
                    base_name = sanitize_filename(base_name)
                else:
                    base_name = f"track_{row_num:06d}"
                
                # Ensure unique filename
                filename = f"{base_name}.gpx"
                filepath = os.path.join(output_dir, filename)
                counter = 1
                while os.path.exists(filepath):
                    filename = f"{base_name}_{counter:03d}.gpx"
                    filepath = os.path.join(output_dir, filename)
                    counter += 1
                
                with open(filepath, 'w', encoding='utf-8') as out:
                    out.write(gpx_content)
                
                processed += 1
                if processed % 100 == 0:
                    print(f"   Processed {processed:,} GPX files...")
                
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"⚠️ Error on row {row_num}: {e}")
                continue
    
    print(f"\n📊 Summary:")
    print(f"   ✅ GPX files created: {processed:,}")
    print(f"   ⚠️ Skipped (filtered/empty/invalid): {skipped:,}")
    print(f"   ❌ Errors: {errors:,}")
    print(f"   📁 Output directory: {output_dir}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract GPX from CSV')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--output', '-o', default='data/raw', help='Output directory')
    parser.add_argument('--max-rows', '-n', type=int, default=None, help='Max rows to process')
    parser.add_argument('--start-row', '-s', type=int, default=0, help='Start row (for resuming)')
    parser.add_argument('--filter-switzerland', action='store_true',
                        help='Filter tracks to only those intersecting Switzerland (approx bounds)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"❌ CSV file not found: {args.csv_file}")
        sys.exit(1)
    
    # Define Switzerland bounding box (approximate)
    swiss_bounds = {
        'min_lat': 45.8,
        'max_lat': 47.8,
        'min_lon': 5.9,
        'max_lon': 10.5
    }
    
    extract_gpx_from_csv(
        args.csv_file,
        args.output,
        args.max_rows,
        args.start_row,
        area_bounds=swiss_bounds if args.filter_switzerland else None,
        filter_bounds=args.filter_switzerland
    )