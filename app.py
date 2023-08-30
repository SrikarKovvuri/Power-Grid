from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import re
from flask_cors import CORS
import pandas as pd
import networkx as nx
import math
from sklearn.neighbors import NearestNeighbors
import numpy as np

app = Flask(__name__)
CORS(app)

# Read data from CSV files
buses_df = pd.read_csv('data/gridkit_north_america-highvoltage-vertices.csv')
transmission_df = pd.read_csv('data/gridkit_north_america-highvoltage-links.csv')

# Fill NaN values
buses_df.fillna('', inplace=True)

# Create a graph
G = nx.Graph()

# Add buses (nodes) to the graph
nodes = [(row['v_id'], {"pos": (row['lon'], row['lat']), "name": row['name'], "operator": row['operator']}) for index, row in buses_df.iterrows()]
G.add_nodes_from(nodes)

# Add transmission lines (edges) to the graph
edges = [(row['v_id_1'], row['v_id_2'], {"id": row['l_id']}) for index, row in transmission_df.iterrows()]
G.add_edges_from(edges)

# Define a function that converts Degree Minute Second (DMS) format to Decimal Degrees.
def dms_to_decimal(dms_str):
    """
    Convert a string in DMS format (like '44 13 19.5') to a decimal number.
    
    Parameters:
        dms_str (str): The string containing the DMS representation.
    
    Returns:
        float: The decimal representation of the DMS value.
    """
    # Determine if the input is negative
    negative = False
    if "-" in dms_str:
        negative = True
        dms_str = dms_str.replace("-", "")
    
    # Extract all the numbers (degrees, minutes, seconds) from the input string.
    parts = list(map(float, re.findall(r"[\d.]+", dms_str)))

    # Convert DMS to Decimal based on the number of extracted parts.
    decimal_val = 0
    if len(parts) == 3:  # degrees, minutes, seconds
        decimal_val = parts[0] + parts[1]/60 + parts[2]/3600
    elif len(parts) == 2:  # degrees, minutes
        decimal_val = parts[0] + parts[1]/60
    else:  # just degrees
        decimal_val = parts[0]

    return -decimal_val if negative else decimal_val

@app.route('/')
def index():
    return open("index.html").read()

@app.route('/get_data', methods=['GET'])
def get_data():
    nodes = [{"id": n, "lon": d['pos'][0], "lat": d['pos'][1], "name": d.get('name', ''), "operator": d.get('operator', '')} for n, d in G.nodes(data=True)]
    edges = [{"from": u, "to": v, "id": d['id']} for u, v, d in G.edges(data=True)]
    return jsonify({"nodes": nodes, "edges": edges})

@app.route('/get_wildfires')
def data():
    wildfires = feed()
            
    for wildfire in wildfires:
        lat1 = wildfire['latitude']
        lon1 = wildfire['longitude']
        distances = [haversine(lon1, lat1, lon2, lat2) for lon2, lat2 in [G.nodes[node]['pos'] for node in G.nodes()]]
        wildfire['distances'] = distances
         
    return jsonify(wildfires)

@app.route('/get_wildfires/<int:k>')
def get_wildfires(k):
    
    wildfires = feed()
    
     # Prepare the data for NearestNeighbors
    node_positions = np.array([G.nodes[node]['pos'] for node in G.nodes()])
    wildfire_positions = np.array([(wildfire['longitude'], wildfire['latitude']) for wildfire in wildfires])

    # Fit the model
    neigh = NearestNeighbors(n_neighbors=k)
    neigh.fit(node_positions)

    # Find the k closest nodes for each wildfire
    distances, indices = neigh.kneighbors(wildfire_positions)

    k_closest_nodes = []
    for i, wildfire in enumerate(wildfires):
        k_closest = [{"id": nodes[j]['id'], "name": nodes[j].get('name', ''), "operator": nodes[j].get('operator', '')} for j in indices[i]]
        k_closest_nodes.append({
            'wildfire': wildfire,
            'nodes': k_closest
        })

     # Find shortest paths from each closest node to all other nodes using A* algorithm
        for closest_node in k_closest:
            node_id = closest_node['id']
            shortest_paths = {}
            for target_node in G.nodes:
                if target_node != node_id:
                    try:
                        path_length = nx.astar_path_length(G, node_id, target_node, weight='distance', heuristic=haversine)
                        shortest_paths[target_node] = path_length
                    except nx.NetworkXNoPath:
                        pass  # No path found between the nodes
            closest_node['shortest_paths'] = shortest_paths

    return jsonify(k_closest_nodes)
    

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r

def feed():
    # URL of the RSS feed containing wildfire incidents.
    url = "https://inciweb.nwcg.gov/incidents/rss.xml"
    # Fetch the XML content from the URL using the requests library.
    response = requests.get(url)
    # Parse the fetched XML using BeautifulSoup.
    soup = BeautifulSoup(response.content, 'xml')
    # Extract all the items (or incidents) from the XML.
    items = soup.find_all('item')
    # Initialize an empty list to store information about wildfires.
    wildfires = []
    
    # Loop through each item to extract relevant information.
    for item in items:
        # Get the title of the incident (name of the fire).
        title = item.title.text
        # Get the detailed description of the incident.
        description = item.description.text
        # Check if the incident type is a Wildfire.
        if "The type of incident is Wildfire" in description:
            # Extract latitude and longitude from the description using regex.
            latitude_match = re.search(r"Latitude:\s*([\d\s.]+)", description)
            longitude_match = re.search(r"Longitude:\s*([-]?[\d\s.]+)", description)
            # Convert the regex match to a string or assign None if not found.
            latitude_str = latitude_match.group(1).strip() if latitude_match else None
            longitude_str = longitude_match.group(1).strip() if longitude_match else None
            # If both latitude and longitude are found, convert them from DMS to Decimal format.
            if latitude_str and longitude_str:
                try:
                    latitude = dms_to_decimal(latitude_str)
                    longitude = dms_to_decimal(longitude_str)
                    # Append the wildfire details to the list.
                    wildfires.append({
                        'title': title,
                        'latitude': latitude,
                        'longitude': longitude
                    })
                except Exception as e:
                    # If there's an error in conversion, skip that entry.
                    pass
    return wildfires


if __name__ == '__main__':
    app.run(debug=True)
