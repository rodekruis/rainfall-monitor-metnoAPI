# rainfall-monitor-malawi-metnoAPI
Use MET Weather API to get forecast of rainfall for Malawi cities. Starting point for trigger-based warning system



## What does the code do? 
The code `rainfall_per_catchment_area.py` will:
1. Based on a shapefile with predefined locations, download the rainfall (in mm) predictions from the MET Weather API. 
  - In `settings.yml`, specify `points_API_calls_file` (absolute path) ('.geojson')
  - We sampled Malawi (MWI) in its entirety with regularly spaced points separated by the reported spatial resultion of the available data 
  - Produces a (temporary) GeoPandas Dataframe with all the predictions at all available timepoints (long-format): 'geotable_file' key in `settings.yml` ('.geojson')
2. Convert it into TIFF images (one per timepoint), using xarray
  - Save into `raster_file` of `settings.yml` (.TIFF)
3. Perform 'zonal statistics' to get aggregated values per catchement area
  - Shapefile catchment area: `catchment_areas` in `settings.yml` (`Folder with (zipped) shapefile(s)`)
  - Resulting zonal statistics:  `zonal_stats_catchment` in `settings.yml` (.CSV)
4. Aggregate predictions by the day. Get the total for that day (typically three days worth of data available). Note that the final day might be based on less than a full day. 
  - both zonal and daily aggregates stored into `csv_zonal_stats_daily`
  - bar graph stored into `png_bar_plot_daily_by_catchment`
  - daily aggregates for all locations stored into TIF file `tif_raw_daily`
5. Finally, write all files produced into Azure's cloud storage: 
  - `in_cloud/output_dir` in `settings.yml` 


**NOTE 1:** Running the code with the `--remove_temp` option will delete all intermediate files created and will just write the resulting CSV into the cloud storage.

**NOTE 2:** All shapefiles can be supplied simply as ZIP packages (the code will automatically unpack them first) 

**NOTE 3:** Running the Dockerized version of the code will automatically run the script (with the `--remove_temp` option). 


## Building the Docker image with costum `settings.yml` 
To run the code for a different country, or to simply adjust the filenames of the output: 
1. Supply the following `.yml`-format file:

  - `METnoAPI`:
    - `user-agent`: "510Global" (*Technically, it's value doesn't matter, just that you supply somekind of identification of "Hi I am downloading this file and my name is `user-agent`")
    - `download_dir`: (temporary) directory to store the downloaded data from MET Weather
  - `geoCoordinates`:
    - `catchment_areas`: shapefile (directory) with boundaries you will aggregate your results by 
    - `locations_of_interest`: GeoJSON file with coordinates for which you want to download the rainfall predictions 
  - `on_local`:
    - `output_dir`: Destination within local machine (or within docker container)
    - `geojson_raw`: GeoJSON file with long-format rainfall predictions after download
    - `tif_raw`:  TIF file with one image/layer per timepoint, every layer contains rainfall predictions accross the ROI sampled, as supplied in `points_API_calls_file`
    - `tif_raw_daily`: TIF file with one image/layer per day 
    - `csv_zonal_stats`: CSV file with aggregate rainfall predictions
    - `csv_zonal_stats_daily`: CSV file with aggregate rainfall predictions both by catchment area and by day 
    - `png_images_dir`: destination folder for all PNGs generates 
  - `in_cloud`:
    - `output_dir`: Destination (container) in Azure's cloud storrage (OPTIONAL)
  
2. Build the Docker image: 
  ```
  docker build --pull --rm -f "Dockerfile" -t rainfallmonitormetnoapi:latest "."
  ``` 
3. Run the Docker container: 
  ``` 
  docker run --rm -it -d  rainfallmonitormetnoapi:latest 
  ```


**NOTE:** Visual Studio Code has convenient pluggins for building Docker images and running Docker containers (so you don't actually need to know the above commands) 



## Runnig without Docker 
**note: due to GDAL-dependent packages being used, It is recommended to use the Dockerized version when possible**
If for whatever reason you want to run the code without Docker, you first install the required Python packages.
#### Using Conda 
Use the `environment.yml` file to create a new conda environment with all the requirements installed into it. 
```
conda env create --file environment.yml
```
then enter the newly created environment 
```
conda activate RK510-RainFallMonitorYr
```
#### Using PIP 
Alternatively, install the required packages (as specified in the `requirements.txt` file) into your existing Python environment. 
```
pip install -r requirements_incl_GDAL.txt
```
#### run the code  
Simply run the following line of code in your terminal (command prompt)
```
python rainfall_per_catchment_area.py --help
```
which returns: 
~~~
Usage: rainfall_per_catchment_area.py [OPTIONS]

  Uses Metno weather API (LocationForecast) to retrieve rainfall predictions
  (approx. until ~10days in advance). Aggregate the predicted rainfall in mm
  (for every timepoint available through the API) over catchment areas. Obtain
  a single long-format CSV-file with columns:

  |area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm|
  min_rainfall_mm| time_of_prediction

Options:
  --settings_file TEXT  YAML file with global settings (input/output file
                        names, etc.)  [default: settings.yml; required]
  --remove_temp         remove the intermediate files created by the pipeline?
                        (default: keep temp/ folder)
  --store_in_cloud      Store final CSV in Azure's cloud storage
  --help                Show this message and exit.
~~~

