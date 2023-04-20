PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games"
export PATH
unset PYTHONPATH
unset GISBASE
unset LD_LIBRARY_PATH
#printenv
SERVICE_DATA=/data/patracdata/service
ogr2ogr -append -f "GeoJSON" -s_srs "EPSG:4326" -t_srs "EPSG:5514" $SERVICE_DATA/data/projekty/$3/pracovni/sektory_group.shp $SERVICE_DATA/data/$3_create.geojson
python $2/grass/create_sector.py $1 $2 $3
