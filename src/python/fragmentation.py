import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import unary_union, buffer
from scipy.spatial import KDTree
import json
import subprocess
import os

class TrailFragmentationAnalyzer:
    def __init__(self, protected_area_shapefile, buffer_distance=10):
        self.protected_area = gpd.read_file(protected_area_shapefile)
        self.buffer_distance = buffer_distance
        self.crs = self.protected_area.crs
        if self.crs.is_geographic:
            self.protected_area = self.protected_area.to_crs("EPSG:3857")
            self.crs = "EPSG:3857"
        self.total_area = self.protected_area.geometry.area.sum()
    
    def load_trails_from_gpx(self, gpx_files, use_fastgeotoolkit=True):
        if use_fastgeotoolkit:
            return self._process_with_fastgeotoolkit(gpx_files)
        else:
            return self._load_with_geopandas(gpx_files)
    
    def _process_with_fastgeotoolkit(self, gpx_files):
        cmd = ['node', 'src/javascript/process_tracks.js'] + gpx_files
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"fastgeotoolkit failed: {result.stderr}")
        data = json.loads(result.stdout)
        return self._load_with_geopandas(gpx_files, frequency_data=data)
    
    def _load_with_geopandas(self, gpx_files, frequency_data=None):
        trails = []
        for gpx_file in gpx_files:
            gdf = gpd.read_file(gpx_file, layer='tracks')
            trails.append(gdf)
        all_trails = pd.concat(trails, ignore_index=True)
        all_trails = gpd.GeoDataFrame(all_trails, crs="EPSG:4326")
        all_trails = all_trails.to_crs(self.crs)
        all_trails['frequency'] = 1
        return all_trails
    
    def calculate_fragmentation_index(self, trails_gdf):
        buffered_trails = trails_gdf.geometry.buffer(self.buffer_distance)
        affected_geometry = unary_union(buffered_trails)
        if affected_geometry.geom_type == 'MultiPolygon':
            affected_area = sum(p.area for p in affected_geometry.geoms)
        else:
            affected_area = affected_geometry.area
        fragmentation_index = affected_area / self.total_area
        total_trail_length = trails_gdf.geometry.length.sum()
        trail_density = total_trail_length / (self.total_area / 1e6)
        if affected_geometry.geom_type == 'MultiPolygon':
            perimeter = sum(p.length for p in affected_geometry.geoms)
        else:
            perimeter = affected_geometry.length
        edge_to_area = perimeter / affected_area if affected_area > 0 else 0
        core_buffer = self.buffer_distance * 10
        core_habitat = self.protected_area.geometry.buffer(-core_buffer).area
        core_habitat = max(0, core_habitat)
        return {
            'fragmentation_index': fragmentation_index,
            'fragmentation_percent': fragmentation_index * 100,
            'affected_area_km2': affected_area / 1e6,
            'total_trail_length_km': total_trail_length / 1000,
            'trail_density_km_per_km2': trail_density,
            'edge_to_area_ratio': edge_to_area,
            'core_habitat_area_km2': core_habitat / 1e6,
            'core_habitat_percent': (core_habitat / self.total_area) * 100
        }
    
    def spatial_analysis(self, trails_gdf):
        trail_points = []
        for geom in trails_gdf.geometry:
            if geom.geom_type == 'LineString':
                for i in range(0, int(geom.length), 10):
                    point = geom.interpolate(i)
                    trail_points.append((point.x, point.y))
        if trail_points:
            points = np.array(trail_points)
            tree = KDTree(points)
            distances, _ = tree.query(points, k=2)
            mean_dist = distances[:, 1].mean()
            return {'mean_nearest_neighbor_distance_m': mean_dist, 'total_sample_points': len(points)}
        return {'mean_nearest_neighbor_distance_m': None, 'total_sample_points': 0}

    def run_full_analysis(self, gpx_files):
        trails = self.load_trails_from_gpx(gpx_files)
        fragmentation = self.calculate_fragmentation_index(trails)
        spatial = self.spatial_analysis(trails)
        return {'fragmentation': fragmentation, 'spatial': spatial, 'metadata': {'total_trails': len(trails), 'protected_area_km2': self.total_area / 1e6, 'buffer_distance_m': self.buffer_distance, 'crs': self.crs}}

    def export_results(self, results, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        pd.DataFrame([results['fragmentation']]).to_csv(f"{output_dir}/fragmentation_metrics.csv", index=False)
        with open(f"{output_dir}/analysis_results.json", 'w') as f:
            json.dump(results, f, indent=2)

if __name__ == "__main__":
    analyzer = TrailFragmentationAnalyzer("data/boundaries/protected_area.shp")
    print("Analyzer initialized")
