#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from geopy.distance import geodesic
import math


# In[2]:


# Load all files 
desirable_df = pd.read_csv("../../data/processed/scoring_indicators/desirable_activities_google_places_v2.csv")
grocery_df = pd.read_csv("../../data/processed/scoring_indicators/desirable_activities_google_places.csv")
usda_df = pd.read_csv("../../data/raw/scoring_indicators/food_access_research_atlas.csv", dtype={'CensusTract': str})
tract_gdf = gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp")
undesirable_df = pd.read_csv("../../data/processed/scoring_indicators/undesirable_hsi_tri_cdr_rcra_google_places.csv")
rural_gdf = gpd.read_file("../../data/raw/shapefiles/USDA_Rural_Housing_by_Tract_7054655361891465054/USDA_Rural_Housing_by_Tract.shp").to_crs("EPSG:4326")

# wetlands_filepath = "../../data/preprocessed/scoring_indicators/DesirableUndesirableActivities/ga_wetlands_cleaned.gpkg"


# ### Helper Function

# In[3]:


rural_union_geom = rural_gdf.geometry.union_all()


# In[4]:


def classify_location(lat, lon, rural_union_geom):
    point = Point(lon, lat)
    return point.within(rural_union_geom)


# In[5]:


def manhattan_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Manhattan (taxicab) distance between two points specified by latitude and longitude (in degrees).
    Assumes:
      - 1 degree of latitude is approximately 69 miles.
      - 1 degree of longitude is approximately 69 * cos(mean latitude) miles.
    Returns the distance in miles.
    """
    # Calculate the absolute differences in latitude and longitude.
    lat_diff = abs(lat2 - lat1)
    lon_diff = abs(lon2 - lon1)
    
    # Conversion: approximate 69 miles per degree latitude.
    lat_distance = lat_diff * 69
    
    # Compute the mean latitude (in radians) for scaling the longitude difference.
    mean_lat = math.radians((lat1 + lat2) / 2)
    lon_distance = lon_diff * 69 * math.cos(mean_lat)
    
    return lat_distance + lon_distance


# In[6]:


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    Returns the distance in miles.
    """
    R = 3958.8  
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance


# ### Compute Desirable Activities Score

# In[7]:


def compute_score(distance, group, is_rural):
    """
    Assign points based on the distance from the LIHTC site, the amenity’s scoring group,
    and whether the site is in the rural pool.
    
    For Group 1:
        - distance <= 0.5 miles:      2.5 points
        - distance <= 1 mile:         2.0 points
        - distance <= 1.5 miles (metro): 1.5 points
        - distance <= 2.5 miles (rural): 2.5 points
        
    For Group 2:
        - distance <= 0.5 miles:      2.0 points
        - distance <= 1 mile:         1.5 points
        - distance <= 1.5 miles (metro): 1.0 point
        - distance <= 2.5 miles (rural): 1.0 point
    """

    points = 0.0
    if group == 1:
        if distance <= 0.55:
            points = 2.5
        elif distance <= 1.05:
            points = 2.0
        elif (not is_rural) and distance <= 1.5:
            points = 1.5
        elif is_rural and distance <= 2.5:
            points = 2.5
    elif group == 2:
        if distance <= 0.55:
            points = 2.0
        elif distance <= 1.05:
            points = 1.5
        elif (not is_rural) and distance <= 1.5:
            points = 1.0
        elif is_rural and distance <= 2.5:
            points = 1.0
    return points


# In[ ]:


def compute_desirable_score(lat, lon, is_rural, desirable_df):
    df = desirable_df.copy()


    df['lat'] = df['lat'].astype(float)
    df['lon'] = df['lon'].astype(float)

    # Mapping of amenity names to their scoring groups.
    amenity_groups = {
        "national_big_box_store": 1,
        "retail_store": 2,
        "grocery_store": 1,
        "restaurant": 2,
        "hospital": 1,
        "medical_clinic": 1,
        "pharmacy": 1,
        "technical_college": 2,
        "school": 1,  
        "town_square": 1,
        "community_center": 1,
        "public_park": 1,
        "library": 1,
        "fire_police_station": 2,
        "bank": 2,
        "place_of_worship": 2,
        "post_office": 2
    }

    total_score = 0.0
    scores = {}  

    # Loop through each desirable amenity type
    for amenity, group in amenity_groups.items():
        # Filter to rows matching THE amenity.
        df_subset = df[df['amenity_key'].str.lower() == amenity.lower()]
        if df_subset.empty:
            continue

        # Compute the distance for each record in the subset from the LIHTC development site.
        df_subset = df_subset.copy()  
        df_subset['distance'] = df_subset.apply(
            lambda row: manhattan_distance(lat, lon, row['lat'], row['lon']),
            axis=1
        )

        # Find the nearest amenity of this type (minimum distance)
        min_distance = df_subset['distance'].min()
        # print(f"{amenity}: min_distance = {min_distance}")

        # Compute the score for this amenity based on the computed distance.
        points = compute_score(min_distance, group, is_rural)
        scores[amenity] = {"distance": min_distance, "points": points}
        total_score += points

    return total_score, scores


# ## Compute Undesirable Deduction

# ### Food Deserts

# In[9]:


def check_grocery_store_eligibility(lat, lon, grocery_df):
    """
    Determine if a grocery store is within the qualifying threshold (0.25 miles)
    from the LIHTC site using a preloaded DataFrame and vectorized haversine.
    
    Returns:
        qualifies (bool), min_distance (float)
    """
    # Filter only grocery stores
    df_grocery = grocery_df[grocery_df['amenity_key'].str.lower() == 'grocery_store']
    if df_grocery.empty:
        return False, None
        
    # Calculate distances from the LIHTC site to each grocery store
    df_grocery = df_grocery.copy()
    df_grocery['distance'] = df_grocery.apply(
        lambda row: haversine(lat, lon, row['lat'], row['lon']),
        axis=1
    )
    
    if df_grocery.empty:
        return False, None
    
    min_distance = df_grocery['distance'].min()
    
    # Check if any grocery store is within 0.25 miles
    qualifies = min_distance <= 0.25
    return qualifies, min_distance


# In[ ]:


def check_food_desert_status_csv(lat, lon, usda_df, tract_gdf):
    """
    Determine if the LIHTC site lies in a USDA-designated food desert using a preloaded USDA DataFrame
    and a preloaded tract GeoDataFrame.
    
    Returns:
        in_food_desert (bool), census tract ID (str), USDA flag (int/bool)
    """
    # Determine which column contains the tract ID
    if 'GEOID' in tract_gdf.columns:
        tract_field = 'GEOID'
    elif 'CensusTract' in tract_gdf.columns:
        tract_field = 'CensusTract'
    else:
        # print("Tract shapefile missing 'GEOID' or 'CensusTract' field.")
        return False, None, None

    # Create a GeoDataFrame for the LIHTC site
    site_point = Point(lon, lat)
    site_gdf = gpd.GeoDataFrame({'geometry': [site_point]}, crs='EPSG:4326')
    site_gdf = site_gdf.to_crs(tract_gdf.crs)

    # Perform spatial join to find which tract the site falls in
    join_result = gpd.sjoin(site_gdf, tract_gdf, how='left', predicate='within')

    if join_result.empty:
        # print("LIHTC site does not fall within any census tract.")
        return False, None, None

    # Extract and clean tract ID
    tract_id = str(join_result.iloc[0][tract_field]).strip()

    # Find corresponding USDA row
    usda_row = usda_df[usda_df['CensusTract'].str.strip() == tract_id]

    if usda_row.empty:
        # print(f"No USDA data found for census tract {tract_id}.")
        return False, tract_id, None

    # Check USDA flag for food desert designation
    usda_flag = usda_row.iloc[0]['LILATracts_1And10']
    in_food_desert = usda_flag in [1, '1', True]

    return in_food_desert, tract_id, usda_flag


# In[11]:


def compute_food_desert_deduction(lat, lon, grocery_df, usda_df, tract_gdf):
    """
    Compute a 2-point deduction for food desert status if:
      - No grocery store is within the threshold distance.
      - The site is in a USDA-designated food desert.
    
    Inputs:
        grocery_df: Preloaded DataFrame of grocery stores
        usda_df: Preloaded DataFrame of USDA Food Access data
        tract_gdf: Preloaded GeoDataFrame of census tracts
    """
    # Check for nearby grocery store
    qualifies, min_grocery_distance = check_grocery_store_eligibility(lat, lon, grocery_df)

    # Check if the site falls in a USDA-designated food desert
    in_food_desert, tract_id, usda_flag = check_food_desert_status_csv(lat, lon, usda_df, tract_gdf)

    # Deduct 2 points only if it's in a food desert AND no qualifying grocery is nearby
    deduction = 2 if (in_food_desert and not qualifies) else 0

    details = {
        'qualifies_for_grocery': qualifies,
        'min_grocery_distance': min_grocery_distance,
        'in_food_desert': in_food_desert,
        'census_tract': tract_id,
        'usda_flag': usda_flag,
        'deduction': deduction
    }

    return deduction, details


# ### Inappropriate Surroundings and Environmental Hazards 

# In[ ]:


def get_undesirable_activities(lat, lon, undesirable_df): 
    """
    Get the undesirable activities within a 1-mile radius of the LIHTC development site.
    """
    df = undesirable_df.copy()

    # Compute the distance for each record in the subset from the LIHTC development site.
    df = df.copy()  
    df['distance'] = df.apply(
        lambda row: haversine(lat, lon, row['site_latitude'], row['site_longitude']),
        axis=1
    )
    # Find all undesirable activities within 1 mile
    nearby_activities = df[df['distance'] <= 0.25]
    total_deduction = len(nearby_activities) * 2

    # print(f"Found {len(nearby_activities)} undesirable activities within 0.25 miles:")
    # if not nearby_activities.empty:
    #     print(nearby_activities[['undesirable_activity', 'site_latitude', 'site_longitude', 'distance']])
    # else:
    #     print("No undesirable activities within the threshold.")
    
    return total_deduction, nearby_activities


# ### Wetlands

# In[ ]:


# def compute_wetland_deduction(lihtc_lat, lihtc_lon, wetlands_filepath,
#                               buffer_meters=402, threshold_acres=1.0, deduction_points=2):
#     wetlands_gdf = gpd.read_file(wetlands_filepath)
#     wetlands_proj = wetlands_gdf.to_crs(epsg=3857)
#     site_point = Point(lihtc_lon, lihtc_lat)
#     site_gdf = gpd.GeoDataFrame({'geometry': [site_point]}, crs='EPSG:4326')
#     site_proj = site_gdf.to_crs(epsg=3857)
#     site_buffer = site_proj.buffer(buffer_meters).iloc[0]
#     wetlands_in_buffer = wetlands_proj[wetlands_proj.intersects(site_buffer)]
#     total_wetland_acres = wetlands_in_buffer['acres'].sum()
#     deduction = deduction_points if total_wetland_acres >= threshold_acres else 0
#     return deduction, total_wetland_acres, wetlands_in_buffer


# ## Compute Overall Score

# In[13]:


def compute_overall_score(lat, lon, is_rural,
                          desirable_df, grocery_df, usda_df, tract_gdf, undesirable_df):

    # Compute Desirable Activities Score
    desirable_score, desirable_details = compute_desirable_score(lat, lon, is_rural, desirable_df)
    
    # Compute Food Desert Deduction
    food_desert_deduction, food_desert_details = compute_food_desert_deduction(
        lat, lon, grocery_df, usda_df, tract_gdf
    )
    
    # Compute Undesirable Activities Deduction
    undesirable_deduction, undesirable_details = get_undesirable_activities(lat, lon, undesirable_df)
    
    # # Compute Wetlands Deduction
    # wetlands_deduction, total_wetland_acres, wetlands_details = compute_wetland_deduction(
    #     lihtc_lat, lihtc_lon, wetlands_filepath,
    #     buffer_meters=wetlands_buffer, threshold_acres=wetlands_threshold_acres,
    #     deduction_points=wetlands_deduction_points
    # )
    
    total_deductions = food_desert_deduction + undesirable_deduction
    overall_score = desirable_score - total_deductions
    overall_score = max(0, overall_score)  # Ensure overall score is not negative.
    final_score = min(overall_score, 20)

    breakdown = {
        "Desirable Score": desirable_score,
        "Food Desert Deduction": food_desert_deduction,
        "Undesirable Activities Deduction": undesirable_deduction,
        "Total Deductions": total_deductions,
        "Overall Score": overall_score,
        "Final Score": final_score,
        "Details": {
            "desirable": desirable_details,
            "food_desert": food_desert_details,
            "undesirable": undesirable_details
        }
    }
    return breakdown


# In[ ]:


if __name__ == "__main__":
    lat = 32.082897
    lon = -83.78846

    is_rural = classify_location(lat, lon, rural_union_geom)

    result = compute_overall_score(
        lat, lon, is_rural,
        desirable_df, grocery_df, usda_df, tract_gdf, undesirable_df
    )
        
    # # Print results
    # print("Overall Desirable/Undesirable Activities Score Breakdown:")
    # for key, value in result.items():
    #     if key != "Details":
    #         print(f"{key}: {value}")
    # print("\nDetailed Breakdown:")
    # for key, detail in result["Details"].items():
    #     print(f"{key}:\n{detail}\n")

