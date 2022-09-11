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




WORKDIR /home/myapp/ 
RUN mkdir shapefiles/ 
COPY shapefiles/CatchmentsShapefile.zip  ./shapefiles/CatchmentsShapefile.zip
COPY shapefiles/CatchmentsShapefile_dissolved.zip ./shapefiles/CatchmentsShapefile_dissolved.zip
COPY shapefiles/grid.zip ./shapefiles/grid.zip 
COPY shapefiles/Malawi_API_calls_catchments_dissolved.geojson ./shapefiles/Malawi_API_calls_catchments_dissolved.geojson
COPY settings.yml settings.yml 
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY rainfall_per_catchment_area.py ./src/rainfall_per_catchment_area.py 
COPY .env.yml /home/myapp/
CMD [ "python", "./src/rainfall_per_catchment_area.py", "--settings_file=./settings.yml", "--remove_temp", "--store_in_cloud" ]







