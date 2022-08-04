# rainfall-monitor-malawi-metnoAPI
Use MET Weather API to get forecast of rainfall for Malawi cities. Starting point for trigger-based warning system


...
## Instalation 

### using conda 
Use the `environment.yml` file to create a new conda environment with all the requirements installed into it. 
```
conda env create --file environment.yml
```

### using pip only
Alternatively, install the required packages (as specified in the `requirements.txt` file) into your existing Python environment. 
```
pip install -r requirements.txt
```



## How to use 
Simply run the following line of code in your terminal (command prompt)
```
python rainfall_per_catchment_area.py --help
```
which returns: 
~~~
Usage: rainfall_per_catchment_area.py [OPTIONS]

  Uses Metno weather API (LocationForecast) to retrieve rainfall predictions
  (approx. until ~2days in advance). Aggregate the predicted rainfall in mm
  (for every timepoint available through the API) over catchment areas. Obtain
  a single long-format CSV-file with columns:

  |area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm|
  min_rainfall_mm| time_of_prediction

Options:
  --settings_file TEXT  YAML file with global settings (input/output file
                        names, etc.)  [default: settings.yaml; required]
  --remove_temp         remove the intermediate files created by the pipeline?
                        (default: keep temp/ folder)
  --help                Show this message and exit.
~~~

