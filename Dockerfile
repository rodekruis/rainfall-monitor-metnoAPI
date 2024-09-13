FROM python:3.10-slim

RUN pip install poetry==1.4.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

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
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR
COPY rainfall-monitor-metnoapi ./rainfall-monitor-metnoapi
COPY credentials/env.yml ./credentials/env.yml

CMD ["poetry", "run", "python", "./rainfall-monitor-metnoapi/rainfall_forecast.py", "--settings_file=./rainfall-monitor-metnoapi/settings.yml", "--remove_temp", "--store_in_cloud" ]







