import datetime
import pysolar
import pytz
import pandas as pd
import requests
import os
import numpy as np

from solartk.helpers import granularity_to_freq

from typing import List, Dict, Tuple



import pvlib
from pvlib import clearsky, atmosphere, solarposition
from pvlib.location import Location
from pvlib.iotools import read_tmy3

def get_clearsky_irradiance(start_time: datetime.datetime = None, end_time: datetime.datetime = None, timezone: pytz.timezone = None,
                latitude: float = None, longitude: float = None, sun_zenith: pd.DataFrame = None,
                granularity: int = 60, clearsky_estimation_method: str = 'pysolar',
                google_api_key: str = None):



    if (clearsky_estimation_method == 'pysolar' or google_api_key==None):

        ################################################################################## 
        # 
        # Pandas .apply based code, but it is slower than while loop
        # from helpers import granularity_to_freq
        #       
        # datetime_series = pd.date_range(start_time, end_time, freq=granularity_to_freq(granularity))
        # datetime_series_localized = datetime_series.tz_localize(timezone)
        # data = pd.DataFrame({'time':datetime_series_localized})
        # data['altitude_deg'] = data['time'].apply(lambda timestamp: pysolar.solar.get_altitude(latitude, longitude, timestamp))
        # data['clearsky'] = data.apply(lambda row: pysolar.solar.radiation.get_radiation_direct(row['time'], row['altitude_deg']), axis=1)
        # data['time'] = data['time'].apply(lambda x: x.replace(tzinfo=pytz.utc).replace(tzinfo=None))  
        ################################################################################## 

        time = pd.DatetimeIndex(pd.date_range(start_time- 0* pd.Timedelta(hours=1), end_time- 0* pd.Timedelta(hours=1), freq=pd.Timedelta(seconds=granularity)), tz="UTC")
        solpos = pvlib.solarposition.get_solarposition(time, latitude, longitude)
        apparent_zenith = solpos['apparent_zenith']
        airmass = pvlib.atmosphere.get_relative_airmass(apparent_zenith)
        pressure = pvlib.atmosphere.alt2pres(115)
        airmass = pvlib.atmosphere.get_absolute_airmass(airmass, pressure)
        linke_turbidity = pvlib.clearsky.lookup_linke_turbidity(time, latitude, longitude)
        dni_extra = pvlib.irradiance.get_extra_radiation(time)
        #linke_turbidity.mean()["dni"].values

        loc = Location(latitude, longitude)
        c_sky =  clearsky.ineichen(apparent_zenith, airmass, linke_turbidity.mean(), 115, dni_extra)["ghi"].values
        irradiance = pd.DataFrame({'time': time, 'clearsky': c_sky})

    elif (clearsky_estimation_method == 'lau_model' and google_api_key!=None):

        # use google maps python api to get elevation
        gmaps = googlemaps.Client(key=google_api_key)
        elevation_api_response:list = gmaps.elevation((latitude, longitude))
        elevation_km:float = elevation_api_response[0]['elevation']/1000

        # create a date_range and set it as a time column in a dataframe
        datetime_series = pd.date_range(start_time, end_time, freq=granularity_to_freq(granularity))
        # datetime_series_localized = datetime_series.tz_localize(timezone)
        irradiance = pd.DataFrame({'time':datetime_series})

        # based on "E. G. Laue. 1970. The Measurement of Solar Spectral Irradiance at DifferentTerrestrial Elevations.Solar Energy13 (1970)", 
        # Check details on this model on Section 2.4 on PVeducation.org
        irradiance['air_mass'] = 1/(np.cos(sun_zenith) + 0.50572*pow(96.07995 - np.rad2deg(sun_zenith), -1.6364))
        irradiance['clearsky_direct'] = 1.361*((1 - 0.14*elevation_km)*pow(0.7,irradiance['air_mass']**0.678) + 0.14*elevation_km)
        irradiance['clearsky'] = 1000*1.1*irradiance['clearsky_direct']

        # replace nan with 0 and keep only time and clearsky columns
        irradiance['clearsky'] = irradiance['clearsky'].fillna(0)
        irradiance = irradiance[['time', 'clearsky']]

    else:
        raise ValueError('Invalid argument for clearsky_estimation_method or google_api_key.')

    return irradiance


