# Deployment

Make sure you have:

- Docker
- Visual Studio Code (optional)

## Running with Docker
### Build the Docker image
Run command:
  ```
  docker build -t rainfallmonitormetnoapi:latest .
  ``` 
### Run and execute the Docker container
Run command:
  ``` 
  docker run --rm -it -d  rainfallmonitormetnoapi:latest 
  ```
### Run interactively the Docker container
Run command to enter the Docker container:
  ```
  docker run -it --entrypoint /bin/bash rainfallmonitormetnoapi:latest
  ```
In the Docker container bash, execute the code by running command:
  ```
  python src/rainfall_forecast.py
  ```

**NOTE 1:** Running the code with the `--remove_temp` option will delete all intermediate files created and will just write the resulting CSV into the cloud storage.

**NOTE 2:** All shapefiles can be supplied simply as ZIP packages (the code will automatically unpack them first) 

**NOTE 3:** Running the Dockerized version of the code will automatically run the script (with the `--remove_temp` option). 


## Running without Docker 
**Note:** due to GDAL-dependent packages being used, It is recommended to use the Dockerized version when possible.

If for whatever reason you want to run the code without Docker, you first install the required Python packages.
### Using Conda 
Use the `environment.yml` file to create a new conda environment with all the requirements installed into it. 
```
conda env create --file environment.yml
```
then enter the newly created environment 
```
conda activate RK510-RainFallMonitorYr
```
### Using PIP 
Alternatively, install the required packages (as specified in the `requirements.txt` file) into your existing Python environment. 
```
pip install -r requirements_incl_GDAL.txt
```
### Run the code  
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
