# src/python/data_loader.py
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, Point
import pandas as pd

def generate_synthetic_trails(num_trails=50, area_size=10):
    """
    Generate synthetic trail data for testing.
    Area is in km².
    """
    np.random.seed(42)  # For reproducibility
    trails = []
    
    for i in range(num_trails):
        # Random start point within area
        start_x = np.random.uniform(0, area_size)
        start_y = np.random.uniform(0, area_size)
        
        # Generate a meandering path
        num_points = np.random.randint(20, 100)
        x = [start_x]
        y = [start_y]
        
        for _ in range(num_points - 1):
            # Random walk with some persistence
            dx = np.random.normal(0, 0.1)
            dy = np.random.normal(0, 0.1)
            x.append(x[-1] + dx)
            y.append(y[-1] + dy)
        
        # Clip to area bounds
        x = np.clip(x, 0, area_size)
        y = np.clip(y, 0, area_size)
        
        # Create LineString
        trail = LineString(list(zip(x, y)))
        trails.append(trail)
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({'geometry': trails}, crs="EPSG:4326")
    return gdf

# Test data generation (run this to create sample data)
if __name__ == "__main__":
    trails = generate_synthetic_trails(50)
    # Ensure directory exists would be handled by script but for repo we just show logic
    # trails.to_file("data/raw/synthetic_trails.geojson", driver="GeoJSON")
    print("Synthetic trails generated")
