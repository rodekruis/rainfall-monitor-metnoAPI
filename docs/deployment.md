# Deployment

Make sure you have:

- Docker, for running with Docker
- Github account, for running in Github
- Visual Studio Code (optional), for editing scripts

## Option 1 : Running with Docker
Firstly, open your Docker Desktop and leave it running.

Then follow the steps below in a command prompt window or in a powershell terminal in Visual Studio Code.

### Build the Docker image
For the first time, an image for this tool should be created. After it is created, it is no need to build the image again. Unless, the code is updated, the image will need to be rebuilt to wrap the updates.

To build the image, run command:
  ```
  docker build -t rainfallmonitormetnoapi:latest .
  ``` 
### Run and execute the Docker container
When the building is complete, or when you would like to execute a container from the created image, you can run the command:
  ``` 
  docker run --rm -it -d  rainfallmonitormetnoapi:latest 
  ```
### Run interactively the Docker container
Preferrably, the container can also be executed interactively. It means you can interact within the containers more than just execute the code.

Run command to enter the Docker container for interactivity:
  ```
  docker run -it --entrypoint /bin/bash rainfallmonitormetnoapi:latest
  ```
To view the run results (mps with forecast rainfall) when running locally, add argument at the end of the command to mount the image `results` folder to the local one:
  ```
  -v $pwd\results:/home/rainfall/results rainfallmonitormetnoapi:latest 
  ```
In the Docker container bash, execute the code by running command:
  ```
  poetry run python rainfall-monitor-metnoapi/rainfall_forecast.py --settings_file rainfall-monitor-metnoapi/settings-<country_code>.yml
  ```

**NOTE 1:** Running the code with the `--remove_temp` option will delete all intermediate files created and will just write the resulting CSV into the cloud storage.

**NOTE 2:** All shapefiles can be supplied simply as ZIP packages (the code will automatically unpack them first) 

**NOTE 3:** Running the Dockerized version of the code will automatically run the script (with the `--remove_temp` option). 


## Running without Docker 
**Note:** due to Python GDAL-dependent packages such as `geopandas`, `rasterio`, `contextily` being used, It is recommended to use the Dockerized version when possible. 

If for whatever reason you want to run the code without Docker, you first install the required Python packages. It is highly recommended to do so in a fresh new environment.

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
python rainfall-monitor-metnoapi/rainfall_forecast.py --help
```
which returns: 
~~~
Usage: rainfall_forecast.py [OPTIONS]

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
