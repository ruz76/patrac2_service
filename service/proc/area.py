import csv, io, math, socket, subprocess, os, sys, uuid
import json

pluginPath = "qgis/qgis_patrac"
dataPath = "/data/patracdata/service/data"
logsPath = "/data/patracdata/service/logs"

def get_sectors_grass(id, search_id, person_type, percentage):
    with open(logsPath + "/" + id + ".log", "a") as log:
        log.write("JUST TEST\n15\n")
    with open(dataPath + "/" + id + "_coords.json") as c:
        coords = json.load(c)
    writeAzimuthReclass(0, 0, 0)
    i = 0
    distances_costed_cum = ""
    max_weight = 1
    for coord in coords:
        generateRadialOnPoint(coord)
        findAreaWithRadial(coord, i, getPersonTypeId(person_type), search_id)
        cats_status = checkCats()
        if not cats_status:
            # TODO return error
            return
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

def getPersonTypeId(person_type):
    # TODO check if the type exists
    types = ["child_1_3", "child_4_6", "child_7_12", "child_13_15", "despondent", "psychical_illness", "retarded", "alzheimer", "tourist", "dementia"]
    return types.index(person_type)

def findAreaWithRadial(coord, id, person_type_id, search_id):
    coords = str(coord[0]) + ',' + str(coord[1])
    # writes coord to file for grass
    with open (pluginPath + '/grass/coords.txt', 'w') as f_coords:
        f_coords.write(coords)
    # TODO - get personType - 1
    p = subprocess.Popen(
        ('bash', pluginPath + "/grass/run_cost_distance.sh", dataPath + "/projekty/" + search_id, pluginPath, str(id), str(person_type_id)))
    p.wait()

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
    csv = open(pluginPath + "/grass/radial.csv", "w")
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
    reclass = open(pluginPath + "/grass/azimuth_reclass.rules", "w")
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
    rules_percentage_path = pluginPath + "/grass/rules_percentage.txt"
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
    f = open(dataPath + "/projekty/" + search_id + '/pracovni/distancesCostedEquation.txt', 'w')
    f.write(distances_costed_cum)
    f.close()

def createCumulativeArea(search_id):
    DATAPATH = dataPath + "/projekty/" + search_id
    if os.path.isfile(DATAPATH + '/pracovni/distances_costed_cum.tif.aux.xml'):
        os.remove(DATAPATH + '/pracovni/distances_costed_cum.tif.aux.xml')
    if os.path.isfile(DATAPATH + '/pracovni/distances_costed_cum.tif'):
        os.remove(DATAPATH + '/pracovni/distances_costed_cum.tif')
    if os.path.isfile(DATAPATH + '/pracovni/distances_costed_cum.tfw'):
        os.remove(DATAPATH + '/pracovni/distances_costed_cum.tfw')

    p = subprocess.Popen(
        ('bash', pluginPath + "/grass/run_distance_costed_cum.sh", DATAPATH, pluginPath))
    p.wait()

def getSectors(min, max, search_id):
    """Selects sectors from grass database based on filtered raster"""
    p = subprocess.Popen(('bash', pluginPath + "/grass/run_sectors.sh", dataPath + "/projekty/" + search_id, pluginPath,
                          str(min), str(max)))
    p.wait()

id = sys.argv[1]
search_id = sys.argv[3]
person_type = sys.argv[4]
percentage = int(sys.argv[5])
get_sectors_grass(id, search_id, person_type, percentage)
