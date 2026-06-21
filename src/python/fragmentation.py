import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union
from scipy.spatial import KDTree
import json
import subprocess
import os
import glob
from pathlib import Path

class TrailFragmentationAnalyzer:
    """
    Core class for computing trail-induced fragmentation metrics.
    Now supports multiple shapefiles (union them automatically).
    
    Metrics calculated:
    - Fragmentation Index = affected_area / total_protected_area
    - Trail density (km/km²)
    - Edge-to-area ratio
    - Core habitat area (area > buffer_distance * 10 from any trail)
    """
    
    def __init__(self, protected_area_input, buffer_distance=10):
        """
        Args:
            protected_area_input: can be:
                - string path to a single shapefile (.shp)
                - string path to a directory containing shapefiles
                - list of paths to shapefiles
            buffer_distance: buffer distance in meters around trails for impact zone
        """
        self.buffer_distance = buffer_distance
        
        # Load and union all protected area geometries
        self.protected_area = self._load_protected_areas(protected_area_input)
        self.crs = self.protected_area.crs
        
        # Reproject to projected CRS (meters) if needed
        if self.crs.is_geographic:
            self.protected_area = self.protected_area.to_crs("EPSG:3857")
            self.crs = "EPSG:3857"
        
        self.total_area = self.protected_area.geometry.area.sum()
        print(f" Total protected area: {self.total_area / 1e6:.2f} km²")
        print(f"   (using {len(self.protected_area)} polygon features)")
    
    def _load_protected_areas(self, input_path):
        """Load one or multiple shapefiles and union them into a single GeoDataFrame."""
        if isinstance(input_path, str):
            # Check if it's a directory
            if os.path.isdir(input_path):
                # Find all .shp files in directory
                shp_files = glob.glob(os.path.join(input_path, "*.shp"))
                if not shp_files:
                    raise FileNotFoundError(f"No .shp files found in directory: {input_path}")
                print(f" Found {len(shp_files)} shapefiles in directory")
                gdfs = []
                for shp in shp_files:
                    gdf = gpd.read_file(shp)
                    gdfs.append(gdf)
                combined = pd.concat(gdfs, ignore_index=True)
                return gpd.GeoDataFrame(combined, crs=combined.crs)
            else:
                # Single file
                return gpd.read_file(input_path)
        elif isinstance(input_path, list):
            gdfs = [gpd.read_file(p) for p in input_path]
            combined = pd.concat(gdfs, ignore_index=True)
            return gpd.GeoDataFrame(combined, crs=combined.crs)
        else:
            raise TypeError("protected_area_input must be str (file or directory) or list of paths")
    
    def load_trails(self, gpx_files, use_fastgeotoolkit=True):
        """
        Load GPX files using the fastgeotoolkit Node.js server.
        """
        if use_fastgeotoolkit:
            try:
                # Send the list of file paths to the Node.js server
                response = requests.post(
                    'http://localhost:3000/process',
                    json={'files': gpx_files},
                    timeout=60  # Adjust timeout for large files
                )
                response.raise_for_status()
                data = response.json()

                # The server returns a 'tracks' array with coordinates and frequency
                # We'll convert these to a GeoDataFrame
                geometries = []
                frequencies = []
                for track in data['tracks']:
                    # fastgeotoolkit returns coordinates as [lat, lng]
                    # We need to convert to (x, y) for Shapely, where x=longitude, y=latitude
                    coords = [(lon, lat) for lat, lon in track['coordinates']]
                    if len(coords) > 1:
                        geometries.append(LineString(coords))
                        frequencies.append(track['frequency'])

                if not geometries:
                    raise ValueError("No valid track geometries found in the data.")

                # Create a GeoDataFrame
                gdf = gpd.GeoDataFrame({
                    'geometry': geometries,
                    'frequency': frequencies
                }, crs="EPSG:4326")

                # Reproject to match the protected area's CRS
                gdf = gdf.to_crs(self.crs)
                return gdf

            except requests.exceptions.ConnectionError:
                print("Error: Could not connect to the fastgeotoolkit server.")
                print("Please make sure it's running with: node src/javascript/server.mjs")
                raise
            except Exception as e:
                print(f"Error processing with fastgeotoolkit: {e}")
                raise

        else:
            # Fallback to the pure Python method (without frequency data)
            # ... (keep your existing fallback code here)
            pass
    
    def calculate_fragmentation_index(self, trails_gdf):
        """Compute all fragmentation metrics."""
        print(" Buffering trails...")
        buffered = trails_gdf.geometry.buffer(self.buffer_distance)
        affected_geom = unary_union(buffered)
        
        if affected_geom.geom_type == 'MultiPolygon':
            affected_area = sum(p.area for p in affected_geom.geoms)
        else:
            affected_area = affected_geom.area
        
        frag_index = affected_area / self.total_area
        total_length = trails_gdf.geometry.length.sum()
        trail_density = total_length / (self.total_area / 1e6)
        
        if affected_geom.geom_type == 'MultiPolygon':
            perimeter = sum(p.length for p in affected_geom.geoms)
        else:
            perimeter = affected_geom.length
        edge_to_area = perimeter / affected_area if affected_area > 0 else 0
        
        core_buffer = self.buffer_distance * 10
        core_geom = self.protected_area.geometry.buffer(-core_buffer).buffer(0)
        core_area = core_geom.area.sum() if not core_geom.is_empty else 0
        core_area = max(0, core_area)
        
        return {
            'fragmentation_index': frag_index,
            'fragmentation_percent': frag_index * 100,
            'affected_area_km2': affected_area / 1e6,
            'total_trail_length_km': total_length / 1000,
            'trail_density_km_per_km2': trail_density,
            'edge_to_area_ratio': edge_to_area,
            'core_habitat_area_km2': core_area / 1e6,
            'core_habitat_percent': (core_area / self.total_area) * 100
        }
    
    def spatial_clustering(self, trails_gdf, sample_interval=10):
        """Compute mean nearest neighbor distance."""
        points = []
        for geom in trails_gdf.geometry:
            if geom.geom_type == 'LineString' and geom.length > 0:
                for dist in np.arange(0, geom.length, sample_interval):
                    pt = geom.interpolate(dist)
                    points.append((pt.x, pt.y))
        if not points:
            return {'mean_nearest_neighbor_distance_m': None, 'total_sample_points': 0}
        pts = np.array(points)
        tree = KDTree(pts)
        distances, _ = tree.query(pts, k=2)
        mean_dist = distances[:, 1].mean()
        return {
            'mean_nearest_neighbor_distance_m': mean_dist,
            'total_sample_points': len(points)
        }
    
    def run_full_analysis(self, gpx_files):
        """Orchestrate the entire analysis pipeline."""
        print(" Starting fragmentation analysis...")
        trails = self.load_trails(gpx_files)
        frag = self.calculate_fragmentation_index(trails)
        cluster = self.spatial_clustering(trails)
        
        results = {
            'fragmentation': frag,
            'spatial': cluster,
            'metadata': {
                'total_trails': len(trails),
                'protected_area_km2': self.total_area / 1e6,
                'buffer_distance_m': self.buffer_distance,
                'crs': str(self.crs),
                'num_protected_features': len(self.protected_area)
            }
        }
        return results
    
    def export_results(self, results, output_dir):
        """Save results to CSV and JSON."""
        os.makedirs(output_dir, exist_ok=True)
        pd.DataFrame([results['fragmentation']]).to_csv(
            os.path.join(output_dir, 'fragmentation_metrics.csv'), index=False
        )
        with open(os.path.join(output_dir, 'analysis_results.json'), 'w') as f:
            json.dump(results, f, indent=2)
        print(f" Results exported to {output_dir}")