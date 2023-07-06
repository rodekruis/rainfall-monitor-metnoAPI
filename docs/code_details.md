# Code details

The main code is in `rainfall_forecast.py`. The code will:
1. Based on a shapefile with predefined locations, download the rainfall (in mm) predictions from the MET Weather API. 
    - In `settings.yml`, specify gridded point shapefile ('.geojson')
    - We sampled the area of interest in its entirety with regularly spaced points separated by the reported spatial resultion of the available data 
    - Produces a (temporary) GeoPandas Dataframe with all the predictions at all available timepoints (long-format): 'geotable_file' key in `settings.yml` ('.geojson')
2. Convert it into TIFF images (one per timepoint), using xarray
    - Save as `tif_raw` (.TIFF) specified in `settings.yml`
3. Perform 'zonal statistics' to get aggregated values per catchement area
    - Shapefile admin area: `adm{}` in `settings.yml` (Folder with (zipped) shapefile(s))
    - Resulting zonal statistics: `csv_zonal` in `settings.yml` (.CSV)
4. Aggregate predictions by the day. Get the total for that day (typically three days worth of data available). Note that the final day might be based on less than a full day. 
    - both zonal and daily aggregates stored into `csv_zonal_daily`
    - bar graph stored into `png_bar_plot_daily_by_admin`
    - daily aggregates for all locations stored into TIF file `tif_raw_daily`
5. Finally, write all files produced into Azure's cloud storage: 
    - `localStorage/output_dir` in `settings.yml` 




