# Spuštění na Windows 10 bez docker

* Testováno na systému s OSGeo4W64 s grass 7.8. Byly využity knihovny a cesty z jeho konfigurace.
* Viruální prostředí bylo vytvořeno pomocí Python 3.10 mimo distribuci OSGeo4W64.
* Spouští se pomocí patrac2service.bat, který se umístí do C:\OSGeo4W64\bin

## Připravení prostředí
* Nainstalovat Python 3.10
* Nastavit proměné prostředí. Přidat %USERPROFILE%\AppData\Local\Microsoft\WindowsApps;C:\Users\gis\AppData\Local\Programs\Python\Python310\Scripts do Path

### Instalace venv a knihoven
```bat
cd C:\Users\gis\patrac2service\service
virtualenv venv
venv\Scripts\activate
pip install Flask
pip install pyproj
pip install fiona
pip install shapely
```

### Nastavení cest k datům
Cesty jsou v:
* [config](./config.py)
* [grass_config](./proc/grass_config.py)
* [patrac2service.bat](./patrac2service.bat)

# Linux

```bash
cd ~/Documents/Projekty/PCR/github/patrac2_service/service/
source venv/bin/activate 
python3 patrac2service.py
```
