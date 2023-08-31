import math
import re
import requests
import numpy as np
import pandas as pd
import networkx as nx
from flask import Flask, jsonify
from bs4 import BeautifulSoup
from flask_cors import CORS
from sklearn.neighbors import NearestNeighbors

app = Flask(__name__)
CORS(app)

# Constants
DATA_FOLDER = 'data'
VERTICES_FILE = f'{DATA_FOLDER}/gridkit_north_america-highvoltage-vertices.csv'
LINKS_FILE = f'{DATA_FOLDER}/gridkit_north_america-highvoltage-links.csv'
WILDFIRE_FEED_URL = "https://inciweb.nwcg.gov/incidents/rss.xml"
EARTH_RADIUS = 6371  # Radius of earth in kilometers

# Data
buses_df = pd.read_csv(VERTICES_FILE)
transmission_df = pd.read_csv(LINKS_FILE)

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


# Helper Functions
def dms_to_decimal(dms_str):
    negative = False
    if "-" in dms_str:
        negative = True
        dms_str = dms_str.replace("-", "")
    
    parts = list(map(float, re.findall(r"[\d.]+", dms_str)))

    decimal_val = 0
    if len(parts) == 3:
        decimal_val = parts[0] + parts[1]/60 + parts[2]/3600
    elif len(parts) == 2:
        decimal_val = parts[0] + parts[1]/60
    else:
        decimal_val = parts[0]

    return -decimal_val if negative else decimal_val

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return c * EARTH_RADIUS

def fetch_wildfires():
    response = requests.get(WILDFIRE_FEED_URL)
    soup = BeautifulSoup(response.content, 'xml')
    items = soup.find_all('item')
    wildfires = []
    
    for item in items:
        title = item.title.text
        description = item.description.text
        if "The type of incident is Wildfire" in description:
            latitude_match = re.search(r"Latitude:\s*([\d\s.]+)", description)
            longitude_match = re.search(r"Longitude:\s*([-]?[\d\s.]+)", description)
            latitude_str = latitude_match.group(1).strip() if latitude_match else None
            longitude_str = longitude_match.group(1).strip() if longitude_match else None
            if latitude_str and longitude_str:
                try:
                    latitude = dms_to_decimal(latitude_str)
                    longitude = dms_to_decimal(longitude_str)
                    wildfires.append({
                        'title': title,
                        'latitude': latitude,
                        'longitude': longitude
                    })
                except Exception as e:
                    pass
    return wildfires

def get_k_nearest_neighbors(k, wildfire_positions, node_positions):
    neigh = NearestNeighbors(n_neighbors=k)
    neigh.fit(node_positions)
    distances, indices = neigh.kneighbors(wildfire_positions)
    return distances, indices

def get_shortest_paths(indices, wildfire_positions, nodes, k):
    k_closest_nodes = []
    for i, wildfire in enumerate(wildfire_positions):
        k_closest = [{"id": nodes[j]['id'], "name": nodes[j].get('name', ''), "operator": nodes[j].get('operator', '')} for j in indices[i]]
        k_closest_nodes.append({
            'wildfire': wildfire,
            'nodes': k_closest
        })

        for closest_node in k_closest:
            node_id = closest_node['id']
            shortest_paths = {}
            for target_node in G.nodes:
                if target_node != node_id:
                    try:
                        path_length = nx.astar_path_length(G, node_id, target_node, weight='distance', heuristic=haversine)
                        shortest_paths[target_node] = path_length
                    except nx.NetworkXNoPath:
                        pass
            closest_node['shortest_paths'] = shortest_paths

    return k_closest_nodes


# Routes
@app.route('/')
def index():
    return open("index.html").read()

@app.route('/get_data', methods=['GET'])
def get_data():
    nodes = [{"id": n, "lon": d['pos'][0], "lat": d['pos'][1], "name": d.get('name', ''), "operator": d.get('operator', '')} for n, d in G.nodes(data=True)]
    edges = [{"from": u, "to": v, "id": d['id']} for u, v, d in G.edges(data=True)]
    return jsonify({"nodes": nodes, "edges": edges})

@app.route('/get_wildfires', methods=['GET'])
def get_wildfires():
    wildfires = fetch_wildfires()
            
    for wildfire in wildfires:
        lat1 = wildfire['latitude']
        lon1 = wildfire['longitude']
        distances = [haversine(lon1, lat1, lon2, lat2) for lon2, lat2 in [G.nodes[node]['pos'] for node in G.nodes()]]
        wildfire['distances'] = distances
         
    return jsonify(wildfires)

@app.route('/get_wildfires/<int:k>', methods=['GET'])
def get_k_closest_nodes(k):
    wildfires = fetch_wildfires()

    node_positions = np.array([G.nodes[node]['pos'] for node in G.nodes])
    wildfire_positions = np.array([(wildfire['longitude'], wildfire['latitude']) for wildfire in wildfires])

    distances, indices = get_k_nearest_neighbors(k, wildfire_positions, node_positions)

    k_closest_nodes = get_shortest_paths(indices, wildfire_positions, nodes, k)

    return jsonify(k_closest_nodes)

if __name__ == '__main__':
    app.run(debug=True)
