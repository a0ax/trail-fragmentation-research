#!/usr/bin/env python
"""
Main entry point for trail fragmentation analysis.
Now accepts either a single shapefile or a directory of shapefiles.
"""

import sys
import os
import glob
from pathlib import Path

# Add src/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

from fragmentation import TrailFragmentationAnalyzer
from visualize import TrailVisualizer

def main():
    # --- CONFIGURATION ---
    # Path to protected area data: can be a single .shp file or a directory
    protected_input = 'data/boundaries'   # <-- CHANGE THIS if needed
    
    # Path to GPX files
    gpx_files = glob.glob('data/raw/*.gpx')
    if not gpx_files:
        print(" No GPX files found in data/raw/")
        print("   Place your GPX files there, or generate synthetic data:")
        print("   python -c 'from src.python.data_loader import generate_synthetic_trails; generate_synthetic_trails()'")
        return

    # Check protected area input
    if os.path.isdir(protected_input):
        shp_files = glob.glob(os.path.join(protected_input, "*.shp"))
        if not shp_files:
            print(f" No shapefiles found in directory: {protected_input}")
            return
        print(f" Found {len(shp_files)} shapefiles in {protected_input}")
    elif os.path.isfile(protected_input):
        print(f" Using single shapefile: {protected_input}")
    else:
        print(f" Protected area input not found: {protected_input}")
        return

    # Initialize analyzer (it will handle both cases)
    analyzer = TrailFragmentationAnalyzer(protected_input, buffer_distance=10)

    # Run analysis
    results = analyzer.run_full_analysis(gpx_files)
    analyzer.export_results(results, 'outputs/tables')

    # Load trails for visualization (reload to have the GeoDataFrame)
    trails = analyzer.load_trails(gpx_files)

    # Create visualizations
    viz = TrailVisualizer()
    os.makedirs('outputs/figures', exist_ok=True)

    viz.create_fragmentation_map(analyzer.protected_area, trails, 
                                 'outputs/figures/fragmentation_map.png',
                                 buffer_distance=10)
    viz.create_metrics_dashboard(results, 'outputs/figures/metrics_dashboard.png')
    viz.create_interactive_map(analyzer.protected_area, trails,
                               'outputs/figures/interactive_map.html')

    print("\n Analysis complete! Check the outputs/ directory.")
    print("\n KEY FINDINGS:")
    frag = results['fragmentation']
    print(f"   Fragmentation Index: {frag['fragmentation_percent']:.2f}%")
    print(f"   Affected Area: {frag['affected_area_km2']:.2f} km²")
    print(f"   Trail Density: {frag['trail_density_km_per_km2']:.2f} km/km²")
    print(f"   Core Habitat Remaining: {frag['core_habitat_percent']:.1f}%")

if __name__ == "__main__":
    main()