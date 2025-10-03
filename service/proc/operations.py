#!/usr/bin/env python
import csv, io, math, socket, subprocess, os, sys, uuid
import json
from .grass_config import *
import fiona
# from fiona.transform import transform_geom
from shapely.ops import transform
from shapely.geometry import mapping, shape
import pyproj
import sqlite3
from sqlite3 import Error

def init_grass(gisdb, location, mapset):
    ########### SOFTWARE
    if sys.platform.startswith('linux'):
        # we assume that the GRASS GIS start script is available and in the PATH
        # query GRASS 7 itself for its GISBASE
        grass7bin = grass7bin_lin
        # query GRASS 7 itself for its GISBASE
        startcmd = [grass7bin, '--config', 'path']

        p = subprocess.Popen(startcmd, shell=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            print("ERROR: Cannot find GRASS GIS 7 start script (%s)" % startcmd)
            sys.exit(-1)
        # print(out)
        # gisbase = out.strip('\n\r')
        gisbase = out.decode('utf-8').strip('\n\r')
    elif sys.platform.startswith('win'):
        grass7bin = grass7bin_win
        gisbase = gisbase_win
    else:
        raise OSError('Platform not configured.')

    # Set GISBASE environment variable
    os.environ['GISBASE'] = gisbase
    # the following not needed with trunk
    os.environ['PATH'] += os.pathsep + os.path.join(gisbase, 'extrabin')
    # add path to GRASS addons
    home = os.path.expanduser("~")
    os.environ['PATH'] += os.pathsep + os.path.join(home, '.grass7', 'addons', 'scripts')

    # define GRASS-Python environment
    gpydir = os.path.join(gisbase, "etc", "python")
    sys.path.append(gpydir)

    # print(sys.path)

    ########### DATA
    # Set GISDBASE environment variable
    os.environ['GISDBASE'] = gisdb

    # import GRASS Python bindings (see also pygrass)
    import grass.script.setup as gsetup
    #from grass.pygrass.modules.shortcuts import raster as r

    ###########
    # launch session
    gsetup.init(gisbase,
                gisdb, location, mapset)

def logInfo(message, ID):
    with open(os.path.join(logsPath, ID + ".log"), "a") as log:
        log.write(message)

def export(datapath, plugin_path, xmin, ymin, xmax, ymax, data_output_path, id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH=datapath
    ID=id
    gisdb = os.path.join(DATAPATH, "grassdata")
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    logInfo("EXPORT STARTED\n5\n", ID)

    PLUGIN_PATH=plugin_path
    XMIN=xmin
    YMIN=ymin
    XMAX=xmax
    YMAX=ymax
    DATAOUTPUTPATH=data_output_path

    #Sets the region for export
    #g.region e=-641060.857143 w=-658275.142857 n=-1036549.0 s=-1046549.0
    try:
        # Removes mask to be ready for another calculations for whole area
        print(gscript.read_command('r.mask', flags="r"))
    except:
        print("MASK NOT USED")
    print(gscript.read_command('g.region', e=XMAX, w=XMIN, n=YMAX, s=YMIN))
    #Exports landuse
    #r.out.ascii input=landuse output=landuse.ascii
    #Bin would be better (size is smaller, export is faster), but there are some problems with import
    print(gscript.read_command('r.out.bin', flags="h", input='landuse', output=os.path.join(DATAOUTPUTPATH, 'grassdata', 'landuse.bin'), overwrite=True))

    logInfo("LANDUSE EXPORTED\n10\n", ID)

    #Exports friction only, without slope, we will use r.walk instead r.cost
    print(gscript.read_command('r.out.bin', flags="h", null=100, input='friction', output=os.path.join(DATAOUTPUTPATH, 'grassdata', 'friction.bin'), overwrite=True))

    logInfo("FRICTION EXPORTED\n20\n", ID)

    #Exports dem, r.walk needs dem to calculate slope in realtime
    print(gscript.read_command('r.out.bin', flags="h", input='dem', output=os.path.join(DATAOUTPUTPATH, 'grassdata', 'dem.bin'), overwrite=True))

    logInfo("DEM EXPORTED\n25\n", ID)

    import_data(DATAOUTPUTPATH, PLUGIN_PATH, XMIN, YMIN, XMAX, YMAX, DATAPATH, ID)

def import_data(datapath, plugin_path, xmin, ymin, xmax, ymax, data_input_path, id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH=datapath
    ID=id
    gisdb = os.path.join(DATAPATH, "grassdata")
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    logInfo("IMPORT STARTED\n30\n", ID)

    PLUGIN_PATH=plugin_path
    XMIN=xmin
    YMIN=ymin
    XMAX=xmax
    YMAX=ymax
    DATAINPUTPATH=data_input_path

    #Sets the region for export
    #g.region e=-641060.857143 w=-658275.142857 n=-1036549.0 s=-1046549.0
    print(gscript.read_command('g.region', e=XMAX, w=XMIN, n=YMAX, s=YMIN, res='5'))

    #Imports landuse
    print(gscript.read_command('r.in.bin', flags="h", bytes=2, output='landuse', input=os.path.join(DATAPATH, 'grassdata', 'landuse.bin'), overwrite=True))
    # Delete the file
    os.remove(os.path.join(DATAPATH, 'grassdata', 'landuse.bin'))

    logInfo("LANDUSE IMPORTED\n35\n", ID)

    #Imports friction
    print(gscript.read_command('r.in.bin', flags="h", bytes=2, anull=100, output='friction', input=os.path.join(DATAPATH, 'grassdata', 'friction.bin'), overwrite=True))
    # Delete the file
    os.remove(os.path.join(DATAPATH, 'grassdata', 'friction.bin'))

    logInfo("FRICTION IMPORTED\n45\n", ID)

    #Imports dem
    print(gscript.read_command('r.in.bin', flags="hf", output='dem', input=os.path.join(DATAPATH, 'grassdata', 'dem.bin'), overwrite=True))
    # Delete the file
    os.remove(os.path.join(DATAPATH, 'grassdata', 'dem.bin'))

    logInfo("DEM IMPORTED\n50\n", ID)

    #If the data are from ZABAGED
    if os.path.isfile(os.path.join(DATAINPUTPATH, 'vektor', 'ZABAGED', 'sectors.shp')):
        print(gscript.read_command('v.in.ogr', output='sectors_group', input=os.path.join(DATAINPUTPATH, 'vektor', 'ZABAGED'), snap=0.01, layer='sectors', spatial=str(XMIN)+','+str(YMIN)+','+str(XMAX)+','+str(YMAX), overwrite=True, flags="o"))
        print(gscript.read_command('r.reclass', input='landuse', output='landuse_type', rules=os.path.join(PLUGIN_PATH, 'grass', 'landuse_type_zbg.rules')))

    logInfo("SECTORS IMPORTED\n55\n", ID)

    logInfo("LANDUSE RECLASSED IMPORTED\n60\n", ID)

    #Adds progress columns
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='"stav INTEGER"', overwrite=True))
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='prostredky VARCHAR(254)', overwrite=True))

    #Computes areas
    # print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='area_ha DOUBLE PRECISION', overwrite=True))
    # print(gscript.read_command('v.to.db', map='sectors_group', layer='1', option='area', units='hectares', columns='area_ha', overwrite=True))
    #Adds label column
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='label VARCHAR(50)', overwrite=True))
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='poznamka VARCHAR(255)', overwrite=True))
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='od_cas VARCHAR(50)', overwrite=True))
    #print(gscript.read_command('v.db.addcolumn', map='sectors_group', layer='1', columns='do_cas VARCHAR(50)', overwrite=True))

    logInfo("ADDED COLUMNS TO SECTORS\n65\n", ID)

    #Exports sectors with comupted areas
    print(gscript.read_command('v.out.ogr', format='ESRI_Shapefile', input='sectors_group', output=os.path.join(DATAPATH, 'pracovni', 'sektory_group_selected.shp'), overwrite=True))
    print(gscript.read_command('v.out.ogr', format='ESRI_Shapefile', input='sectors_group', output=os.path.join(DATAPATH, 'pracovni', 'sektory_group.shp'), overwrite=True))

    logInfo("SECTORS EXPORTED\n100\n", ID)


def get_sectors_grass(id, search_id, person_type, percentage):
    logInfo("STARTED SECTORS EXPORT\n15\n", id)
    with open(os.path.join(dataPath, id + "_coords.json")) as c:
        coords = json.load(c)
    writeAzimuthReclass(0, 0, 0)
    i = 0
    distances_costed_cum = ""
    max_weight = 1
    for coord in coords:
        generateRadialOnPoint(coord)
        result = findAreaWithRadial(coord, i, getPersonTypeId(person_type), search_id)
        error_on_coords = False
        if result is None:
            logInfo("WARNING: ERROR MOVING POINT FROM NULL AREA ON RESULT\n15\n", id)
            error_on_coords = True
        cats_status = checkCats()
        if not cats_status:
            logInfo("WARNING: ERROR MOVING POINT FROM NULL AREA ON CATS\n15\n", id)
            error_on_coords = True
        if error_on_coords:
            findAreaWithRingsOnly(coord, i, getPersonTypeId(person_type), search_id)
        cur_weight = "1"
        if (i == 0):
            distances_costed_cum = "(distances0_costed/" + cur_weight + ")"
        else:
            distances_costed_cum = distances_costed_cum + ",(distances" + str(
                i) + "_costed/" + cur_weight + ")"
        i += 1
    # print "DC: min(" + distances_costed_cum + ")*" + str(max_weight)
    saveDistancesCostedEquation("min(" + distances_costed_cum + ")*" + str(max_weight), search_id)
    createCumulativeArea(search_id)
    getSectors(0, percentage, search_id)
    convertToGeoJSON(id, search_id)
    saveRegion(id, search_id)
    logInfo("SECTORS EXPORTED\n100\n", id)

def getPersonTypeId(person_type):
    # TODO check if the type exists
    types = ["child_1_3", "child_4_6", "child_7_12", "child_13_15", "despondent", "psychical_illness", "retarded", "alzheimer", "tourist", "dementia"]
    return types.index(person_type)

def findAreaWithRadial(coord, id, person_type_id, search_id):
    coords = str(coord[0]) + ',' + str(coord[1])
    # writes coord to file for grass
    with open(os.path.join(pluginPath, 'grass', 'coords.txt'), 'w') as f_coords:
        f_coords.write(coords)
    result = cost_distance(os.path.join(dataPath, 'projekty', search_id), id, person_type_id)
    return result

def findAreaWithRingsOnly(coord, id, person_type_id, search_id):
    coords = str(coord[0]) + ',' + str(coord[1])
    # writes coord to file for grass
    with open(os.path.join(pluginPath, 'grass', 'coords.txt'), 'w') as f_coords:
        f_coords.write(coords)
    result = cost_distance_on_rings(os.path.join(dataPath, 'projekty', search_id), id, person_type_id)
    return result

def getRadialAlpha(i, KVADRANT):
    """Returns angle based on quandrante"""
    alpha = (math.pi / float(2)) - ((math.pi / float(180)) * i)
    if KVADRANT == 2:
        alpha = ((math.pi / float(180)) * i) - (math.pi / float(2))
    if KVADRANT == 3:
        alpha = (3 * (math.pi / float(2))) - ((math.pi / float(180)) * i)
    if KVADRANT == 4:
        alpha = ((math.pi / float(180)) * i) - (3 * (math.pi / float(2)))
    return alpha

def getRadialTriangleX(alpha, CENTERX, xdir, RADIUS):
    """Gets X coordinate of the triangle"""
    dx = xdir * math.cos(alpha) * RADIUS
    x = CENTERX + dx
    return x

def getRadialTriangleY(alpha, CENTERY, ydir, RADIUS):
    """Gets Y coordinate of the triangle"""
    dy = ydir * math.sin(alpha) * RADIUS
    y = CENTERY + dy
    return y

def generateRadialOnPoint(coord):
    """Generates triangles from defined point in step one degree"""
    CENTERX = coord[0]
    CENTERY = coord[1]
    # Radius is set ot 20000 meters to be sure that whole area is covered
    RADIUS = 20000;
    # Writes output to radial.csv
    csv = open(os.path.join(pluginPath, 'grass', 'radial.csv'), "w")
    # Writes in WKT format
    csv.write("id;wkt\n")
    generateRadial(CENTERX, CENTERY, RADIUS, 1, csv)
    generateRadial(CENTERX, CENTERY, RADIUS, 2, csv)
    generateRadial(CENTERX, CENTERY, RADIUS, 3, csv)
    generateRadial(CENTERX, CENTERY, RADIUS, 4, csv)
    csv.close()

def generateRadial(CENTERX, CENTERY, RADIUS, KVADRANT, csv):
    """Generates triangles in defined quadrante"""
    # First quadrante is from 0 to 90 degrees
    # In both axes is coordinates increased
    from_deg = 0
    to_deg = 90
    xdir = 1
    ydir = 1
    # Second quadrante is from 90 to 180 degrees
    # In axe X is coordinate increased
    # In axe Y is coordinate decreased
    if KVADRANT == 2:
        from_deg = 90
        to_deg = 180
        xdir = 1
        ydir = -1
    # Second quadrante is from 180 to 270 degrees
    # In axe X is coordinate decreased
    # In axe Y is coordinate decreased
    if KVADRANT == 3:
        from_deg = 180
        to_deg = 270
        xdir = -1
        ydir = -1
    # Second quadrante is from 270 to 360 degrees
    # In axe X is coordinate decreased
    # In axe Y is coordinate increased
    if KVADRANT == 4:
        from_deg = 270
        to_deg = 360
        xdir = -1
        ydir = 1
    for i in range(from_deg, to_deg):
        alpha = getRadialAlpha(i, KVADRANT);
        x = getRadialTriangleX(alpha, CENTERX, xdir, RADIUS)
        y = getRadialTriangleY(alpha, CENTERY, ydir, RADIUS)
        # Special condtions where one of the axes is on zero direction
        if i == 0:
            x = CENTERX
            y = CENTERY + RADIUS
        if i == 90:
            x = CENTERX + RADIUS
            y = CENTERY
        if i == 180:
            x = CENTERX
            y = CENTERY - RADIUS
        if i == 270:
            x = CENTERX - RADIUS
            y = CENTERY
        # Triangle is written as Polygon
        wkt_polygon = "POLYGON((" + str(CENTERX) + " " + str(CENTERY) + ", " + str(x) + " " + str(y)
        alpha = getRadialAlpha(i + 1, KVADRANT);
        x = getRadialTriangleX(alpha, CENTERX, xdir, RADIUS)
        y = getRadialTriangleY(alpha, CENTERY, ydir, RADIUS)
        # Special condtions where one of the axes is on zero direction
        if i == 89:
            x = CENTERX + RADIUS
            y = CENTERY
        if i == 179:
            x = CENTERX
            y = CENTERY - RADIUS
        if i == 269:
            x = CENTERX - RADIUS
            y = CENTERY
        if i == 359:
            x = CENTERX
            y = CENTERY + RADIUS
        wkt_polygon = wkt_polygon + ", " + str(x) + " " + str(y) + ", " + str(CENTERX) + " " + str(CENTERY) + "))"
        csv.write(str(i) + ";" + wkt_polygon + "\n")

def writeAzimuthReclass(azimuth, tolerance, friction):
    """Creates reclass rules for direction
        Tolerance is for example 30 degrees
        Friction is how frict is the direction
    """
    reclass = open(os.path.join(pluginPath, 'grass', 'azimuth_reclass.rules'), "w")
    tolerance_half = tolerance / 2
    astart = int(azimuth) - tolerance_half
    aend = int(azimuth) + tolerance_half
    if astart < 0:
        astart = 360 + astart
        reclass.write(str(astart) + " thru 360 = 0\n")
        reclass.write("0 thru " + str(aend) + " = 0\n")
        reclass.write("* = " + str(friction) + "\n")
        reclass.write("end\n")
    else:
        if aend > 360:
            aend = aend - 360
            reclass.write(str(astart) + " thru 360 = 0\n")
            reclass.write("0 thru " + str(aend) + " = 0\n")
            reclass.write("* = " + str(friction) + "\n")
            reclass.write("end\n")
        else:
            reclass.write(str(astart) + " thru " + str(aend) + "= 0\n")
            reclass.write("* = " + str(friction) + "\n")
            reclass.write("end\n")
    # reclass.write(str(azimuth) + " " + str(tolerance) + " " + str(friction) + "\n")
    reclass.close()

def checkCats():
    rules_percentage_path = os.path.join(pluginPath, 'grass', 'rules_percentage.txt')
    if os.path.exists(rules_percentage_path):
        try:
            cats = ["= 10", "= 20", "= 30", "= 40", "= 50", "= 60", "= 70", "= 80", "= 95"]
            cats_count = 0
            with open(rules_percentage_path) as f:
                lines = f.readlines()
                for line in lines:
                    for cat in cats:
                        if cat in line:
                            cats_count += 1
            if cats_count != len(cats):
                return False
            else:
                return True
        except:
            return False
    else:
        return False

def saveDistancesCostedEquation(distances_costed_cum, search_id):
    f = open(os.path.join(dataPath, 'projekty', search_id, 'pracovni', 'distancesCostedEquation.txt'), 'w')
    f.write(distances_costed_cum)
    f.close()

def createCumulativeArea(search_id):
    DATAPATH = os.path.join(dataPath, 'projekty', search_id)
    if os.path.isfile(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tif.aux.xml')):
        os.remove(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tif.aux.xml'))
    if os.path.isfile(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tif')):
        os.remove(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tif'))
    if os.path.isfile(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tfw')):
        os.remove(os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tfw'))

    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    DISTANCES = open(os.path.join(DATAPATH, 'pracovni', 'distancesCostedEquation.txt'), 'r').read()

    #Gets all distances costed created in cost_distance and reads minimum value from it
    #I think that now this is not necessary, because we use only one start point so the DISTANCES has only one layer
    #But this can be used in future in a case when there are more than one input point
    print(gscript.read_command('r.mapcalc', expression='distances_costed_cum = ' + DISTANCES, overwrite=True))
    #Exports output to the GeoTIFF format
    print(gscript.read_command('r.out.gdal', input='distances_costed_cum', output=os.path.join(DATAPATH, 'pracovni', 'distances_costed_cum.tif'), type='Float64', createopt='PROFILE=BASELINE,TFW=YES', overwrite=True))



def getSectors(min, max, search_id):
    """Selects sectors from grass database based on filtered raster"""

    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH = os.path.join(dataPath, 'projekty', search_id)
    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    MIN=str(min)
    MAX=str(max)
    print("MIN/MAX:" +  MIN + " " + MAX)

    # print(gscript.read_command('v.in.ogr', output='sectors_group_modified', input=DATAPATH +'/pracovni', layer='sektory_group', snap=0.01, overwrite=True, flags="o"))
    print(gscript.read_command('r.mapcalc', expression='distances_costed_cum_selected = if(distances_costed_cum<='+MIN+'||distances_costed_cum>='+MAX+', null(), 1)', overwrite=True))
    print(gscript.read_command('r.to.vect', input='distances_costed_cum_selected',  output='distances_costed_cum_selected', type='area', overwrite=True))
    print(gscript.read_command('v.select', ainput='sectors_group', binput='distances_costed_cum_selected', output='sektory_group_selected', overwrite=True))
    #Linux
    #print gscript.read_command('v.out.ogr', input='sektory_group_selected', output=DATAPATH +'/pracovni/', overwrite=True)
    #Windows
    print(gscript.read_command('v.out.ogr', format='ESRI_Shapefile', input='sektory_group_selected', output=os.path.join(DATAPATH, 'pracovni', 'sektory_group_selected.shp'), overwrite=True))
    print(gscript.read_command('v.out.ogr', format='CSV', input='sektory_group_selected', output=os.path.join(DATAPATH, 'pracovni', 'sektory_group_selected.csv'), overwrite=True))

def convertToGeoJSON(id, search_id):
    features = []

    with fiona.open(os.path.join(dataPath, 'projekty', search_id, 'pracovni', 'sektory_group_selected.shp'), "r") as sectors:

        wgs84 = "EPSG:4326"
        jtsk = {"init": "epsg:5514", "towgs84": "570.8,85.7,462.8,4.998,1.587,5.261,3.56"}

        wgs84_crs = pyproj.CRS(wgs84)
        jtsk_crs = pyproj.CRS(jtsk)

        for sector in sectors:
            # print(sector)
            # This does not work correctly - it switches lat, lon
            # geom_transformed = transform_geom(jtsk, wgs84, sector["geometry"])
            project = pyproj.Transformer.from_crs(jtsk_crs, wgs84_crs, always_xy=True).transform
            geom_transformed = transform(project, shape(sector["geometry"]))
            props = sector['properties']

            feature = {
                "geometry": mapping(geom_transformed),
                "properties": {"id": props["id"], "label": props["label"], "typ": props["typ"], "area_ha": props["area_ha"]}
            }
            features.append(feature)

    schema1 = {"geometry": "Unknown", "properties": [("id", "str"), ("label", "str"), ("typ", "str"), ("area_ha", "float")]}

    # attempt to overwrite it with a valid file
    with fiona.open(os.path.join(dataPath, id + "_sectors.geojson"), "w", driver="GeoJSON", schema=schema1) as dst:
        dst.writerecords(features)

    # This does not work on Windows Python 3.10
    # with open(dataPath + "/" + id + "_sectors.geojson", "w") as out:
    #     json.dump(data, out)

def saveRegion(id, search_id):
    with open(os.path.join(dataPath, 'projekty', search_id, 'pracovni', 'region.txt')) as r:
        region = r.read().rstrip()
        with open(os.path.join(dataPath, id + "_sectors.geojson")) as g:
            data = json.load(g)
            data['metadata'] = {}
            data['metadata']['region'] = region
            data['metadata']['search_id'] = search_id

    with open(os.path.join(dataPath, id + "_sectors.geojson"), "w") as out:
        json.dump(data, out)

def move_from_null(data_path):

    PLUGIN_PATH=pluginPath
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    gisdb = os.path.join(data_path, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    print("Moving from null")
    # if the min value is null
    print(gscript.read_command('r.mapcalc', expression='friction_null_rec=if(isnull(friction), 1, null())',
                               overwrite=True))
    print(gscript.read_command('r.buffer', input='friction_null_rec', output='friction_null_rec_buf_10', distances='10',
                               overwrite=True))
    print(gscript.read_command('r.null', map='friction_null_rec_buf_10', setnull='1', overwrite=True))
    print(gscript.read_command('r.mapcalc', expression='friction_flat=1', overwrite=True))
    print(gscript.read_command('r.cost', input='friction_flat', output='friction_flat_cost', start_points='coords',
                               overwrite=True))
    print(gscript.read_command('r.mapcalc',
                               expression='friction_flat_cost_buf=friction_flat_cost*friction_null_rec_buf_10',
                               overwrite=True))
    stats2 = gscript.parse_command('r.univar', map='friction_flat_cost_buf', flags='g')
    try:
        # Reads min value
        MIN = float(stats2['min'])
        with open(os.path.join(PLUGIN_PATH, 'grass', 'move.rules'), 'w') as f:
            f.write(str(MIN) + ' = 1\n')
            f.write('* = null\n')
            f.write('end')

        print(gscript.read_command('r.reclass', input='friction_flat_cost_buf', output='coords',
                                   rules=os.path.join(PLUGIN_PATH, 'grass', 'move.rules'), overwrite=True))
        print(gscript.read_command('r.to.vect', input='coords', output='coords', type='point', overwrite=True))
    except:
        print("Problem with moving of the point from null area")

def cost_distance(data_path, id, person_type_id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH=data_path
    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    PLUGIN_PATH=pluginPath
    PLACE_ID=str(id)
    TYPE=int(person_type_id)

    try:
        print(gscript.read_command('r.mask', flags="r"))
    except:
        print("NO MASK")

    #Removes reclass rules
    rules_percentage_path = os.path.join(PLUGIN_PATH, 'grass', 'rules_percentage.txt')
    if os.path.exists(rules_percentage_path):
        os.remove(rules_percentage_path)

    #Reads coords from coords.txt written by patracdockwidget.getArea
    print(gscript.read_command('g.remove', type='vector', name='coords'))
    print(gscript.read_command('g.remove', type='raster', name='coords'))
    print(gscript.read_command('v.in.ascii', input=os.path.join(PLUGIN_PATH, 'grass', 'coords.txt'), output='coords', separator='comma' , overwrite=True))
    #Converts to the raster
    print(gscript.read_command('v.to.rast', input='coords', output='coords', use='cat' , overwrite=True))

    #Tests if the coord is not in null area
    print(gscript.read_command('r.mapcalc', expression='coords_friction=friction * coords', overwrite=True))
    stats = gscript.parse_command('r.univar', map='coords_friction', flags='g')

    try:
        # Reads min value
        MIN = float(stats['min'])
        print("MINIMUM: " + str(MIN))
        if str(MIN) == "nan":
            move_from_null(data_path)
    except:
        move_from_null(data_path)


    #Reads radial CSV with WKT of triangles writtent by patracdockwidget.generateRadialOnPoint
    print(gscript.read_command('v.in.ogr', input=os.path.join(PLUGIN_PATH, 'grass', 'radial.csv'), output='radial', flags='o' , overwrite=True))
    #Converts triangles to raster
    print(gscript.read_command('v.to.rast', input='radial', output='radial', use='cat', overwrite=True))
    #Reclass triangles according to rules created by patracdockwidget.writeAzimuthReclass
    print(gscript.read_command('r.reclass', input='radial', output='radial' + PLACE_ID, rules=os.path.join(PLUGIN_PATH, 'grass', 'azimuth_reclass.rules'), overwrite=True))
    #Combines friction_slope with radial (direction)
    print(gscript.read_command('r.mapcalc', expression='friction_radial' + PLACE_ID + ' = friction + radial' + PLACE_ID, overwrite=True))

    #Reads distances from distances selected (or defined) by user
    distances_f=open(os.path.join(PLUGIN_PATH, 'grass', 'distances.txt'))
    lines=distances_f.readlines()
    DISTANCES=lines[TYPE-1]

    #Distances methodology
    print(gscript.read_command('r.buffer', input='coords', output='distances' + PLACE_ID, distances=DISTANCES , overwrite=True))
    #Friction methodology
    print(gscript.read_command('r.walk', friction='friction_radial' + PLACE_ID, elevation='dem', output='cost' + PLACE_ID, start_points='coords' , overwrite=True))

    #Creates new reclass rules
    rules_percentage_f = open(rules_percentage_path, 'w')
    #Creates empty raster with zero values
    print(gscript.read_command('r.mapcalc', expression='distances' + PLACE_ID + '_costed = 0', overwrite=True))

    # we have to start on cat 3, so on min of the ring for 20%
    cat=3
    #Percentage for distances
    variables = [10, 20, 30, 40, 50, 60, 70, 80]
    PREVMIN = 0
    for i in variables:
        print(i)
        #Writes rules for the category so we have only one ring in the output
        with open(os.path.join(PLUGIN_PATH, 'grass', 'rules.txt'), 'w') as f:
            f.write(str(cat) + ' = 1\n')
            f.write('end')

        #Gets only one ring
        print(gscript.read_command('r.reclass', input='distances' + PLACE_ID, output='distances' + PLACE_ID + '_' + str(i), rules=PLUGIN_PATH + '/grass/rules.txt', overwrite=True))
        #Combines ring with friction (cost algorithm result)
        print(gscript.read_command('r.mapcalc', expression='cost' + PLACE_ID + '_distances_' + str(i) + ' = distances' + PLACE_ID + '_' + str(i) + ' * cost' + PLACE_ID, overwrite=True))
        #Gets basic statistics for cost values in ring
        stats = gscript.parse_command('r.univar', map='cost' + PLACE_ID + '_distances_' + str(i), flags='g')
        #print stats
        try:
            #Reads min value
            MIN = float(stats['min'])
            print(str(MIN))
            #Reads max value
            MAX = float(stats['max'])
            print(str(MAX))
            #Minimum value and maximum value is used as extent for relass of the whole cost layer
            #rules_percentage_f.write(str(MIN) + ' thru ' + str(MAX) + ' = ' + str(i) + '\n')
            if str(PREVMIN) != 'nan' and str(MIN) != 'nan':
                rules_percentage_f.write(str(PREVMIN) + ' thru ' + str(MIN) + ' = ' + str(i) + '\n')
            else:
                return None
            PREVMIN = MIN
        except:
            print("Problem with category " + str(cat) + " " + str(i) + "%")
            return None
        cat = cat + 1

    #Add 95% category
    if str(PREVMIN) != 'nan' and str(MAX) != 'nan':
        rules_percentage_f.write(str(PREVMIN) + ' thru ' + str(MAX) + ' = 95\n')
    else:
        return None

    #Finish reclass rules
    rules_percentage_f.write('end')
    rules_percentage_f.close()

    #Finaly reclass whole cost layer based on min and max values for each ring
    print(gscript.read_command('r.reclass', input='cost' + PLACE_ID, output='distances' + PLACE_ID + '_costed', rules=os.path.join(PLUGIN_PATH, 'grass', 'rules_percentage.txt'), overwrite=True))

    return "CALCULATED"

def cost_distance_on_rings(data_path, id, person_type_id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH=data_path
    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    PLUGIN_PATH=pluginPath
    PLACE_ID=str(id)
    TYPE=int(person_type_id)

    try:
        print(gscript.read_command('r.mask', flags="r"))
    except:
        print("NO MASK")

    #Removes reclass rules
    rules_percentage_path = os.path.join(PLUGIN_PATH, 'grass', 'rules_percentage.txt')
    if os.path.exists(rules_percentage_path):
        os.remove(rules_percentage_path)

    #Reads coords from coords.txt written by patracdockwidget.getArea
    print(gscript.read_command('g.remove', type='vector', name='coords'))
    print(gscript.read_command('g.remove', type='raster', name='coords'))
    print(gscript.read_command('v.in.ascii', input=os.path.join(PLUGIN_PATH, 'grass', 'coords.txt'), output='coords', separator='comma' , overwrite=True))
    #Converts to the raster
    print(gscript.read_command('v.to.rast', input='coords', output='coords', use='cat' , overwrite=True))

    #Reads distances from distances selected (or defined) by user
    distances_f=open(os.path.join(PLUGIN_PATH, 'grass', 'distances.txt'))
    lines=distances_f.readlines()
    DISTANCES=lines[TYPE-1]

    #Distances methodology
    print(gscript.read_command('r.buffer', input='coords', output='distances' + PLACE_ID, distances=DISTANCES , overwrite=True))

    #Creates new reclass rules
    rules_percentage_f = open(rules_percentage_path, 'w')
    #Creates empty raster with zero values
    print(gscript.read_command('r.mapcalc', expression='distances' + PLACE_ID + '_costed = 0', overwrite=True))

    # we have to start on cat 3, so on min of the ring for 20%
    cat=3
    #Percentage for distances
    rules_percentage_f.write('1 = 10\n')
    rules_percentage_f.write('2 = 10\n')
    rules_percentage_f.write('3 = 20\n')
    rules_percentage_f.write('4 = 30\n')
    rules_percentage_f.write('5 = 40\n')
    rules_percentage_f.write('6 = 50\n')
    rules_percentage_f.write('7 = 60\n')
    rules_percentage_f.write('8 = 70\n')
    rules_percentage_f.write('9 = 80\n')
    rules_percentage_f.write('10 = 95\n')
    #Finish reclass rules
    rules_percentage_f.write('end')
    rules_percentage_f.close()

    print(gscript.read_command('r.reclass', input='distances' + PLACE_ID, output='distances' + PLACE_ID + '_costed', rules=os.path.join(PLUGIN_PATH, 'grass', 'rules_percentage.txt'), overwrite=True))

    return "CALCULATED"

def fixUt(ut):
    if ut == 0:
        print("The unit speed value is set to 0, this is not correct. Returning 1.")
        return 1
    else:
        return ut

def getReportItems(feature):
    # Returns type of the search landuse based on landuse type
    # 1 volný schůdný bez porostu
    # 2 volný schůdný s porostem
    # 3 volný obtížně schůdný
    # 4 porost lehce průchozí
    # 5 porost obtížně průchozí
    # 6 zastavěné území měst a obcí
    # 7 městské parky a hřiště s pohybem osob
    # 8 městské parky a hřiště bez osob
    # 9 vodní plocha
    # 10 ostatní plochy
    types = [
        ['ODPOCI', 'OSPLSI', 'TRTRPO'],
        ['ORNAPU', 'SADZAH'],
        ['KOLEJI', 'POTELO', 'SKLADK'],
        ['LPSTROM', 'VINICE', 'CHMELN'],
        ['LPKOSO', 'LPKROV', 'MAZCHU'],
        ['AREZAS', 'ARUCZA', 'HRBITO', 'PRSTPR', 'ROZTRA', 'ROZZRI', 'ULOMIS', 'USNAOD', 'INTRAV'],
        ['ZAHPAR'],
        [],
        ['VODPLO'],
        ['ELEKTR', 'LETISTE', 'OTHER'],
    ]
    selected_type = 10
    id = 1
    for type in types:
        if feature["properties"]['typ'] in type:
            selected_type = id
        id += 1
    stats = str(selected_type) + '||' + str(feature["properties"]['area_ha'] * 10000) + '|100%'
    return [stats]

def get_units_report(ID, surfaces):
    # Reads numbers for existing search units from units.txt
    units_counts = []

    fileInput = open(os.path.join(settingsPath, 'grass', 'units.txt'), mode="r")

    for row in csv.reader(fileInput, delimiter=';'):
        # unicode_row = [x.decode('utf8') for x in row]
        unicode_row = row
        cur_count = int(unicode_row[0])
        units_counts.append(cur_count)

    fileInput.close()

    surfaces_int = [int(math.ceil(v)) for v in surfaces]

    unitsTimesPath = os.path.join(settingsPath, 'grass', 'units_times.csv')
    fileInput = open(unitsTimesPath, mode="r")

    # Reads CSV and populates the array
    unitsTimes = []
    for row in csv.reader(fileInput, delimiter=';'):
        row_out = []
        for field in row:
            row_out.append(float(field))
        unitsTimes.append(row_out)

    units_areas = []
    if units_counts[5] > 0:
        # We have a drone
        units_areas.append(int(math.ceil(surfaces[2] + surfaces[3] + surfaces[4] + surfaces[7]))) # handlers
        units_areas.append(int(math.ceil(surfaces[5] + surfaces[6] + surfaces[9]))) # phalanx
        units_areas.append(0) # No terrain_vehicles yet
        units_areas.append(0) # No road_vehicles yet
        units_areas.append(0) # No horses yet
        units_areas.append(int(math.ceil(surfaces[0] + surfaces[1]))) # Drones
        units_areas.append(0) # No Helicopters yet
        units_areas.append(0) # No boats
        units_areas.append(int(math.ceil(surfaces[8]))) # Divers
        units_areas.append(0) # No other
    else:
        # We do not have a drone
        units_areas.append(int(math.ceil(surfaces[0] + surfaces[1] + surfaces[2] + surfaces[3] + surfaces[4] + surfaces[7]))) # handlers
        units_areas.append(int(math.ceil(surfaces[5] + surfaces[6] + surfaces[9]))) # phalanx
        units_areas.append(0) # No terrain_vehicles yet
        units_areas.append(0) # No road_vehicles yet
        units_areas.append(0) # No horses yet
        units_areas.append(0) # Drones
        units_areas.append(0) # No Helicopters yet
        units_areas.append(0) # No boats
        units_areas.append(int(math.ceil(surfaces[8]))) # Divers
        units_areas.append(0) # No other

    units_times = []
    # handlers
    if units_counts[0] > 0:
        if units_counts[5] > 0:
            # We have a drone
            P3_P5_KPT = float(surfaces[2]) / fixUt(unitsTimes[2][0]) + float(surfaces[4]) / fixUt(unitsTimes[4][0])
            P4_P8_KPT = float(surfaces[3]) / fixUt(unitsTimes[3][0]) + float(surfaces[7]) / fixUt(unitsTimes[7][0])
            units_times.append(int(math.ceil((P3_P5_KPT + P4_P8_KPT) / float(units_counts[0]))))
        else:
            # We do not have a drone
            P2_P3_P5_KPT = float(surfaces[1]) / fixUt(unitsTimes[1][0]) + float(surfaces[2]) / fixUt(unitsTimes[2][0]) + float(surfaces[4]) / fixUt(unitsTimes[4][0])
            P1_P4_P8_KPT = float(surfaces[0]) / fixUt(unitsTimes[0][0]) + float(surfaces[3]) / fixUt(unitsTimes[3][0]) + float(surfaces[7]) / fixUt(unitsTimes[7][0])
            units_times.append(int(math.ceil((P2_P3_P5_KPT + P1_P4_P8_KPT) / float(units_counts[0]))))
    else:
        units_times.append(-99)

    # pedestrians
    if units_counts[1] > 0:
        P6_P7_P10_PT = float(surfaces[5]) / fixUt(unitsTimes[5][1]) + float(surfaces[6]) / fixUt(unitsTimes[6][1]) + float(surfaces[9]) / fixUt(unitsTimes[9][1])
        units_times.append(int(math.ceil(P6_P7_P10_PT / float(units_counts[1]))))
    else:
        units_times.append(-99)

    units_times.append(-99) # No terrain_vehicles yet
    units_times.append(-99) # No road_vehicles yet
    units_times.append(-99) # No horse_riders

    # Drone
    if units_counts[5] > 0:
        P1_P2_APT = float(surfaces[0]) / fixUt(unitsTimes[0][5]) + float(surfaces[1]) / fixUt(unitsTimes[1][5])
        units_times.append(int(math.ceil(P1_P2_APT / float(units_counts[5]))))
    else:
        units_times.append(-99)

    units_times.append(-99) # No helicopters
    units_times.append(-99) # No boats

    # Diver
    if units_counts[8] > 0:
        P9_VPT = float(surfaces[8]) / fixUt(unitsTimes[8][8])
        units_times.append(int(math.ceil(P9_VPT / float(units_counts[8]))))
    else:
        units_times.append(-99)

    units_times.append(-99) # No other yet

    # Second variant
    # drone for P1, P2 if is available else phalanx for P1, P2
    # phalanx for P3, P4, P5, P6, P7, P8, P10
    # diver for P9

    units_areas_alternatives = []
    if units_counts[5] > 0:
        # We have a drone
        units_areas_alternatives.append(0) # handlers
        units_areas_alternatives.append(int(math.ceil(surfaces[2] + surfaces[3] + surfaces[4] + surfaces[5] + surfaces[6] + surfaces[7] + surfaces[9]))) # phalanx
        units_areas_alternatives.append(0) # No terrain_vehicles
        units_areas_alternatives.append(0) # No road_vehicles
        units_areas_alternatives.append(0) # No horse_riders
        units_areas_alternatives.append(int(math.ceil(surfaces[0] + surfaces[1]))) # Drones
        units_areas_alternatives.append(0) # No helicopters
        units_areas_alternatives.append(0) # No boats
        units_areas_alternatives.append(int(math.ceil(surfaces[8]))) # Divers
        units_areas_alternatives.append(0) # No other
    else:
        # We do not have a drone
        units_areas_alternatives.append(0) # handlers
        units_areas_alternatives.append(int(math.ceil(surfaces[0] + surfaces[1] + surfaces[2] + surfaces[3] + surfaces[4] + surfaces[5] + surfaces[6] + surfaces[7] + surfaces[9]))) # phalanx
        units_areas_alternatives.append(0) # No terrain_vehicles
        units_areas_alternatives.append(0) # No road_vehicles
        units_areas_alternatives.append(0) # No horse_riders
        units_areas_alternatives.append(0) # Drones
        units_areas_alternatives.append(0) # No helicopters
        units_areas_alternatives.append(0) # No boats
        units_areas_alternatives.append(int(math.ceil(surfaces[8]))) # Divers
        units_areas_alternatives.append(0) # No other

    maxtime = 3
    if os.path.isfile(os.path.join(settingsPath, 'grass', 'maxtime.txt')):
        try:
            maxtime = int(open(os.path.join(settingsPath, 'grass', 'maxtime.txt'), 'r').read())
        except ValueError:
            maxtime = 3

    if maxtime <= 0:
        maxtime = 3

    units_necessary = []

    P3_P5_KPT = float(surfaces[2]) / fixUt(unitsTimes[2][0]) + float(surfaces[4]) / fixUt(unitsTimes[4][0])
    P4_P8_KPT = float(surfaces[3]) / fixUt(unitsTimes[3][0]) + float(surfaces[7]) / fixUt(unitsTimes[7][0])
    units_necessary.append(int(math.ceil((P3_P5_KPT + P4_P8_KPT) / float(maxtime)))) # handlers

    P6_P7_P10_PT = float(surfaces[5]) / fixUt(unitsTimes[5][1]) + float(surfaces[6]) / fixUt(unitsTimes[6][1]) + float(surfaces[9]) / fixUt(unitsTimes[9][1])
    units_necessary.append(int(math.ceil(P6_P7_P10_PT / float(maxtime)))) # pedestrians

    units_necessary.append(0) # No terrain_vehicles yet
    units_necessary.append(0) # No road_vehicles yet
    units_necessary.append(0) # No horse_riders yet

    P1_P2_APT = float(surfaces[0]) / fixUt(unitsTimes[0][5]) + float(surfaces[1]) / fixUt(unitsTimes[1][5])
    units_necessary.append(int(math.ceil(P1_P2_APT / float(maxtime)))) # drones

    units_necessary.append(0) # No helicopter yet
    units_necessary.append(0) # No boat yet

    P9_VPT = float(surfaces[8]) / fixUt(unitsTimes[8][8])
    units_necessary.append(int(math.ceil(P9_VPT / float(maxtime))))

    units_necessary.append(0) # No other yet

    report = {
        "id": ID,
        "report": {
            "surfaces": surfaces_int,
            "units_areas": units_areas,
            "units_areas_alternatives": units_areas_alternatives,
            "units_times": units_times,
            "units_necessary": units_necessary
        }
    }

    return report

def report_export(id):
    ID = id

    with open(os.path.join(dataPath, ID + "_sectors.geojson")) as g:
        geojson = json.load(g)

    DATAPATH = os.path.join(dataPath, 'projekty', geojson["metadata"]["search_id"])
    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    print(gscript.read_command('v.in.ogr', output='sektory_group_selected_modified', input=os.path.join(DATAPATH, 'pracovni'), snap=0.01, layer='sektory_group_selected', overwrite=True, flags="o"))

    # Sets area of areas to zero
    SUM_P1 = 0
    SUM_P2 = 0
    SUM_P3 = 0
    SUM_P4 = 0
    SUM_P5 = 0
    SUM_P6 = 0
    SUM_P7 = 0
    SUM_P8 = 0
    SUM_P9 = 0
    SUM_P10 = 0

    # conn = None
    # try:
    #     conn = sqlite3.connect(os.path.join(patracDataPath, 'kraje', geojson["metadata"]["region"], 'vektor', 'ZABAGED', 'line_x', 'stats.db'))
    # except Error as e:
    #     # TODO this is not good way
    #     sys.exit()

    # Loops via all selected search sectors based on number of sectors
    for feature in geojson["features"]:
        # print(feature["properties"]["id"])
        # vybrani jednoho sektoru dle poradi
        # Selects one sector based on order (attribute cats is from 1 to number of items)
        # print gscript.read_command('v.extract', input='sektory_group_selected_modified', output='sektory_group_selected_modified_' + str(i), where="cat='"+str(i)+"'", overwrite=True)
        # ziskani atributu plocha a label
        # Gets attribute plocha (area) and label
        # VALUES=gscript.read_command('v.db.select', map='sektory_group_selected_modified_' + str(i), columns='label,area_ha', flags="c")
        # Pipe is delimiter of v.db.select output
        # VALUESITEMS=VALUES.split('|')

        # zamaskovani rastru s vyuzitim polygonu sektoru
        # Mask working area based on are of current sector
        REPORT = ""
        #print(DATAPATH + "/../../vektor/ZABAGED/line_x/" + LABELS[i-1] + ".stats")
        # if not conn is None:
        #     try:
        #         c = conn.cursor()
        #         c.execute("SELECT def_text FROM stats WHERE id = '" + feature["properties"]["id"] + "'")
        #         row = c.fetchone()
        #         if row is not None:
        #             REPORT = row[0]
        #         c.close()
        #     except:
        #         if c is not None:
        #             c.close()

        # TODO maybe include in the final version
        # if not REPORT == "":
        #     print(REPORT)
        # else:
        #     print(gscript.read_command('r.mask', vector='sektory_group_selected_modified', where="id='" + feature["properties"]["id"] + "'",
        #                                overwrite=True))
        #
        #     # ziskani reportu - procenta ploch v sektoru
        #     # Gets stats for landuse areas in masked region
        #     REPORT = gscript.read_command('r.stats', input='landuse_type', separator='pipe', flags='plna')
        #     #print(REPORT)
        #
        # if REPORT == "":
        #     print("ERROR ON " + feature["properties"]["id"])
        #     continue

        # Sets areas of types of areas to zero
        # TODO - vyjasnit zarazeni typu + mozna pouzit i letecke snimky - nejaká jednoduchá automaticka rizena klasifikace
        P1 = 0  # volny schudny bez porostu (louky, pole ) - nejsem schopen zatim z dat identifikovat, mozna dle data patrani, v zime bude pole bez porostu a louka asi taky
        P2 = 0  # volny schudny s porostem (louky, pole ) - zatim tedy bude vse s porostem
        P3 = 0  # volny obtizne schudny (hory, skaly, lomy) - v prostoru mam lomy, skaly asi taky nejsem zatim schopen identifikovat
        P4 = 0  # porost lehce pruchozi (les bez prekazek) - asi vsechn les, kde neni krovi
        P5 = 0  # porost obtizne pruchozi (houstiny, skaly) - asi les s krovinami
        P6 = 0  # zastavene uzemi mest a obci
        P7 = 0  # mestske parky a hriste s pohybem osob - pohyb osob nejsem schopen posoudit, tedy asi co je zahrada bude bez pohybu a co je park bude s pohybem
        P8 = 0  # mestske parky a hriste bez osob
        P9 = 0  # vodni plocha
        P10 = 0  # ostatni

        REPORTITEMS = getReportItems(feature)
        # REPORTITEMS = REPORT.splitlines(False)

        # Decides for each type of area from REPORT in which category belongs
        try:
            for REPORTITEM in REPORTITEMS:
                REPORTITEMVALUES = REPORTITEM.split('|')
                if REPORTITEMVALUES[0] == '1':
                    P1 = P1 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P1 = SUM_P1 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '2':
                    P2 = P2 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P2 = SUM_P2 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '3':
                    P3 = P3 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P3 = SUM_P3 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '4':
                    P4 = P4 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P4 = SUM_P4 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '5':
                    P5 = P5 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P5 = SUM_P5 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '6':
                    P6 = P6 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P6 = SUM_P6 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '7':
                    P7 = P7 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P7 = SUM_P7 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '8':
                    P8 = P8 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P8 = SUM_P8 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '9':
                    P9 = P9 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P9 = SUM_P9 + float(REPORTITEMVALUES[2])
                if REPORTITEMVALUES[0] == '10':
                    P10 = P10 + float(REPORTITEMVALUES[3].split('%')[0])
                    SUM_P10 = SUM_P10 + float(REPORTITEMVALUES[2])
        except ValueError:
            print("The statistic for current sector is invalid, can not compute.")

        # Corect 100%
        if P1 > 100:
            P1 = 100
        if P2 > 100:
            P2 = 100
        if P3 > 100:
            P3 = 100
        if P4 > 100:
            P4 = 100
        if P5 > 100:
            P5 = 100
        if P6 > 100:
            P6 = 100
        if P7 > 100:
            P7 = 100
        if P8 > 100:
            P8 = 100
        if P9 > 100:
            P9 = 100
        if P10 > 100:
            P10 = 100

    # if not conn is None:
    #     conn.close()

    try:
        # Removes mask to be ready for another calculations for whole area
        print(gscript.read_command('r.mask', flags="r"))
    except:
        print("MASK NOT USED")

    # Sets area to ha
    SUM_P1 = SUM_P1 / float(10000)
    SUM_P2 = SUM_P2 / float(10000)
    SUM_P3 = SUM_P3 / float(10000)
    SUM_P4 = SUM_P4 / float(10000)
    SUM_P5 = SUM_P5 / float(10000)
    SUM_P6 = SUM_P6 / float(10000)
    SUM_P7 = SUM_P7 / float(10000)
    SUM_P8 = SUM_P8 / float(10000)
    SUM_P9 = SUM_P9 / float(10000)
    SUM_P10 = SUM_P10 / float(10000)

    surfaces_float = [
        SUM_P1,
        SUM_P2,
        SUM_P3,
        SUM_P4,
        SUM_P5,
        SUM_P6,
        SUM_P7,
        SUM_P8,
        SUM_P9,
        SUM_P10
    ]

    report = get_units_report(ID, surfaces_float)

    with open(os.path.join(dataPath, ID + "_report.json"), "w") as r:
        json.dump(report, r)


def create_sector(data_path, search_id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH = data_path
    gisdb = os.path.join(DATAPATH,  'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    ID = search_id

    logInfo("\nCREATE OF SECTOR IN SEARCH " + ID + " STARTED\n10\n", ID)

    try:
        print(gscript.read_command('v.in.ogr', output='sectors_group', input=os.path.join(DATAPATH, 'pracovni'), snap=0.01, layer='sektory_group', overwrite=True, flags="o"))
    except Exception as e:
        logInfo(str(e) + "\nERROR IN CREATE OF SECTOR IN SEARCH " + ID + "\n-1", ID)
        exit(1)

    logInfo("CREATE OF SECTOR IN SEARCH " + ID + " FINISHED\n100\n", ID)

def delete_sector(data_path, search_id, sector_id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH = data_path
    gisdb = os.path.join(DATAPATH, 'grassdata')
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    ID = search_id
    SECTOR_ID = sector_id

    logInfo("\nDELETE OF " + SECTOR_ID + " IN SEARCH " + ID + " STARTED\n10\n", ID)

    try:
        print(gscript.read_command('v.edit', map='sectors_group', tool='delete', where="id = '" + SECTOR_ID + "'"))
        print(gscript.read_command('v.out.ogr', format='ESRI_Shapefile', input='sectors_group', output=os.path.join(DATAPATH, 'pracovni', 'sektory_group.shp'), overwrite=True))
    except Exception as e:
        logInfo(str(e) + "\nERROR IN DELETE OF " + SECTOR_ID + " IN SEARCH " + ID + "\n-1", ID)
        exit(1)

    logInfo("DELETE OF " + SECTOR_ID + " IN SEARCH " + ID + " FINISHED\n100\n", ID)
