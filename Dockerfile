FROM python:3

COPY requirements.txt ./

RUN apt-get update && apt-get -y install gdal-bin grass
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --gid 1000 patrac
RUN adduser --home /home/patrac --uid 1000 --gid 1000 patrac
RUN adduser patrac sudo

COPY service /home/patrac/app
RUN chown -R patrac /home/patrac/app

EXPOSE 5000

CMD bash /home/patrac/app/run.sh
