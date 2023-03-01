cd /home/patrac/app

if [ -d "/data/patracdata/cr" ] && [ -d "/data/patracdata/kraje" ] && [ -d "/data/patracdata/service/data/" ]
then
    python patrac2service.py
else
    echo "Error: Directories for work do not exist. Can not start the service. You have to mount /data/patracdata directory."
fi

