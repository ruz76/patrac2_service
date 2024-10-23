from osgeo import gdal

# Definice BBOXu (minx, miny, maxx, maxy)
# (14.863941, 49.162404) - (15.310676, 49.530744)
xmin = 14.963941
ymin = 49.362404
xmax = 15.310676
ymax = 49.530744
bbox = (xmin, ymin, xmax, ymax)

# Otevření vstupního a výstupního souboru
input_file = "/data/patracdata/service/data/projekty/13ea04a3-19d2-44b3-bb75-ebed4dcb0aaa/line_search/data.gpkg"
output_file = "/data/patracdata/service/data/projekty/13ea04a3-19d2-44b3-bb75-ebed4dcb0aaa/line_search/output.gpkg"

# Definice prostorového ořezu (BBOX) ve formátu pro GDAL
bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

# Použití VectorTranslate k výřezu dat
gdal.VectorTranslate(
    output_file,
    input_file,
    options=gdal.VectorTranslateOptions(
        format='GPKG',  # Formát výstupního souboru
        spatFilter=bbox  # Prostorový filtr na základě BBOXu
    )
)

print(f"Výřez dokončen, data uložena do: {output_file}")
