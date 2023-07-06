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

COPY fonts ./
RUN mkdir -p /usr/share/fonts/opensans
RUN install -m644 ./*.ttf /usr/share/fonts/opensans/
RUN rm ./*.ttf

WORKDIR /home/rainfall/ 
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY src/rainfall_forecast.py ./src/rainfall_forecast.py 
COPY src/settings.yml ./src/settings.yml 
COPY src/utils.py ./src/utils.py
COPY credentials/env.yml ./credentials/env.yml
CMD [ "python", "./src/rainfall_forecast.py", "--settings_file=./src/settings.yml", "--remove_temp", "--store_in_cloud" ]







