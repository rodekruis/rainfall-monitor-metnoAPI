"""
Uses Metno weather API (LocationForecast) to retrieve rainfall predictions (approx. until ~2days in advance).
Aggregate the predicted rainfall in mm (for every timepoint available through the API) over catchment areas.
Obtain a single long-format CSV-file with columns:

|area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm| min_rainfall_mm| time_of_prediction


-------> first version created by: Misha Klein, August 2022
"""
import numpy as np
import pandas as pd
from metno_locationforecast import Place, Forecast
import geopandas as gpd
import rasterio
import rasterstats
import rioxarray
import xarray as xr
import os
import shutil
import zipfile
import yaml
import click

@click.command()
@click.option("--settings_file", type = str, required = True, default = 'settings.yaml', show_default = True, help = "YAML file with global settings (input/output file names, etc.)" )
@click.option('--remove_temp', is_flag=True, default=False, show_default = True, help = "remove the intermediate files created by the pipeline? (default: keep temp/ folder)")
def collect_rainfall_data(settings_file, remove_temp):
    """
    Uses Metno weather API (LocationForecast) to retrieve rainfall predictions (approx. until ~10days in advance).
    Aggregate the predicted rainfall in mm (for every timepoint available through the API) over catchment areas.
    Obtain a single long-format CSV-file with columns:

    |area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm| min_rainfall_mm| time_of_prediction
    """

    # --- unzip shapefiles from archives (if not already done) --- 
    unzip_shapefiles(dirname='./shapefiles/')


    # --- prepare folder(s) for (temporary) files --- 
    if not os.path.exists('./temp'):
        os.mkdir('./temp')
        os.mkdir('./temp/downloads')

    # --- unpack settings ---
    with open(settings_file,'r') as f:
        settings = yaml.safe_load(f)
    USER_AGENT = settings['user-agent']
    download_dir = settings['download_dir']
    file_points_api_calls = settings['points_API_calls_file']
    file_geotable = settings['geotable_file']
    file_raster = settings['raster_file']
    file_catchment_areas = settings['catchment_areas']
    file_zonal_stats = settings['zonal_stats_catchment']

    # -- Get predictions on grid ---

    print("weather predictions for gridpoints...")
    rainfall_gdf = API_requests_at_gridpoints(
        filename_gridpoints=file_points_api_calls, 
        destination_dir = download_dir,
        save_to_file=file_geotable, 
        USER_AGENT=USER_AGENT
        )
    print(f"created: {file_geotable}")
    print("--"*8 + "\n"*2)

    # --- Save as TIF file ---
    print("save into TIF format....")
    rainfall_array = gdf_to_rasterfile(rainfall_gdf, save_to_file=file_raster)
    print(f"created: {file_raster}")
    print("--"*8 + "\n"*2)

    # --- perform zonal statistics ---
    print("zonal stats...")
    # get info in long-format
    rainfall_per_catchment = pd.DataFrame()
    for band_idx, timepoint in enumerate(rainfall_array.time_of_prediction):
        aggregate = zonal_statistics(rasterfile=file_raster,
                                     shapefile=file_catchment_areas,
                                     minval=0.,  # rainfall cannot be negative
                                     aggregate_by=[np.mean, np.std, np.max, np.min],
                                     nameKey='name',
                                     polygonKey='geometry',
                                     band=band_idx
                                     )

        rename_dict = {"value_1": "mean",
                       "value_2": "std",
                       "value_3": "max",
                       "value_4": "min"}
        aggregate.rename(rename_dict, axis='columns', inplace=True)
        aggregate['time_of_prediction'] = pd.to_datetime(timepoint.values)
        rainfall_per_catchment = pd.concat([rainfall_per_catchment, aggregate])

    # save to CSV file
    rainfall_per_catchment.reset_index(drop=True, inplace=True)
    rainfall_per_catchment.to_csv(file_zonal_stats, index=False)
    print(f"created: {file_zonal_stats}")
    print("--"*8 + "\n"*2)

    if remove_temp:
        shutil.rmtree('./temp/')
        print("removed temporary files")


    print("done")
    return



#################
#     UTILS    ## 
#################
def unzip_shapefiles(dirname = './shapefiles/'):
    """
    Extract contents of the ".zip"-files to get all the information to load shapefiles
    ----
    function will only unzip if needed 
    """
    zipfiles = [os.path.join(dirname, file) for file in os.listdir(dirname) if file.endswith('.zip')]    
    for zipped in zipfiles: 
        extracted = os.path.splitext(zipped)[0]
        if not os.path.exists(extracted):
            with zipfile.ZipFile(zipped, 'r') as archive:
                archive.extractall(extracted)

def API_requests_at_gridpoints(filename_gridpoints, save_to_file, destination_dir, USER_AGENT):
    """
    use metno weather API to get rainfal predictions at specified set of points
    
    return a GeoDataFrame
    (save this to file)
    """
    grid = read_grid(filename_gridpoints)
    lat = []
    long = []
    geometries = []
    rain_in_mm = []
    time_of_prediction = []
    predicted_hrs_ahead = [] 

    for idx,row in grid.iterrows(): 

        # --- create Place() object --- 
        name = f"point_{idx}"
        point = Place(name,row["latitude"], row["longtitude"])

        # --- create Forecast() object ---- 
        forecast = Forecast(place=point,
                           user_agent=USER_AGENT,
                           forecast_type = "complete",
                           save_location= destination_dir
                          )

        # --- retrieve latest available forecast from API --- 
        forecast.update()


        # --- add data in long format --- 
        for interval in forecast.data.intervals:
            if "precipitation_amount" in interval.variables.keys():
                prediction = interval.variables['precipitation_amount'].value
                timestamp = interval.start_time
                duration = interval.duration

                rain_in_mm.append(prediction)
                time_of_prediction.append(timestamp)
                predicted_hrs_ahead.append(duration.seconds / 3600.)
                lat.append(row["latitude"])
                long.append(row["longtitude"])
                geometries.append(row["geometry"])


    # --- store long-format data as GeoDataFrame --- 
    rainfall_gdf = gpd.GeoDataFrame()
    rainfall_gdf['rain_in_mm'] = rain_in_mm
    rainfall_gdf['time_of_prediction'] = time_of_prediction
    rainfall_gdf['predicted_hrs_ahead'] = predicted_hrs_ahead
    rainfall_gdf['latitude'] = lat
    rainfall_gdf['longtitude'] = long
    rainfall_gdf['geometry'] = geometries
    
    if save_to_file is not None:
        rainfall_gdf.to_file(save_to_file , driver='GeoJSON')
    return rainfall_gdf

def read_grid(dirname):
    """
    read in the grid and prep the table by dropping unnecessary columns etc. 
    """
    grid = gpd.read_file(dirname)
    grid.rename({"left":"longtitude", 
                 "top":"latitude"}, axis="columns", inplace = True)
    grid.drop(["right","bottom", "id"], axis = "columns", inplace = True)
    
    grid['geometry'] = gpd.points_from_xy(x = grid['longtitude'], 
                                          y = grid['latitude'])
    return grid 

def gdf_to_rasterfile(rainfall_gdf, save_to_file = None):
    """
    convert GeoDataFrame to xarray with dimensions and coordinates equal to latitude, longtitude and the time prediction
    
    
    Produce a geoTIF file with one band per timepoint 
    """
    # --- convert the GeoDataFrame into xarray (to have it as a 3D object with coordinates of lat, long and timepoint) ---- 
    rainfall_array = rainfall_gdf.rename({'longtitude':'x', 'latitude':'y'}, axis ='columns')
    rainfall_array = rainfall_array[rainfall_array['predicted_hrs_ahead'] == 1.]
    rainfall_array.set_index(['time_of_prediction', 'y','x'], inplace = True)
    rainfall_array = rainfall_array['rain_in_mm'].to_xarray()
    
    if save_to_file is not None:
        rainfall_array.rio.to_raster(save_to_file)
    
    return rainfall_array

def zonal_statistics(rasterfile, shapefile, 
                    minval=-np.inf,
                    maxval=+np.inf,
                    aggregate_by=[np.mean, np.max,np.sum], 
                    nameKey = None,
                    pcodeKey = None,
                    polygonKey = 'geometry',
                    band = 1
                    ): 
    
    '''
    Perform zonal statistics on raster data ('.tif') , based on polygons defined in shape file ('.shp')
    
    INPUT:
    - rasterfile: path to TIFF file 
    - shapefile : path to .shp file 
    - aggregate_by: A Python function that returns a single numnber. Will use this to aggregate values per polygon.
    NOTE: Can also provide a list of functions if multiple metrics are disired.
    - minval / maxval : Physical boundaries of quantity encoded in TIFF file. Values outside this range are usually reserved to denote special terrain/areas in image
    - nameKey / pcodeKey : column names in shape file that contain unique identifiers for every polygon 
    - polygonKey : by default geopandas uses the 'geometry' column to store the polygons 
    - band: index of band to read (for data with a single band: just keep default of band = 1)
    
    
    OUTPUT:
    table (DataFrame) with the one-number metric (aggregate) for every zone defined in the provided shape file
    '''
    
    # handle supplying either one or mulitple metrics at once: 
    if type(aggregate_by) != list:
        aggregate_by = [aggregate_by]
    aggregates_of_zones = [[] for i in range(len(aggregate_by))]

        
    
    # ---- open the shape file and access info needed --- 
    shapeData = gpd.read_file(shapefile)
    shapes = list(shapeData[polygonKey])
    if nameKey:
        names = list(shapeData[nameKey])
    if pcodeKey:
        pcodes = list(shapeData[pcodeKey])
        
    # --- open the raster image data --- 
    with rasterio.open(rasterfile, 'r') as src:
        img = src.read(1)
        
        # --- for every polygon: mask raster image and calculate value --- 
        for shape in shapes: 
            out_image, out_transform = rasterio.mask.mask(src, [shape], crop=True)
            
            # --- show the masked image (shows non-zero value within boundaries, zero outside of boundaries shape) ----
            img = out_image[band-1, :, :]

            # --- Only use physical values  ----
            data = img[(img >= minval) & (img <= maxval)]
            
            #--- determine metric: Must be a one-number metric for every polygon ---
            for idx, metric in enumerate(aggregate_by):
                aggregates_of_zones[idx].append( metric(data) )
    
    # --- store output --- 
    zonalStats = pd.DataFrame()
    if nameKey:
        zonalStats['name'] = names
    if pcodeKey:
        zonalStats['pcode'] = pcodes
        
    for idx, metric in enumerate(aggregate_by):
        zonalStats[f'value_{idx+1}'] = aggregates_of_zones[idx]    
    return zonalStats



if __name__ == '__main__':
    collect_rainfall_data()