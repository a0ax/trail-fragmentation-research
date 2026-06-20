import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import seaborn as sns
import folium
import os

class TrailVisualizer:
    """Create publication-quality maps and dashboards."""
    
    @staticmethod
    def create_fragmentation_map(protected_area, trails_gdf, 
                                 output_path='outputs/figures/fragmentation_map.png',
                                 buffer_distance=10):
        """Map showing protected area (union if multiple polygons) and trails."""
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        # If multiple polygons, union for display (but keep original for area calc)
        if len(protected_area) > 1:
            display_area = gpd.GeoDataFrame(
                geometry=[protected_area.geometry.union_all()], 
                crs=protected_area.crs
            )
        else:
            display_area = protected_area
        
        display_area.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', 
                         linewidth=1, alpha=0.3, label='Protected Area')
        
        if 'frequency' in trails_gdf.columns:
            max_freq = trails_gdf['frequency'].max()
            cmap = plt.cm.Reds
            for _, row in trails_gdf.iterrows():
                intensity = row['frequency'] / max_freq if max_freq > 0 else 0.5
                color = cmap(intensity)
                gpd.GeoSeries([row.geometry]).plot(ax=ax, color=color, 
                                                   linewidth=1.5, alpha=0.8)
        else:
            trails_gdf.plot(ax=ax, color='red', linewidth=1, alpha=0.5, label='Trails')
        
        buffered = trails_gdf.geometry.buffer(buffer_distance)
        buffered_union = buffered.union_all()
        gpd.GeoSeries([buffered_union]).plot(ax=ax, color='red', alpha=0.15, label='Impact Zone')
        
        ax.set_title('Trail-Induced Fragmentation Analysis', fontsize=16)
        ax.set_xlabel('Easting (m)')
        ax.set_ylabel('Northing (m)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"️ Map saved to {output_path}")
    
    # The rest of the functions (dashboard, interactive map) remain the same
    # as in the previous version. They already work with any GeoDataFrame.
    # I'll include them here for completeness, but they are unchanged.
    
    @staticmethod
    def create_metrics_dashboard(results, output_path='outputs/figures/metrics_dashboard.png'):
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        metrics = results['fragmentation']
        meta = results['metadata']
        
        affected = metrics['affected_area_km2']
        intact = meta['protected_area_km2'] - affected
        axes[0,0].pie([affected, intact], labels=['Affected', 'Intact'], 
                      autopct='%1.1f%%', colors=['red', 'lightgreen'], startangle=90)
        axes[0,0].set_title('Habitat Fragmentation')
        
        axes[0,1].bar(['Trail Density'], [metrics['trail_density_km_per_km2']], color='orange')
        axes[0,1].set_ylabel('km / km²')
        axes[0,1].set_title('Trail Density')
        
        axes[0,2].bar(['Edge-to-Area'], [metrics['edge_to_area_ratio']], color='purple')
        axes[0,2].set_title('Edge-to-Area Ratio')
        
        axes[1,0].bar(['Core Habitat'], [metrics['core_habitat_percent']], color='darkgreen')
        axes[1,0].set_ylabel('Percent of Area (%)')
        axes[1,0].set_title(f"Core Habitat Remaining\n({metrics['core_habitat_area_km2']:.2f} km²)")
        axes[1,0].set_ylim(0, 100)
        
        axes[1,1].text(0.5, 0.5, 'Frequency distribution\n(requires track-level data)', 
                       ha='center', va='center', transform=axes[1,1].transAxes)
        axes[1,1].set_title('Trail Usage')
        
        summary = (f"Fragmentation Index: {metrics['fragmentation_percent']:.1f}%\n"
                   f"Affected Area: {metrics['affected_area_km2']:.2f} km²\n"
                   f"Total Trails: {meta['total_trails']}\n"
                   f"Trail Density: {metrics['trail_density_km_per_km2']:.2f} km/km²\n"
                   f"Edge-to-Area: {metrics['edge_to_area_ratio']:.3f}\n"
                   f"Core Habitat: {metrics['core_habitat_percent']:.1f}%")
        axes[1,2].text(0.1, 0.5, summary, transform=axes[1,2].transAxes,
                       fontsize=12, verticalalignment='center', fontfamily='monospace')
        axes[1,2].axis('off')
        axes[1,2].set_title('Summary Statistics')
        
        plt.suptitle('Trail Fragmentation Analysis Dashboard', fontsize=16, y=1.02)
        plt.tight_layout()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f" Dashboard saved to {output_path}")
    
    @staticmethod
    def create_interactive_map(protected_area, trails_gdf, 
                               output_path='outputs/figures/interactive_map.html'):
        prot_wgs = protected_area.to_crs("EPSG:4326")
        trails_wgs = trails_gdf.to_crs("EPSG:4326")
        
        centroid = prot_wgs.geometry.centroid.iloc[0] if len(prot_wgs) > 0 else (0,0)
        m = folium.Map(location=[centroid.y, centroid.x], zoom_start=13)
        
        # If multiple polygons, add each
        for _, row in prot_wgs.iterrows():
            folium.GeoJson(row.geometry, name='Protected Area',
                           style_function=lambda x: {'fillColor': 'green', 'color': 'darkgreen',
                                                     'weight': 2, 'fillOpacity': 0.1}).add_to(m)
        
        for _, row in trails_wgs.iterrows():
            freq = row.get('frequency', 1)
            color = '#FF0000' if freq > 1 else '#FF8C00'
            folium.GeoJson(row.geometry, name=f'Trail (freq={freq})',
                           style_function=lambda x, c=color: {'color': c, 'weight': 2}).add_to(m)
        
        folium.LayerControl().add_to(m)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f" Interactive map saved to {output_path}")