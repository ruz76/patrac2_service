from flask import Flask, request, Response
import json, uuid
from grass_process import *
from chinesse_process import *
from config import *
import time
import os
import pyproj
import fiona
from shapely.geometry import shape
from shapely.geometry import Point
from threading import Thread

app = Flask(__name__)

def get_region(x, y):
    with fiona.open(os.path.join(dataPath, 'cr', 'vusc.shp'), 'r', encoding='utf-8') as kraje:
        for feature in kraje:
            poly = shape(feature['geometry'])
            point = Point(x, y)
            if (poly.contains(point) or point.touches(poly)) and os.path.exists(os.path.join(dataPath, 'kraje', feature['properties']['region'],  'vektor', 'ZABAGED', 'sectors.shp')):
                return feature['properties']['region']
    return None

def transform_coordinates_to_5514(x, y, from_code):
    from_proj = pyproj.Proj("+init=epsg:" + str(from_code))
    to_proj = pyproj.Proj("+init=epsg:5514")
    return pyproj.transform(from_proj, to_proj, x, y)

def transform_coordinates_to_4326(x, y, from_code):
    from_proj = pyproj.Proj("+init=epsg:" + str(from_code))
    to_proj = pyproj.Proj("+init=epsg:4326")
    return pyproj.transform(from_proj, to_proj, x, y)

def get_log_progress(id):
    if os.path.exists(os.path.join(serviceStoragePath, "logs", id + ".log")):
        with open(os.path.join(serviceStoragePath, "logs", id + ".log"), "r") as log:
            lines = log.readlines()
            return lines[len(lines) - 1]
    else:
        return "-1"

def get_log_info(id):
    if os.path.exists(os.path.join(serviceStoragePath, "logs", id + ".log")):
        with open(os.path.join(serviceStoragePath, "logs", id + ".log"), "r") as log:
            lines = log.readlines()
            return lines[len(lines) - 2].strip()
    else:
        return "ERROR. Unknown Error."

def get_ok_response(id, type):
    progress = int(get_log_progress(id))
    print(progress)
    status = 'PROCESSING'
    sectors = None
    search_path = None
    if progress == 100:
        status = 'DONE'
        if type == 'calculate_sectors':
            sectors = get_sectors_to_return(id)
    if progress == -1:
        status = 'ERROR'
    if progress > 0 and type == 'calculate_path_search':
        search_path = get_paths_to_return(id)

    ret = {
        "status": status,
    }

    if type not in ['delete_sector', 'create_sector']:
        ret["id"] = id
        ret["progress"] = progress

    if sectors is not None:
        ret["sectors"] = sectors
    else:
        if progress == 100 and type == 'calculate_sectors':
            ret["status"] = {"status": "ERROR"}

    if search_path is not None:
        ret["search_path"] = search_path
    else:
        if progress == 100 and type == 'calculate_path_search':
            ret["search_path"] = {"status": "ERROR"}

    resp = Response(response=json.dumps(ret),
                    status=200,
                    mimetype="application/json")
    return resp

def get_400_response(message):
    ret = {
        "errorMessage": message
    }
    resp = Response(response=json.dumps(ret),
                    status=400,
                    mimetype="application/json")
    return resp

def search_exists(id):
    if os.path.exists(serviceStoragePath + "/data/projekty/" + id):
        return True
    else:
        return False

@app.route("/")
def hello():
    return "Vítejte. Toto je Patrac 2 service!. Dokumentaci najdete na https://github.com/ruz76/patrac2_service/tree/main/api_doc"


@app.route("/create_search", methods=['POST'])
def create_search():
    args = request.args
    existing = True
    timeout = args.get("timeout", default=60, type=int)
    id = args.get("id", default="", type=str)
    epsg = args.get("epsg", default=4326, type=int)
    if id == "":
        id = str(uuid.uuid4())
        existing = False

    if not existing:
        try:
            x = float(args.get('x'))
            y = float(args.get('y'))
        except:
            return get_400_response('Illegal inputs. Coordinates are not float numbers.')

        if epsg != 5514:
            xy = transform_coordinates_to_5514(x, y, epsg)
            x = xy[0]
            y = xy[1]
        extent_limit = 5000
        xmin = x - extent_limit
        ymin = y - extent_limit
        xmax = x + extent_limit
        ymax = y + extent_limit

        region = get_region(x, y)
        if region is not None:
            thread = Thread(target=create_project_grass, args=(id, xmin, ymin, xmax, ymax, region,))
            thread.daemon = True
            thread.start()
            with open(os.path.join(serviceStoragePath, "logs", id + ".log"), "a") as log:
                log.write("THREAD STARTED\n0\n")
        else:
            return get_400_response('Illegal inputs. Coordinates are out of any region.')

    progress = int(get_log_progress(id))
    time_elapsed = 0
    while (progress > -1 and progress < 100) and time_elapsed < timeout:
        time.sleep(1)
        time_elapsed += 1
        progress = int(get_log_progress(id))

    message = get_log_info(id)
    if message.startswith('ERROR'):
        return get_400_response(message)
    else:
        return get_ok_response(id, 'create_search')

def check_coordinates(coords, wind_path):
    if not os.path.exists(wind_path):
        return [False, get_400_response('Illegal inputs. Selected search does not exists.')]
    else:
        try:
            with open(wind_path) as wind:
                lines = wind.readlines()
                # north:      -975000
                # south:      -1065000
                # east:       -585000
                # west:       -690000
                for line in lines:
                    if line.startswith('north:'):
                        north = float(line.split(':')[1].strip())
                    if line.startswith('south:'):
                        south = float(line.split(':')[1].strip())
                    if line.startswith('east:'):
                        east = float(line.split(':')[1].strip())
                    if line.startswith('west:'):
                        west = float(line.split(':')[1].strip())
            for coord in coords:
                print(coord)
                print(west, east, south, north)
                if coord[0] < west + 100 or coord[0] > east - 100:
                    return [False, '']
                if coord[1] < south + 100 or coord[1] > north - 100:
                    return [False, '']
        except:
            return [False, get_400_response('The selected search is corrupted. Can not compute.')]
        return [True, 'Coordinates are inside']

@app.route("/calculate_sectors", methods=['POST'])
def calculate_sectors():
    content = request.get_json(silent=True)
    timeout = 60
    if 'timeout' in content:
        timeout = content["timeout"]

    existing = False
    id = str(uuid.uuid4())
    if 'id' in content and content['id'] != '':
        id = content['id']
        existing = True

    if not existing:
        if 'search_id' in content and \
           'coordinates' in content and \
           'person_type' in content and \
           'percentage' in content:
            epsg = 4326
            coords = content['coordinates']
            if 'epsg' in content:
                epsg = content['epsg']
            if epsg != 5514:
                coords = []
                for coord in content['coordinates']:
                    try:
                        x = float(coord[0])
                        y = float(coord[1])
                    except:
                        return get_400_response('Illegal inputs. Coordinates ' + str(coord[0]) + ' ' + str(coord[1]) + ' are not float numbers.')
                    xy = transform_coordinates_to_5514(coord[0], coord[1], epsg)
                    coords.append([xy[0], xy[1]])
            wind_path = os.path.join(serviceStoragePath, "data", "projekty", content['search_id'], "grassdata", "jtsk", "PERMANENT", "WIND")
            if not os.path.exists(wind_path):
                return get_400_response('Illegal inputs. Selected search_id ' + str(content['search_id']) + ' does not exists.')
            else:
                coordinates_status = check_coordinates(coords, wind_path)
                if not coordinates_status[0]:
                    if coordinates_status[1] == '':
                        return get_400_response('Illegal inputs. One of the coordinates is out of the search area.')
                    else:
                        return coordinates_status[1]

            thread = Thread(target=get_sectors_grass, args=(id, content['search_id'], coords, content['person_type'], content['percentage'],))
            thread.daemon = True
            thread.start()
            with open(os.path.join(serviceStoragePath, "logs", id + ".log"), "a") as log:
                log.write("THREAD STARTED\n0\n")
        else:
            return get_400_response('Illegal inputs.')

    progress = int(get_log_progress(id))
    time_elapsed = 0
    while (progress > -1 and progress < 100) and time_elapsed < timeout:
        time.sleep(1)
        time_elapsed += 1
        progress = int(get_log_progress(id))

    message = get_log_info(id)
    if message.startswith('ERROR'):
        return get_400_response(message)
    else:
        return get_ok_response(id, 'calculate_sectors')

@app.route("/calculate_report", methods=['POST'])
def calculate_report():
    content = request.get_json(silent=True)

    if 'calculated_sectors_id' in content and os.path.exists(os.path.join(serviceStoragePath, "data", content['calculated_sectors_id'] + "_sectors.geojson")):
        with open(os.path.join(settingsPath, "grass", "maxtime.txt"), "w") as m:
            if 'max_time' in content:
                m.write(str(int(math.ceil(content['max_time'] / 3600))))
            else:
                m.write("3")
        with open(os.path.join(settingsPath, "grass", "units.txt"), "w") as u:
            if 'handlers' in content:
                u.write(str(content['handlers']) + ";\n")
            else:
                u.write("6;\n")
            if 'phalanx_persons' in content:
                u.write(str(content['phalanx_persons']) + ";\n")
            else:
                u.write("20;\n")
            if 'horse_riders' in content:
                u.write(str(content['horse_riders']) + ";\n")
            else:
                u.write("0;\n")
            if 'vehicle_drivers' in content:
                u.write(str(content['vehicle_drivers']) + ";\n")
            else:
                u.write("0;\n")
            if 'drones' in content:
                u.write(str(content['drones']) + ";\n")
            else:
                u.write("0;\n")
            if 'drones' in content:
                u.write(str(content['drones']) + ";\n")
            else:
                u.write("0;\n")
            if 'other_resources' in content:
                u.write(str(content['other_resources']) + ";\n")
            else:
                u.write("0;\n")

        report = get_report_grass(content['calculated_sectors_id'])
        resp = Response(response=json.dumps(report),
                    status=200,
                    mimetype="application/json")
        return resp
    else:
        return get_400_response('Illegal inputs.')

@app.route("/create_sector", methods=['POST'])
def create_sector():
    # TODO do not allow when previous edit or delete is not finished
    content = request.get_json(silent=True)

    if 'search_id' in content and 'sector' in content and search_exists(content['search_id']):
        collection = {
            "type": "FeatureCollection",
            "name": "sektory_group_selected",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            },
            "features": [content['sector']]
        }
        with open(os.path.join(serviceStoragePath, "data", content['search_id'] + "_create.geojson"), "w") as out:
            json.dump(collection, out)
        create_sector_grass(content['search_id'])
        resp = get_ok_response(content['search_id'], 'create_sector')
        return resp
    else:
        return get_400_response('Illegal inputs.')

@app.route("/delete_sector", methods=['POST'])
def delete_sector():
    # TODO do not allow when previous edit or delete is not finished
    content = request.get_json(silent=True)

    if 'search_id' in content and 'sector_id' in content and search_exists(content['search_id']):

        delete_sector_grass(content['sector_id'], content['search_id'])
        resp = get_ok_response(content['search_id'], 'delete_sector')
        return resp
    else:
        return get_400_response('Illegal inputs.')

@app.route("/version", methods=['GET'])
def version():
    resp = Response(response=json.dumps({"version": "2024-12-12"}),
                    status=200,
                    mimetype="application/json")
    return resp

@app.route("/calculate_path_search", methods=['POST'])
def calculate_path_search():
    content = request.get_json(silent=True)
    timeout = 60
    if 'timeout' in content:
        timeout = content["timeout"]

    existing = False
    id = str(uuid.uuid4())
    if 'id' in content and content['id'] != '':
        id = content['id']
        existing = True

    if not existing:
        if 'search_id' in content and \
                'coordinates' in content and \
                len(content['coordinates']) == 2 and \
                'unit_type' in content and \
                search_exists(content['search_id']):
            epsg = 4326
            coords = content['coordinates']
            if 'epsg' in content:
                epsg = content['epsg']
            if epsg != 4326:
                coords = []
                for coord in content['coordinates']:
                    xy = transform_coordinates_to_4326(coord[0], coord[1], epsg)
                    coords.append([xy[0], xy[1]])
            config = {
                    "log_level": "debug",
                    "gpkg_path": os.path.join(serviceDataPath, "projekty", content["search_id"], "line_search", "data.gpkg"),
                    "output_dir": os.path.join(serviceDataPath, id),
                    "shortest_path": {
                        "handler": 4000,
                        "pedestrian": 4000,
                        "rider": 7000,
                        "quad_bike": 10000,
                        "undefined": 10000
                    },
                    "covers": {
                        "handler": 12,
                        "pedestrian": 12,
                        "rider": 18,
                        "quad_bike": 25
                    },
                    "searchers": {
                        "handler": 1,
                        "pedestrian": 1,
                        "rider": 2,
                        "quad_bike": 3
                    },
                    "unit_type": content['unit_type'],
                    "sectors": [],
                    "start_point": coords[0],
                    "end_point": coords[1]
                }
            if not os.path.exists(config['output_dir']):
                os.makedirs(config['output_dir'])
            with open(os.path.join(config['output_dir'], "config.json"), "w") as config_out:
                config_out.write(json.dumps(config))
            # "start_point": [15.0339242, 49.340751],
            # "end_point": [15.0677249, 49.3256828]
            thread = Thread(target=find_path_based_on_shortest_path, args=(id, content['search_id'], config, ))
            thread.daemon = True
            thread.start()
            with open(os.path.join(serviceStoragePath, "logs", id + ".log"), "a") as log:
                log.write("THREAD STARTED\n0\n")
        else:
            return get_400_response('Illegal inputs.')

    progress = int(get_log_progress(id))
    time_elapsed = 0
    while (progress > -1 and progress < 100) and time_elapsed < timeout:
        time.sleep(1)
        time_elapsed += 1
        progress = int(get_log_progress(id))

    message = get_log_info(id)
    if message.startswith('ERROR'):
        return get_400_response(message)
    else:
        return get_ok_response(id, 'calculate_path_search')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
