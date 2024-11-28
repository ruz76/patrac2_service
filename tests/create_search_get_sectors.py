import sys
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
import json
import os
from shapely.geometry import shape
import time
import shutil

def return_valid_features(geojson_data):
    valid_features = []

    for feature in geojson_data["features"]:
        try:
            # Vytvoř geometrii pomocí Shapely
            geom = shape(feature["geometry"])
            if geom.is_valid and not geom.is_empty:  # Jen validní a neprázdné geometrie
                valid_features.append(feature)
        except Exception as e:
            print(f"Invalid feature skipped: {e}")

    return valid_features

def create_search(base_url, lon, lat, timeout):
    response = requests.post(base_url + "create_search?x=" + str(lon) + "&y=" + str(lat) + "&timeout=" + str(timeout))
    if response.status_code == 200:
        geojson_data = response.json()
        print(geojson_data)
        return geojson_data
    else:
        print(response)
        return None

def calculate_sectors(base_url, search_id, lon, lat, timeout):
    data = {
        "search_id": search_id,
        "person_type": "child_1_3",
        "coordinates": [[float(lon), float(lat)]],
        "percentage": 60,
        "timeout": timeout
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(base_url + "calculate_sectors", data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        geojson_data = response.json()
        print(geojson_data['status'])
        return geojson_data
    else:
        print(response)
        return None

def save_results(status, output_dir, pos, lon, lat):
    base_name = str(pos) + "_" + str(lon) + "_" + str(lat) + "_" + status['sectors']['metadata']['search_id'] + "_" + status['id']

    with open(os.path.join(output_dir, base_name + "_orig.geojson"), 'w') as out:
        out.write(json.dumps(status['sectors']))

    geojson_data = status['sectors']
    # features = return_valid_features(geojson_data)

    # Vytvoření GeoDataFrame z GeoJSON dat
    # gdf = gpd.read_file(os.path.join(output_dir, base_name + "_orig.geojson"))
    # gdf = gpd.GeoDataFrame.from_features(features)

    # Zobrazení ploch pomocí matplotlib
    # ax = gdf.plot(edgecolor="black", alpha=0.5, figsize=(10, 6))
    # ax.set_title("Vizualizace GeoJSON dat")

    # Inicializuj graf
    fig, ax = plt.subplots(figsize=(10, 10))

    # Projdi všechny geometrie v GeoJSON
    for feature in geojson_data['features']:
        geometry = shape(feature['geometry'])  # Převeď na Shapely objekt

        if geometry.is_valid:  # Pokud je geometrie validní
            # Pokud je geometrie typu Polygon nebo MultiPolygon
            if geometry.geom_type == 'Polygon':
                x, y = geometry.exterior.xy  # Získej souřadnice vnějšího okraje
                ax.fill(x, y, alpha=0.5, fc='blue', edgecolor='black')  # Nakresli polygon
            elif geometry.geom_type == 'MultiPolygon':
                for poly in geometry.geoms:
                    x, y = poly.exterior.xy
                    ax.fill(x, y, alpha=0.5, fc='blue', edgecolor='black')  # Nakresli každý polygon

    # Nastavení os a zobrazení
    ax.set_title("GeoJSON Vykreslení")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect('equal')
    plt.tight_layout()


    # Uložení do obrázkového souboru
    plt.savefig(os.path.join(output_dir, base_name + ".png"), dpi=300)

    # Uložení GeoJSON dat do souboru
    # gdf.to_file(os.path.join(output_dir, base_name + ".geojson"), driver="GeoJSON")

def delete_project(status):
    shutil.rmtree(os.path.join('/media/jencek/Elements1/patrac/patracdata_patrac2/service/data/projekty', status['sectors']['metadata']['search_id']))

def calculate_sectors_2(base_url, status, lon, lat, timeout):
    status = calculate_sectors(base_url, status['id'], lon, lat, timeout)
    if status['status'] == 'DONE':
        save_results(status, sys.argv[2], pos, lon, lat)
        delete_project(status)
    else:
        time.sleep(60)
        save_results(status, sys.argv[2], pos, lon, lat)
        delete_project(status)

if len(sys.argv) != 3:
    print("You have to specify input file with list of coordinates to test and output directory where to store results.")
    print("Example: python3 create_search_get_sectors.py coordinates.txt /tmp/output/")
    sys.exit(1)

base_url = "http://localhost:5000/"
timeout = 50

with open(sys.argv[1]) as coords_file:
    coords_list = coords_file.readlines()
    pos = 1
    restart = 0
    running_path = '/home/jencek/Documents/Projekty/PCR/github/patrac2_service/service/running.txt'
    restart_path = '/home/jencek/Documents/Projekty/PCR/github/patrac2_service/service/restartme.txt'
    while True:
        if os.path.exists(running_path):
            print(pos)
            if (pos > 1000 and pos < 1605) or (pos > 1750):
                coords = coords_list[pos]
                try:
                    print("\n\nCreating search for: " + str(pos) + " " + str(coords))
                    lon = coords.strip().split(',')[0]
                    lat = coords.strip().split(',')[1]
                    status = create_search(base_url, lon, lat, timeout)
                    if status is not None:
                        if status['status'] == 'DONE':
                            calculate_sectors_2(base_url, status, lon, lat, timeout)
                        else:
                            time.sleep(60)
                            calculate_sectors_2(base_url, status, lon, lat, timeout)

                except:
                    print("ERROR processing: " + str(pos))

                restart += 1
                if restart >= 100:
                    os.remove(running_path)
                    with open(restart_path, 'w') as rp:
                        rp.write('RRR')
                    restart = 0
            else:
                print("Already computed: " + str(pos))
            pos += 1
        else:
            print("Server is not running")

        time.sleep(1)
