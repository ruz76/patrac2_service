import os

# Windows
dataPath = r"C:\Users\gis\temp\testing environment\patrac_service\data"  # Replace with path to the data

# Linux
dataPath = "/data/patracdata"

serviceStoragePath = os.path.join(dataPath, "service")
serviceDataPath = os.path.join(dataPath, "service/data")
pluginPath = os.path.join("qgis", "qgis_patrac")
settingsPath = os.path.join("qgis", "qgis_patrac_settings")
logsPath = os.path.join(serviceStoragePath, "logs")


