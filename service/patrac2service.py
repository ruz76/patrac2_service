from flask import Flask, request, Response
import json, uuid
from grass_process import *
import time
import os
import pyproj
import fiona
from shapely.geometry import shape
from shapely.geometry import Point

app = Flask(__name__)
dataPath = "/data/patracdata"
serviceDataPath = dataPath + "/service"
settingsPath = "qgis/qgis_patrac_settings"

def get_region(x, y):
    with fiona.open(dataPath + '/cr/vusc.shp', 'r', encoding='utf-8') as kraje:
        for feature in kraje:
            poly = shape(feature['geometry'])
            point = Point(x, y)
            if poly.contains(point) or point.touches(poly):
                return feature['properties']['region']
    return None

def transform_coordinates_to_5514(x, y, from_code):
    from_proj = pyproj.Proj("+init=epsg:" + str(from_code))
    to_proj = pyproj.Proj("+init=epsg:5514")
    return pyproj.transform(from_proj, to_proj, x, y)

def get_log_progress(id):
    if os.path.exists(serviceDataPath + "/logs/" + id + ".log"):
        with open(serviceDataPath + "/logs/" + id + ".log", "r") as log:
            lines = log.readlines()
            return lines[len(lines) - 1]
    else:
        return "-1"

def get_ok_response(id, type):
    progress = int(get_log_progress(id))
    status = 'PROCESSING'
    sectors = None
    if progress == 100:
        status = 'DONE'
        if type == 'calculate_sectors':
            sectors = get_sectors_to_return(id)

    ret = {
        "id": id,
        "status": status,
        "progress": progress
    }

    if sectors is not None:
        ret["sectors"] = sectors

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
        x = float(args.get('x'))
        y = float(args.get('y'))
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
            create_project_grass(id, xmin, ymin, xmax, ymax, region)
        else:
            return get_400_response('Illegal inputs. Coordinates are out of any region.')

    time.sleep(timeout)

    return get_ok_response(id, "create_search")

@app.route("/calculate_sectors", methods=['POST'])
def calculate_sectors():
    content = request.get_json(silent=True)
    timeout = 60
    if 'timeout' in content:
        timeout = content["timeout"]

    existing = False
    id = str(uuid.uuid4())
    if 'id' in content:
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
                    xy = transform_coordinates_to_5514(coord[0], coord[1], epsg)
                    coords.append([xy[0], xy[1]])
            get_sectors_grass(id, content['search_id'], coords, content['person_type'], content['percentage'])
        else:
            return get_400_response('Illegal inputs.')

    time.sleep(timeout)

    return get_ok_response(id, 'calculate_sectors')

@app.route("/calculate_report", methods=['POST'])
def calculate_report():
    content = request.get_json(silent=True)

    if 'calculated_sectors_id' in content:
        with open(settingsPath + "/grass/maxtime.txt", "w") as m:
            if 'max_time' in content:
                m.write(str(int(math.ceil(content['max_time'] / 3600))))
            else:
                m.write("3")
        with open(settingsPath + "/grass/units.txt", "w") as u:
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


if __name__ == "__main__":
    app.run(host='0.0.0.0')
