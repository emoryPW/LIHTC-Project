#!/usr/bin/env python
# coding: utf-8

# In[4]:


import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point
import numpy as np
from geopy.distance import geodesic


# In[ ]:


# Note: if getting error "not recognized as being in a supported file format. It might help to specify the correct driver explicitly by prefixing the file path with '<DRIVER>:', e.g. 'CSV:path'.", then run 
# git lfs pull

census_tracts = gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp")
ga_tracts = census_tracts.to_crs(epsg=4326)


# In[7]:


def find_census_tracts(lat, lon, census_tracts_gdf):
    """
    Identify the census tract containing the point and census tracts within 0.25 miles.
    """
    point = Point(lon, lat)
    
    # Ensure the census tracts are in WGS 84 (EPSG:4326) for point lookup
    census_tracts_gdf = census_tracts_gdf.to_crs(epsg=4326)
    actual_tract = census_tracts_gdf[census_tracts_gdf.contains(point)]
    
    # Convert to a projected CRS (meters) for distance calculations
    census_tracts_meters = census_tracts_gdf.to_crs(epsg=3857)
    point_meters = gpd.GeoSeries([point], crs=4326).to_crs(epsg=3857).iloc[0]
    
    # Buffer 0.25 miles (~402 meters) and find nearby census tracts
    point_buffer = point_meters.buffer(402)  
    nearby_tracts = census_tracts_meters[census_tracts_meters.intersects(point_buffer)]
    
    tract_dict = {}
    if not actual_tract.empty:
        tract_dict["actual"] = actual_tract.iloc[0]["GEOID"]  
    
    for idx, row in nearby_tracts.iterrows():
        if row["GEOID"] != tract_dict.get("actual"):
            tract_dict[f"tract{idx}"] = row["GEOID"]
    
    return tract_dict


# In[8]:


def calculate_indicators_score(tract_dict, indicators_df):
    """
    Calculate the number of indicators above the 50th percentile and determine the score.
    """
    indicators = [
        "above_median_Environmental Health Index",
        "above_median_Transit Access Index",
        "above_median_Percent of Population Above the Poverty Level",
        "above_median_Median Income",
        "above_median_Jobs Proximity Index"
    ]
    
    actual_tract = tract_dict.get("actual")
    
    # Ensure census tract column is treated as string for proper matching
    indicators_df["2020 Census Tract"] = indicators_df["2020 Census Tract"].astype(str)
    
    if actual_tract and actual_tract in indicators_df["2020 Census Tract"].values:
        actual_data = indicators_df[indicators_df["2020 Census Tract"] == actual_tract]
        actual_count = actual_data[indicators].sum(axis=1).iloc[0]  # Use .iloc[0] to extract value properly
    else:
        actual_count = 0
    
    near_counts = []
    for key, tract in tract_dict.items():
        if key == "actual":
            continue
        if tract in indicators_df["2020 Census Tract"].values:
            near_data = indicators_df[indicators_df["2020 Census Tract"] == tract]
            near_counts.append(near_data[indicators].sum(axis=1).iloc[0])
    
    near_max = max(near_counts) if near_counts else 0
    
    # Determine points based on the rules
    if actual_count >= 4:
        score = 10
    elif actual_count == 3:
        score = 8
    elif actual_count == 2:
        score = 6
    elif near_max >= 4:
        score = 9
    elif near_max == 3:
        score = 7
    elif near_max == 2:
        score = 5
    else:
        score = 0
    
    return {
        "actual_tract": actual_tract,
        "actual_count": actual_count,
        "nearby_max": near_max,
        "score": score
    }

# Load the census tracts shapefile
gdf = gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp")
gdf = gdf.to_crs(epsg=4326)  

# Load the indicators dataset
indicators_df = pd.read_csv("../../data/processed/scoring_indicators/stable_communities_2024_processed_v3.csv")


# In[9]:


def calculate_indicators_score(tract_dict, indicators_df):
    """
    Calculate the Stable Communities score for a LIHTC development based on QAP rules:
    - Use actual tract score if all qualifying indicators are in that tract (2–4 indicators).
    - Else, use nearby tract score (2–4 indicators) with 1 point deducted.
    """
    # These are the columns that reflect whether an indicator is above the pool-specific 50th percentile
    indicators = [
        "above_median_Environmental Health Index",
        "above_median_Transit Access Index",
        "above_median_Percent of Population Above the Poverty Level",
        "above_median_Median Income",
        "above_median_Jobs Proximity Index"
    ]

    indicators_df["2020 Census Tract"] = indicators_df["2020 Census Tract"].astype(str)
    actual_tract = tract_dict.get("actual")

    # --- Actual tract flags ---
    actual_flags = pd.Series([0] * len(indicators), index=indicators)
    if actual_tract and actual_tract in indicators_df["2020 Census Tract"].values:
        actual_row = indicators_df[indicators_df["2020 Census Tract"] == actual_tract]
        actual_flags = actual_row[indicators].iloc[0]
    actual_count = int(actual_flags.sum())

    # --- Nearby tract flags (only nearby, excluding actual) ---
    nearby_flags = pd.Series([0] * len(indicators), index=indicators)
    for key, tract in tract_dict.items():
        if key == "actual":
            continue
        if tract in indicators_df["2020 Census Tract"].values:
            row = indicators_df[indicators_df["2020 Census Tract"] == tract]
            flags = row[indicators].iloc[0]
            nearby_flags = nearby_flags.combine(flags, func=max)
    nearby_count = int(nearby_flags.sum())

    # --- Combined flags (actual + all nearby) ---
    combined_flags = actual_flags.combine(nearby_flags, func=max)
    combined_count = int(combined_flags.sum())

    # --- Actual-only scoring (must come 100% from actual tract) ---
    if actual_count >= 4:
        actual_only_score = 10
    elif actual_count == 3:
        actual_only_score = 8
    elif actual_count == 2:
        actual_only_score = 6
    else:
        actual_only_score = 0

    # --- Nearby scoring (uses combined indicators) ---
    if nearby_count > 0:
        if combined_count >= 4:
            nearby_score = 9
        elif combined_count == 3:
            nearby_score = 7
        elif combined_count == 2:
            nearby_score = 5
        else:
            nearby_score = 0
    else:
        nearby_score = 0 

    return {
        "actual_tract": actual_tract,
        "actual_count": actual_count,
        "nearby_count": nearby_count,
        "combined_count": combined_count,
        "actual_only_score": actual_only_score,
        "nearby_score": nearby_score
    }

    # indicators_df["2020 Census Tract"] = indicators_df["2020 Census Tract"].astype(str)
    # actual_tract = tract_dict.get("actual")

    # # Get indicator flags for actual tract
    # actual_flags = pd.Series([0]*len(indicators), index=indicators)
    # if actual_tract and actual_tract in indicators_df["2020 Census Tract"].values:
    #     row = indicators_df[indicators_df["2020 Census Tract"] == actual_tract]
    #     actual_flags = row[indicators].iloc[0]

    # # Get indicator flags from all nearby tracts (combined)
    # nearby_flags = pd.Series([0]*len(indicators), index=indicators)
    # for key, tract in tract_dict.items():
    #     if key == "actual":
    #         continue
    #     if tract in indicators_df["2020 Census Tract"].values:
    #         row = indicators_df[indicators_df["2020 Census Tract"] == tract]
    #         flags = row[indicators].iloc[0]
    #         nearby_flags = nearby_flags.combine(flags, func=max)

    # # Check if ANY indicators came from nearby tracts
    # mixed_sources = any((actual_flags + nearby_flags) > 1) or any(nearby_flags > 0)

    # if mixed_sources:
    #     # Use nearby score, combining all indicator sources
    #     total_indicators = (actual_flags + nearby_flags).clip(upper=1).sum()
    #     if total_indicators >= 4:
    #         score = 9
    #     elif total_indicators == 3:
    #         score = 7
    #     elif total_indicators == 2:
    #         score = 5
    #     else:
    #         score = 0
    #     source = "nearby"
    # else:
    #     # Use within score from actual tract only
    #     total_indicators = actual_flags.sum()
    #     if total_indicators >= 4:
    #         score = 10
    #     elif total_indicators == 3:
    #         score = 8
    #     elif total_indicators == 2:
    #         score = 6
    #     else:
    #         score = 0
    #     source = "actual"

    # return {
    #     "actual_tract": actual_tract,
    #     "actual_count": int(actual_flags.sum()),
    #     "nearby_count": int(nearby_flags.sum()),
    #     "total_unique_indicators": int((actual_flags + nearby_flags).clip(upper=1).sum()),
    #     "score": score,
    #     "used": source
    # }
# Load the census tracts shapefile
gdf = gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp")
gdf = gdf.to_crs(epsg=4326)  

# Load the indicators dataset
indicators_df = pd.read_csv("../../data/processed/scoring_indicators/stable_communities_2024_processed_v3.csv")


# In[14]:


def get_stable_communities_score(lat, lon, score_type, verbose=False):
    tract_info = find_census_tracts(lat, lon, gdf)
    score_info = calculate_indicators_score(tract_info, indicators_df)
    if verbose:
        print(f"Point: ({lat}, {lon})")
        print("Score Info:", score_info)
    if score_type == "use_only_actual_tract":
        return score_info["actual_only_score"]
    elif score_type == "use_nearby_tract":
        return score_info["nearby_score"]
    else:
        raise ValueError("Invalid score_type. Choose 'actual_only' or 'nearby'.")


# In[16]:


# Hertitage Competitive Core
latitude = 33.278968
longitude = -83.965148
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)

print(get_stable_communities_score(33.278968,-83.965148, score_type = 'use_only_actual_tract'))
print(get_stable_communities_score(33.278968,-83.965148, score_type = 'use_nearby_tract'))


# In[15]:


# Jonesboro Appartments
latitude = 33.690717
longitude = -84.36506
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)

print(get_stable_communities_score(33.690717,-84.36506, score_type = 'use_only_actual_tract'))
print(get_stable_communities_score(33.690717,-84.36506, score_type = 'use_nearby_tract'))


# In[78]:


# The Benson
latitude = 31.811994
longitude = -81.604555
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)


# In[79]:


# Retreat at McIntosh Farms
latitude = 31.63724
longitude = -84.24108
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)


# In[80]:


# Westchester Place
latitude = 33.558082
longitude = -84.338218
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)


# In[81]:


# The Shelby
latitude = 33.856192
longitude = -84.347348
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)


# In[ ]:


# Berwick Sr II
latitude = 32.0317
longitude = -81.22135
tract_info = find_census_tracts(latitude, longitude, gdf)
score_info = calculate_indicators_score(tract_info, indicators_df)

print("Tract Information:", tract_info)
print("Score Information:", score_info)

