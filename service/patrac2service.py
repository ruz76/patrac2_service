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
serviceDataPath = "/data/patracdata/service"

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
            # TODO return ERROR
            placeholder = ''

    time.sleep(timeout)

    progress = int(get_log_progress(id))
    status = 'PROCESSING'
    if progress == 100:
        status = 'DONE'

    ret = {
        "id": id,
        "status": status,
        "progress": progress
    }

    resp = Response(response=json.dumps(ret),
                    status=200,
                    mimetype="application/json")
    return resp


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
            # TODO return error
            placeholder = ''

    time.sleep(timeout)

    progress = int(get_log_progress(id))
    status = 'PROCESSING'
    sectors = None
    if progress == 100:
        status = 'DONE'
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


if __name__ == "__main__":
    app.run(host='0.0.0.0')
