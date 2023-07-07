
# Customise AOI

## Define area of interest in GIS

1. Identify your area of interest, search and retrieve a polygon shapefile (in .geojson format). Ensure in the attribute that area names are available. Column name should be correspond to the area's administrive level, for example: `ADM1_EN`. File name: `{iso3}_{admin_level}.geojson`
2. Load the shapefile on the GIS software and generate gridded points over the area. Ideal resolution (space between points) can be  10 km, or 0.1 geographic degree. Remove points that are outside of the polygon.
3. Save gridded point shapefile as: `{iso3}_forecast_points.geojson`

## Edit settings 
Supply the following `settings.yml`-format file or to simply adjust the filenames of input/output as following. See an example `settings-template.yml` .

  - `METnoAPI`:
    - `user-agent` str: identifier/name of requester. Technically, its value doesn't matter, just that you supply somekind of identification of "Hi I am downloading this file and my name is `user-agent`")
    - `download_dir` str: (temporary) directory to store the downloaded data from the source 
  - Shapefile input `geoCoordinates`:
    - `country_code` str: ISO-2 or -3 code of area of interest
    - `location_name` str: name of area of interest (for map)
    - `locations_of_interest`: GeoJSON file with coordinates for which you want to download the rainfall predictions 
    - `adm1` str: (polygon) shapefile for admin level 1 (.geojson). If not available, leave the value as `FALSE`
    - `adm2` str: (polygon) shapefile for admin level 2 (.geojson). If not available, leave the value as `FALSE`
    - `adm3` str: (polygon) shapefile for admin level 3 (.geojson). If not available, leave the value as `FALSE`
    - `adm4` str: (polygon/point) shapefile for admin level 3 (.geojson). If not available, leave the value as `FALSE`
  - On cloud storage `AzureCloudStorage`:
    - `main_dir`: main directory for all in- and output
    - `input_dir`: folder stored shapefile (geojson) of input
    - `input_shape_file`: zip file contained all input shapefile
    - `output_dir`: parent directory for all output files
    - `raw_output`: destination for outputs
  - Local directories `localStorage`:
    - `main_dir`: main directory for all in- and output
    - `input_dir`: folder stored shapefile (geojson) of input
    - `output_dir`: parent directory for all output files
    - `raw_output`: destination for raw output
    - `figures_dir`: destination folder for all PNGs generates 
  - Names of output files `outputFiles`: 
    - `geojson_raw` str: raw weather forecast file name from the weather data source (.geojson)
    - `tif_raw` str: tif file of raw rainfall forecast (.tif)
    - `csv_zonal` str: table name for aggregated rainfall by percentile given below per area (.csv)
    - `csv_zonal_daily` str: table name for aggregated rainfall per 24 hrs (.csv)
    - `trigger_status` str: file contained trigger status i.e. if threshold is exceeded (.txt)
    - `png_bar_plot_daily_by_admin` str: figure plotting column chart per area per lead time (.png)
    - `tif_raw_daily` str: tif file of daily aggregated rainfall forecast (.tif)
  - Thresholds for rainfall forecast `rainfallThreshold`: 
    - `agg_percentile` int: aggregated rainfall by a percentile over an area
    - `one_day` int: threshold for 1-day cumulative threshold in mm.
    - `three_day` int: threshold for 3-day cumulative threshold in mm.

## Execute or pack the code tool
See instruction at [Customisation](./customisation.md).




