PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games"
export PATH
unset PYTHONPATH
unset GISBASE
unset LD_LIBRARY_PATH
#printenv
python $2/grass/area.py $1 $2 $3 $4 $5
SERVICE_DATA=/data/patracdata/service
ogr2ogr -f "GeoJSON" -s_srs "EPSG:5514" -t_srs "EPSG:4326" $SERVICE_DATA/data/$1_sectors.geojson $SERVICE_DATA/data/projekty/$3/pracovni/sektory_group_selected.shp -overwrite
python $2/grass/save_region.py $SERVICE_DATA/data/$1_sectors.geojson $SERVICE_DATA/data/projekty/$3/pracovni/region.txt $3
echo "SECTORS EXPORTED" >> $SERVICE_DATA/logs/$1.log
echo "100" >> $SERVICE_DATA/logs/$1.log
