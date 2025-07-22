
import geopandas as gpd

# Load the street network
streets = gpd.read_file("brussels_streets.geojson")

# Print unique street names
print(streets['DESCRFRE'].unique())
