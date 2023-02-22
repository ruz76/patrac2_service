# patrac2_service

docker build -t ruz76-patrac2-service .
docker run -v /data/patracdata:/data/patracdata -p 5000:5000 -it ruz76-patrac2-service /bin/bash
