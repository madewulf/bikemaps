import geopandas as gpd
from shapely.geometry import Point

# Load the street network
streets = gpd.read_file("brussels_streets.geojson")

# Filter out driveways
streets = streets[streets['DESCRFRE'] != 'Entrée carrossable']

# Define home and office coordinates
home_coords = (148723.90645584, 168526.692207825)
office_coords = (152189.591428308, 169671.141820495)

home_point = Point(home_coords)
office_point = Point(office_coords)

# Find the nearest street to home
home_street_index = streets.distance(home_point).idxmin()
home_street = streets.loc[home_street_index]

# Find the nearest street to the office
office_street_index = streets.distance(office_point).idxmin()
office_street = streets.loc[office_street_index]

print(f"Nearest street to home: {home_street['DESCRFRE']}")
print(f"Nearest street to office: {office_street['DESCRFRE']}")