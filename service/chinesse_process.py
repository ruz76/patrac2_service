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
    # TODO maybe check the distance
    if coord1[0] == coord2[0] and coord1[1] == coord2[1]:
        return True
    else:
        return False

def get_points_on_path(gpkg_path, table_name):
    print('Before fiona open')
    # print(fiona.__version__)
    output_coords_sequence = []
    pos = 0
    coords_0 = None
    with fiona.open(gpkg_path, layer=table_name) as layer:
        for feature in layer:
            geometry = shape(feature["geometry"])
            coords = geometry.coords
            coords_fixed = coords
            if pos == 0:
                coords_0 = coords_fixed
            # print(feature['properties']['ord'])
            if pos == 1:
                if are_on_the_same_position(coords_0[0], coords_fixed[0], 0):
                    # The first point on line1 is at the same position as first point of the line2
                    # So flip the line1
                    coords_0_fixed = coords_0[::-1]
                    coords_1_fixed = coords_fixed
                if are_on_the_same_position(coords_0[len(coords_0) - 1], coords_fixed[0], 0):
                    # The last point on line1 is at the same position as first point of the line2
                    # Do not flip anything
                    coords_0_fixed = coords_0
                    coords_1_fixed = coords_fixed
                if are_on_the_same_position(coords_0[0], coords_fixed[len(coords_fixed) - 1], 0):
                    # The first point on line1 is at the same position as last point of the line2
                    # Flip the line1
                    coords_0_fixed = coords_0[::-1]
                    # Flip the line2
                    coords_1_fixed = coords_fixed[::-1]
                if are_on_the_same_position(coords_0[len(coords_0) - 1], coords_fixed[len(coords_fixed) - 1], 0):
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
                if not are_on_the_same_position(output_coords_sequence[len(output_coords_sequence) - 1], coords_fixed[0], 0):
                    # The line N+1 does not have the first point on the last point of the line N
                    # Flip the line N+1
                    coords_fixed = coords[::-1]
                for coord in coords_fixed:
                    # print(coord)
                    output_coords_sequence.append([coord[0], coord[1]])
            pos += 1
    return output_coords_sequence

def save_layer_as_geojson(gpkg_path, table_name, fields, output_path):
    features_output = []
    print('Before fiona open')
    # print(fiona.__version__)
    with fiona.open(gpkg_path, layer=table_name) as layer:
        for feature in layer:
            # print(feature)
            # print(feature["geometry"])
            # print(shape(feature["geometry"]))
            # try:
            #     print(mapping(shape(feature["geometry"])))
            # except Exception as e:
            #     print(e)
            # feature_output = {
            #     "type": "Feature",
            #     "properties": {},
            #     "geometry": mapping(shape(feature["geometry"]))
            # }
            feature_output = {
                "type": "Feature",
                "properties": {},
                "geometry": feature["geometry"]
            }
            # print('Before fields')
            for field in fields:
                feature_output['properties'][field] = feature['properties'][field]
            # print('After fields')
            features_output.append(feature_output)
    data = {
        "type": "FeatureCollection",
        "features": features_output
    }
    print('Before write')
    with open(output_path, 'w') as out:
        json.dump(data, out)

def save_layer_as_shp(gpkg_path, table_name, label, output_path):
    vector = QgsVectorLayer(gpkg_path + '|layername=' + table_name, label, "ogr")
    crs = QgsCoordinateReferenceSystem(4326)
    print('Saving into: ' + output_path)
    QgsVectorFileWriter.writeAsVectorFormat(vector, output_path, "utf-8", crs, "ESRI Shapefile")

def array_to_in_param(arr, quotes=False):
    output = ''
    for item in arr:
        if quotes:
            output += "'" + str(item) + "', "
        else:
            output += str(item) + ', '
    return output[:-2]

def prepare_data(config):
    output_data = {}
    sectors = array_to_in_param(config['sectors'])

    run_query(config['gpkg_path'], 'DELETE FROM sectors')
    run_query(config['gpkg_path'], 'INSERT INTO sectors SELECT * FROM sectors_all WHERE id IN (' + sectors + ')')

    run_query(config['gpkg_path'], 'delete from sectors_by_path_with_neighbors_agg_export')
    run_query(config['gpkg_path'], "insert into sectors_by_path_with_neighbors_agg_export (id, type_5_length_m) select id, type_5_length_m from sectors_by_path_with_neighbors_agg WHERE id IN (" + sectors + ") order by type_5_length_m desc")
    output_data['sectors_by_path_with_neighbors_agg'] = get_table_data(config['gpkg_path'], 'sectors_by_path_with_neighbors_agg_export', ['id', 'type_5_length_m'])

    run_query(config['gpkg_path'], 'delete from sum_length_export')
    run_query(config['gpkg_path'], "insert into sum_length_export (sum_length_m) select round(sum(length_m) / 1000) sum_length_m from sectors_by_path_type WHERE id IN (" + sectors + ")")
    output_data['sum_length'] = get_table_data(config['gpkg_path'], 'sum_length_export', ['sum_length_m'])

    run_query(config['gpkg_path'], 'delete from sectors_with_paths_lengths_export')
    run_query(config['gpkg_path'], "insert into sectors_with_paths_lengths_export (id, length_m, x, y) select sp.id, length_m, ST_X(ST_Centroid(s.geom)) x, ST_Y(ST_Centroid(s.geom)) y from sectors_with_pl sp join sectors s on (s.id IN (" + sectors + ") AND s.id = sp.id)")
    output_data['sectors_with_paths_lengths'] = get_table_data(config['gpkg_path'], 'sectors_with_paths_lengths_export', ['id', 'length_m', 'x', 'y'])

    run_query(config['gpkg_path'], 'delete from sectors_neighbors_export')
    run_query(config['gpkg_path'], "insert into sectors_neighbors_export (id, string_agg) select id, string_agg from sectors_neighbors WHERE id IN (" + sectors + ")")
    output_data['sectors_neighbors'] = get_table_data(config['gpkg_path'], 'sectors_neighbors_export', ['id', 'string_agg'])

    run_query(config['gpkg_path'], 'delete from sectors_envelope_export')
    run_query(config['gpkg_path'], "insert into sectors_envelope_export (minx, miny, maxx, maxy) select MIN(ST_MinX(geom)) AS min_x, MIN(ST_MinY(geom)) AS min_y, MAX(ST_MaxX(geom)) AS max_x, MAX(ST_MaxY(geom)) AS max_y FROM sectors")
    output_data['sectors_envelope'] = get_table_data(config['gpkg_path'], 'sectors_envelope_export', ['minx', 'miny', 'maxx', 'maxy'])

    return output_data

def get_cluster(config, clusters, sectors, placement, grid):
    distance = 1000000
    sector_id = -1
    for sector in sectors:
        # The sector is not used yet
        if sector not in clusters:
            curdistance = math.sqrt(math.pow(sectors[sector]['x'] - grid[placement][0], 2) + math.pow(sectors[sector]['y'] - grid[placement][1], 2))
            if curdistance < distance:
                if config['log_level'] == 'debug':
                    print(curdistance)
                    print(sector)
                    print(sectors[sector])
                sector_id = sector
                distance = curdistance

    return sector_id


def get_grid_position(sector, grid):
    distance = 1000000
    grid_id = -1
    pos = 0
    for grid_item in grid:
        curdistance = math.sqrt(math.pow(sector['x'] - grid_item[0], 2) + math.pow(sector['y'] - grid_item[1], 2))
        if curdistance < distance:
            grid_id = pos
            distance = curdistance
        pos += 1
    return grid_id


def grid_position_is_empty(grid_pos, clusters):
    is_empty = True
    for cluster_id in clusters:
        if clusters[cluster_id]['grid'] == grid_pos:
            is_empty = False
    return is_empty


def is_neighbor(sector_id, clusters, sectors_neighbors):
    is_neighbor = False
    for cluster_id in clusters:
        if cluster_id in sectors_neighbors[sector_id]:
            is_neighbor = True
    return is_neighbor


def is_already_in_clusters(clusters, sector_id):
    for cluster_id in clusters:
        if sector_id in clusters[cluster_id]['sectors']:
            return True
    return False


def append_sector_into_cluster(clusters, sectors, sectors_neighbors, cluster_id):
    for sector_in_cluster in clusters[cluster_id]['sectors']:
        for sector_in_neighbors in sectors_neighbors[sector_in_cluster]:
            if not is_already_in_clusters(clusters, sector_in_neighbors):
                # print(sector_in_neighbors)
                # if sector_in_neighbors == "3035":
                #     print(sectors)
                if sector_in_neighbors in sectors:
                    clusters[cluster_id]['sectors'].append(sector_in_neighbors)
                    clusters[cluster_id]['length'] += sectors[sector_in_neighbors]['length']
                    return

def fix_not_assigned(config, sectors_not_assigned, clusters, sectors_neighbors, sectors, iteration):
    if config['log_level'] == 'debug':
        print(sectors_not_assigned)
    items_to_remove = []
    for not_assigned_sector in sectors_not_assigned:
        if config['log_level'] == 'debug':
            print('Processing: ' + str(not_assigned_sector))
        cluster_candidates = {}
        for cluster_id in clusters:
            for sector_id in clusters[cluster_id]['sectors']:
                if not_assigned_sector in sectors_neighbors[sector_id]:
                    if iteration > 5:
                        cluster_candidates[cluster_id] = clusters[cluster_id]['length']
                    else:
                        if clusters[cluster_id]['length'] < config['covers'][clusters[cluster_id]['unit']] * 1000:
                            cluster_candidates[cluster_id] = clusters[cluster_id]['length']
        if config['log_level'] == 'debug':
            print('Len cluster_candidates: ' + str(len(cluster_candidates)))
        if len(cluster_candidates) < 1:
            if config['log_level'] == 'debug':
                print("We have a problem with: " + str(not_assigned_sector))
        if len(cluster_candidates) > 0:
            cluster_id_candidate = - 1
            max_diff_length_candidate = -10000000
            for cluster_id in cluster_candidates:
                if (config['covers'][clusters[cluster_id]['unit']] * 1000 - clusters[cluster_id]['length']) > max_diff_length_candidate:
                    cluster_id_candidate = cluster_id
                    max_diff_length_candidate = config['covers'][clusters[cluster_id]['unit']] * 1000 - clusters[cluster_id]['length']
            clusters[cluster_id_candidate]['sectors'].append(not_assigned_sector)
            clusters[cluster_id_candidate]['length'] += sectors[not_assigned_sector]['length']
            if config['log_level'] == 'debug':
                print('Removing: ' + str(not_assigned_sector))
            items_to_remove.append(not_assigned_sector)

    # Remove the items
    for item in items_to_remove:
        sectors_not_assigned.remove(item)

def get_the_most_undersized_or_oversized_cluster(config, clusters):
    cluster_id_candidate = - 1
    max_diff_length_candidate_in_percent = -10000000
    for cluster_id in clusters:
        if config['log_level'] == 'debug':
            print(str(cluster_id) + ': ' + str(clusters[cluster_id]['length']))
        difference = abs(config['covers'][clusters[cluster_id]['unit']] * 1000 - clusters[cluster_id]['length'])
        current_max_diff_length_candidate_in_percent = difference / (config['covers'][clusters[cluster_id]['unit']] * 1000 / 100)
        if current_max_diff_length_candidate_in_percent > max_diff_length_candidate_in_percent:
            cluster_id_candidate = cluster_id
            max_diff_length_candidate_in_percent = current_max_diff_length_candidate_in_percent
    if config['log_level'] == 'debug':
        print(max_diff_length_candidate_in_percent)
        print('Candidate: ' + str(cluster_id_candidate))
    if max_diff_length_candidate_in_percent > 10:
        return cluster_id_candidate
    else:
        return -1

def get_type_of_optimized_cluster(cluster_id, clusters, covers):
    difference = covers[clusters[cluster_id]['unit']] * 1000 - clusters[cluster_id]['length']
    if difference < 0:
        return -1
    else:
        return 1

def get_cluster_candidate(cluster_candidates, clusters, covers, increase):
    # We should move the sector that in result makes difference for the current_cluster_id length from optimal smallest
    # But also the one that will be used from the cluster that has the biggest difference of the length from optimal
    # The flow is not probably optimal, but first we find the suitable cluster
    # Then we select one of the sector from the cluster that covers the first condition
    cluster_id_candidate = - 1
    max_diff_length_candidate_in_percent = -10000000
    for cluster_id in cluster_candidates:
        difference = clusters[cluster_id]['length'] - covers[clusters[cluster_id]['unit']] * 1000
        if not increase:
            difference = covers[clusters[cluster_id]['unit']] * 1000 - clusters[cluster_id]['length']
        current_max_diff_length_candidate_in_percent = difference / (covers[clusters[cluster_id]['unit']] * 1000 / 100)
        if current_max_diff_length_candidate_in_percent > max_diff_length_candidate_in_percent:
            cluster_id_candidate = cluster_id
            max_diff_length_candidate_in_percent = current_max_diff_length_candidate_in_percent
    return cluster_id_candidate

def get_sector_candidate(current_cluster_id, cluster_id_candidate, cluster_candidates, clusters, sectors, covers, sectors_neighbors, increase):
    sector_id_candidate = -1
    min_diff_length_candidate = 10000000
    if increase:
        for sector_id in cluster_candidates[cluster_id_candidate]:
            if increase:
                if (abs(clusters[current_cluster_id]['length'] + sectors[sector_id]['length'] - covers[clusters[current_cluster_id]['unit']] * 1000)) < min_diff_length_candidate:
                    sector_id_candidate = sector_id
                    min_diff_length_candidate = abs(clusters[current_cluster_id]['length'] + sectors[sector_id]['length'] - covers[clusters[current_cluster_id]['unit']] * 1000)
    else:
        # We have to loop all sectors in current_cluster_id since we want to decrease the current_cluster_id
        # We have to check if the sector is neighbor with any sector in cluster_id_candidate and if the decrease brings the best result
        for sector_id in clusters[current_cluster_id]['sectors']:
            for current_sector_id in clusters[cluster_id_candidate]['sectors']:
                if sector_id in sectors_neighbors[current_sector_id]:
                    if (abs(clusters[current_cluster_id]['length'] - sectors[sector_id]['length'] - covers[clusters[current_cluster_id]['unit']] * 1000)) < min_diff_length_candidate:
                        sector_id_candidate = sector_id
                        min_diff_length_candidate = abs(clusters[current_cluster_id]['length'] + sectors[sector_id]['length'] - covers[clusters[current_cluster_id]['unit']] * 1000)

    return sector_id_candidate

def move_sector_between_clusters(config, current_cluster_id, clusters, sectors, sectors_neighbors):
    cluster_candidates = {}
    for cluster_id in clusters:
        if cluster_id != current_cluster_id:
            for sector_id in clusters[cluster_id]['sectors']:
                for current_sector_id in clusters[current_cluster_id]['sectors']:
                    if sector_id in sectors_neighbors[current_sector_id]:
                        # The sector_id is a neighbor of the current_sector_id
                        if cluster_id not in cluster_candidates:
                            cluster_candidates[cluster_id] = [sector_id]
                        else:
                            cluster_candidates[cluster_id].append(sector_id)

    current_cluster_optimize_type = get_type_of_optimized_cluster(current_cluster_id, clusters, config['covers'])
    if current_cluster_optimize_type == 1:
        cluster_id_candidate = get_cluster_candidate(cluster_candidates, clusters, config['covers'], True)
        sector_id_candidate = get_sector_candidate(current_cluster_id, cluster_id_candidate, cluster_candidates, clusters, sectors, config['covers'], sectors_neighbors, True)
    else:
        cluster_id_candidate = get_cluster_candidate(cluster_candidates, clusters, config['covers'], False)
        sector_id_candidate = get_sector_candidate(current_cluster_id, cluster_id_candidate, cluster_candidates, clusters, sectors, config['covers'], sectors_neighbors, False)

    # We know the final candidate, so we move it from its cluster into current processed cluster
    if config['log_level'] == 'debug':
        print('Type: ' + str(current_cluster_optimize_type))
        print('Before: ' + str(clusters[current_cluster_id]['length']) + ' ' + str(clusters[cluster_id_candidate]['length']))
        print('Sector length: ' + str(sectors[sector_id_candidate]['length']))
    if current_cluster_optimize_type == 1:
        clusters[current_cluster_id]['sectors'].append(sector_id_candidate)
        clusters[cluster_id_candidate]['sectors'].remove(sector_id_candidate)
        clusters[current_cluster_id]['length'] += sectors[sector_id_candidate]['length']
        clusters[cluster_id_candidate]['length'] -= sectors[sector_id_candidate]['length']
    else:
        clusters[cluster_id_candidate]['sectors'].append(sector_id_candidate)
        clusters[current_cluster_id]['sectors'].remove(sector_id_candidate)
        clusters[current_cluster_id]['length'] -= sectors[sector_id_candidate]['length']
        clusters[cluster_id_candidate]['length'] += sectors[sector_id_candidate]['length']
    if config['log_level'] == 'debug':
        print(current_cluster_id + ' ' + cluster_id_candidate)
        print('After: ' + str(clusters[current_cluster_id]['length']) + ' ' + str(clusters[cluster_id_candidate]['length']))

def optimize_clusters(config, clusters, sectors, sectors_neighbors):
    for i in range(100):
        cluster_id_to_optimize = get_the_most_undersized_or_oversized_cluster(config, clusters)
        if cluster_id_to_optimize != -1:
            move_sector_between_clusters(config, cluster_id_to_optimize, clusters, sectors, sectors_neighbors)
        else:
            if config['log_level'] == 'debug':
                print('Breaking optimization at ' + str(i) + ' iteration')
            break

def print_clusters(clusters):
    with open('/tmp/clusters.csv', 'w') as out:
        for cluster_id in clusters:
            for sector in clusters[cluster_id]['sectors']:
                out.write(sector + ';' + str(clusters[cluster_id]['grid']) + ';' + clusters[cluster_id]['type'] + ';' + clusters[cluster_id]['unit'] + ';' + str(cluster_id) + '\n')

def print_clusters_2(clusters):
    for cluster_id in clusters:
        print(str(clusters[cluster_id]['grid']) + ';' + clusters[cluster_id]['type'] + ';' + clusters[cluster_id]['unit'] + ';' + str(clusters[cluster_id]['length']))

def get_used_searchers(config, total_length):

    used_searchers = {
        "handler": 0,
        "pedestrian": 0,
        "rider": 0,
        "quad_bike": 0
    }

    cover = config['searchers']['handler'] * config['covers']['handler']
    cover += config['searchers']['pedestrian'] * config['covers']['pedestrian']
    cover += config['searchers']['rider'] * config['covers']['rider']
    cover += config['searchers']['quad_bike'] * config['covers']['quad_bike']

    print('COVER: ' + str(cover))

    # We do not cover whole area
    if cover < total_length:
        diff = total_length - cover
        if diff < config['covers']['pedestrian'] / 2:
            used_searchers = config['searchers']
        else:
            used_searchers = config['searchers']
            used_searchers['pedestrian'] += math.ceil(diff / config['covers']['pedestrian'])

    # We cover perfectly the whole area - should not happen so often
    if cover == total_length:
        used_searchers = config['searchers']

    # We do cover whole area and have more units
    if cover > total_length:
        diff = cover - total_length
        if diff < config['covers']['pedestrian'] / 2:
            used_searchers = config['searchers']
        else:
            cover = 0
            for i in range(config['searchers']['handler']):
                cover += config['covers']['handler']
                if cover <= total_length:
                    used_searchers['handler'] += 1
            for i in range(config['searchers']['pedestrian']):
                cover += config['covers']['pedestrian']
                if cover <= total_length:
                    used_searchers['pedestrian'] += 1
            for i in range(config['searchers']['rider']):
                cover += config['covers']['rider']
                if cover <= total_length:
                    used_searchers['rider'] += 1
            for i in range(config['searchers']['quad_bike']):
                cover += config['covers']['quad_bike']
                if cover <= total_length:
                    used_searchers['quad_bike'] += 1
            # TODO maybe necessary to add last unit once more
            if used_searchers['handler'] == 0:
                used_searchers['handler'] = 1

    return used_searchers

def get_clusters(config, data):
    total_length = int(float(data['sum_length'][0]['sum_length_m']))
    print('TOTAL LENGTH: ' + str(total_length))

    used_searchers = get_used_searchers(config, total_length)
    number_of_clusters = used_searchers['handler'] + used_searchers['pedestrian'] + used_searchers['rider'] + used_searchers['quad_bike']
    clusters = {}

    if number_of_clusters == 1:
        clusters['0'] = {
            "unit": 'handler',
            "type": "5",
            "sectors": config['sectors'],
            "length": total_length,
            "grid": 1
        }
        return clusters

    number_of_5_type_searchers = config['searchers']['handler'] + config['searchers']['pedestrian']
    sectors = {}
    sectors_neighbors = {}
    sectors_5_max_order = []
    bbox = []
    grid = []
    grid_size = math.ceil(math.sqrt(number_of_clusters))
    print('GRID: ' + str(grid_size))
    grid_rows = grid_size
    grid_cols = grid_size

    for item in data['sectors_by_path_with_neighbors_agg']:
        sectors_5_max_order.append(str(item['id']))

    for item in data['sectors_with_paths_lengths']:
        sectors[str(item['id'])] = {"length": int(item['length_m']), "x": item['x'], "y": item['y']}

    for item in data['sectors_neighbors']:
        neighbors = item['string_agg'].split(';')
        sectors_neighbors[str(item['id'])] = neighbors

    bbox.append(data['sectors_envelope'][0]['minx'])
    bbox.append(data['sectors_envelope'][0]['miny'])
    bbox.append(data['sectors_envelope'][0]['maxx'])
    bbox.append(data['sectors_envelope'][0]['maxy'])

    area_width = bbox[2] - bbox[0]
    area_height =  bbox[3] - bbox[1]
    cell_width = area_width / grid_cols
    cell_height = area_height / grid_rows
    for row in range(grid_rows):
        for col in range(grid_cols):
            x = bbox[0] + cell_width * col + (cell_width / 2)
            y = bbox[1] + cell_height * row + (cell_height / 2)
            grid.append([x, y])

    grid = random.sample(grid, number_of_clusters)


    # We set the first 5 type cluster, if we have a person/handler for it
    used_handlers = 0
    used_pedestrians = 0
    if number_of_5_type_searchers > 0:
        grid_pos = get_grid_position(sectors[sectors_5_max_order[0]], grid)
        unit = 'handler'
        if used_searchers['handler'] == 0:
            unit = 'pedestrian'
            used_pedestrians += 1
        else:
            used_handlers += 1
        clusters[sectors_5_max_order[0]] = {
            "unit": unit,
            "type": "5",
            "sectors": [sectors_5_max_order[0]],
            "length": sectors[sectors_5_max_order[0]]['length'],
            "grid": grid_pos
        }

    while len(clusters) < number_of_5_type_searchers:
        for sector_id in sectors_5_max_order:
            if sector_id not in clusters and sector_id in sectors and not is_neighbor(sector_id, clusters, sectors_neighbors):
                grid_pos = get_grid_position(sectors[sector_id], grid)
                unit = 'handler'
                if used_handlers == used_searchers['handler']:
                    unit = 'pedestrian'
                    used_pedestrians += 1
                else:
                    used_handlers += 1
                if grid_position_is_empty(grid_pos, clusters):
                    clusters[sector_id] = {
                        "unit": unit,
                        "type": "5",
                        "sectors": [sector_id],
                        "length": sectors[sector_id]['length'],
                        "grid": grid_pos
                    }
                    if config['log_level'] == 'debug':
                        print(len(clusters))
                    break
    used_riders = 0
    used_quad_bike = 0
    for i in range(number_of_clusters):
        if grid_position_is_empty(i, clusters):
            cluster_id = get_cluster(config, clusters, sectors, i, grid)
            unit = 'rider'
            if used_riders == used_searchers['rider']:
                unit = 'quad_bike'
                used_quad_bike += 1
            else:
                used_riders += 1
            clusters[cluster_id] = {
                "unit": unit,
                "type": "4",
                "sectors": [cluster_id],
                "length": sectors[cluster_id]['length'],
                "grid": i
            }

    for it in range(100):
        if config['log_level'] == 'debug':
            print("Iteration: " + str(it))
        for cluster_id in clusters:
            if config['log_level'] == 'debug':
                print("Cluster: " + str(cluster_id))
            if clusters[cluster_id]['length'] < config['covers'][clusters[cluster_id]['unit']] * 1000:
                if config['log_level'] == 'debug':
                    print("Adding another sector into cluster.")
                append_sector_into_cluster(clusters, sectors, sectors_neighbors, cluster_id)
            else:
                if config['log_level'] == 'debug':
                    print("Cluster is full. Skipping.")

    # print(sectors)
    # print(sectors_neighbors)
    # print(clusters)
    # return

    sectors_not_assigned = []
    for sector in sectors:
        sector_is_assigned = False
        for cluster_id in clusters:
            if sector in clusters[cluster_id]['sectors']:
                sector_is_assigned = True
        if not sector_is_assigned:
            sectors_not_assigned.append(sector)

    # print(sectors_not_assigned)
    #
    for i in range(10):
        if config['log_level'] == 'debug':
            print("Fix not assigned. Iteration: " + str(i))
        fix_not_assigned(config, sectors_not_assigned, clusters, sectors_neighbors, sectors, i)

    optimize_clusters(config, clusters, sectors, sectors_neighbors)
    # print(clusters)
    if config['log_level'] == 'debug':
        print_clusters_2(clusters)
        print_clusters(clusters)

    return clusters


def prepare_data_for_graph_based_on_polygon(config):

    # TODO use grades as well
    run_query(config['gpkg_path'], 'delete from ways_for_sectors_export')
    sql = "insert into ways_for_sectors_export (source, target, length_m, gid, x1, y1, x2, y2) select distinct source, target, length_m, ways.gid gid, x1, y1, x2, y2 from ways, new_polygon_layer where st_intersects(ways.the_geom, st_buffer(new_polygon_layer.geom, -0.00005))"
    # print(sql)
    run_query(config['gpkg_path'], sql)
    output_data = get_table_data(config['gpkg_path'], 'ways_for_sectors_export', ['source', 'target', 'length_m', 'gid', 'x1', 'y1', 'x2', 'y2'])

    return output_data

def prepare_data_for_graph(config, sectors_list, grades):
    sectors = array_to_in_param(sectors_list)

    run_query(config['gpkg_path'], 'delete from ways_for_sectors_export')
    # sql = "insert into ways_for_sectors_export (source, target, length_m, gid, x1, y1, x2, y2) select distinct source, target, length_m, ways.gid gid, x1, y1, x2, y2 from ways join ways_for_sectors wfs on (grade in (" + grades + ") and id IN (" + sectors + ") and ways.gid = wfs.gid)"
    # print(sql)
    sql = "insert into ways_for_sectors_export (source, target, length_m, gid, x1, y1, x2, y2) select distinct source, target, length_m, ways.gid gid, x1, y1, x2, y2 from ways where grade in (" + grades + ")"
    run_query(config['gpkg_path'], sql)
    output_data = get_table_data(config['gpkg_path'], 'ways_for_sectors_export', ['source', 'target', 'length_m', 'gid', 'x1', 'y1', 'x2', 'y2'])

    return output_data

    # TODO - seems that the implementation is wrong
    # This is an optimisation where we removed nodes that are not on intersection or are not isolated nodes (end of line)
    nodes = {

    }

    for way in output_data:
        if way['source'] in nodes:
            nodes[way['source']] += 1
        else:
            nodes[way['source']] = 1

        if way['target'] in nodes:
            nodes[way['target']] += 1
        else:
            nodes[way['target']] = 1

    output_data_fixed = []
    for key in nodes:
        if nodes[key] == 2:
            # This should be a node that is not necessary since it is not a node on intersection, and it is not an isolated node
            ways_to_merge = []
            for way in output_data:
                if way['source'] == key or way['target'] == key:
                    ways_to_merge.append(way)
            if len(ways_to_merge) > 1:
                # We start on 0 source and end on 1 target
                if ways_to_merge[0]['target'] == ways_to_merge[1]['source']:
                    merged_way = ways_to_merge[0]
                    merged_way['target'] = ways_to_merge[1]['target']
                    merged_way['length_m'] += ways_to_merge[1]['length_m']
                    output_data_fixed.append(merged_way)
                # We start on 0 source and end on 1 source
                if ways_to_merge[0]['target'] == ways_to_merge[1]['target']:
                    merged_way = ways_to_merge[0]
                    merged_way['target'] = ways_to_merge[1]['source']
                    merged_way['length_m'] += ways_to_merge[1]['length_m']
                    output_data_fixed.append(merged_way)
                # We start on 1 source and end on 0 target
                if ways_to_merge[0]['source'] == ways_to_merge[1]['target']:
                    merged_way = ways_to_merge[1]
                    merged_way['target'] = ways_to_merge[0]['target']
                    merged_way['length_m'] += ways_to_merge[0]['length_m']
                    output_data_fixed.append(merged_way)
                # We start on 0 target and end on 1 target
                if ways_to_merge[0]['source'] == ways_to_merge[1]['source']:
                    merged_way = ways_to_merge[1]
                    merged_way['source'] = ways_to_merge[0]['target']
                    merged_way['length_m'] += ways_to_merge[0]['length_m']
                    output_data_fixed.append(merged_way)
        else:
            # These nodes should be correct
            for way in output_data:
                if way['source'] == key or way['target'] == key:
                    output_data_fixed.append(way)

    return output_data_fixed

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

        info = "Component: " + str(component_id) + "\n"
        info += "Total length of roads: %.3f km\n" % in_length
        info += "Total length of path: %.3f km\n" % path_length
        info += "Length of sections visited twice: %.3f km\n" % duplicate_length

        print(info)

        create_layer(config, eulerian_graph, nodes, name + '_' + str(component_id))
        with open(os.path.join(config['output_dir'], name + '_' + str(component_id) + '_nodes_sequence.json'), 'w') as f:
            json.dump(nodes, f)
        points = get_points_on_path(config['gpkg_path'], 'chpostman_path_export')

        # TODO
        suggested_unit_types = []
        if path_length > 18:
            suggested_unit_types = ["quad_bike"]
        if path_length < 12:
            suggested_unit_types = ["pedestrian", "handler", "horse_rider"]
        if 12 > path_length <= 18:
            suggested_unit_types = ["horse_rider", "handler", "quad_bike"]

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

    print('Before export create_layer_simple_with_export')

    # Crashes when running inside QGIS, so we will do not use fiona for export in QGIS but QGIS API
    # save_layer_as_geojson(config['gpkg_path'], 'chpostman_path_export', ['gid', 'ord', 'ts'], os.path.join(config['output_dir'], name + '.geojson'))
    if export:
        save_layer_as_shp(config['gpkg_path'], 'chpostman_path_export', name, os.path.join(config['output_dir'], name + '.shp'))

    print('After export create_layer_simple_with_export')

def create_layer(config, graph, nodes, name):
    run_query(config['gpkg_path'], 'delete from chpostman_path')
    pos = 0
    ts = datetime.now()
    queries = []
    # for u, v in pairs(nodes, False):
    #     pos += 1
    #     ts = ts + timedelta(seconds=1)
    #     queries.append("insert into chpostman_path (gid, ord, ts) values (" + graph[u][v]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "')")

    # Projití všech hran a vypsání jejich vah
    # Toto funguje blbě v tom, že jsou hrany chybně za sebou poskládány
    # for u, v, data in graph.edges(data=True):
    #     pos += 1
    #     ts = ts + timedelta(seconds=1)
    #     print(str(u) + " " + str(v))
    #     if 'id' in data:
    #         queries.append("insert into chpostman_path (gid, ord, ts) values (" + data['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "')")
    #         # print(f'Hrana mezi {u} a {v} má váhu {data["weight"]}')

    # Tady zase s nějakého důvodu chybí ty vnitřní cesty. Tak ty vnitřní cesty chybí i u toho předtím. teyd je chyba někde jinde.
    for u, v in pairs(nodes, False):
        pos += 1
        ts = ts + timedelta(seconds=1)
        # print(str(u) + " " + str(v))
        # print(v)
        # print(graph[u][v])
        if 0 in graph[u][v] and 'id' in graph[u][v][0]:
            queries.append("insert into chpostman_path (gid, ord, ts, source, target) values (" + graph[u][v][0]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "', " + str(u) + ", " + str(v) + ")")
        else:
            if 'id' in graph[u][v]:
                queries.append("insert into chpostman_path (gid, ord, ts, source, target) values (" + graph[u][v]['id'] + ", '" + str(pos) + "', '" + str(ts).split('.')[0] + "', " + str(u) + ", " + str(v) + ")")

    run_queries(config['gpkg_path'], queries)
    run_query(config['gpkg_path'], 'delete from chpostman_path_export')
    run_query(config['gpkg_path'], "insert into chpostman_path_export (gid, ord, ts, source_path, target_path, source_way, target_way, the_geom) select ch.gid, ch.ord, ch.ts, ch.source, ch.target, w.source, w.target, w.the_geom from chpostman_path ch join ways w on (ch.gid = w.gid) order by ch.ts")

    print('Before export')

    # Crashes when running inside QGIS, so we will do not use fiona for export in QGIS but QGIS API
    # save_layer_as_geojson(config['gpkg_path'], 'chpostman_path_export', ['gid', 'ord', 'ts'], os.path.join(config['output_dir'], name + '.geojson'))
    # save_layer_as_shp(config['gpkg_path'], 'chpostman_path_export', name, os.path.join(config['output_dir'], name + '.shp'))

    print('After export')

def get_units_grades(unit):
    if unit == 'handler':
        return '0, 1, 2, 3, 4, 5, 6'
        # return '5'
    if unit == 'pedestrian':
        return '0, 1, 2, 3, 4, 5, 6'
    if unit == 'rider':
        return '0, 1, 2, 3'
    if unit == 'quad_bike':
        return '0, 1, 2, 3'
    return '0, 1, 2, 3'

def solve_area(config):
    # Reads sectors and prepares data for clustering
    data = prepare_data(config)
    # Returns clusters
    clusters = get_clusters(config, data)
    solutions = []
    used_edges = []
    for cluster_id in clusters:
        # print(clusters[cluster_id]['sectors'])
        print(clusters[cluster_id]['unit'])
        # Prepares data in a form of nodes and edges
        grades = get_units_grades(clusters[cluster_id]['unit'])
        print(grades)
        graph_data_input = prepare_data_for_graph(config, clusters[cluster_id]['sectors'], grades)
        graph = build_graph(graph_data_input, used_edges)
        # Remembers already used edges
        for edge in graph_data_input:
            used_edges.append(edge['gid'])
        # print(graph_data_input)
        used_edges = [] # Use this if you do not want to remove duplicities
        graph_solution = solve_graph(graph, config, clusters[cluster_id]['unit'] + '_' + str(cluster_id))
        solutions.append(graph_solution)
    return solutions

def test_me():
    config = {
        "log_level": "debug",
        "gpkg_path": "/home/jencek/Documents/Projekty/PCR/test_data/test.gpkg",
        "output_dir": "/tmp/",
        "covers": {
            "handler": 12,
            "pedestrian": 12,
            "rider": 16,
            "quad_bike": 20
        },
        "searchers": {
            "handler": 1,
            "pedestrian": 1,
            "rider": 2,
            "quad_bike": 3
        },
        "sectors": [128, 84, 94, 177, 3025, 3035, 3038, 3254, 3288, 3290, 3291, 3295, 3299, 4226, 4227, 4238, 4277, 4301, 4302, 4304, 4311, 4410, 4413, 4427, 4430, 4431, 4433, 4440, 4441, 28938, 40255, 101753, 101850, 101865, 109484, 109758, 109791, 109808, 109819, 109823, 109829, 109830, 109831, 109848, 109853, 109854, 109855, 109857, 110347, 110348, 110354, 110425, 110426, 110430, 110434, 110446, 110458, 110500, 110542, 110633, 110638, 110647, 170252, 179681, 752557, 768172, 235, 4300, 4309, 34963, 126, 2097, 768067, 123, 297, 2356, 4310, 39965, 40060, 40441]
    }
    solve_area(config)


def solve_one_part(start_node, end_node, config, graph_data_input, id):
    if os.path.exists(os.path.join(config['output_dir'], end_node + '_graph.json')):
        # Deserializace z JSON
        with open(os.path.join(config['output_dir'], end_node + '_graph.json'), 'r') as f:
            data = json.load(f)
        G_union = nx.node_link_graph(data)
        graph_solution = solve_graph(G_union, config, 'test_' + str(end_node))
        # print(graph_solution)

    else:
        graph = build_graph(graph_data_input, [])
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
            return

        # Výpis výsledků
        print(f'Nodes: {start_node} a {end_node}')
        print(f'Shortest path between {start_node} and {end_node} is: {shortest_path}')
        print(f'Length of the shortest path is: {shortest_path_length}')

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

        try:
            shortest_path = nx.shortest_path(graph, source=start_node, target=end_node, weight='weight')
            shortest_path_length = nx.shortest_path_length(graph, source=start_node, target=end_node, weight='weight')
        except Exception as e:
            print(e)
            # print(f'Hrany v grafu: {graph.edges(data=True)}')
            return

        # Výpis výsledků
        print(f'Nodes: {start_node} a {end_node}')
        print(f'Shortest path between {start_node} and {end_node} is: {shortest_path}')
        print(f'Length of the shortest path is: {shortest_path_length}')

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
        graph_data_input_missing_edges = prepare_data_for_graph_based_on_polygon(config)
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
    # layer_name = 'new_polygon_layer'
    #
    # # Specifikace CRS (zde EPSG:4326, můžete upravit podle potřeby)
    # crs = from_epsg(4326)
    #
    # # Definice schématu pro novou vrstvu
    # schema = {
    #     'geometry': 'Polygon',
    #     'properties': {
    #         'id': 'int',
    #     },
    # }

    # Přidání nové vrstvy do existujícího souboru GPKG
    # nefunguje - nevím proč
    # print(config['gpkg_path'])
    # with fiona.open(gpkg_path, 'a', driver='GPKG', schema=schema, layer=layer_name, crs=crs) as sink:
    #     # Přidání polygonů do nové vrstvy
    #     for i, polygon in enumerate(polygons):
    #         sink.write({
    #             'geometry': mapping(polygon),
    #             'properties': {'id': i},
    #         })
    #
    # print(f'Polygony byly úspěšně uloženy do vrstvy {layer_name} v souboru {gpkg_path}.')

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

def export_linies_into_xy_csv(shp_path):
    with fiona.open(shp_path) as layer:
        with open(shp_path + ".csv", "w") as out_csv:
            for feature in layer:
                # print(feature["properties"]["ord"])
                line = shape(feature["geometry"])
                for coord in line.coords:
                    # print(coord)
                    out_csv.write(str(coord[0]) + ',' + str(coord[1]) + '\n')

def graph_exists(solved_graphs, solved_graph):
    for i in range(len(solved_graphs)):
        if are_graphs_identical(solved_graphs[i], solved_graph):
            return True
    return False

def find_path_based_on_shortest_path(id, search_id, config):

    # "start_point": [15.1321449, 49.4054798],
    # "start_point": [15.017469, 49.433281]
    # "source" IN (3609, 6932, 726, 6305, 712, 5028, 5841, 5788)

    grades = '0, 1, 2, 3, 4, 5, 6'
    # print(grades)
    graph_data_input = prepare_data_for_graph(config, config['sectors'], grades)
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
    solutions = []
    solved_graphs = []
    logInfo("POINTS ON GRAPH FOUND\n15\n", id)
    for i in range(len(end_points)):
        pos_end_points = 0
        # We take only first 10 points
        step = round(70 / 10)
        for end_point in end_points[i]:
            solution_results = solve_one_part(str(start_point[0]), str(end_point['id']), config, graph_data_input, id)
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

    logInfo("DONE\n100\n", id)
