import csv, io, math, socket, subprocess, os, sys, uuid
from shutil import copy
from glob import glob
import json
import proc.export as grass_export

pluginPath = "qgis/qgis_patrac"
dataPath = "/data/patracdata/service/data"

def copyTemplate(NEW_PROJECT_PATH, NAMESAFE, region):
    TEMPLATES_PATH = pluginPath + "/templates"
    if not os.path.isdir(NEW_PROJECT_PATH):
        os.mkdir(NEW_PROJECT_PATH)

        # sets the settings to zero, so no radial and no weight limit is used
        os.mkdir(NEW_PROJECT_PATH + "/config")
        settingsPath = "qgis/qgis_patrac_settings"
        copy(settingsPath + "/grass/" + "weightlimit.txt", NEW_PROJECT_PATH + '/config/weightlimit.txt')
        copy(settingsPath + "/grass/" + "maxtime.txt", NEW_PROJECT_PATH + '/config/maxtime.txt')
        copy(settingsPath + "/grass/" + "radialsettings.txt", NEW_PROJECT_PATH + '/config/radialsettings.txt')

        copy(TEMPLATES_PATH + "/projekt/clean_v3.qgs", NEW_PROJECT_PATH + "/" + NAMESAFE + ".qgs")
        os.mkdir(NEW_PROJECT_PATH + "/pracovni")
        for file in glob(TEMPLATES_PATH + '/projekt/pracovni/*'):
            copy(file, NEW_PROJECT_PATH + "/pracovni/")
        with open(NEW_PROJECT_PATH + "/pracovni/region.txt", "w") as r:
            r.write(region)
        copy(NEW_PROJECT_PATH + "/pracovni/sektory_group_selected.dbf",
             NEW_PROJECT_PATH + "/pracovni/sektory_group.dbf")
        copy(NEW_PROJECT_PATH + "/pracovni/sektory_group_selected.shp",
             NEW_PROJECT_PATH + "/pracovni/sektory_group.shp")
        copy(NEW_PROJECT_PATH + "/pracovni/sektory_group_selected.shx",
             NEW_PROJECT_PATH + "/pracovni/sektory_group.shx")
        copy(NEW_PROJECT_PATH + "/pracovni/sektory_group_selected.qml",
             NEW_PROJECT_PATH + "/pracovni/sektory_group.qml")
        os.mkdir(NEW_PROJECT_PATH + "/search")
        copy(TEMPLATES_PATH + "/projekt/search/sectors.txt", NEW_PROJECT_PATH + "/search/")
        os.mkdir(NEW_PROJECT_PATH + "/search/gpx")
        os.mkdir(NEW_PROJECT_PATH + "/search/shp")
        copy(TEMPLATES_PATH + "/projekt/search/shp/style.qml", NEW_PROJECT_PATH + "/search/shp/")
        os.mkdir(NEW_PROJECT_PATH + "/search/temp")
        os.mkdir(NEW_PROJECT_PATH + "/sektory")
        os.mkdir(NEW_PROJECT_PATH + "/sektory/gpx")
        os.mkdir(NEW_PROJECT_PATH + "/sektory/shp")
        os.mkdir(NEW_PROJECT_PATH + "/sektory/pdf")
        os.mkdir(NEW_PROJECT_PATH + "/sektory/html")
        os.mkdir(NEW_PROJECT_PATH + "/sektory/styles")
        for file in glob(TEMPLATES_PATH + "/projekt/sektory/shp/*"):
            copy(file, NEW_PROJECT_PATH + "/sektory/shp/")
        for file in glob(TEMPLATES_PATH + "/projekt/sektory/styles/*"):
            copy(file, NEW_PROJECT_PATH + "/sektory/styles/")
        # copy(TEMPLATES_PATH + "/projekt/sektory/shp/style.qml", NEW_PROJECT_PATH + "/sektory/shp/")
        os.mkdir(NEW_PROJECT_PATH + "/grassdata")
        os.mkdir(NEW_PROJECT_PATH + "/grassdata/jtsk")
        os.mkdir(NEW_PROJECT_PATH + "/grassdata/jtsk/PERMANENT")
        # print TEMPLATES_PATH + '/grassdata/jtsk/PERMANENT'
        for file in glob(TEMPLATES_PATH + '/grassdata/jtsk/PERMANENT/*'):
            # print file
            copy(file, NEW_PROJECT_PATH + "/grassdata/jtsk/PERMANENT/")
        os.mkdir(NEW_PROJECT_PATH + "/grassdata/wgs84")
        os.mkdir(NEW_PROJECT_PATH + "/grassdata/wgs84/PERMANENT")
        for file in glob(TEMPLATES_PATH + '/grassdata/wgs84/PERMANENT/*'):
            copy(file, NEW_PROJECT_PATH + "/grassdata/wgs84/PERMANENT/")

def create_project_grass(id, xmin, ymin, xmax, ymax, region):
    # TODO select right region
    KRAJ_DATA_PATH = "/data/patracdata/kraje/" + region
    NEW_PROJECT_PATH = dataPath + "/projekty/" + id
    copyTemplate(NEW_PROJECT_PATH, id, region)
    # subprocess.Popen(('bash', pluginPath + "/grass/run_export.sh", KRAJ_DATA_PATH, pluginPath,
    #                       str(xmin), str(ymin), str(xmax), str(ymax), NEW_PROJECT_PATH, id))
    grass_export.export(KRAJ_DATA_PATH, pluginPath, str(xmin), str(ymin), str(xmax), str(ymax), NEW_PROJECT_PATH, id)

def get_sectors_grass(id, search_id, coordinates, person_type, percentage):
    with open(dataPath + "/" + id + "_coords.json", "w") as c:
        json.dump(coordinates, c)
    subprocess.Popen(('bash', pluginPath + "/grass/run_area.sh", id, pluginPath, search_id, person_type, str(percentage)))

def get_sectors_to_return(id):
    with open(dataPath + "/" + id + "_sectors.geojson") as s:
        return json.load(s)

def get_report_grass(id):
    p = subprocess.Popen(('bash', pluginPath + "/grass/run_report_export.sh", id, pluginPath))
    p.wait()
    with open(dataPath + "/" + id + "_report.json") as s:
        return json.load(s)

def create_sector_grass(search_id):
    p = subprocess.Popen(('bash', pluginPath + "/grass/run_create_sector.sh", dataPath + "/projekty/" + search_id, pluginPath, search_id))
    p.wait()

def delete_sector_grass(sector_id, search_id):
    p = subprocess.Popen(('bash', pluginPath + "/grass/run_delete_sector.sh", dataPath + "/projekty/" + search_id, pluginPath, sector_id, search_id))
    p.wait()
