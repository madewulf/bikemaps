import osmnx as ox
import networkx as nx
import requests
import json
import geopandas as gpd
from shapely.geometry import LineString

# Define home and office coordinates
home_coords = (50.82716562268852, 4.3506397976862505)
office_coords = (50.83745069693055, 4.3998367283686)

# Download the street network for Brussels
G = ox.graph_from_place("Brussels, Belgium", network_type="bike")

# Find the nearest nodes to the home and office coordinates
home_node = ox.nearest_nodes(G, home_coords[1], home_coords[0])
office_node = ox.nearest_nodes(G, office_coords[1], office_coords[0])

# Calculate the shortest path
route = nx.shortest_path(G, home_node, office_node, weight="length")

# Get the coordinates for the route
route_coords = []
for u, v in zip(route[:-1], route[1:]):
    edge_data = G.get_edge_data(u, v)[0]
    if 'geometry' in edge_data:
        for point in edge_data['geometry'].coords:
            route_coords.append(point)
    else:
        route_coords.append((G.nodes[u]['x'], G.nodes[u]['y']))
        route_coords.append((G.nodes[v]['x'], G.nodes[v]['y']))

# Remove duplicate coordinates
unique_coords = list(dict.fromkeys(route_coords))

# Get elevation data from Open-Elevation API
locations = []
for lon, lat in unique_coords:
    locations.append({"latitude": lat, "longitude": lon})

url = "https://api.open-elevation.com/api/v1/lookup"
headers = {"Content-Type": "application/json"}
data = {"locations": locations}

response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code != 200:
    raise Exception(f"API request failed with status {response.status_code}: {response.text}")

elevation_data = response.json()

if 'results' not in elevation_data:
    raise Exception("Could not fetch elevation data.")

elevations = [result['elevation'] for result in elevation_data['results']]

# Create a new list of coordinates with elevation
coords_with_elevation = []
for i, coord in enumerate(unique_coords):
    coords_with_elevation.append([coord[0], coord[1], elevations[i]])

# Create a GeoDataFrame with the route and elevation
# Provide a dictionary for properties, even if empty
gdf = gpd.GeoDataFrame({'geometry': [LineString(coords_with_elevation)]}, crs="EPSG:4326")

# Save the route as a GeoJSON file
gdf.to_file("route.geojson", driver="GeoJSON")

print("Successfully created route.geojson with elevation data.")