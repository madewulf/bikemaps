
import osmnx as ox
import networkx as nx
import requests
import json
import geopandas as gpd
from shapely.geometry import LineString
import random

# Define home and office coordinates
home_coords = (50.82716562268852, 4.3506397976862505)
office_coords = (50.83745069693055, 4.3998367283686)

# Download the street network for Brussels
G = ox.graph_from_place("Brussels, Belgium", network_type="bike")

# Find the nearest nodes to the home and office coordinates
home_node = ox.nearest_nodes(G, home_coords[1], home_coords[0])
office_node = ox.nearest_nodes(G, office_coords[1], office_coords[0])

def get_route_details(graph, start_node, end_node):
    try:
        # Calculate the shortest path
        route_nodes = nx.shortest_path(graph, start_node, end_node, weight="length")
        route_length = nx.shortest_path_length(graph, start_node, end_node, weight="length")
    except nx.NetworkXNoPath:
        return None, None, None, None, None

    # Get the coordinates for the route
    route_coords = []
    for u, v in zip(route_nodes[:-1], route_nodes[1:]):
        edge_data = graph.get_edge_data(u, v)[0]
        if 'geometry' in edge_data:
            for point in edge_data['geometry'].coords:
                route_coords.append(point)
        else:
            route_coords.append((graph.nodes[u]['x'], graph.nodes[u]['y']))
            route_coords.append((graph.nodes[v]['x'], graph.nodes[v]['y']))

    # Remove duplicate coordinates while preserving order
    unique_coords = []
    seen = set()
    for coord in route_coords:
        # Convert tuple to string for hashing in set
        coord_tuple = (coord[0], coord[1]) 
        if coord_tuple not in seen:
            unique_coords.append(coord)
            seen.add(coord_tuple)

    # Get elevation data from Open-Elevation API
    locations = []
    for lon, lat in unique_coords:
        locations.append({"latitude": lat, "longitude": lon})

    url = "https://api.open-elevation.com/api/v1/lookup"
    headers = {"Content-Type": "application/json"}
    
    # Split locations into chunks if necessary (API limit is usually 10,000 points)
    chunk_size = 10000
    all_elevations = []
    for i in range(0, len(locations), chunk_size):
        chunk = locations[i:i + chunk_size]
        try:
            response = requests.post(url, headers=headers, data=json.dumps({"locations": chunk}))
            response.raise_for_status() # Raise an exception for HTTP errors
            elevation_data = response.json()

            if 'results' not in elevation_data:
                raise Exception("Could not fetch elevation data: 'results' key missing.")
            
            all_elevations.extend([result['elevation'] for result in elevation_data['results']])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching elevation for chunk: {e}")
            # Fallback to 0 elevation for this chunk if API fails
            all_elevations.extend([0] * len(chunk))


    # Create a new list of coordinates with elevation
    coords_with_elevation = []
    for i, coord in enumerate(unique_coords):
        # Ensure elevation exists for this point, default to 0 if not
        elevation = all_elevations[i] if i < len(all_elevations) else 0
        coords_with_elevation.append([coord[0], coord[1], elevation])

    # Calculate elevation gain and loss
    elevation_gain = 0
    elevation_loss = 0
    for i in range(1, len(coords_with_elevation)):
        prev_elevation = coords_with_elevation[i-1][2]
        curr_elevation = coords_with_elevation[i][2]
        diff = curr_elevation - prev_elevation
        if diff > 0:
            elevation_gain += diff
        else:
            elevation_loss += abs(diff)

    return route_nodes, route_length, coords_with_elevation, elevation_gain, elevation_loss

# --- Generate Multiple Routes ---
all_routes_features = []
num_routes_to_generate = 3
found_route_geometries = set() # To store string representations of geometries for uniqueness

route_counter = 0
current_graph = G.copy()

for i in range(num_routes_to_generate):
    route_nodes, route_length, coords_with_elevation, elevation_gain, elevation_loss = get_route_details(current_graph, home_node, office_node)

    if route_nodes is None:
        print(f"Could not find route {i+1}. Skipping.")
        break

    # Create a LineString from the coordinates for uniqueness check
    current_line = LineString(coords_with_elevation)
    current_geometry_str = str(current_line.wkt) # Convert to WKT for hashing

    if current_geometry_str not in found_route_geometries:
        found_route_geometries.add(current_geometry_str)
        route_counter += 1

        route_name = f"Route {route_counter}"
        
        feature = {
            "type": "Feature",
            "properties": {
                "name": route_name,
                "distance_m": round(route_length, 2),
                "elevation_gain_m": round(elevation_gain, 2),
                "elevation_loss_m": round(elevation_loss, 2)
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords_with_elevation
            }
        }
        all_routes_features.append(feature)

        # Temporarily remove some edges from the found route to find alternatives
        edges_to_remove = []
        for u, v in zip(route_nodes[:-1], route_nodes[1:]):
            # Get all keys for multi-edges between u and v
            for key in list(current_graph.get_edge_data(u, v).keys()):
                edges_to_remove.append((u, v, key))
        
        # Remove a random subset of edges to encourage alternative paths
        if len(edges_to_remove) > 0:
            num_to_remove = max(1, len(edges_to_remove) // 3) # Remove at least 1/3 of edges
            random.shuffle(edges_to_remove)
            for u, v, key in edges_to_remove[:num_to_remove]:
                if current_graph.has_edge(u, v, key):
                    current_graph.remove_edge(u, v, key)

# Create a GeoJSON FeatureCollection
geojson_output = {
    "type": "FeatureCollection",
    "name": "bike_routes",
    "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    "features": all_routes_features
}

# Save the GeoJSON file
with open("route.geojson", "w") as f:
    json.dump(geojson_output, f, indent=2)

print(f"Successfully created route.geojson with {len(all_routes_features)} routes and elevation data.")
