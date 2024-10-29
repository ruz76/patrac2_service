import csv, io, math, socket, subprocess, os, sys, uuid
from shutil import copy
from glob import glob
import json
import proc.operations as grass_operations
from config import *
from osgeo import gdal
import pyproj

def copyTemplate(NEW_PROJECT_PATH, NAMESAFE, region):
    TEMPLATES_PATH = os.path.join(pluginPath, "templates")
    if not os.path.isdir(NEW_PROJECT_PATH):
        os.mkdir(NEW_PROJECT_PATH)

        # sets the settings to zero, so no radial and no weight limit is used
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "config"))
        settingsPath = os.path.join("qgis", "qgis_patrac_settings")
        copy(os.path.join(settingsPath, "grass", "weightlimit.txt"), os.path.join(NEW_PROJECT_PATH, 'config', 'weightlimit.txt'))
        copy(os.path.join(settingsPath, "grass", "maxtime.txt"), os.path.join(NEW_PROJECT_PATH, 'config', 'maxtime.txt'))
        copy(os.path.join(settingsPath, "grass", "radialsettings.txt"), os.path.join(NEW_PROJECT_PATH, 'config', 'radialsettings.txt'))

        copy(os.path.join(TEMPLATES_PATH, "projekt", "clean_v3.qgs"), os.path.join(NEW_PROJECT_PATH, NAMESAFE + ".qgs"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "pracovni"))
        for file in glob(os.path.join(TEMPLATES_PATH, 'projekt', 'pracovni', '*')):
            copy(file, os.path.join(NEW_PROJECT_PATH, "pracovni"))
        with open(os.path.join(NEW_PROJECT_PATH, "pracovni", "region.txt"), "w") as r:
            r.write(region)
        copy(os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group_selected.dbf"),
             os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group.dbf"))
        copy(os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group_selected.shp"),
             os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group.shp"))
        copy(os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group_selected.shx"),
             os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group.shx"))
        copy(os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group_selected.qml"),
             os.path.join(NEW_PROJECT_PATH, "pracovni", "sektory_group.qml"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "search"))
        copy(os.path.join(TEMPLATES_PATH, "projekt", "search", "sectors.txt"), os.path.join(NEW_PROJECT_PATH, "search"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "search", "gpx"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "search", "shp"))
        copy(os.path.join(TEMPLATES_PATH, "projekt", "search", "shp", "style.qml"), os.path.join(NEW_PROJECT_PATH, "search", "shp"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "search", "temp"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory", "gpx"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory", "shp"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory", "pdf"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory", "html"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "sektory", "styles"))
        for file in glob(os.path.join(TEMPLATES_PATH, "projekt", "sektory", "shp", "*")):
            copy(file, os.path.join(NEW_PROJECT_PATH, "sektory", "shp"))
        for file in glob(os.path.join(TEMPLATES_PATH, "projekt", "sektory", "styles", "*")):
            print(file)
            copy(file, os.path.join(NEW_PROJECT_PATH, "sektory", "styles"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "grassdata"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "grassdata", "jtsk"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "grassdata", "jtsk", "PERMANENT"))
        for file in glob(os.path.join(TEMPLATES_PATH, "grassdata", "jtsk", "PERMANENT", "*")):
            print(file)
            copy(file, os.path.join(NEW_PROJECT_PATH, "grassdata", "jtsk", "PERMANENT"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "grassdata", "wgs84"))
        os.mkdir(os.path.join(NEW_PROJECT_PATH, "grassdata", "wgs84", "PERMANENT"))
        for file in glob(os.path.join(TEMPLATES_PATH, "grassdata", "wgs84", "PERMANENT", "*")):
            copy(file, os.path.join(NEW_PROJECT_PATH, "grassdata", "wgs84", "PERMANENT"))


def transform_coordinates_to_4326(x, y, from_code):
    from_proj = pyproj.Proj("+init=epsg:" + str(from_code))
    to_proj = pyproj.Proj("+init=epsg:4326")
    return pyproj.transform(from_proj, to_proj, x, y)

def extract_line_search_data(source_data_path, target_data_path, xmin, ymin, xmax, ymax):
    if os.path.exists(os.path.join(source_data_path, "line_search", "data.gpkg")) and os.path.exists(target_data_path):
        if not os.path.exists(os.path.join(target_data_path, "line_search")):
            os.mkdir(os.path.join(target_data_path, "line_search"))

        xy_min_wgs84 = transform_coordinates_to_4326(xmin, ymin, 5514)
        xy_max_wgs84 = transform_coordinates_to_4326(xmax, ymax, 5514)
        bbox = (xy_min_wgs84[0], xy_min_wgs84[1], xy_max_wgs84[0], xy_max_wgs84[1])

        # Otevření vstupního a výstupního souboru
        input_file = os.path.join(source_data_path, "line_search", "data.gpkg")
        output_file = os.path.join(target_data_path, "line_search", "data.gpkg")

        # Použití VectorTranslate k výřezu dat
        gdal.VectorTranslate(
            output_file,
            input_file,
            options=gdal.VectorTranslateOptions(
                format='GPKG',  # Formát výstupního souboru
                spatFilter=bbox  # Prostorový filtr na základě BBOXu
            )
        )


def create_project_grass(id, xmin, ymin, xmax, ymax, region):
    KRAJ_DATA_PATH = os.path.join(dataPath, "kraje", region)
    NEW_PROJECT_PATH = os.path.join(serviceDataPath, "projekty", id)
    copyTemplate(NEW_PROJECT_PATH, id, region)
    CR_DATA_PATH = os.path.join(dataPath, "cr")
    extract_line_search_data(CR_DATA_PATH, NEW_PROJECT_PATH, xmin, ymin, xmax, ymax)
    grass_operations.export(KRAJ_DATA_PATH, pluginPath, xmin, ymin, xmax, ymax, NEW_PROJECT_PATH, id)


def get_sectors_grass(id, search_id, coordinates, person_type, percentage):
    with open(os.path.join(serviceDataPath, id + "_coords.json"), "w") as c:
        json.dump(coordinates, c)
    grass_operations.get_sectors_grass(id, search_id, person_type, str(percentage))


def get_sectors_to_return(id):
    if os.path.exists(os.path.join(serviceDataPath, id + "_sectors.geojson")):
        with open(os.path.join(serviceDataPath, id + "_sectors.geojson")) as s:
            return json.load(s)
    else:
        return None


def get_paths_to_return(id):
    if os.path.exists(os.path.join(serviceDataPath, id, "config.json")):
        output = {}
        with open(os.path.join(serviceDataPath, id, "config.json")) as s:
            config = json.load(s)
            output["start_point_user"] = config["start_point"]
            output["end_point_user"] = config["end_point"]
            output["search_path_alternatives"] = []

        directory = os.fsencode(os.path.join(serviceDataPath, id))

        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            if filename.endswith("solution.json"):
                with open(os.path.join(serviceDataPath, id, filename)) as s:
                    solution = json.load(s)
                    output["search_path_alternatives"].append(solution)

        return output
    else:
        return None


def get_report_grass(id):
    grass_operations.report_export(id)
    with open(os.path.join(serviceDataPath, id + "_report.json")) as s:
        return json.load(s)


def create_sector_grass(search_id):
    grass_operations.create_sector(os.path.join(serviceDataPath, "projekty", search_id), search_id)


def delete_sector_grass(sector_id, search_id):
    grass_operations.delete_sector(os.path.join(serviceDataPath, "projekty", search_id), search_id, sector_id)
