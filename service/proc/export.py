#!/usr/bin/env python
import os
import sys
import subprocess
from .grass_config import *

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

def export(datapath, plugin_path, xmin, ymin, xmax, ymax, data_output_path, id):
    # DATA
    # define GRASS DATABASE
    # add your path to grassdata (GRASS GIS database) directory
    DATAPATH=datapath
    ID=id
    gisdb = DATAPATH + "/grassdata"
    # the following path is the default path on MS Windows
    # gisdb = os.path.join(os.path.expanduser("~"), "Documents/grassdata")

    # specify (existing) location and mapset
    location = "jtsk"
    mapset   = "PERMANENT"

    init_grass(gisdb, location, mapset)
    import grass.script as gscript

    logsPath = "/data/patracdata/service/logs"

    with open(logsPath + "/" + ID + ".log", "a") as log:
        log.write("EXPORT STARTED\n5\n")

    PLUGIN_PATH=plugin_path
    XMIN=xmin
    YMIN=ymin
    XMAX=xmax
    YMAX=ymax
    DATAOUTPUTPATH=data_output_path
    # print(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])

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
    print(gscript.read_command('r.out.bin', flags="h", input='landuse', output=DATAOUTPUTPATH+'/grassdata/landuse.bin', overwrite=True))

    with open(logsPath + "/" + ID + ".log", "a") as log:
        log.write("LANDUSE EXPORTED\n10\n")

    #Exports friction_slope
    #r.out.ascii input=friction_slope output=friction_slope.ascii
    #Bin would be better (size is smaller, export is faster), but there are some problems with import
    print(gscript.read_command('r.out.bin', flags="h", null=-99, input='friction_slope', output=DATAOUTPUTPATH+'/grassdata/friction_slope.bin', overwrite=True))

    with open(logsPath + "/" + ID + ".log", "a") as log:
        log.write("FRICTION_SLOPE EXPORTED\n15\n")

    #Exports friction only, without slope, we will use r.walk instead r.cost
    print(gscript.read_command('r.out.bin', flags="h", null=100, input='friction', output=DATAOUTPUTPATH+'/grassdata/friction.bin', overwrite=True))

    with open(logsPath + "/" + ID + ".log", "a") as log:
        log.write("FRICTION EXPORTED\n20\n")

    #Exports dem, r.walk needs dem to calculate slope in realtime
    print(gscript.read_command('r.out.bin', flags="h", input='dem', output=DATAOUTPUTPATH+'/grassdata/dem.bin', overwrite=True))

    with open(logsPath + "/" + ID + ".log", "a") as log:
        log.write("DEM EXPORTED\n25\n")

    p = subprocess.Popen(('bash', PLUGIN_PATH + "/grass/run_import.sh", DATAOUTPUTPATH, PLUGIN_PATH,
                           str(XMIN), str(YMIN), str(XMAX), str(YMAX), DATAPATH, ID))
