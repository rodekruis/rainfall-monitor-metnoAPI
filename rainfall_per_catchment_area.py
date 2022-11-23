"""
Uses Metno weather API (LocationForecast) to retrieve rainfall predictions (approx. until ~2days in advance).
Aggregate the predicted rainfall in mm (for every timepoint available through the API) over catchment areas.
Obtain a single long-format CSV-file with columns:

|area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm| min_rainfall_mm| time_of_prediction


-------> first version created by: Misha Klein, August 2022
"""
from asyncore import write
from email.policy import default
import enum
from mimetypes import common_types
from threading import local
import numpy as np
import pandas as pd
from metno_locationforecast import Place, Forecast
import geopandas as gpd
import rasterio
import rasterstats
import rioxarray
import xarray as xr
from tqdm import tqdm
import os
import glob
import shutil
import zipfile
import yaml
import click
from azure.storage.blob import BlobServiceClient
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns 
import cmocean
import datetime


@click.command()
@click.option("--settings_file", type = str, required = True, default = 'settings.yml', show_default = True, help = "YAML file with global settings (input/output file names, etc.)" )
@click.option('--remove_temp', is_flag=True, default=False, show_default = True, help = "remove the intermediate files created by the pipeline? (default: keep temp/ folder)")
@click.option('--store_in_cloud', is_flag=True, default=False, show_default = True, help = "Store final CSV in Azure's cloud storage")
def collect_rainfall_data(settings_file, remove_temp, store_in_cloud):
    """
    Uses Metno weather API (LocationForecast) to retrieve rainfall predictions (approx. until ~10days in advance).
    Aggregate the predicted rainfall in mm (for every timepoint available through the API) over catchment areas.
    Obtain a single long-format CSV-file with columns:

    |area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm| min_rainfall_mm| time_of_prediction
    """

    now_stamp = datetime.datetime.today().strftime(format="%Y%m%d%H")
    # now_stamp = '2022111016'

    # --- unzip shapefiles from archives (if not already done) --- 
    unzip_shapefiles(dirname='./shapefiles/')


    # --- prepare folder(s) for (temporary) files --- 
    if not os.path.exists('./temp'):
        os.mkdir('./temp')
        os.mkdir('./temp/downloads')
    
    if not os.path.exists('./output'):
        os.mkdir('./output')

    if not os.path.exists(f'./output/{now_stamp}'):
        os.mkdir(f'./output/{now_stamp}')

    # --- unpack settings ---
    with open(settings_file,'r') as f:
        settings = yaml.safe_load(f)
    USER_AGENT = settings['METnoAPI']['user-agent']
    download_dir = settings['METnoAPI']['download_dir']
    file_points_api_calls = settings['geoCoordinates']['locations_of_interest']
    file_catchment_areas = settings['geoCoordinates']['catchment_areas']
    adm3_areas = settings['geoCoordinates']['admin3_shapefile']
    adm4_points = settings['geoCoordinates']['admin4_shapefile']
    output_dir = settings['on_local']['output_dir'] + f'{now_stamp}'
    rainfall_thresholds = settings['rainfall_threshold']
    file_geotable = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['geojson_raw']}")
    file_raster = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['tif_raw']}")
    file_trigger = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['trigger_status']}")


    dir_png_local = settings['on_local']['png_images_dir']
    if not os.path.exists(dir_png_local):
        os.mkdir(dir_png_local)
    
    file_zonal_stats = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['csv_zonal_stats']}")
    file_zonal_daily = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['csv_zonal_stats_daily']}")
    file_png_bar_plot_daily = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['png_bar_plot_daily_by_catchment']}")
    file_raster_daily = os.path.join(output_dir, f"{now_stamp}_{settings['on_local']['tif_raw_daily']}")

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
    # rainfall_gdf = gpd.read_file(file_geotable)

    # --- Save as TIF file ---
    print("save into TIF format....")
    rainfall_array = gdf_to_rasterfile(rainfall_gdf, save_to_file=file_raster)
    print(f"created: {file_raster}")
    print("--"*8 + "\n"*2)

    # --- perform zonal statistics ---
    print("zonal stats...")
    # get info in long-format
    rainfall_per_catchment = pd.DataFrame()
    for band_idx, timepoint in tqdm(enumerate(rainfall_array.time_of_prediction)):
        aggregate = zonal_statistics(rasterfile=file_raster,
                                     shapefile=file_catchment_areas,
                                     minval=0.,  # rainfall cannot be negative
                                     aggregate_by=[np.mean, np.std, np.max, np.min],
                                     nameKey = 'ADM2_EN',
                                     pcodeKey = 'ADM2_PCODE',
                                     band=band_idx
                                     )

        rename_dict = {"value_1": "mean",
                       "value_2": "std",
                       "value_3": "max",
                       "value_4": "min"}
        aggregate.rename(rename_dict, axis='columns', inplace=True)
        aggregate['time_of_prediction'] = pd.to_datetime(timepoint.values)
        rainfall_per_catchment = pd.concat([rainfall_per_catchment, aggregate])
    rainfall_per_catchment.reset_index(drop=True, inplace=True)
    rainfall_per_catchment.to_csv(file_zonal_stats, index=False)
    print(f"created: {file_zonal_stats}")
    print("--"*8 + "\n"*2)




    # ---- get daily aggregates ------- 
    print(f"determining daily aggregates per catchment area....")
    # per catchment area 
    daily_rainfall_per_catchment, rainfall_per_catchment = daily_aggregates_per_catchment(rainfall_per_catchment, \
        rainfall_thresholds, save_to_file=file_zonal_daily, \
        save_fig_to_png=file_png_bar_plot_daily)
    check_threshold(daily_rainfall_per_catchment, 'ONE-DAY', save_to_file=file_trigger)
    check_threshold(rainfall_per_catchment, 'THREE-DAY', save_to_file=file_trigger)
    print(f"created:{file_zonal_daily}")
    print(f"created:{file_png_bar_plot_daily}")

    # per timestamp 
    print(f"determining daily aggregates for every location....")
    daily_rainfall_arr = daily_aggregates_per_location(rainfall_gdf, save_to_file=file_raster_daily)
    print("creating PNG images .....")
    plot_rainfall_map_per_day(rainfall_da=daily_rainfall_arr, \
        catchment_shapefile=file_catchment_areas, \
        adm3_shapefile=adm3_areas, \
        adm4_points=adm4_points, \
        destination_fldr=output_dir,
        timestamp=now_stamp)
    print(f"wrote PNG files into: {output_dir}")
    print("--"*8 + "\n"*2)


    # ---- create image of rainfall with overlay of catchement areas --- 
    # print("creating PNG images per timestamp...")
    # plot_rainfall_map_per_timestamp(rainfall_da=rainfall_array, \
    #         catchment_shapefile=file_catchment_areas, \
    #         destination_fldr=dir_png_local)
    # print(f"wrote PNG files into: {dir_png_local}")
    # print("--"*8 + "\n"*2)

    # # --- write output files to cloud if needed  ---
    # NOTE: It is assumed you wrote all files into the same directory on local 
    if store_in_cloud:
        cloud_dir = settings['in_cloud']['output_dir'] + f'{now_stamp}'
        output_files = [f for f in glob.glob(f'{output_dir}/**', recursive=True) if os.path.isfile(f)]
        for file_on_local in output_files:
            file_in_cloud = os.path.join(cloud_dir, os.path.relpath(file_on_local, output_dir))
            write_to_azure_cloud_storage(local_filename=file_on_local, cloud_filename=file_in_cloud)
            print(f"created: {file_in_cloud} in Azure datalake")
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

    for idx,row in tqdm(grid.iterrows()): 

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


def gdf_to_rasterfile(rainfall_gdf, key_values='rain_in_mm', key_index='time_of_prediction',save_to_file = None):
    """
    convert GeoDataFrame to xarray with dimensions and coordinates equal to latitude, longtitude and the time prediction
    
    
    Produce a geoTIF file with one band per timepoint 
    """
    max_days_ahead = 3

    # --- convert the GeoDataFrame into xarray (to have it as a 3D object with coordinates of lat, long and timepoint) ---- 
    rainfall_array = rainfall_gdf.rename({'longtitude':'x', 'latitude':'y'}, axis ='columns')
    if 'predicted_hrs_ahead' in rainfall_gdf.columns:
        rainfall_array['time_of_prediction'] = pd.to_datetime(rainfall_array['time_of_prediction'])
        first_forecast_hour = rainfall_array['time_of_prediction'][0]
        last_forecast_hour = first_forecast_hour + pd.Timedelta(days= max_days_ahead)
        forecast_hour_range = {
            first_forecast_hour,
            last_forecast_hour
        }
        # rainfall_array = rainfall_array[rainfall_array['predicted_hrs_ahead'] == 1.]
        rainfall_array['included'] = np.where(rainfall_array['time_of_prediction'] >= last_forecast_hour, 1, 0)
        rainfall_array = rainfall_array[rainfall_array['included']==1]
    rainfall_array.set_index([key_index, 'y','x'], inplace = True)
    rainfall_array = rainfall_array[key_values].to_xarray()
    
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


def daily_aggregates(df, aggregate_by):
    """
    sum up predicted rainfall over 24 hour.
    Will continue to do such for however many days you have retreived a prediction for 

    NOTE: Final day might be less than 24hrs worth of hourly predictions TODO: check this statement
    """
    # start by resetting index as an ensurance (to make it work in combination with 'groupby' operation)
    df.reset_index(inplace=True, drop=True)
    
    # initialize 
    start_indx_hour = 0
    hours_predicted_ahead = 24
    one_block = datetime.timedelta(hours=hours_predicted_ahead)
    daily_totals = pd.DataFrame()
    
    # let the algorithm automatically find how many days we have predictions for 
    while start_indx_hour < len(df)-1:
        
        # index / timestamps of first and last predictions within a day 
        first_hour = pd.to_datetime(df.time_of_prediction[start_indx_hour])
        end_indx_hour  = np.where(pd.to_datetime(df.time_of_prediction)<=first_hour+one_block)[0][-1]
        last_hour = pd.to_datetime(df.time_of_prediction[end_indx_hour])
        
        
        # slice data to get data belonging to the same day 
        data_of_day = df.iloc[start_indx_hour:end_indx_hour]
        data_of_day.reset_index(inplace=True, drop=True)
        
        # summarize by adding together the average rainfall over the day
        aggregate_of_day = pd.DataFrame()
        aggregate_of_day['hours_ahead'] = [f'hr-{hours_predicted_ahead}']
        aggregate_of_day['tot_rainfall_mm'] = [data_of_day[aggregate_by].sum()]
        
        # combine days into single output 
        daily_totals = pd.concat([daily_totals, aggregate_of_day])
        
        # progress number days we could predict for 
        hours_predicted_ahead += 24
        # reset loop: Start from the start of the next day 
        start_indx_hour = end_indx_hour + 1

    return daily_totals 


def daily_aggregates_per_catchment(df, rainfall_thresholds, save_to_file=None, save_fig_to_png=None):
    """
    aggregate predicted rainfall per day (per catchment area)

    returns resulting dataframe 
    creates PNG with barplot 
    """
    combine_areas_daily = pd.DataFrame()
    for area, group in df.groupby('name'):
        one_area_daily = daily_aggregates(group, aggregate_by='mean')
        one_area_daily['name'] = area
        combine_areas_daily =  pd.concat([combine_areas_daily, one_area_daily])
    combine_areas_daily['trigger'] = np.where(combine_areas_daily['tot_rainfall_mm'] > rainfall_thresholds['one_day'], 1 , 0)

    combine_areas = combine_areas_daily.fillna(0).groupby(['name'])['tot_rainfall_mm'].sum().reset_index()
    combine_areas['trigger'] = np.where(combine_areas['tot_rainfall_mm'] > rainfall_thresholds['three_day'], 1 , 0)

    if save_fig_to_png is not None:
        combine_areas_daily.to_csv(save_to_file, index=False)

    if save_fig_to_png is not None:
        plt.figure(figsize=(10,5))
        sns.barplot(x = 'name', 
                    y = 'tot_rainfall_mm', 
                    hue = 'hours_ahead', 
                    data = combine_areas_daily,
                    palette = 'Accent',
            )
        plt.xticks(fontsize = 14, rotation = 90);
        plt.yticks(fontsize = 14);
        plt.xlabel("catchment area", fontsize = 14);
        plt.ylabel("total rainfall (mm)", fontsize = 16);
        sns.despine();
        plt.savefig(save_fig_to_png, format='png', dpi=300, bbox_inches='tight');

    return combine_areas_daily, combine_areas


def daily_aggregates_per_location(gdf, save_to_file=None):
    """
    Aggregate raw data by day and store into TIF. 
    Also produce PNGs with daily totals with overlay of catchment areas 
    """

    # just use the predictions for 1 hour ahead (not for 6 hours ahead)
    gdf = gdf[gdf['predicted_hrs_ahead'] == 1]

    # because df.groupby() is much faster in pandas vs geopandas, convert back and forth 
    df = pd.DataFrame(gdf)  
    combine_locations_daily = pd.DataFrame()
    for (lat,long), group in df.groupby(['latitude','longtitude']):
        one_location_daily = daily_aggregates(group,'rain_in_mm')
        one_location_daily['latitude'] = lat
        one_location_daily['longtitude'] = long
        one_location_daily['geometry'] = group['geometry'].iloc[0]
        combine_locations_daily = pd.concat([combine_locations_daily, one_location_daily])
    combine_locations_daily = gpd.GeoDataFrame(combine_locations_daily)

    # Convert to TIF in order to make plot
    combine_locations_daily_arr = gdf_to_rasterfile(combine_locations_daily, \
        key_values='tot_rainfall_mm' , \
        key_index = 'hours_ahead', \
        save_to_file = save_to_file)

    # # Convert to TIF for other uses
    # for day in np.unique(combine_locations_daily['hours_ahead']):
    #     combine_locations_day = combine_locations_daily[combine_locations_daily['hours_ahead']==day]
    #     gdf_to_rasterfile(combine_locations_day, \
    #         key_values='tot_rainfall_mm' , \
    #         key_index = 'hours_ahead', \
    #         save_to_file = save_to_file)
    
    return combine_locations_daily_arr 


def plot_rainfall_map_per_day(rainfall_da, catchment_shapefile, adm3_shapefile, adm4_points, destination_fldr, timestamp):
    """
    create colormap of rainfall in mm per day
    will save the image into png 
    """

    # --- load in catchment area shapes --- 
    catchmentAreas = gpd.read_file(catchment_shapefile)
    adm3_shapefile = gpd.read_file(adm3_shapefile)
    adm4_points = gpd.read_file(adm4_points)
    location = 'Southern Malawi' 
    
    production_time = pd.to_datetime(timestamp, format="%Y%m%d%H").strftime(format="%H:00 %d-%m-%Y")
    
    levels = [0, 5, 20, 40, 60, 80, 100]
    # cmap = cmocean.cm.rain
    cmap = (mpl.colors.ListedColormap(['#FFFFFF', '#ffffcc', '#a1dab4', '#41b6c4', 
        '#2c7fb8', '#253494'])).with_extremes(over='#1C286E') # YlGnBu 1+5 scale
    cbar_kwargs = {
        'label':'Forecasted rainfall (mm)',
        'extend': 'max',
        'spacing': 'proportional',
        'fraction': 0.046,
        'pad': 0.04
    }

    rainfall_ds = rainfall_da.to_dataset('hours_ahead')
    rainfall_ds = rainfall_ds.rename(
         {nmbr_days:nmbr_days for nmbr_days in rainfall_ds}
         )
    for nmbr_days in tqdm(rainfall_da.hours_ahead.values):
        hour_range = int(nmbr_days[3:])
        forecast_start_time = pd.to_datetime(timestamp, format="%Y%m%d%H") + pd.Timedelta(hours=hour_range-24)
        forecast_end_time = forecast_start_time + pd.Timedelta(hours=hour_range)
        forecast_start_time = forecast_start_time.strftime(format="%H:00 %d-%m-%Y ")
        forecast_end_time = forecast_end_time.strftime(format="%H:00 %d-%m-%Y ")
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        # ax = plt.gca().strftime(format="%d-%m-%Y")
        map = rainfall_ds[nmbr_days].plot(ax=ax, cmap=cmap, \
            vmax=150, vmin=5, levels=levels, \
            cbar_kwargs=cbar_kwargs)
        # map = rainfall_ds[nmbr_days].plot(ax=ax, cmap=cmap, \
        #     vmax=100, vmin=5)
        # map.cmap.set_over(color='#1C286E')
        # map.cmap.set_under(color='#FFFFFF')
        # colorbar = fig.colorbar(map, extend='both',#mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=ax, 
        #     label='Predicted rainfall (mm)', spacing='proportional',
        #     fraction=0.046, pad=0.04)
        adm3_shapefile.boundary.plot(ax = ax, color="darkgrey", linewidth = 0.75, linestyle='dashed')
        catchmentAreas.boundary.plot(ax=ax, color="black", linewidth = 1.25)
        ax.scatter(data=adm4_points, x='x_mean', y='y_mean', label='group_village_head_name')
        for x, y, label in zip(adm4_points.geometry.x, adm4_points.geometry.y, adm4_points.group_village_head_name):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points")

        plt.suptitle(f"TOTAL RAINFALL FORECAST \n{location.upper()}", \
            fontweight='bold', fontsize=16, fontname='Arial')
        plt.title(f'Forecast period: {forecast_start_time} to {forecast_end_time} \n Run on {production_time}', \
            fontsize=14, fontname='Arial')
        plt.xlabel('Longtitude')
        plt.ylabel('Latitude')
        plt.xlim([34.2, 35.4])
        sns.despine(bottom=True, left=True)

        basename = f"{timestamp}_day_{nmbr_days}"
        filename = os.path.join(destination_fldr, f"{basename}.png")
        plt.savefig(filename, format="png", dpi=300, bbox_inches='tight');
        plt.close();


def plot_rainfall_map_per_timestamp(rainfall_da, catchment_shapefile, destination_fldr):
    """
    create colormap of rainfall in mm at one time stamp
    will save the image into png 
    """

    # --- load in catchment area shapes --- 
    catchmentAreas = gpd.read_file(catchment_shapefile)

    rainfall_ds = rainfall_da.to_dataset('time_of_prediction')
    rainfall_ds = rainfall_ds.rename(
         {time:timestamp_str(time) for time in rainfall_ds}
         )
    for timestamp in tqdm(rainfall_da.time_of_prediction.values):

        time_str = timestamp_str(timestamp)
        plt.figure()
        ax = plt.gca()
        rainfall_ds[time_str].plot(ax=ax, cmap=cmocean.cm.rain, cbar_kwargs={'label':'Predicted rainfall (mm)'})
        catchmentAreas.boundary.plot(ax = ax, color="darkgrey", linewidth = 1., linestyle='dashed')

        plt.title(time_str)
        plt.xlabel('longtitude')
        plt.ylabel('latitude')
        plt.xlim([34, 36])
        sns.despine(bottom=True, left=True)

        basename = timestamp_str(timestamp, fmt="%Y%m%d_%H_%M_%S")
        filename = os.path.join(destination_fldr, f"{basename}.png")
        plt.savefig(filename, format="png", dpi=300, bbox_inches='tight');
        plt.close();
 

def timestamp_str(timestamp, fmt = "%m/%d/%Y, %H:%M:%S"):
    timestring = pd.to_datetime(timestamp)
    return timestring.strftime(format=fmt)


def write_to_azure_cloud_storage(local_filename, cloud_filename):
    """
    write resulting .csv file to cloud storrage of Azure. 

    data container: ibf 
    -----
    local_filename: Path to the file on your computer (or inside Docker Container)
    cloud_filename: Path to the destination in Azure 
    """

    # TODO: Replace the following by call to Azure's secure information storage service --- 
    with open(".env.yml","r") as env:
        secrets = yaml.safe_load(env)
 
    # --- Create instance of BlobServiceClient to connect to Azure's data storage ---
    blob_service_client = BlobServiceClient.from_connection_string(secrets['connectionString'])
    blob_client = blob_service_client.get_blob_client(container=secrets['DataContainer'], blob=cloud_filename)

    # --- write data to cloud --- 
    with open(local_filename, "rb") as upload_file:
        blob_client.upload_blob(upload_file, overwrite=True)
    

def check_threshold(df_rain, num_days, save_to_file=None):

    if max(df_rain['trigger']) == 1:
        trigger = num_days
    else:
        trigger = False
    
    with open(save_to_file, "w") as text_file:
        text_file.write(f"TRIGGER: {str(trigger)}")


if __name__ == '__main__':
    collect_rainfall_data()