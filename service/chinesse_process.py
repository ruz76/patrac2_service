"""
Based on Ralf Kistner postman https://github.com/rkistner/chinese-postman
"""

import os
from osgeo import ogr
from osgeo import osr
import fiona
from fiona.crs import from_epsg
import math
import random
import csv
import networkx as nx
import xml.dom.minidom as minidom
from datetime import datetime, timedelta
import json
from shapely.geometry import mapping, shape
from shapely.ops import linemerge, polygonize
from shapely.geometry import LineString, Point, MultiLineString
from operator import itemgetter, attrgetter
from config import *
from collections import defaultdict
import numpy as np

QGIS_RUN=False
if QGIS_RUN:
    from qgis.PyQt.QtCore import *
    from qgis.PyQt.QtGui import *

    from qgis.core import *
    from qgis.gui import *

_NX_BELOW_2_DOT_1 = False

def logInfo(message, ID):
    with open(os.path.join(logsPath, ID + ".log"), "a") as log:
        log.write(message)

def pairs(lst, circular=False):
    """
    Loop through all pairs of successive items in a list.

    >>> list(pairs([1, 2, 3, 4]))
    [(1, 2), (2, 3), (3, 4)]
    >>> list(pairs([1, 2, 3, 4], circular=True))
    [(1, 2), (2, 3), (3, 4), (4, 1)]
    """
    i = iter(lst)
    first = prev = item = next(i)
    for item in i:
        yield prev, item
        prev = item
    if circular:
        yield item, first

def specify_positions(graph):
    lat_min = min([data['latitude'] for n, data in graph.nodes(data=True)])
    lat_max = max([data['latitude'] for n, data in graph.nodes(data=True)])
    lon_min = min([data['longitude'] for n, data in graph.nodes(data=True)])
    lon_max = max([data['longitude'] for n, data in graph.nodes(data=True)])

    for node, data in graph.nodes(data=True):
        latitude = data['latitude']
        longitude = data['longitude']
        y = (latitude - lat_min) / (lat_max - lat_min) * 1000
        x = (longitude - lon_min) / (lon_max - lon_min) * 1000
        graph.nodes[node]['pos'] = "%d,%d" % (int(x), int(y))

def graph_components(graph):
    # The graph may contain multiple components, but we can only handle one connected component. If the graph contains
    # more than one connected component, we only use the largest one.
    components = list(graph.subgraph(c) for c in nx.connected_components(graph))
    components.sort(key=lambda c: c.size(), reverse=True)

    return components

def odd_graph(graph):
    """
    Given a graph G, construct a graph containing only the vertices with odd degree from G. The resulting graph is
    fully connected, with each weight being the shortest path between the nodes in G.

    Complexity: O(V'*(E + V log(V)) )
    """
    result = nx.Graph()
    odd_nodes = [n for n in graph.nodes() if graph.degree(n) % 2 == 1]
    for u in odd_nodes:
        # We calculate the shortest paths twice here, but the overall performance hit is low
        paths = nx.shortest_path(graph, source=u, weight='weight')
        lengths = nx.shortest_path_length(graph, source=u, weight='weight')
        for v in odd_nodes:
            if u <= v:
                # We only add each edge once
                continue
            # The edge weights are negative for the purpose of max_weight_matching (we want the minimum weight)
            result.add_edge(u, v, weight=-lengths[v], path=paths[v])

    return result


def as_gpx(graph, track_list, name=None):
    """
    Convert a list of tracks to GPX format
    Example:

    >>> g = nx.Graph()
    >>> g.add_node(1, latitude="31.1", longitude="-18.1")
    >>> g.add_node(2, latitude="31.2", longitude="-18.2")
    >>> g.add_node(3, latitude="31.3", longitude="-18.3")
    >>> print(as_gpx(g, [{'points': [1,2,3]}]))
    <?xml version="1.0" ?><gpx version="1.0"><trk><name>Track 1</name><number>1</number><trkseg><trkpt lat="31.1" lon="-18.1"><ele>1</ele></trkpt><trkpt lat="31.2" lon="-18.2"><ele>2</ele></trkpt><trkpt lat="31.3" lon="-18.3"><ele>3</ele></trkpt></trkseg></trk></gpx>
    """
    doc = minidom.Document()

    root = doc.createElement("gpx")
    root.setAttribute("version", "1.0")
    doc.appendChild(root)

    if name:
        gpx_name = doc.createElement("name")
        gpx_name.appendChild(doc.createTextNode(name))
        root.appendChild(gpx_name)

    for i, track in enumerate(track_list):
        nr = i+1
        track_name = track.get('name') or ("Track %d" % nr)
        trk = doc.createElement("trk")
        trk_name = doc.createElement("name")
        trk_name.appendChild(doc.createTextNode(track_name))
        trk.appendChild(trk_name)
        trk_number = doc.createElement("number")
        trk_number.appendChild(doc.createTextNode(str(nr)))
        trk.appendChild(trk_number)
        trkseg = doc.createElement("trkseg")

        for u in track['points']:
            longitude = graph.nodes[u].get('longitude')
            latitude = graph.nodes[u].get('latitude')
            trkpt = doc.createElement("trkpt")
            trkpt.setAttribute("lat", str(latitude))
            trkpt.setAttribute("lon", str(longitude))
            ele = doc.createElement("ele")
            ele.appendChild(doc.createTextNode(str(u)))
            trkpt.appendChild(ele)
            trkseg.appendChild(trkpt)

        trk.appendChild(trkseg)
        root.appendChild(trk)

    return doc.toxml()

def write_csv(graph, nodes, out):
    writer = csv.writer(out)
    writer.writerow(["Start Node", "End Node", "Segment Length", "Segment ID", "Start Longitude", "Start Latitude", "End Longitude", "End Latitude"])
    for u, v in pairs(nodes, False):
        length = graph[u][v]['weight']
        id = graph[u][v]['id']
        start_latitude = graph.nodes[u].get('latitude')
        start_longitude = graph.nodes[u].get('longitude')
        end_latitude = graph.nodes[v].get('latitude')
        end_longitude = graph.nodes[v].get('longitude')
        writer.writerow([u, v, length, id, start_longitude, start_latitude, end_longitude, end_latitude])

def edge_sum(graph):
    total = 0
    for u, v, data in graph.edges(data=True):
        total += data['weight']
    return total

def matching_cost(graph, matching):
    # Calculate the cost of the additional edges
    cost = 0
    for u, v in (matching.items() if _NX_BELOW_2_DOT_1 else matching):
        if _NX_BELOW_2_DOT_1 and (v <= u):
            continue
        data = graph[u][v]
        cost += abs(data['weight'])
    return cost


def find_matchings(graph, n=5):
    """
    Find the n best matchings for a graph. The best matching is guaranteed to be the best, but the others are only
    estimates.

    A matching is a subset of edges in which no node occurs more than once.

    The result may contain less than n matchings.

    See https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.matching.max_weight_matching.html
    """
    best_matching = nx.max_weight_matching(graph, True)
    matchings = [best_matching]

    for u, v in (best_matching.items() if _NX_BELOW_2_DOT_1 else best_matching):
        if _NX_BELOW_2_DOT_1 and (v <= u):
            continue
        # Remove the matching
        smaller_graph = nx.Graph(graph)
        smaller_graph.remove_edge(u, v)
        matching = nx.max_weight_matching(smaller_graph, True)
        if len(matching) > 0:
            # We may get an empty matching if there is only one edge (that we removed).
            matchings.append(matching)

    matching_costs = [(matching_cost(graph, matching), matching) for matching in matchings]
    matching_costs.sort(key=lambda k: k[0])

    # HACK: The above code end up giving duplicates of the same path, even though the matching is different. To prevent
    # this, we remove matchings with the same cost.
    final_matchings = []
    last_cost = None
    for cost, matching in matching_costs:
        if cost == last_cost:
            continue
        last_cost = cost
        final_matchings.append((cost, matching))

    return final_matchings


def build_eulerian_graph(graph, odd, matching):
    """
    Build an Eulerian graph from a matching. The result is a MultiGraph.
    """

    # Copy the original graph to a multigraph (so we can add more edges between the same nodes)
    eulerian_graph = nx.MultiGraph(graph)

    # For each matched pair of odd vertices, connect them with the shortest path between them
    for u, v in (matching.items() if _NX_BELOW_2_DOT_1 else matching):
        if _NX_BELOW_2_DOT_1 and (v <= u):
            # With max_weight_matching of NetworkX <2.1 each matching occurs twice in the matchings: (u => v) and (v => u). We only count those where v > u
            continue
        edge = odd[u][v]
        path = edge['path']  # The shortest path between the two nodes, calculated in odd_graph()

        # Add each segment in this path to the graph again
        for p, q in pairs(path):
            eulerian_graph.add_edge(p, q, weight=graph[p][q]['weight'])

    return eulerian_graph

def eulerian_circuit(graph, start_node=None):
    """
    Given an Eulerian graph, find one eulerian circuit. Returns the circuit as a list of nodes, with the first and
    last node being the same.
    """
    node = None
    if start_node in graph.nodes():
        node = start_node
    # print(graph.nodes()[start_node])
    # print("eulerian_circuit: " + str(node))
    circuit = list(nx.eulerian_circuit(graph, source=node))
    nodes = []
    for u, v in circuit:
        nodes.append(u)
    # Close the loop
    nodes.append(circuit[0][0])
    return nodes

def chinese_postman_paths(graph, n=5, start_node=None):
    """
    Given a graph, return a list of node id's forming the shortest chinese postman path.
    """

    # Find all the nodes with an odd degree, and create a graph containing only them
    odd = odd_graph(graph)

    # Find the best matching of pairs of odd nodes
    matchings = find_matchings(odd, n)

    paths = []
    for cost, matching in matchings[:n]:
        # Copy the original graph to a multigraph (so we can add more edges between the same nodes)
        eulerian_graph = build_eulerian_graph(graph, odd, matching)

        # Now that we have an eulerian graph, we can calculate the eulerian circuit
        nodes = eulerian_circuit(eulerian_graph, start_node)

        paths.append((eulerian_graph, nodes))
    return paths


def single_chinese_postman_path(graph):
    """
    Given a graph, return a list of node id's forming the shortest chinese postman path.

    If we assume V' (number of nodes with odd degree) is at least some constant fraction of V (total number of nodes),
    say 10%, the overall complexity is O(V^3).
    """

    # Build a fully-connected graph containing only the odd edges.  Complexity: O(V'*(E + V log(V)) )
    odd = odd_graph(graph)

    # Find the best matching of pairs of odd nodes. Complexity: O(V'^3)
    matching = nx.max_weight_matching(odd, True)

    # Complexity of the remainder is less approximately O(E)
    eulerian_graph = build_eulerian_graph(graph, odd, matching)
    nodes = eulerian_circuit(eulerian_graph)

    return eulerian_graph, nodes

def run_query(gpkg_path, query):
    # based on https://svn.osgeo.org/gdal/trunk/autotest/ogr/ogr_gpkg.py

    gpkg_ds = ogr.Open(gpkg_path, update=1)
    gpkg_ds.ExecuteSQL(query)
    gpkg_ds.ExecuteSQL('VACUUM')
    gpkg_ds = None

def run_queries(gpkg_path, queries):
    # based on https://svn.osgeo.org/gdal/trunk/autotest/ogr/ogr_gpkg.py

    gpkg_ds = ogr.Open(gpkg_path, update=1)
    for query in queries:
        gpkg_ds.ExecuteSQL(query)
    gpkg_ds.ExecuteSQL('VACUUM')
    gpkg_ds = None

def get_table_data(gpkg_path, table_name, fields):
    features_output = []
    with fiona.open(gpkg_path, layer=table_name) as layer:
        for feature in layer:
            feature_output = {}
            for field in fields:
                feature_output[field] = feature['properties'][field]
            features_output.append(feature_output)
    return features_output

def are_on_the_same_position(coord1, coord2, tolerance):
    deltax = coord1[0] - coord2[0]
    deltay = coord1[1] - coord2[1]
    distance = math.hypot(deltax, deltay)
    if distance < tolerance:
        return True
    else:
        return False

def get_points_on_path(gpkg_path, table_name):
    print('Before fiona open')
    # print(fiona.__version__)
    output_coords_sequence = []
    segment_grades = []
    pos = 0
    coords_0 = None
    tolerance = 0.00001  # ~1 metr
    try:
        with fiona.open(gpkg_path, layer=table_name) as layer:
            for feature in layer:
                geometry = shape(feature["geometry"])
                segment_grades.append(feature["properties"]["grade"])
                # print(feature['properties']['ord'])
                coords = geometry.coords
                coords_fixed = coords
                if pos == 0:
                    coords_0 = coords_fixed
                # print(feature['properties']['ord'])
                if pos == 1:
                    # TODO Do not check single points but start and end together and compare the distances
                    if are_on_the_same_position(coords_0[0], coords_fixed[0], tolerance):
                        # The first point on line1 is at the same position as first point of the line2
                        # So flip the line1
                        coords_0_fixed = coords_0[::-1]
                        coords_1_fixed = coords_fixed
                    if are_on_the_same_position(coords_0[len(coords_0) - 1], coords_fixed[0], tolerance):
                        # The last point on line1 is at the same position as first point of the line2
                        # Do not flip anything
                        coords_0_fixed = coords_0
                        coords_1_fixed = coords_fixed
                    if are_on_the_same_position(coords_0[0], coords_fixed[len(coords_fixed) - 1], tolerance):
                        # The first point on line1 is at the same position as last point of the line2
                        # Flip the line1
                        coords_0_fixed = coords_0[::-1]
                        # Flip the line2
                        coords_1_fixed = coords_fixed[::-1]
                    if are_on_the_same_position(coords_0[len(coords_0) - 1], coords_fixed[len(coords_fixed) - 1], tolerance):
                        # The last point on line1 is at the same position as last point of the line2
                        # Do not the line1
                        coords_0_fixed = coords_0
                        # Flip the line2
                        coords_1_fixed = coords_fixed[::-1]
                    for coord in coords_0_fixed:
                        # print(coord)
                        output_coords_sequence.append([coord[0], coord[1]])
                    for coord in coords_1_fixed:
                        # print(coord)
                        output_coords_sequence.append([coord[0], coord[1]])
                if pos > 1:
                    # if feature['properties']['source_path'] != feature['properties']['target_path']:
                    #     coords_fixed = coords[::-1]
                    if not are_on_the_same_position(output_coords_sequence[len(output_coords_sequence) - 1], coords_fixed[0], tolerance):
                        # The line N+1 does not have the first point on the last point of the line N
                        # Flip the line N+1
                        coords_fixed = coords[::-1]
                    for coord in coords_fixed:
                        # print(coord)
                        output_coords_sequence.append([coord[0], coord[1]])
                pos += 1
    except Exception as e:
        print('Unexpected error' + str(e))

    return output_coords_sequence, segment_grades


def prepare_data_for_graph_based_on_polygon(config, grades):

    run_query(config['gpkg_path'], 'delete from ways_for_sectors_export')

    sql = "insert into ways_for_sectors_export (source, target, length_m, gid, x1, y1, x2, y2) select distinct source, target, length_m, ways.gid gid, x1, y1, x2, y2 from ways, new_polygon_layer where st_intersects(ways.the_geom, st_buffer(new_polygon_layer.geom, -0.00005)) and ways.grade in (" + grades + ")"
    print(sql)
    run_query(config['gpkg_path'], sql)
    output_data = get_table_data(config['gpkg_path'], 'ways_for_sectors_export', ['source', 'target', 'length_m', 'gid', 'x1', 'y1', 'x2', 'y2'])

    return output_data

def prepare_data_for_graph(config, grades):

    run_query(config['gpkg_path'], 'delete from ways_for_sectors_export')

    sql = "insert into ways_for_sectors_export (source, target, length_m, gid, x1, y1, x2, y2) select distinct source, target, length_m, ways.gid gid, x1, y1, x2, y2 from ways where grade in (" + grades + ")"
    print(sql)

    run_query(config['gpkg_path'], sql)
    output_data = get_table_data(config['gpkg_path'], 'ways_for_sectors_export', ['source', 'target', 'length_m', 'gid', 'x1', 'y1', 'x2', 'y2'])

    return output_data

def build_graph(features, used_edges):
    # print(nx.__version__)
    graph = nx.Graph()
    for feature in features:
        # print(used_edges)
        if feature['gid'] not in used_edges:
            # print(feature['gid'])
            graph.add_edge(str(feature['source']), str(feature['target']), weight=feature['length_m'], id=str(feature['gid']), label=str(feature['gid']))
            # We keep the GPS coordinates as strings
            graph.nodes[str(feature['source'])]['longitude'] = feature['x1']
            graph.nodes[str(feature['source'])]['latitude'] = feature['y1']
            graph.nodes[str(feature['target'])]['longitude'] = feature['x2']
            graph.nodes[str(feature['target'])]['latitude'] = feature['y2']

    return graph

def solve_graph(graph, config, name):
    components = graph_components(graph)
    # for component in components:
    #     print(component)
    #     for item in component:
    #         print(item)

    if len(components) > 1:
        print("Warning: the selected area contains multiple disconnected " +
              "components.")

    if len(components) == 0:
        print("Error: Could not find any components. Try selecting different features.")
        return

    outputs = []
    component_id = 0
    for component in components:

        eulerian_graph, nodes = single_chinese_postman_path(component)

        in_length = edge_sum(component)/1000.0
        path_length = edge_sum(eulerian_graph)/1000.0
        duplicate_length = path_length - in_length

        info = "Component: " + str(component_id) + " of graph " + str(name) + "\n"
        info += "Total length of roads: %.3f km\n" % in_length
        info += "Total length of path: %.3f km\n" % path_length
        info += "Length of sections visited twice: %.3f km\n" % duplicate_length

        print(info)
        print(nodes)

        create_layer(config, eulerian_graph, nodes, name + '_' + str(component_id))
        with open(os.path.join(config['output_dir'], name + '_' + str(component_id) + '_nodes_sequence.json'), 'w') as f:
            json.dump(nodes, f)
        points, segments_grades = get_points_on_path(config['gpkg_path'], 'chpostman_path_export')

        print("SEGMENTS GRADES")
        print(segments_grades)

        suggested_unit_types = []
        print(path_length)
        for item in config["covers"]:
            min = config["covers"][item] * config["covers_fuzzy"][item][0]
            max = config["covers"][item] * config["covers_fuzzy"][item][1]
            # We test if the path has only grades for current search unit type
            grades_diff = set(segments_grades) - set(config["allowed_grades"][item])
            if min <= (path_length * 1000) <= max and not grades_diff:
                suggested_unit_types.append(item)

        # We add the path only in the case that at least one search unit type is suggested
        # if len(suggested_unit_types) > 0:

        output = {
            "id": name + '_' + str(component_id),
            "total_roads": round(in_length * 1000),
            "total_path": round(path_length * 1000),
            "duplicate_length": round(duplicate_length * 1000),
            "suggested_unit_types": suggested_unit_types,
            "coordinates": points
        }

        outputs.append(output)

        component_id += 1

    return outputs


def create_layer_for_polygon(config, graph, nodes, name, export=True):
    run_query(config['gpkg_path'], 'delete from chpostman_path')
    pos = 0
    ts = datetime.now()
    queries = []
    for u, v in graph.edges():
        pos += 1
        ts = ts + timedelta(seconds=1)
        queries.append("insert into chpostman_path (gid, ord, ts, source, target) values (" + graph[u][v]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "', " + str(u) + ", " + str(v) + ")")

    run_queries(config['gpkg_path'], queries)
    run_query(config['gpkg_path'], 'delete from chpostman_path_export')
    run_query(config['gpkg_path'], "insert into chpostman_path_export (gid, ord, ts, source_path, target_path, source_way, target_way, the_geom) select ch.gid, ch.ord, ch.ts, ch.source, ch.target, w.source, w.target, w.the_geom from chpostman_path ch join ways w on (ch.gid = w.gid) order by ch.ts")


def create_layer(config, graph, nodes, name):
    run_query(config['gpkg_path'], 'delete from chpostman_path')
    pos = 0
    ts = datetime.now()
    queries = []

    for u, v in pairs(nodes, False):
        pos += 1
        ts = ts + timedelta(seconds=1)
        query = ""
        if 0 in graph[u][v] and 'id' in graph[u][v][0]:
            query = "insert into chpostman_path (gid, ord, ts, source, target) values (" + graph[u][v][0]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "', " + str(u) + ", " + str(v) + ")"
        else:
            if 'id' in graph[u][v]:
                query = "insert into chpostman_path (gid, ord, ts, source, target) values (" + graph[u][v]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "', " + str(u) + ", " + str(v) + ")"
        if query != "":
            # print(query)
            queries.append(query)

    run_queries(config['gpkg_path'], queries)
    run_query(config['gpkg_path'], 'delete from chpostman_path_export')
    # run_query(config['gpkg_path'], "SELECT 'ALTER TABLE chpostman_path_export ADD COLUMN grade TEXT;' WHERE NOT EXISTS ( SELECT 1 FROM pragma_table_info('chpostman_path_export') WHERE name = 'grade')")
    run_query(config['gpkg_path'], "insert into chpostman_path_export (gid, ord, ts, source_path, target_path, source_way, target_way, the_geom, grade) select ch.gid, ch.ord, ch.ts, ch.source, ch.target, w.source, w.target, w.the_geom, w.grade from chpostman_path ch join ways w on (ch.gid = w.gid) order by ch.ts")

    print('Before export')

    # Crashes when running inside QGIS, so we will do not use fiona for export in QGIS but QGIS API
    # save_layer_as_geojson(config['gpkg_path'], 'chpostman_path_export', ['gid', 'ord', 'ts'], os.path.join(config['output_dir'], name + '.geojson'))
    # save_layer_as_shp(config['gpkg_path'], 'chpostman_path_export', name, os.path.join(config['output_dir'], name + '.shp'))

    print('After export')

def get_shortest_path(start_node, end_node, graph):
    # print(graph)
    if not start_node in graph or end_node not in graph:
        if not start_node in graph:
            print("Node " + str(start_node) + " is not in the graph")
        if end_node not in graph:
            print("Node " + str(end_node) + " is not in the graph")
        return

    # Výpočet nejkratší trasy mezi těmito uzly
    try:
        shortest_path = nx.shortest_path(graph, source=start_node, target=end_node, weight='weight')
        shortest_path_length = nx.shortest_path_length(graph, source=start_node, target=end_node, weight='weight')
    except:
        print('The path between start and end nodes has not been found')
        return None

    # Výpis výsledků
    # print(f'Nodes: {start_node} a {end_node}')
    # print(f'Shortest path between {start_node} and {end_node} is: {shortest_path}')
    print(f'Length of the shortest path is: {shortest_path_length}')

    return [shortest_path, shortest_path_length]

def solve_one_part(start_node, end_node, config, graph_data_input, id, grades):
    if os.path.exists(os.path.join(config['output_dir'], end_node + '_graph.json')):
        # Deserializace z JSON
        with open(os.path.join(config['output_dir'], end_node + '_graph.json'), 'r') as f:
            data = json.load(f)
        G_union = nx.node_link_graph(data)
        graph_solution = solve_graph(G_union, config, 'test_' + str(end_node))
        # print(graph_solution)

    else:

        graph = build_graph(graph_data_input, [])
        sp_outputs = get_shortest_path(start_node, end_node, graph)
        if sp_outputs is None:
            return

        shortest_path = sp_outputs[0]

        # Vytvoření nového grafu obsahujícího hrany z obou nejkratších cest
        H = nx.Graph()

        # Přidání hran z první nejkratší cesty
        for i in range(len(shortest_path) - 1):
            u, v = shortest_path[i], shortest_path[i + 1]
            H.add_edge(u, v, weight=graph.get_edge_data(u, v)['weight'], id=graph.get_edge_data(u, v)['id'])

        # create_layer_for_polygon(config, H, H.nodes, 'line1_' + str(start_node))

        # Odstranění hran, které tvoří nalezenou trasu, z grafu. Ponechání první hrany.
        for i in range(len(shortest_path) - 2):
            graph.remove_edge(shortest_path[i + 1], shortest_path[i + 2])
        # graph.remove_edge(shortest_path[len(shortest_path) - 2], shortest_path[len(shortest_path) - 1])

        # Výpočet nejkratší trasy mezi těmito uzly
        start_node_orig = start_node
        start_node = end_node
        end_node = start_node_orig

        # print(end_node)

        sp_outputs = get_shortest_path(start_node, end_node, graph)
        if sp_outputs is None:
            return

        shortest_path = sp_outputs[0]

        # print(shortest_path)
        # Přidání hran z druhé nejkratší cesty
        for i in range(len(shortest_path) - 1):
            u, v = shortest_path[i], shortest_path[i + 1]
            if not H.has_edge(u, v):
                H.add_edge(u, v, weight=graph.get_edge_data(u, v)['weight'], id=graph.get_edge_data(u, v)['id'])
                # print(str(u) + " " + str(v) + " " + str(graph.get_edge_data(u, v)['weight']) + " " + str(graph.get_edge_data(u, v)['id']))

        create_layer_for_polygon(config, H, H.nodes, 'test_ring_only_' + str(start_node), False)
        # print(H.nodes)

        get_ring_polygon(config)
        graph_data_input_missing_edges = prepare_data_for_graph_based_on_polygon(config, grades)
        graph_missing_edges = build_graph(graph_data_input_missing_edges, [])
        # print(graph_missing_edges)

        G_union = nx.compose(H, graph_missing_edges)
        # print(G_union)

        number_of_edges = G_union.number_of_edges()
        print("Number of edges in the graph:", number_of_edges)

        if number_of_edges > 300:
            logInfo('ERROR: Can not solve this graph to node: ' + str(end_node) + '. It has more than 300 edges.\n', id)
            return

        graph_solution = solve_graph(G_union, config, 'test_' + str(start_node))
        # print(graph_solution)

    return [graph_solution, G_union]

def robust_snap(lines, tolerance):
    """
    Snapne linie k nejbližším bodům pouze jednorázově, bez opakovaného přesunu bodů.
    """
    # Všechny body v jedné sadě
    all_coords = np.array([coord for line in lines for coord in line.coords])

    # Jedinečné body
    unique_coords = np.unique(all_coords, axis=0)

    # Výsledné snapnuté linie
    snapped_lines = []
    for line in lines:
        snapped_coords = []
        for coord in line.coords:
            # Najdeme nejbližší bod v unikátních souřadnicích
            dists = np.linalg.norm(unique_coords - coord, axis=1)
            min_idx = np.argmin(dists)
            if dists[min_idx] <= tolerance:
                snapped_coords.append(tuple(unique_coords[min_idx]))
            else:
                snapped_coords.append(coord)
        snapped_lines.append(LineString(snapped_coords))
    return snapped_lines

def connect_unclosed_lines(lines, tolerance):
    """
    Explicitně vytvoří linie mezi nespojenými body.
    """
    endpoints = defaultdict(int)
    for line in lines:
        endpoints[line.coords[0]] += 1
        endpoints[line.coords[-1]] += 1

    unclosed = [Point(coord) for coord, count in endpoints.items() if count % 2 != 0]

    additional_lines = []
    for i, point1 in enumerate(unclosed):
        for j, point2 in enumerate(unclosed):
            if i < j and point1.distance(point2) <= tolerance:
                additional_lines.append(LineString([point1, point2]))

    return lines + additional_lines

def get_ring_polygon(config):
    with fiona.open(config['gpkg_path'], layer='chpostman_path_export') as layer:
        lines = []
        for feature in layer:
            # print(feature)
            line = shape(feature['geometry'])
            # print(line)
            lines.append(line)

        # Krok 1: Snapping
        tolerance = 0.00001  # ~1 metr
        snapped_lines = robust_snap(lines, tolerance)

        # Krok 2: Spojení nespojených bodů
        fixed_lines = connect_unclosed_lines(snapped_lines, tolerance)

        # Krok 3: Polygonizace
        merged_lines = linemerge(MultiLineString(fixed_lines))
        polygons = list(polygonize(merged_lines))

        print('POLYGONS CONUT: ' + str(len(polygons)))
        # for polygon in polygons:
        #     print('POLYGON: ')
        #     print(polygon)

    # Soubor GeoPackage, do kterého chceme uložit polygony
    gpkg_path = config['gpkg_path']

    # Soubor GeoPackage, do kterého chceme uložit polygony
    layer_name = 'new_polygon_layer'

    # Specifikace CRS (zde EPSG:4326, můžete upravit podle potřeby)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Otevření souboru GeoPackage
    gpkg_ds = ogr.Open(gpkg_path, update=1)
    if not gpkg_ds:
        raise ValueError(f"Could not open {gpkg_path}")

    # Kontrola a odstranění existující vrstvy
    layer = gpkg_ds.GetLayerByName(layer_name)
    if layer:
        gpkg_ds.DeleteLayer(layer_name)
        print(f"Layer {layer_name} was deleted.")

    # Vytvoření nové vrstvy
    layer = gpkg_ds.CreateLayer(layer_name, srs, ogr.wkbPolygon)
    if not layer:
        raise ValueError(f"Could not create layer {layer_name}")

    # Přidání pole 'id'
    field_defn = ogr.FieldDefn('id', ogr.OFTInteger)
    if layer.CreateField(field_defn) != 0:
        raise ValueError("Creating 'id' field failed")

    # Přidání polygonů do nové vrstvy
    for i, polygon in enumerate(polygons):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField('id', i)
        geom = ogr.CreateGeometryFromWkt(polygon.wkt)
        feature.SetGeometry(geom)
        if layer.CreateFeature(feature) != 0:
            raise ValueError("Failed to create feature in layer")
        feature = None  # Zajistí, že funkce bude uvolněna

    # Uvolnění datasetu
    gpkg_ds.ExecuteSQL('VACUUM')
    gpkg_ds = None

    print(f'Polygons has been saved into {layer_name} in database {gpkg_path}.')

def find_points(config, nodes_with_degree_one):
    source_point = config['start_point'] #[15.0339242, 49.340751]
    edge_points = []
    diff_x = 0.025
    diff_y = 0.018

    if 'end_point' in config and config['end_point'] is not None:
        end_point = config['end_point']
        edge_points.append(Point(end_point[0], end_point[1]))

    else:

        # top
        edge_points.append(Point(source_point[0] - diff_x, source_point[1] + diff_y))
        edge_points.append(Point(source_point[0], source_point[1] + diff_y))
        edge_points.append(Point(source_point[0] + diff_x, source_point[1] + diff_y))
        # middle
        edge_points.append(Point(source_point[0] - diff_x, source_point[1]))
        edge_points.append(Point(source_point[0] + diff_x, source_point[1]))
        # bottom
        edge_points.append(Point(source_point[0] - diff_x, source_point[1] - diff_y))
        edge_points.append(Point(source_point[0], source_point[1] - diff_y))
        edge_points.append(Point(source_point[0] + diff_x, source_point[1] - diff_y))

    closets_points = {}
    for i in range(8):
        closets_points[i] = []

    # print(edge_points)
    start_point = [0, 1000000]
    start_point_point = Point(source_point[0], source_point[1])

    with fiona.open(config['gpkg_path'], layer='ways_nodes') as layer:
        for feature in layer:
            # node = shape(feature['geometry'])
            # print(node)
            point_to_check = Point(feature['geometry']['coordinates'])
            pos = 0
            for point in edge_points:
                # point1 = Point(x1, y1)
                cur_distance = point.distance(point_to_check)
                if cur_distance < diff_x and feature['properties']['source'] not in nodes_with_degree_one:
                    if {"id": feature['properties']['source'], "distance": cur_distance, "x": point_to_check.x, "y": point_to_check.y} not in closets_points[pos]:
                        closets_points[pos].append({"id": feature['properties']['source'], "distance": cur_distance, "x": point_to_check.x, "y": point_to_check.y})
                pos += 1
            cur_distance = start_point_point.distance(point_to_check)
            if cur_distance < start_point[1]:
                start_point = [feature['properties']['source'], cur_distance, start_point_point.x, start_point_point.y]

    # print(start_point)
    for key in closets_points:
        closets_points[key] = sorted(closets_points[key], key=itemgetter('distance'))

    # Remove the starting point from the list
    for key in closets_points:
        pos_to_remove = -1
        pos = 0
        for point in closets_points[key]:
            if point['id'] == start_point[0]:
                pos_to_remove = pos
            pos += 1
        if pos_to_remove > -1:
            print('Removing starting point from the list of points')
            closets_points[key].pop(pos_to_remove)

    # print(closets_points)
    # cp = ''
    # for key in closets_points:
    #     cp += ', ' + str(closets_points[key][0])
    # print(cp)

    return [start_point, closets_points]

def is_subgraph(G1, G2):
    """
    Checks if G1 is a subgraph of G2.
    This means all nodes and edges of G1 are contained in G2.
    """
    # Check if all nodes of G1 are in G2
    for node in G1.nodes():
        if node not in G2.nodes():
            return False

    # Check if all edges of G1 are in G2
    for edge in G1.edges():
        if edge not in G2.edges() and (edge[1], edge[0]) not in G2.edges():
            return False

    return True

def are_graphs_identical(G1, G2):
    missing_any = 0
    # Check if all nodes of G1 are in G2
    for node in G1.nodes():
        if node not in G2.nodes():
            missing_any += 1

    for node in G2.nodes():
        if node not in G1.nodes():
            missing_any += 1

    # Check if all edges of G1 are in G2
    for edge in G1.edges():
        if edge not in G2.edges() and (edge[1], edge[0]) not in G2.edges():
            missing_any += 1

    # Check if all edges of G2 are in G1
    for edge in G2.edges():
        if edge not in G1.edges() and (edge[1], edge[0]) not in G1.edges():
            missing_any += 1

    if missing_any > 0:
        return False
    else:
        return True

def graph_exists(solved_graphs, solved_graph):
    for i in range(len(solved_graphs)):
        if are_graphs_identical(solved_graphs[i], solved_graph):
            return True
    return False


def is_shortest_path_within_distance_tolerance(config, graph, start_node, end_points):
    min_length = 10000000
    for i in range(len(end_points)):
        pos_end_points = 0
        for end_node in end_points[i]:
            sp_outputs = get_shortest_path(str(start_node[0]), str(end_node['id']), graph)
            if sp_outputs is not None:
                if sp_outputs[1] < min_length:
                    min_length = sp_outputs[1]
            pos_end_points += 1
            if pos_end_points > 9:
                break
    if config["shortest_path"][config["unit_type"]] > min_length:
        return [True, min_length]
    else:
        return [False, min_length]

def move_point(start, end, percentage):
    """
    Moves the end point of a vector closer to the start point by a specified percentage
    of the total distance between the two points.

    :param start: Tuple (x1, y1) - starting point of the vector
    :param end: Tuple (x2, y2) - ending point of the vector
    :param percentage: Float - percentage to move closer (0-100)
    :return: Tuple (x_new, y_new) - new moved point
    """
    # Ensure the percentage is within the range [0, 100]
    percentage = max(0, min(100, percentage)) / 100

    # Calculate the new point
    x_new = start[0] + (end[0] - start[0]) * percentage
    y_new = start[1] + (end[1] - start[1]) * percentage
    return [x_new, y_new]


def correct_end_point(config, distance):
    percentage = config["shortest_path"][config["unit_type"]] / (distance / 100)
    print(percentage)
    return move_point(config["start_point"], config["end_point"], percentage)


def find_path_based_on_shortest_path(id, search_id, config):

    # "start_point": [15.1321449, 49.4054798],
    # "start_point": [15.017469, 49.433281]
    # "source" IN (3609, 6932, 726, 6305, 712, 5028, 5841, 5788)

    # grades = '0, 1, 2, 3, 4, 5, 6'
    grades = ', '.join(str(n) for n in config["allowed_grades"][config["unit_type"]])
    print("GRADES: ")
    print(grades)
    graph_data_input = prepare_data_for_graph(config, grades)
    # print(graph_data_input)
    logInfo("GRAPH DATA PREPARED\n5\n", id)
    graph = build_graph(graph_data_input, [])
    logInfo("GRAPH BUILT\n10\n", id)
    nodes_with_degree_one = [node for node, degree in dict(graph.degree()).items() if degree == 1]
    # print("Uzly, které mají spojení pouze na jeden další uzel:", nodes_with_degree_one)
    logInfo("ISOLATED NODES FOUND\n11\n", id)
    points_to_use = find_points(config, nodes_with_degree_one)
    start_point = points_to_use[0]
    end_points = points_to_use[1]

    # Check if the shortest path is within tolerated distance according to the specified unit
    # graph = build_graph(graph_data_input, [])
    number_of_corrections = 0
    while number_of_corrections < 10:
        sp_results = is_shortest_path_within_distance_tolerance(config, graph, start_point, end_points)
        if sp_results[0]:
            print("The specified point is within unit tolerance. Distance is: " + str(sp_results[1]) + ". Continuing without correction.")
            break
        else:
            print("The specified point is not within unit tolerance. The distance is: " + str(sp_results[1]) + ". Moving point closer to he source point.")
            corrected_coordinates = correct_end_point(config, sp_results[1])
            config["end_point"] = corrected_coordinates
            points_to_use = find_points(config, nodes_with_degree_one)
            start_point = points_to_use[0]
            end_points = points_to_use[1]

        number_of_corrections += 1

    solutions = []
    solved_graphs = []
    logInfo("POINTS ON GRAPH FOUND\n15\n", id)
    for i in range(len(end_points)):
        pos_end_points = 0
        # We take only first 10 points
        step = round(70 / 10)
        for end_point in end_points[i]:
            solution_results = solve_one_part(str(start_point[0]), str(end_point['id']), config, graph_data_input, id, grades)
            if solution_results is not None:
                percent = 15 + (pos_end_points + 1) * step
                logInfo("SOLVED PATH " + str(pos_end_points) + " FROM " + str(len(end_points[i])) + " POINTS\n" + str(percent) + "\n", id)
                solution = {
                    "start_point_network": {
                        "id": start_point[0],
                        "coordinates": [start_point[2], start_point[3]]
                    },
                    "end_point_network": {
                        "id": end_point['id'],
                        "coordinates": [end_point['x'], end_point['y']]
                    },
                    "rings": solution_results[0]
                }
                if not graph_exists(solved_graphs, solution_results[1]):
                    solutions.append(solution)
                    solved_graphs.append(solution_results[1])
                    # Serializace do JSON
                    data = nx.node_link_data(solution_results[1])  # Převede graf do formátu pro serializaci
                    with open(os.path.join(config['output_dir'], str(end_point['id']) + '_graph.json'), 'w') as f:
                        json.dump(data, f)
                    with open(os.path.join(config['output_dir'], str(end_point['id']) + '_solution.json'), 'w') as f:
                        json.dump(solution, f)
                # break
            pos_end_points += 1
            if pos_end_points > 9:
                break

    logInfo("ALL ALTERNATIVE PATHS HAS BEEN SOLVED\n90\n", id)
    # for solution in solutions:
    #     print(solution)

    try:
        print(len(solved_graphs))
        print(len(solutions))
        for i in range(len(solved_graphs)):
            for j in range(len(solved_graphs)):
                if i != j:
                    if are_graphs_identical(solved_graphs[i], solved_graphs[j]):
                        print("Graph " + solutions[i]['rings'][0]['id'] + " is same as graph " + solutions[j]['rings'][0]['id'])
                    else:
                        if is_subgraph(solved_graphs[i], solved_graphs[j]):
                            print("Graph " + solutions[i]['rings'][0]['id'] + " is sub-graph of graph " + solutions[j]['rings'][0]['id'])

    except:
        print("Some problems with printing solutions")

    logInfo("DONE\n100\n", id)

# print(move_point([0,0],[2,2],75))
