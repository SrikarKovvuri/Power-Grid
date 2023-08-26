from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import networkx as nx

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

@app.route('/')
def index():
    return open("index.html").read()

@app.route('/get_data', methods=['GET'])
def get_data():
    nodes = [{"id": n, "lon": d['pos'][0], "lat": d['pos'][1], "name": d.get('name', ''), "operator": d.get('operator', '')} for n, d in G.nodes(data=True)]
    edges = [{"from": u, "to": v, "id": d['id']} for u, v, d in G.edges(data=True)]
    return jsonify({"nodes": nodes, "edges": edges})

if __name__ == '__main__':
    app.run(debug=True)
