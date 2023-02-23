# -*- coding: utf-8 -*-
# !/usr/bin/env python

import os
import sys
import subprocess
import math
import io
import csv
from grass_config import *
from os import path
import time
import sqlite3
from sqlite3 import Error
import json

def fixUt(ut):
    if ut == 0:
        print("The unit speed value is set to 0, this is not correct. Returning 1.")
        return 1
    else:
        return ut

ID = str(sys.argv[1])
PLUGIN_PATH = str(sys.argv[2])
pluginPath = "qgis/qgis_patrac"
settingsPath = "qgis/qgis_patrac_settings"
dataPath = "/data/patracdata/service/data"
patracDataPath = "/data/patracdata"

with open(dataPath + "/" + ID + "_sectors.geojson") as g:
    geojson = json.load(g)

DATAPATH = dataPath + "/projekty/" + geojson["metadata"]["search_id"]
print(DATAPATH)
gisdb = DATAPATH + "/grassdata"
# the following path is the default path on MS Windows
# gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

# specify (existing) location and mapset
location = "jtsk"
mapset = "PERMANENT"
system = "na"

########### SOFTWARE
if sys.platform.startswith('linux'):
    system = 'linux'
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
    system = 'win'
    grass7bin = grass7bin_win
    gisbase = 'C:/OSGEO4W64/apps/grass/grass78'
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

########### DATA
# Set GISDBASE environment variable
os.environ['GISDBASE'] = gisdb

# import GRASS Python bindings (see also pygrass)
import grass.script as gscript
import grass.script.setup as gsetup

# from grass.pygrass.modules.shortcuts import raster as r

###########
# launch session
gsetup.init(gisbase,
            gisdb, location, mapset)

# Imports sektory_group_selected.shp to grass layer sektory_group_selected_modified (may be modified by user)
# print(gscript.read_command('v.import', input=DATAPATH + '/pracovni/sektory_group_selected.shp',
#                            layer='sektory_group_selected', output='sektory_group_selected_modified', overwrite=True))

print(gscript.read_command('v.in.ogr', output='sektory_group_selected_modified', input=DATAPATH+'/pracovni', snap=0.01, layer='sektory_group_selected', overwrite=True, flags="o"))


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

conn = None
try:
    conn = sqlite3.connect(patracDataPath + "/kraje/" + geojson["metadata"]["region"] + "/vektor/ZABAGED/line_x/stats.db")
except Error as e:
    sys.exit()

# Loops via all selected search sectors based on number of sectors
for feature in geojson["features"]:
    print(feature["properties"]["id"])
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
    if not conn is None:
        try:
            c = conn.cursor()
            c.execute("SELECT def_text FROM stats WHERE id = '" + feature["properties"]["id"] + "'")
            row = c.fetchone()
            if row is not None:
                REPORT = row[0]
            c.close()
        except:
            if c is not None:
                c.close()

    if not REPORT == "":
        print(REPORT)
    else:
        print(gscript.read_command('r.mask', vector='sektory_group_selected_modified', where="id='" + feature["properties"]["id"] + "'",
                               overwrite=True))

        # ziskani reportu - procenta ploch v sektoru
        # Gets stats for landuse areas in masked region
        REPORT = gscript.read_command('r.stats', input='landuse_type', separator='pipe', flags='plna')
        #print(REPORT)

    if REPORT == "":
        print("ERROR ON " + feature["properties"]["id"])
        continue

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

    REPORTITEMS = REPORT.splitlines(False)

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

if not conn is None:
    conn.close()

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

# Reads numbers for existing search units from units.txt
units_counts = []

fileInput = open(settingsPath + "/grass/units.txt", mode="r")

for row in csv.reader(fileInput, delimiter=';'):
    # unicode_row = [x.decode('utf8') for x in row]
    unicode_row = row
    cur_count = int(unicode_row[0])
    units_counts.append(cur_count)

fileInput.close()

surfaces = [
    int(math.ceil(SUM_P1)),
    int(math.ceil(SUM_P2)),
    int(math.ceil(SUM_P3)),
    int(math.ceil(SUM_P4)),
    int(math.ceil(SUM_P5)),
    int(math.ceil(SUM_P6)),
    int(math.ceil(SUM_P7)),
    int(math.ceil(SUM_P8)),
    int(math.ceil(SUM_P9)),
    int(math.ceil(SUM_P10))
]

unitsTimesPath = settingsPath + "/grass/units_times.csv"
fileInput = open(unitsTimesPath, mode="r")

# Reads CSV and populates the array
unitsTimes = []
for row in csv.reader(fileInput, delimiter=';'):
    row_out = []
    for field in row:
        row_out.append(float(field))
    unitsTimes.append(row_out)

# First variant
# drone for P1, P2 if is available else handler for P1, P2
# handler for P3, P4, P5, P8
# phalanx for P6, P7, P10
# diver for P9

# {"handler": "psovod"},
# {"phalanx_person": "člověk do rojnice"},
# {"horse_rider": "jezdec"},
# {"vehicle_driver": "čtyřkolka"},
# {"drone": "dron"},
# {"diver": "potápěč"},
# {"other": "ostatní"}

units_areas = []
if units_counts[4] > 0:
    # We have a drone
    units_areas.append(int(math.ceil(SUM_P3 + SUM_P4 + SUM_P5 + SUM_P8))) # handlers
    units_areas.append(int(math.ceil(SUM_P6 + SUM_P7 + SUM_P10))) # phalanx
    units_areas.append(0) # No horses yet
    units_areas.append(0) # No drivers
    units_areas.append(int(math.ceil(SUM_P1 + SUM_P2))) # Drones
    units_areas.append(int(math.ceil(SUM_P9))) # Divers
    units_areas.append(0) # No other
else:
    # We do not have a drone
    units_areas.append(int(math.ceil(SUM_P1 + SUM_P2 + SUM_P3 + SUM_P4 + SUM_P5 + SUM_P8))) # handlers
    units_areas.append(int(math.ceil(SUM_P6 + SUM_P7 + SUM_P10))) # phalanx
    units_areas.append(0) # No horses yet
    units_areas.append(0) # No drivers yet
    units_areas.append(0) # Drones
    units_areas.append(int(math.ceil(SUM_P9))) # Divers
    units_areas.append(0) # No other yet

units_times = []
if units_counts[0] > 0:
    if units_counts[4] > 0:
        # We have a drone
        P3_P5_KPT = float(SUM_P3) / fixUt(unitsTimes[2][0]) + float(SUM_P5) / fixUt(unitsTimes[4][0])
        P4_P8_KPT = float(SUM_P4) / fixUt(unitsTimes[3][0]) + float(SUM_P8) / fixUt(unitsTimes[7][0])
        units_times.append(int(math.ceil((P3_P5_KPT + P4_P8_KPT) / float(units_counts[0]))))
    else:
        # We do not have a drone
        P2_P3_P5_KPT = float(SUM_P2) / fixUt(unitsTimes[1][0]) + float(SUM_P3) / fixUt(unitsTimes[2][0]) + float(SUM_P5) / fixUt(unitsTimes[4][0])
        P1_P4_P8_KPT = float(SUM_P1) / fixUt(unitsTimes[0][0]) + float(SUM_P4) / fixUt(unitsTimes[3][0]) + float(SUM_P8) / fixUt(unitsTimes[7][0])
        units_times.append(int(math.ceil((P2_P3_P5_KPT + P1_P4_P8_KPT) / float(units_counts[0]))))
else:
    units_times.append(-99)

if units_counts[1] > 0:
    P6_P7_P10_PT = float(SUM_P6) / fixUt(unitsTimes[5][1]) + float(SUM_P7) / fixUt(unitsTimes[6][1]) + float(SUM_P10) / fixUt(unitsTimes[9][1])
    units_times.append(int(math.ceil(P6_P7_P10_PT / float(units_counts[1]))))
else:
    units_times.append(-99)

units_times.append(-99) # No horses yet
units_times.append(-99) # No drivers yet
if units_counts[4] > 0:
    P1_P2_APT = float(SUM_P1) / fixUt(unitsTimes[0][4]) + float(SUM_P2) / fixUt(unitsTimes[1][4])
    units_times.append(int(math.ceil(P1_P2_APT / float(units_counts[4]))))
else:
    units_times.append(-99)

if units_counts[5] > 0:
    P9_VPT = float(SUM_P9) / fixUt(unitsTimes[8][5])
    units_times.append(int(math.ceil(P9_VPT / float(units_counts[5]))))
else:
    units_times.append(-99)

units_times.append(-99) # No other yet

# Second variant
# drone for P1, P2 if is available else phalanx for P1, P2
# phalanx for P3, P4, P5, P6, P7, P8, P10
# diver for P9

units_areas_alternatives = []
if units_counts[4] > 0:
    # We have a drone
    units_areas_alternatives.append(0) # handlers
    units_areas_alternatives.append(int(math.ceil(SUM_P3 + SUM_P4 + SUM_P5 + SUM_P6 + SUM_P7 + SUM_P8 + SUM_P10))) # phalanx
    units_areas_alternatives.append(0) # No horses yet
    units_areas_alternatives.append(0) # No drivers
    units_areas_alternatives.append(int(math.ceil(SUM_P1 + SUM_P2))) # Drones
    units_areas_alternatives.append(int(math.ceil(SUM_P9))) # Divers
    units_areas_alternatives.append(0) # No other
else:
    # We do not have a drone
    units_areas_alternatives.append(0) # handlers
    units_areas_alternatives.append(int(math.ceil(SUM_P1 + SUM_P2 + SUM_P3 + SUM_P4 + SUM_P5 + SUM_P6 + SUM_P7 + SUM_P8 + SUM_P10))) # phalanx
    units_areas_alternatives.append(0) # No horses yet
    units_areas_alternatives.append(0) # No drivers yet
    units_areas_alternatives.append(0) # Drones
    units_areas_alternatives.append(int(math.ceil(SUM_P9))) # Divers
    units_areas_alternatives.append(0) # No other yet

maxtime = 3
if os.path.isfile(settingsPath + "/grass/maxtime.txt"):
    try:
        maxtime = int(open(settingsPath + "/grass/maxtime.txt", 'r').read())
    except ValueError:
        maxtime = 3

if maxtime <= 0:
    maxtime = 3

units_necessary = []
P3_P5_KPT = float(SUM_P3) / fixUt(unitsTimes[2][0]) + float(SUM_P5) / fixUt(unitsTimes[4][0])
P4_P8_KPT = float(SUM_P4) / fixUt(unitsTimes[3][0]) + float(SUM_P8) / fixUt(unitsTimes[7][0])
units_necessary.append(int(math.ceil((P3_P5_KPT + P4_P8_KPT) / float(maxtime))))
P6_P7_P10_PT = float(SUM_P6) / fixUt(unitsTimes[5][1]) + float(SUM_P7) / fixUt(unitsTimes[6][1]) + float(SUM_P10) / fixUt(unitsTimes[9][1])
units_necessary.append(int(math.ceil(P6_P7_P10_PT / float(maxtime))))
units_necessary.append(0) # No horses yet
units_necessary.append(0) # No drivers yet
P1_P2_APT = float(SUM_P1) / fixUt(unitsTimes[0][4]) + float(SUM_P2) / fixUt(unitsTimes[1][4])
units_necessary.append(int(math.ceil(P1_P2_APT / float(maxtime))))
P9_VPT = float(SUM_P9) / fixUt(unitsTimes[8][5])
units_necessary.append(int(math.ceil(P9_VPT / float(maxtime))))
units_necessary.append(0) # No other yet

report = {
    "id": ID,
    "output": {
        "surfaces": surfaces,
        "units_areas": units_areas,
        "units_areas_alternatives": units_areas_alternatives,
        "units_times": units_times,
        "units_necessary": units_necessary
    }
}
with open(dataPath + "/" + ID + "_report.json", "w") as r:
    json.dump(report, r)
