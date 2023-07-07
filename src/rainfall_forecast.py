"""
Uses Metno weather API (LocationForecast) to retrieve rainfall predictions (approx. until ~2days in advance).
Aggregate the predicted rainfall in mm (for every timepoint available through the API) over catchment areas.
Obtain a single long-format CSV-file with columns:

|area_name| total_rainfall_mm| avg_rainfall_mm| max_rainfall_mm| min_rainfall_mm| time_of_prediction


-------> first version created by: Misha Klein, August 2022
"""
import numpy as np
import pandas as pd
from tqdm import tqdm
import os
import glob
import shutil
import yaml
import click
import datetime
from utils import * 


@click.command()
@click.option("--settings_file", type = str, required = True, default = './src/settings.yml', show_default = True, help = "YAML file with global settings (input/output file names, etc.)" )
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
    # now_stamp = '2023070708'

    # --- unpack settings ---
    with open(settings_file,'r') as f:
        settings = yaml.safe_load(f)
    USER_AGENT = settings['METnoAPI']['user-agent']
    download_dir = settings['METnoAPI']['download_dir']
    
    country = settings['geoCoordinates']['country_code'].lower() # allow user to either enter "MWI" or "mwi"
    file_points_api_calls = settings['geoCoordinates']['locations_of_interest']


    # --- Azure Cloud Storage settings--- 
    cloud_path = settings['AzureCloudStorage']['main_dir']
    cloud_input_shape_dirname = settings['AzureCloudStorage']['input_dir']
    input_shape_file = settings['AzureCloudStorage']['input_shape_file']
    cloud_input_shape_file = os.path.join(cloud_path, country, 
                                          cloud_input_shape_dirname, 
                                          input_shape_file)
    cloud_output = os.path.join(cloud_path, country, 
                                     f"{now_stamp}")

    
    # --- Local Storage settings --- 
    local_path = settings['localStorage']['main_dir']
    local_input_dir = os.path.join(local_path, 
                                   settings['localStorage']['input_dir'])
    local_output = os.path.join(local_path,
                                settings['localStorage']['output_dir'],
                                f"{now_stamp}")
    local_raw_output = os.path.join(local_output,  
                                    settings['localStorage']['raw_output'])
    
    if not os.path.exists(local_output):
        os.makedirs(local_output)
    if not os.path.exists(local_raw_output):
        os.makedirs(local_raw_output)
    if not os.path.exists('./temp'):
        os.mkdir('./temp')
        os.mkdir('./temp/downloads')


    # ---- output filenames ---- 
    file_geotable = "_".join([f"{now_stamp}", 
                              settings['outputFiles']['geojson_raw']])
    file_raster = "_".join([f"{now_stamp}",
                            settings['outputFiles']['tif_raw']])
    file_trigger = "_".join([f"{now_stamp}",
                             settings['outputFiles']['trigger_status']])
    file_zonal_stats = "_".join([f"{now_stamp}",
                                 settings['outputFiles']['csv_zonal']])
    file_zonal_daily = "_".join([f"{now_stamp}",
                                 settings['outputFiles']['csv_zonal_daily']])
    file_raster_daily = "_".join([f"{now_stamp}",
                                  settings['outputFiles']['tif_raw_daily']])
    file_png_bar_plot_daily = "_".join([f"{now_stamp}",
                                        settings['outputFiles']['png_bar_plot_daily_by_admin']])

    # --- fetch thresholds ----  
    rainfall_thresholds = settings['rainfallThreshold']

    ########################
    # start pipeline here  #
    ########################
    # --- 0. unzip shapefiles from archives (if not already done) ---     
    download_from_azure_cloud_storage( 
        cloud_filename=cloud_input_shape_file,
        local_filename=input_shape_file)

    unzip_shapefiles(dirname='./')


    # -- 1. Get predictions on grid ---
    print("weather predictions for gridpoints...")
    rainfall_gdf = API_requests_at_gridpoints(
        filename_gridpoints = os.path.join(local_input_dir, 
                                           file_points_api_calls), 
        destination_dir = download_dir,
        save_to_file= os.path.join(local_raw_output,
                                   file_geotable), 
        USER_AGENT=USER_AGENT
        )
    # rainfall_gdf = gpd.read_file(os.path.join(local_raw_output,
    #                                           file_geotable))
    print(f"created: {file_geotable}")
    print("--"*8 + "\n"*2)


    # --- 2. Save as TIF file ---
    print("save into TIF format....")
    tif_path = os.path.join(local_raw_output,
                            file_raster)
    rainfall_array = gdf_to_rasterfile(
        rainfall_gdf, 
        save_to_file=tif_path
        )
    print(f"created: {file_raster}")
    print("--"*8 + "\n"*2)

    #---- 3. Aggregate by admin boundary and by day ------
    # Fetch from settings what admin levels you want to use: 
    admin_levels = [f"adm{i}" for i in range(1,5)]
    percentile_col = f"q{rainfall_thresholds['agg_percentile']}"
    for admin_lvl in admin_levels:
         # You put either 'TRUE' or 'FALSE' in settings. 
        if settings['geoCoordinates'][admin_lvl]:  
            # Will now be "mwi_catchment.geojson" , "mwi_adm3.geojson" etc.
            basename = f"{country}_{admin_lvl}.geojson"
            file_admin_shapefile = os.path.join(local_input_dir, 
                                                basename)

            #---- 3.1 aggregate by admin ------
            rainfall_by_admin = pd.DataFrame()
            for band_idx, timepoint in tqdm(enumerate(rainfall_array.time_of_prediction)):
                # aggregate by admin boundary: 

                print(f"performing zonal statistics {admin_lvl} ....")
                raster_path = os.path.join(local_raw_output, 
                                           file_raster)
                by_admin = zonal_statistics(rasterfile=raster_path,
                                            shapefile= file_admin_shapefile,
                                            minval=0.,  # rainfall cannot be negative
                                            aggregate_by=[np.mean, np.std, np.max, np.min],
                                            nameKey = "_".join([admin_lvl.upper(), 'EN']), 
                                            pcodeKey = "_".join([admin_lvl.upper(), 'PCODE']), 
                                            band=band_idx
                                            )

                rename_dict = {"value_1": "mean",
                               "value_2": "std",
                               "value_3": "max",
                               "value_4": "min",
                               "value_5": percentile_col}
                by_admin.rename(rename_dict, axis='columns', inplace=True)
                by_admin['time_of_prediction'] = pd.to_datetime(timepoint.values)
                rainfall_by_admin = pd.concat([rainfall_by_admin, by_admin])

            rainfall_by_admin.reset_index(drop=True, inplace=True)
            filename_zonal_stats_admin = "_".join([file_zonal_stats,admin_lvl])+'.csv'
            rainfall_by_admin.to_csv(
                os.path.join(local_raw_output,filename_zonal_stats_admin), 
                index=False)
            print(f"created: {filename_zonal_stats_admin}")


            print(f"determining daily aggregates for {admin_lvl} ...")
            #---- 3.2 Aggregate by day ------
            file_zonal_daily_admin = "_".join([file_zonal_daily,admin_lvl])+'.csv'
            file_bar_plot_admin = "_".join([file_png_bar_plot_daily, admin_lvl])+'.png'
            rainfall_by_admin_by_day, by_admin_by_day = \
                daily_aggregates_per_admin(
                rainfall_by_admin, 
                settings,
                rainfall_thresholds=rainfall_thresholds, 
                save_to_file=os.path.join(local_raw_output,file_zonal_daily_admin), 
                save_fig_to_png=os.path.join(local_output,file_bar_plot_admin),
                destination_fldr=local_output,
                timestamp=now_stamp
                )
            print(f"created: {file_zonal_daily_admin}")
            print(f"bar plot: {file_bar_plot_admin}")

            
            print(f"check thresholds for {admin_lvl}...")
            # file_trigger_admin = "_".join([file_trigger, admin_lvl]) + '.txt'
            check_threshold(rainfall_by_admin_by_day, 
                            'ONE-DAY', 
                            save_to_file=os.path.join(local_raw_output,file_trigger))
            check_threshold(by_admin_by_day, 
                            'THREE-DAY', 
                            save_to_file=os.path.join(local_raw_output,file_trigger))
            print("--"*8 + "\n"*2)


   # ---- 4. display daily aggegrates (determine values for all locations requested by API for plotting purposes) --- 
    print(f"determining daily aggregates for every location....")


    daily_rainfall_arr = \
        daily_aggregates_per_location(
            rainfall_gdf, 
            save_to_file=os.path.join(local_raw_output, file_raster_daily))
    print("creating PNG images .....")
    plot_rainfall_map_per_day(
        rainfall_da=daily_rainfall_arr,
        settings=settings,
        shapefile_fldr=local_input_dir,
        destination_fldr=local_output,
        timestamp=now_stamp)

    print(f"wrote PNG files into: {local_output}")
    print("--"*8 + "\n"*2)


    # # --- write output files to cloud if needed  ---
    # NOTE: It is assumed you wrote all files into the same directory on local 
    if store_in_cloud:
        output_files = [f for f in glob.glob(f'{local_output}/**', recursive=True) if os.path.isfile(f)]
        for file_on_local in output_files:
            file_in_cloud = os.path.join(cloud_output, 
                                         file_on_local.split('/')[-1])
            write_to_azure_cloud_storage(local_filename=file_on_local, 
                                         cloud_filename=file_in_cloud)
            print(f"created: {file_in_cloud} in Azure datalake")
        print("--"*8 + "\n"*2)

    if remove_temp:
        shutil.rmtree('./temp/')
        print("removed temporary files")

    print("done")
    return


if __name__ == '__main__':
    collect_rainfall_data()