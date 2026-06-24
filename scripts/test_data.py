import geopandas as gpd

gdf = gpd.read_file('data/boundaries/swissTLMRegio_LandCover.shp')
print("=== OBJORIG values ===")
print(gdf['OBJORIG'].value_counts())
print("\n=== OBJVAL values ===")
print(gdf['OBJVAL'].value_counts())
print("\n=== NAMN1 values (sample) ===")
print(gdf['NAMN1'].dropna().unique()[:20])
