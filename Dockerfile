FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        grass \
        grass-dev \
        gdal-bin \
        python3-gdal \
        python3-numpy \
        python3-pip \
        wget \
        ca-certificates

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1000 patrac
RUN adduser --home /home/patrac --uid 1000 --gid 1000 patrac
RUN adduser patrac sudo

COPY service /home/patrac/app
RUN chown -R patrac /home/patrac/app

EXPOSE 5000

CMD bash /home/patrac/app/run.sh
