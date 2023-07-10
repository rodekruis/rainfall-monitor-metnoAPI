# rainfall-monitor-metnoAPI

A code to visualise rainfall forecast as maps 3 days lead time (72 hours ahead). It gets free weather data service provided by the [Norwegian Meteorological Institute](https://www.met.no/en).

Built upon [metno-locationforecast](https://github.com/Rory-Sullivan/metno-locationforecast) Python package.

This is developed for Malawi Red Cross Society and Danish Red Cross focused on Southern Region, Malawi.

## What does the code do?
The code comprise of 5 main tasks:
1. Get weather forecast gridded data and extract rainfall forecast for a selected area.
2. Aggregate gridded data per area per 24-hour step (1-day cumulative).
3. Check per area if 1-day cumulative rain exceeds a given threshold.
4. Visualise forecast rainfall over area per each 24-hour step.
5. (for Malawi) This code was dockerised and deployed using Azure Logic App. With the Logic app, warning is automatically sent to selected recipients when the given threshold is exceeded (in step 3) in order to inform early a heavy rain forecasted.

## Set-up guidance

- [Customisation](docs/customisation.md) for an area of interest
- [Deployment](docs/deployment.md)

