#!/usr/bin/env python
import sys
import os
import glob
import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

from fragmentation import TrailFragmentationAnalyzer
from visualize import TrailVisualizer

def prepare_protected_areas(input_shp, output_shp='data/boundaries/swiss_protected_areas_prepared.shp'):
    """
    Load, clean, and prepare the Swiss protected areas dataset.
    
    - Filters to polygon geometries only
    - Reprojects to EPSG:2056 (LV95) for accurate area calculations
    - Filters out zero-area polygons
    - Saves a cleaned version for faster loading
    """
    print(f"📁 Loading Swiss protected areas from: {input_shp}")
    gdf = gpd.read_file(input_shp)
    
    print(f"   Total features: {len(gdf)}")
    
    # 1. Filter to polygon geometries only
    gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])].copy()
    print(f"   After filtering to polygons: {len(gdf)} features")
    
    # 2. Remove features with zero area (invalid geometries)
    # First, reproject to calculate area
    if gdf.crs is None or gdf.crs.is_geographic:
        gdf_temp = gdf.to_crs('EPSG:2056') if gdf.crs is not None else gdf.copy()
        # If CRS is None, we need to set it first
        if gdf.crs is None:
            # Try to set a reasonable CRS
            gdf = gdf.set_crs('EPSG:4326')
            gdf_temp = gdf.to_crs('EPSG:2056')
        else:
            gdf_temp = gdf.to_crs('EPSG:2056')
    else:
        gdf_temp = gdf
    
    # Remove invalid geometries
    gdf = gdf[~gdf.geometry.is_empty].copy()
    print(f"   After removing empty geometries: {len(gdf)} features")
    
    # 3. Reproject to EPSG:2056 (LV95) for accurate area calculations
    gdf = gdf.to_crs('EPSG:2056')
    print(f"   Reprojected to EPSG:2056 (LV95)")
    
    # 4. Calculate area in hectares and add as a column
    gdf['area_ha'] = gdf.geometry.area / 10000
    gdf['area_km2'] = gdf.geometry.area / 1e6
    
    # 5. Filter to meaningful protected areas (remove tiny slivers)
    # Keep areas > 0.01 ha (100 m²)
    gdf = gdf[gdf['area_ha'] > 0.01].copy()
    print(f"   After removing tiny slivers (<0.01 ha): {len(gdf)} features")
    
    # 6. Summary by protected area type
    if 'Res_Type' in gdf.columns:
        print("\n📊 Protected area types:")
        type_summary = gdf.groupby('Res_Type')['area_km2'].agg(['count', 'sum']).round(2)
        type_summary.columns = ['Count', 'Area (km²)']
        print(type_summary)
    
    # 7. Save prepared data
    gdf.to_file(output_shp)
    print(f"\n   ✅ Saved prepared protected areas to: {output_shp}")
    
    total_area_km2 = gdf['area_km2'].sum()
    print(f"   Total protected area: {total_area_km2:.2f} km²")
    
    return gdf

def main():
    # --- CONFIGURATION ---
    input_shp = 'data/boundaries/ALL_SwissReserve.shp'
    prepared_shp = 'data/boundaries/swiss_protected_areas_prepared.shp'
    
    if not os.path.exists(input_shp):
        print(f"❌ Shapefile not found at: {input_shp}")
        return
    
    # Prepare the protected areas
    protected_area = prepare_protected_areas(input_shp, prepared_shp)
    
    if len(protected_area) == 0:
        print("❌ No valid protected areas found. Exiting.")
        return
    
    # Find GPX files
    gpx_files = glob.glob('data/raw/*.gpx')
    if not gpx_files:
        print("❌ No GPX files found in data/raw/")
        return
    
    print(f"\n📁 GPX files found: {len(gpx_files)}")
    
    # Initialize analyzer with prepared protected areas
    analyzer = TrailFragmentationAnalyzer(prepared_shp, buffer_distance=10)
    
    # Run analysis
    results = analyzer.run_full_analysis(gpx_files)
    analyzer.export_results(results, 'outputs/tables')
    
    # Load trails for visualization
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
    
    print("\n✅ Analysis complete! Check the outputs/ directory.")
    print("\n📋 KEY FINDINGS:")
    frag = results['fragmentation']
    print(f"   Protected Area Total: {results['metadata']['protected_area_km2']:.2f} km²")
    print(f"   Fragmentation Index: {frag['fragmentation_percent']:.2f}%")
    print(f"   Affected Area: {frag['affected_area_km2']:.2f} km²")
    print(f"   Trail Density: {frag['trail_density_km_per_km2']:.2f} km/km²")
    print(f"   Core Habitat Remaining: {frag['core_habitat_percent']:.1f}%")

if __name__ == "__main__":
    main()