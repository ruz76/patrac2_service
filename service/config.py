import os

# Windows
dataPath = r"patracdata"

# Linux
dataPath = "/media/jencek/Elements1/patrac/patracdata_patrac2"

serviceStoragePath = os.path.join(dataPath, "service")
serviceDataPath = os.path.join(dataPath, "service/data")
pluginPath = os.path.join("qgis", "qgis_patrac")
settingsPath = os.path.join("qgis", "qgis_patrac_settings")
logsPath = os.path.join(serviceStoragePath, "logs")


