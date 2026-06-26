#!/usr/bin/env python
"""
Analyze fragmentation by protected area type and identify spatial hotspots.
Now with proper map axes (longitude/latitude) for Switzerland.
"""

import sys
import os
import glob
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import folium

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))
from fragmentation import TrailFragmentationAnalyzer

# Set up paths
PROTECTED_SHP = 'data/boundaries/swiss_protected_areas_prepared.shp'
GPX_DIR = 'data/raw'
OUTPUT_DIR = 'outputs/by_type'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Load protected areas (in LV95 for area calculations)
print("Loading protected areas...")
protected = gpd.read_file(PROTECTED_SHP)
if protected.crs is None or protected.crs.is_geographic:
    protected = protected.to_crs('EPSG:2056')  # LV95 for accurate area

# 2. Load trails
analyzer = TrailFragmentationAnalyzer(PROTECTED_SHP, buffer_distance=10)
gpx_files = glob.glob(f"{GPX_DIR}/*.gpx")
trails_gdf = analyzer.load_trails(gpx_files)

# 3. Compute fragmentation per type (using LV95 for accurate area)
def compute_metrics_by_type(protected_gdf, trails_gdf, buffer_dist=10):
    results = []
    types = protected_gdf['Res_Type'].unique()
    
    for t in types:
        print(f"Processing type: {t}")
        sub = protected_gdf[protected_gdf['Res_Type'] == t].copy()
        if sub.empty:
            continue
        union_geom = unary_union(sub.geometry)
        sub_gdf = gpd.GeoDataFrame({'geometry': [union_geom]}, crs=sub.crs)
        
        trail_buffers = trails_gdf.geometry.buffer(buffer_dist)
        affected = gpd.overlay(sub_gdf, gpd.GeoDataFrame(geometry=trail_buffers, crs=trails_gdf.crs), how='intersection')
        affected_area = affected.geometry.area.sum() if not affected.empty else 0
        
        total_area_type = sub_gdf.geometry.area.sum()
        trails_clipped = gpd.overlay(sub_gdf, trails_gdf, how='intersection')
        trail_length = trails_clipped.geometry.length.sum() if not trails_clipped.empty else 0
        
        # Core habitat: fix ambiguous truth value
        core_buffer = buffer_dist * 10
        core_geom = sub_gdf.geometry.buffer(-core_buffer)
        # area.sum() works on GeoSeries; .is_empty is not needed
        core_area = core_geom.area.sum()
        core_area = max(0, core_area)   # ensure non-negative
        
        frag_index = affected_area / total_area_type if total_area_type > 0 else 0
        trail_density = trail_length / (total_area_type / 1e6) if total_area_type > 0 else 0
        core_percent = (core_area / total_area_type) * 100 if total_area_type > 0 else 0
        
        results.append({
            'Res_Type': t,
            'Total_Area_km2': total_area_type / 1e6,
            'Affected_Area_km2': affected_area / 1e6,
            'Fragmentation_Index': frag_index,
            'Fragmentation_Percent': frag_index * 100,
            'Trail_Length_km': trail_length / 1000,
            'Trail_Density_km_per_km2': trail_density,
            'Core_Habitat_km2': core_area / 1e6,
            'Core_Habitat_Percent': core_percent,
            'Num_Features': len(sub)
        })
    
    return pd.DataFrame(results)

print("\nComputing fragmentation metrics by protected area type...")
metrics_df = compute_metrics_by_type(protected, trails_gdf)
metrics_df.to_csv(os.path.join(OUTPUT_DIR, 'fragmentation_by_type.csv'), index=False)
print(f"\n✅ Saved summary table to {OUTPUT_DIR}/fragmentation_by_type.csv")

# 4. Create maps with proper axes (WGS84 for visualization)

# Create a WGS84 version of the data for plotting
protected_wgs = protected.to_crs('EPSG:4326')
trails_wgs = trails_gdf.to_crs('EPSG:4326')

# Merge metrics back to protected polygons
protected_merged = protected_wgs.merge(metrics_df[['Res_Type', 'Fragmentation_Percent']], on='Res_Type', how='left')

# 4a. Static map: Protected areas colored by fragmentation
fig, ax = plt.subplots(1, 1, figsize=(14, 12))

# Plot each polygon with color based on fragmentation
for _, row in protected_merged.iterrows():
    frag = row['Fragmentation_Percent']
    if pd.isna(frag):
        color = '#cccccc'  # gray
    elif frag < 0.5:
        color = '#2ca02c'  # green (low fragmentation)
    elif frag < 2:
        color = '#ff7f0e'  # orange (medium)
    elif frag < 5:
        color = '#d62728'  # red (high)
    else:
        color = '#8B0000'  # dark red (very high)
    gpd.GeoSeries([row.geometry]).plot(ax=ax, color=color, edgecolor='black', linewidth=0.3, alpha=0.7)

# Add trails (sample for performance)
trails_sample = trails_wgs.sample(min(500, len(trails_wgs)))
trails_sample.plot(ax=ax, color='blue', linewidth=0.5, alpha=0.3, label='Trails')

ax.set_xlabel('Longitude (°E)')
ax.set_ylabel('Latitude (°N)')
ax.set_title('Fragmentation Index by Protected Area Type (Switzerland)', fontsize=14)

# Set axis limits for Switzerland (approximate)
ax.set_xlim(5.5, 10.5)
ax.set_ylim(45.5, 48.0)

# Add grid with proper labels
ax.grid(True, alpha=0.3, linestyle='--')
ax.set_aspect('equal')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'fragmentation_map_static.png'), dpi=300)
plt.close()
print(f"✅ Saved static map to {OUTPUT_DIR}/fragmentation_map_static.png")

# 4b. Bar chart of fragmentation by type
plt.figure(figsize=(14, 10))
sorted_df = metrics_df.sort_values('Fragmentation_Percent', ascending=False)
# Only show top 15 for readability
top_df = sorted_df.head(15)
colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(top_df)))[::-1]
bars = plt.barh(top_df['Res_Type'], top_df['Fragmentation_Percent'], color=colors)

# Add value labels
for bar, val in zip(bars, top_df['Fragmentation_Percent']):
    plt.text(val + 0.1, bar.get_y() + bar.get_height()/2, f'{val:.2f}%', 
             va='center', fontsize=9)

plt.xlabel('Fragmentation Index (%)')
plt.ylabel('Protected Area Type')
plt.title('Fragmentation by Protected Area Type (Switzerland)')
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'fragmentation_by_type_bar.png'), dpi=300)
plt.close()
print(f"✅ Saved bar chart to {OUTPUT_DIR}/fragmentation_by_type_bar.png")

# 5. Trail density grid (with proper axes)
print("\nComputing spatial trail density (grid) for hotspots...")

# Use WGS84 for grid creation (but calculate area in projected CRS)
cell_size_deg = 0.05  # ~5.5 km at Swiss latitude
bounds = protected_wgs.total_bounds  # (minx, miny, maxx, maxy)

x_coords = np.arange(bounds[0], bounds[2], cell_size_deg)
y_coords = np.arange(bounds[1], bounds[3], cell_size_deg)
grid_cells = []
for x in x_coords:
    for y in y_coords:
        grid_cells.append(Polygon([
            (x, y),
            (x + cell_size_deg, y),
            (x + cell_size_deg, y + cell_size_deg),
            (x, y + cell_size_deg)
        ]))
grid_gdf = gpd.GeoDataFrame({'geometry': grid_cells}, crs='EPSG:4326')

# Clip grid to protected areas (intersection)
grid_intersects = grid_gdf[grid_gdf.intersects(unary_union(protected_wgs.geometry))]

# For each grid cell, compute trail length (using projected CRS for accurate length)
trails_proj = trails_gdf.to_crs('EPSG:2056')
grid_proj = grid_intersects.to_crs('EPSG:2056')

grid_proj['trail_length'] = 0.0
for idx, cell in grid_proj.iterrows():
    trails_in_cell = trails_proj[trails_proj.intersects(cell.geometry)]
    if not trails_in_cell.empty:
        # Use spatial join for better performance
        clipped = gpd.clip(trails_in_cell, cell.geometry)
        if not clipped.empty:
            grid_proj.at[idx, 'trail_length'] = clipped.geometry.length.sum()

# Calculate density
grid_proj['cell_area_km2'] = grid_proj.geometry.area / 1e6
grid_proj['trail_density'] = grid_proj['trail_length'] / 1000 / grid_proj['cell_area_km2']

# Convert back to WGS84 for plotting
grid_wgs = grid_proj.to_crs('EPSG:4326')

# 5a. Static density grid map (with proper axes)
fig, ax = plt.subplots(1, 1, figsize=(14, 12))

# Plot grid cells
grid_wgs.plot(column='trail_density', ax=ax, cmap='hot_r', 
              legend=True, legend_kwds={'label': 'Trail Density (km/km²)'},
              edgecolor='gray', linewidth=0.3, alpha=0.8)

# Overlay protected area boundaries
protected_wgs.boundary.plot(ax=ax, color='green', linewidth=1, alpha=0.5, label='Protected Areas')

ax.set_xlabel('Longitude (°E)')
ax.set_ylabel('Latitude (°N)')
ax.set_title('Trail Density Hotspots within Protected Areas (5km grid)', fontsize=14)
ax.set_xlim(5.5, 10.5)
ax.set_ylim(45.5, 48.0)
ax.grid(True, alpha=0.3, linestyle='--')
ax.set_aspect('equal')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'trail_density_grid.png'), dpi=300)
plt.close()
print(f"✅ Saved trail density grid map to {OUTPUT_DIR}/trail_density_grid.png")

# 6. Interactive maps with Folium (already use proper coordinates)

# 6a. Protected areas by fragmentation
m1 = folium.Map(location=[46.8, 8.2], zoom_start=8, tiles='OpenStreetMap')

def get_color(frag):
    if pd.isna(frag):
        return 'gray'
    elif frag < 0.5:
        return '#2ca02c'  # green
    elif frag < 2:
        return '#ff7f0e'  # orange
    elif frag < 5:
        return '#d62728'  # red
    else:
        return '#8B0000'  # dark red

for _, row in protected_merged.iterrows():
    frag = row['Fragmentation_Percent']
    color = get_color(frag)
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.6
        },
        tooltip=f"{row['Res_Type']}<br>Fragmentation: {frag:.2f}%"
    ).add_to(m1)

m1.save(os.path.join(OUTPUT_DIR, 'fragmentation_map_interactive.html'))
print(f"✅ Saved interactive fragmentation map to {OUTPUT_DIR}/fragmentation_map_interactive.html")

# 6b. Trail density grid
m2 = folium.Map(location=[46.8, 8.2], zoom_start=8, tiles='OpenStreetMap')

for _, row in grid_wgs.iterrows():
    density = row['trail_density']
    if density > 0:
        if density < 1:
            color = '#2ca02c'
        elif density < 5:
            color = '#ff7f0e'
        else:
            color = '#d62728'
        folium.GeoJson(
            row.geometry,
            style_function=lambda x, c=color: {
                'fillColor': c,
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.6
            },
            tooltip=f"Density: {density:.2f} km/km²"
        ).add_to(m2)

m2.save(os.path.join(OUTPUT_DIR, 'trail_density_hotspots_interactive.html'))
print(f"✅ Saved interactive hotspot map to {OUTPUT_DIR}/trail_density_hotspots_interactive.html")

print("\n🎉 All analyses complete! Check the outputs/by_type/ folder.")
print("\n📊 Files generated:")
print(f"   - {OUTPUT_DIR}/fragmentation_by_type.csv")
print(f"   - {OUTPUT_DIR}/fragmentation_by_type_bar.png")
print(f"   - {OUTPUT_DIR}/fragmentation_map_static.png")
print(f"   - {OUTPUT_DIR}/fragmentation_map_interactive.html")
print(f"   - {OUTPUT_DIR}/trail_density_grid.png")
print(f"   - {OUTPUT_DIR}/trail_density_hotspots_interactive.html")