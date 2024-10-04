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
            if (poly.contains(point) or point.touches(poly)) and os.path.exists(os.path.join(dataPath, 'kraje', feature['properties']['region'],  'vektor', 'ZABAGED', 'line_x', 'merged_polygons_groupped.shp')):
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
    if progress == 100:
        status = 'DONE'
        if type == 'calculate_sectors':
            sectors = get_sectors_to_return(id)
    if progress == -1:
        status = 'ERROR'

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
            ret["status"] = 'ERROR'

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
                    xy = transform_coordinates_to_5514(coord[0], coord[1], epsg)
                    coords.append([xy[0], xy[1]])
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
                'unit_type' in content:
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
                    "gpkg_path": "/home/jencek/Documents/Projekty/PCR/test_data_eustach/test_short_2.gpkg",
                    "output_dir": "/tmp/chp1",
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
                    "unit_type": content['unit_type'],
                    "sectors": [142442, 142444, 143254, 143263, 143884, 143941, 145390, 145401, 145405, 145408, 145446, 145448, 145453, 145464, 145465, 145468, 145525, 145526, 145529, 145547, 145555, 145556, 145557, 145558, 145603, 660753, 660758, 660783, 660800, 660824, 660832, 660837, 660838, 660840, 660843, 664917, 673397, 674517, 674663, 674668, 674669, 674679, 674682, 674693, 674694, 674695, 674696, 674697, 674700, 674704, 674706, 674707, 674712, 674715, 674734, 674736, 674742, 674743, 674744, 674746, 674748, 674750, 674753, 674755, 674762, 674763, 674764, 674767, 674769, 674770, 674771, 674773, 674778, 674779, 674780, 674781, 674783, 674784, 674790, 674795, 674796, 674797, 674798, 674800, 674806, 674813, 674836, 674842, 674844, 674940, 674941, 674943, 674944, 674946, 674952, 674955, 674958, 674959, 674961, 674962, 674963, 674967, 674971, 674973, 674975, 674977, 674983, 675011, 675012, 675919, 676991, 688010, 145350, 145359, 145392, 145418, 145457, 145462, 145463, 145489, 145575, 668767, 674411, 674520, 674533, 674598, 674609, 674667, 674671, 674676, 674683, 674688, 674689, 674699, 674709, 674710, 674716, 674717, 674722, 674725, 674726, 674727, 674745, 674815, 674816, 674817, 674819, 674822, 674826, 674828, 674831, 674832, 674833, 674838, 674843, 674846, 674850, 674866, 674884, 674887, 674897, 674899, 674913, 674914, 674916, 674925, 674926, 674927, 674929, 674931, 674933, 674934, 674937, 674982, 674984, 674989, 674990, 674991, 674993, 674997, 675000, 675001, 675003, 675004, 675008, 675016, 675017, 687754, 687968, 765584, 674751, 142598, 142602, 142656, 142671, 142687, 145458, 654010, 657634, 657673, 657714, 657811, 659980, 660699, 660847, 660856, 663634, 663636, 663639, 663640, 663643, 663660, 663671, 674935, 647978, 674851, 144824, 144828, 144935, 145388, 145427, 145480, 145535, 145539, 145565, 647941, 647949, 671820, 672039, 672041, 672042, 672106, 674662, 674670, 674687, 674692, 674698, 674703, 674733, 674810, 674812, 674814, 685157, 687920, 143201, 144025, 144057, 145373, 145387, 145399, 145404, 145409, 145412, 145444, 145445, 145454, 145455, 145456, 145459, 145528, 145537, 145540, 145542, 145548, 145566, 145598, 145602, 672057, 674446, 674449, 674483, 674600, 674655, 674680, 674684, 674685, 674701, 674702, 674705, 674708, 674718, 674721, 674728, 674731, 674738, 674741, 674747, 674752, 674756, 674757, 674758, 674759, 674760, 674761, 674768, 674777, 674785, 674786, 674787, 674788, 674789, 674792, 674793, 674794, 674799, 674804, 674805, 674809, 674947, 674948, 674949, 674950, 674956, 674957, 674960, 674964, 674968, 674970, 674978, 677001, 648027, 142449, 142494, 663642, 140540, 140545, 142429, 145604, 660756, 660762, 660763, 660778, 660818, 674976, 674980, 674987, 674988, 142668, 143594, 143832, 143838, 143974, 145200, 145372, 145415, 145416, 145417, 145420, 145422, 145441, 145443, 145466, 145477, 145530, 145531, 145532, 145538, 145562, 145569, 145579, 145590, 145597, 645978, 657664, 660685, 660698, 660737, 660761, 663628, 663631, 663633, 663650, 663674, 665246, 668144, 673938, 674280, 674345, 674402, 674420, 674508, 674519, 674636, 674646, 674660, 674681, 674686, 674691, 674711, 674713, 674714, 674719, 674720, 674723, 674724, 674729, 674730, 674735, 674739, 674754, 674766, 674775, 674782, 674791, 674802, 674808, 674811, 674820, 674821, 674823, 674824, 674825, 674827, 674829, 674830, 674834, 674840, 674841, 674845, 674847, 674853, 674855, 674881, 674896, 674904, 674915, 674923, 674928, 674932, 674938, 674945, 674951, 674985, 674995, 674996, 674998, 674999, 675002, 675005, 675006, 675007, 675009, 675010, 675013, 675014, 675015, 681831, 683216, 683221, 765585, 144826, 145389, 672034, 672072, 674732, 674737, 674749, 687932, 765536],
                    "start_point": [15.0339242, 49.340751],
                    "end_point": [15.0677249, 49.3256828]
                }
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
    app.run(host='0.0.0.0')
