FROM python:3.8-slim

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN deps='build-essential cmake gdal-bin python3-gdal libgdal-dev kmod wget apache2' && \
   apt-get update && \
   apt-get install -y $deps && \
   pip install --upgrade pip && \
   pip install GDAL==$(gdal-config --version)

WORKDIR /home/rainfall/ 
RUN mkdir input-shape/ 
COPY input-shape/  ./input-shape/
COPY settings_v2.yml settings-mwi.yml 
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY utils.py ./src/utils.py
COPY rainfall_per_catchment_area.py ./src/rainfall_per_catchment_area.py 
COPY env.yml /home/rainfall/
CMD [ "python", "./src/rainfall_per_catchment_area.py", "--settings_file=./settings-mwi.yml", "--remove_temp", "--store_in_cloud" ]







