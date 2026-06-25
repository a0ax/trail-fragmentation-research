import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
import folium

class TrailVisualizer:
    """Create publication-quality visualizations."""
    
    @staticmethod
    def create_fragmentation_map(protected_area, trails, buffered_trails=None, output_path="outputs/figures/fragmentation_map.png"):
        """Create a map showing the fragmentation analysis."""
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        # Plot protected area
        protected_area.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', 
                           linewidth=1, alpha=0.3, label='Protected Area')
        
        # Plot trails with frequency-based coloring
        if 'frequency' in trails.columns:
            max_freq = trails['frequency'].max()
            cmap = plt.cm.Reds
            for _, trail in trails.iterrows():
                intensity = trail['frequency'] / max_freq
                color = cmap(intensity)
                gpd.GeoSeries([trail.geometry]).plot(ax=ax, color=color, 
                                                   linewidth=1.5, alpha=0.7)
        else:
            trails.plot(ax=ax, color='red', linewidth=1, alpha=0.5, label='Trails')
        
        # Plot buffered trails if provided
        if buffered_trails is not None:
            buffered_trails.plot(ax=ax, color='red', alpha=0.2, label='Impact Zone')
        
        # Add labels and legend
        ax.set_title('Trail-Induced Fragmentation Analysis', fontsize=16)
        ax.set_xlabel('Easting (m)')
        ax.set_ylabel('Northing (m)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"🗺️  Map saved to {output_path}")

    @staticmethod
    def create_metrics_dashboard(results, output_path="outputs/figures/metrics_dashboard.png"):
        """Create a dashboard of all fragmentation metrics."""
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        
        metrics = results['fragmentation']
        
        # 1. Fragmentation Index (pie chart)
        labels = ['Affected Area', 'Intact Habitat']
        sizes = [metrics['affected_area_km2'], 
                 results['metadata']['protected_area_km2'] - metrics['affected_area_km2']]
        colors = ['red', 'lightgreen']
        axes[0, 0].pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        axes[0, 0].set_title('Habitat Fragmentation')
        
        # 2. Trail Density (bar chart)
        axes[0, 1].bar(['Trail Density'], [metrics['trail_density_km_per_km2']], color='orange')
        axes[0, 1].set_ylabel('km / km²')
        axes[0, 1].set_title('Trail Density')
        
        # 3. Edge-to-Area Ratio (bar chart)
        axes[0, 2].bar(['Edge-to-Area'], [metrics['edge_to_area_ratio']], color='purple')
        axes[0, 2].set_title('Edge-to-Area Ratio')
        
        # 4. Core Habitat (bar chart)
        core_remaining = metrics['core_habitat_percent']
        axes[1, 0].bar(['Core Habitat'], [core_remaining], color='darkgreen')
        axes[1, 0].set_ylabel('Percent of Protected Area (%)')
        axes[1, 0].set_title(f'Core Habitat Remaining\
({metrics["core_habitat_area_km2"]:.2f} km²)')
        axes[1, 0].set_ylim(0, 100)
        
        # 5. Trail Length Distribution (histogram)
        axes[1, 1].hist([t['distance_km'] for t in results.get('tracks', [])], 
                       bins=20, color='blue', alpha=0.7)
        axes[1, 1].set_xlabel('Trail Length (km)')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].set_title('Trail Length Distribution')
        
        # 6. Summary statistics (text)
        summary_text = f"""Fragmentation Index: {metrics['fragmentation_percent']:.1f}%
        Affected Area: {metrics['affected_area_km2']:.2f} km²
        Total Trails: {results['metadata']['total_trails']}
        Trail Density: {metrics['trail_density_km_per_km2']:.2f} km/km²
        Edge-to-Area: {metrics['edge_to_area_ratio']:.3f}
        Core Habitat: {metrics['core_habitat_percent']:.1f}%"""
        
        axes[1, 2].text(0.1, 0.5, summary_text, transform=axes[1, 2].transAxes,
                       fontsize=12, verticalalignment='center', fontfamily='monospace')
        axes[1, 2].axis('off')
        axes[1, 2].set_title('Summary Statistics')
        
        plt.suptitle('Trail Fragmentation Analysis Dashboard', fontsize=16, y=1.02)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"📊 Dashboard saved to {output_path}")

    @staticmethod
    def create_interactive_map(protected_area, trails, output_path="outputs/figures/interactive_map.html"):
        """Create an interactive folium map."""
        protected_area_wgs = protected_area.to_crs("EPSG:4326")
        trails_wgs = trails.to_crs("EPSG:4326")
        
        centroid = protected_area_wgs.geometry.centroid.iloc[0]
        m = folium.Map(location=[centroid.y, centroid.x], zoom_start=13)
        
        folium.GeoJson(
            protected_area_wgs,
            name='Protected Area',
            style_function=lambda x: {'fillColor': 'green', 'color': 'darkgreen', 
                                     'weight': 2, 'fillOpacity': 0.1}
        ).add_to(m)
        
        for _, trail in trails_wgs.iterrows():
            freq = trail.get('frequency', 1)
            color = '#FF0000' if freq > 1 else '#FF8C00'
            folium.GeoJson(
                trail.geometry,
                name=f'Trail (freq={freq})',
                style_function=lambda x, c=color: {'color': c, 'weight': 2, 'opacity': 0.7}
            ).add_to(m)
        
        folium.LayerControl().add_to(m)
        m.save(output_path)
        print(f"🌐 Interactive map saved to {output_path}")
