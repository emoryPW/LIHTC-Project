from geopy.distance import geodesic
import requests
import re
from thefuzz import process, fuzz
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import math
import osmnx as ox
import networkx as nx
import numpy as np

######################################################################################################################################

# --- Base class for shared geolocation and flexible input ---
class ScoringCriterion:
    def __init__(self, latitude, longitude, **kwargs):
        self.latitude = latitude
        self.longitude = longitude
        self.extra = kwargs

    def calculate_score(self):
        raise NotImplementedError("Must implement in subclass")

####################################################################################################################################
# kwargs should be a dictionary which has the format:
""" kwargs = {
    # --- CommunityTransportationOptions ---
    "transit_df": pd.read_csv("../../data/raw/scoring_indicators/community_trans_options_sites/georgia_transit_locations_with_hub.csv"),

    # --- DesirableUndesirableActivities ---
    "rural_gdf_unary_union": gpd.read_file("../../data/raw/shapefiles/USDA_Rural_Housing_by_Tract_7054655361891465054/USDA_Rural_Housing_by_Tract.shp").to_crs("EPSG:4326").unary_union,
    "desirable_csv": pd.read_csv("../../data/processed/scoring_indicators/desirable_activities_google_places_v3.csv"),
    "grocery_csv": pd.read_csv("../../data/processed/scoring_indicators/desirable_activities_google_places.csv"),
    "usda_csv": pd.read_csv("../../data/raw/scoring_indicators/food_access_research_atlas.csv", dtype={'CensusTract': str}),
    "tract_shapefile": gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp"),
    "undesirable_csv": pd.read_csv("../../data/processed/scoring_indicators/undesirable_hsi_tri_cdr_rcra_google_places.csv"),

    # --- QualityEducation ---
    "school_df": pd.read_csv("../../data/processed/scoring_indicators/quality_education/Option_C_Scores_Eligibility_with_BTO.csv"),
    "combined_gdf": gpd.read_file("../../data/processed/scoring_indicators/quality_education/merged1.geojson", crs="EPSG:4326"),
    "state_avg_by_year": {
        "elementary": {
            2018: 77.8,
            2019: 79.9
        },
        "middle": {
            2018: 76.2,
            2019: 77
        },
        "high": {
            2018: 75.3,
            2019: 78.8
        }
    },

    # --- StableCommunities ---
    "indicators_df": pd.read_csv("../../data/processed/scoring_indicators/stable_communities_2024_processed.csv"),
    
    "tracts_shp": gpd.read_file("../../data/raw/shapefiles/tl_2024_13_tract/tl_2024_13_tract.shp").to_crs("EPSG:4326"),
    
    # --- HousingNeedsCharacteristics ---
    "census_tract_data": pd.read_csv("../../data/processed/scoring_indicators/housing_needs/merged_housing_data.csv"),
    #"revitalization_score": 4,
    "in_qct": False  # Required for housing need eligibility
} """

#####################################################################################################################################
# --- Community Transportation Options ---
class CommunityTransportationOptions(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.transit_df = kwargs.get("transit_df")  # Pre-loaded transit data

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 3958.8
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_network_walking_distance(self, orig_lat, orig_lon, dest_lat, dest_lon):
        try:
            north = max(orig_lat, dest_lat) + 0.02
            south = min(orig_lat, dest_lat) - 0.02
            east = max(orig_lon, dest_lon) + 0.02
            west = min(orig_lon, dest_lon) - 0.02
            G = ox.graph_from_bbox(north, south, east, west, network_type='walk', simplify=True, truncate_by_edge=True)
            orig_node = ox.nearest_nodes(G, X=orig_lon, Y=orig_lat)
            dest_node = ox.nearest_nodes(G, X=dest_lon, Y=dest_lat)
            distance_meters = nx.shortest_path_length(G, source=orig_node, target=dest_node, weight='length')
            return distance_meters * 0.000621371
        except:
            return None

    def filter_candidate_stops(self):
        candidates = []
        for _, stop in self.transit_df.iterrows():
            dist = self.haversine(self.latitude, self.longitude, stop['latitude'], stop['longitude'])
            if dist <= 1.1:
                stop_data = stop.to_dict()
                stop_data['straight_line_dist'] = dist
                candidates.append(stop_data)
        return candidates

    def calculate_all_walking_distances(self, candidates):
        results = []
        for stop in candidates:
            dist = self.get_network_walking_distance(
                self.latitude, self.longitude, stop['latitude'], stop['longitude'])

            if dist is None:
                # fallback to straight-line if walking distance fails
                dist = self.haversine(self.latitude, self.longitude, stop['latitude'], stop['longitude'])
                stop['used_fallback'] = True
            else:
                stop['used_fallback'] = False 

            stop['walking_distance_miles'] = dist
            results.append(stop)

        return results

    def apply_qap_scoring(self, results):
        POINTS_A = {0.25: 5.0, 0.5: 4.5, 1.0: 4.0}
        POINTS_B = {0.25: 3.0, 0.5: 2.0, 1.0: 1.0}

        score_a, score_b = 0.0, 0.0
        if not results:
            return 0.0

        results.sort(key=lambda x: x['walking_distance_miles'])
        closest_stop = results[0]
        for thresh, pts in sorted(POINTS_B.items()):
            if closest_stop['walking_distance_miles'] <= thresh:
                score_b = pts
                break

        hubs = [r for r in results if r['is_potential_hub']]
        if hubs:
            closest_hub = hubs[0]
            for thresh, pts in sorted(POINTS_A.items()):
                if closest_hub['walking_distance_miles'] <= thresh:
                    score_a = pts
                    break

        return max(score_a, score_b)

    def calculate_score(self):
        candidates = self.filter_candidate_stops()
        results = self.calculate_all_walking_distances(candidates)
        return self.apply_qap_scoring(results)


####################################################################################################################################

# --- Desirable/Undesirable Activities (Updated) ---
class DesirableUndesirableActivities(ScoringCriterion):
    #MILES_PER_DEG = 69.0   
    #RAD_MI        = 5.0 
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.rural_gdf_unary_union = kwargs.get("rural_gdf_unary_union")
        self.desirable_csv = kwargs.get("desirable_csv")
        self.grocery_csv = kwargs.get("grocery_csv")
        self.usda_csv = kwargs.get("usda_csv")
        self.tract_shapefile = kwargs.get("tract_shapefile")
        self.undesirable_csv = kwargs.get("undesirable_csv")
        #print("Loading Done")
    
    def classify_location(self, latitude, longitude):
        rural_union_geom = self.rural_gdf_unary_union
        point = Point(longitude, latitude)
        return point.within(rural_union_geom)

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 3958.8
        phi1, phi2 = map(math.radians, [lat1, lat2])
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def compute_score(self, distance, group):
        is_rural = self.classify_location(self.latitude, self.longitude)

        if group == 1:
            if distance <= 0.55: return 2.5
            elif distance <= 1.05: return 2.0
            elif not is_rural and distance <= 1.5: return 1.5
            elif is_rural and distance <= 2.5: return 2.5
        elif group == 2:
            if distance <= 0.55: return 2.0
            elif distance <= 1.05: return 1.5
            elif not is_rural and distance <= 1.5: return 1.0
            elif is_rural and distance <= 2.5: return 1.0
        return 0

    def compute_desirable_score(self):
        """
        Optimised version: 5-mile bounding box, vectorised Manhattan
        distance, single groupby-min, then QAP scoring.
        """
        df = self.desirable_csv.copy()
        df["lat"] = df["lat"].astype(float)
        df["lon"] = df["lon"].astype(float)

        lat, lon = self.latitude, self.longitude

        # Bounding-box pre-filter
        lat_tol = 5.0 / 69.0
        lon_tol = 5.0 / (69.0 * math.cos(math.radians(lat)))

        df = df[
            (df["lat"].between(lat - lat_tol, lat + lat_tol)) &
            (df["lon"].between(lon - lon_tol, lon + lon_tol))
        ].copy()

        if df.empty:
            return 0.0

        # Vectorised Manhattan distance for remaining rows 
        lat_arr = df["lat"].values
        lon_arr = df["lon"].values

        lat_diff = np.abs(lat_arr - lat) * 69.0
        lon_diff = np.abs(lon_arr - lon) * 69.0 * np.cos(
            np.radians((lat_arr + lat) / 2)
        )
        df["distance"] = lat_diff + lon_diff

        # Keep only amenities truly ≤ 5 mi
        df = df[df["distance"] <= 5.0]
        if df.empty:
            return 0.0

        # One pass: closest distance per amenity_key 
        closest = (
            df.groupby(df["amenity_key"].str.lower())["distance"]
            .min()                    
            .to_dict()
        )

        # QAP amenity: group mapping and scoring
        amenity_groups = {
            "national_big_box_store": 1, "retail_store": 2,      "grocery_store": 1,
            "restaurant": 2,            "hospital": 1,           "medical_clinic": 1,
            "pharmacy": 1,              "technical_college": 2,  "school": 1,
            "town_square": 1,           "community_center": 1,   "public_park": 1,
            "library": 1,               "fire_police_station": 2,"bank": 2,
            "place_of_worship": 2,      "post_office": 2
        }

        total_score = 0.0
        for amenity, group in amenity_groups.items():
            dist = closest.get(amenity)         
            if dist is None:
                continue
            total_score += self.compute_score(dist, group)  

        return total_score

    def check_grocery_eligibility(self):
        df = self.grocery_csv
        df_grocery = df[df['amenity_key'].str.lower() == 'grocery_store'].copy()
        if df_grocery.empty: return False, None
        df_grocery['distance'] = df_grocery.apply(
            lambda row: self.haversine(self.latitude, self.longitude, row['lat'], row['lon']), axis=1)
        return df_grocery['distance'].min() <= 0.25, df_grocery['distance'].min()

    def check_food_desert_status(self):
        tracts = self.tract_shapefile
        tract_field = 'GEOID' if 'GEOID' in tracts.columns else 'CensusTract'
        site_point = Point(self.longitude, self.latitude)
        site_gdf = gpd.GeoDataFrame({'geometry': [site_point]}, crs='EPSG:4326').to_crs(tracts.crs)
        join_result = gpd.sjoin(site_gdf, tracts, how='left', predicate='within')
        if join_result.empty: return False, None, None
        tract_id = str(join_result.iloc[0][tract_field]).strip()
        usda_df = self.usda_csv
        usda_row = usda_df[usda_df['CensusTract'].str.strip() == tract_id]
        if usda_row.empty: return False, tract_id, None
        flag = usda_row.iloc[0]['LILATracts_1And10']
        return flag in [1, True, '1'], tract_id, flag

    def compute_food_desert_deduction(self):
        qualifies, dist = self.check_grocery_eligibility()
        in_fd, tract_id, flag = self.check_food_desert_status()
        return 2 if in_fd and not qualifies else 0

    def get_undesirable_deduction(self):
        df = self.undesirable_csv
        df['distance'] = df.apply(
            lambda row: self.haversine(self.latitude, self.longitude, row['site_latitude'], row['site_longitude']), axis=1)
        return len(df[df['distance'] <= 0.25]) * 2

    def calculate_score(self):
        desirable = self.compute_desirable_score()
        #print("desirable_score done")
        food_deduction = self.compute_food_desert_deduction()
        #print("food done")
        undesirable_deduction = self.get_undesirable_deduction()
        #print("undesirable done")
        final = max(0, desirable - (food_deduction + undesirable_deduction))
        return min(final, 20)

#####################################################################################################################################

# --- Quality Education ---
class QualityEducation(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.school_df = kwargs.get("school_df")
        self.state_avg_by_year = kwargs.get("state_avg_by_year")
        self.combined_gdf = kwargs.get("combined_gdf")

        point = Point(self.longitude, self.latitude)  # Note: (lon, lat) order for Point
        self.matching_area = self.combined_gdf[self.combined_gdf.contains(point)]

    def preprocess_school_name(self, name):
        name = re.sub(r'[^\w\s]', '', str(name).lower())
        name = re.sub(r'\b\w\s?\.?\s?', '', name)
        suffixes = ["elementary", "middle", "high", "school", "academy", "jr", "sr", "dr"]
        tokens = [token for token in name.split() if token not in suffixes]
        return " ".join(tokens).strip()

    def find_best_match(self, school_name, school_type):
        grade_cluster = {"elementary": "E", "middle": "M", "high": "H"}.get(school_type.lower())
        filtered_df = self.school_df[self.school_df["Grade Cluster"] == grade_cluster]
        if filtered_df.empty:
            return None

        cleaned_input = self.preprocess_school_name(school_name)
        cleaned_names = filtered_df["School Name"].apply(self.preprocess_school_name).tolist()
        best_match, score = process.extractOne(cleaned_input, cleaned_names, scorer=fuzz.token_set_ratio)

        if score > 80:
            return filtered_df[filtered_df["School Name"].apply(self.preprocess_school_name) == best_match].iloc[0]
        return None

    def qualifies_by_A(self, school):
        grade_cluster = school.get("Grade Cluster", "").strip().upper()
        cluster_key = {"E": "elementary", "M": "middle", "H": "high"}.get(grade_cluster)
        if not cluster_key:
            return False

        if cluster_key not in self.state_avg_by_year:
            return False

        years = [y for y in [2018, 2019] if y in self.state_avg_by_year[cluster_key] and y in school.index and not pd.isna(school[y])]
        if not years:
            return False

        school_avg = school[years].mean()
        state_avg = sum(self.state_avg_by_year[cluster_key][y] for y in years) / len(years)
        return school_avg > state_avg

    def qualifies_by_B(self, school):
        return school.get('Beating the Odds', False)

    def qualifies_by_C(self, school):
        try:
            return (
                float(school['YoY Average']) > 0 and
                float(school['Average score']) >= float(school['Applicable 25th Percentile'])
            )
        except (ValueError, TypeError, KeyError):
            return False

    def grade_cluster_to_grades(self, cluster):
        mapping = {
            'E': list(range(0, 6)),
            'M': list(range(6, 9)),
            'H': list(range(9, 13)),
        }
        return mapping.get(str(cluster).strip().upper(), [])

    def calculate_score(self):
        if self.matching_area is None or self.matching_area.empty:
            return 0

        elementary = self.matching_area.iloc[0].get("elementary")
        middle = self.matching_area.iloc[0].get("middle")
        high = self.matching_area.iloc[0].get("high")

        best_elementary = self.find_best_match(elementary, "elementary")
        best_middle = self.find_best_match(middle, "middle")
        best_high = self.find_best_match(high, "high")

        total_qualified_grades = set()
        tenancy_type = "family"

        for school in [best_elementary, best_middle, best_high]:
            if school is None or not isinstance(school, pd.Series):
                continue
            if self.qualifies_by_A(school) or self.qualifies_by_B(school) or self.qualifies_by_C(school):
                grades = self.grade_cluster_to_grades(school.get('Grade Cluster', ''))
                total_qualified_grades.update(grades)
                tenancy_type = school.get('tenancy_type', tenancy_type)

        grade_count = len(total_qualified_grades)

        if grade_count == 0:
            return 0
        elif grade_count == 3:
            return 1
        elif grade_count == 7:
            return 1.5
        elif grade_count == 13:
            return 3 if tenancy_type.lower() == 'family' else 2
        elif 3 < grade_count < 7:
            return 1
        elif 7 < grade_count < 13:
            return 1.5
        return 0

####################################################################################################################################

# --- Stable Communities ---
class StableCommunities(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.indicators_df = kwargs.get("indicators_df")
        self.tracts_shp = kwargs.get("tracts_shp")
        self.tract_dict = self.find_census_tracts()

    def find_census_tracts(self):
        point = Point(self.longitude, self.latitude)
        actual_tract = self.tracts_shp[self.tracts_shp.contains(point)]

        gdf_meters = self.tracts_shp.to_crs(epsg=3857)
        point_meters = gpd.GeoSeries([point], crs=4326).to_crs(epsg=3857).iloc[0]
        point_buffer = point_meters.buffer(402)
        nearby_tracts = gdf_meters[gdf_meters.intersects(point_buffer)]

        tract_dict = {}
        if not actual_tract.empty:
            tract_dict["actual"] = actual_tract.iloc[0]["GEOID"]

        for idx, row in nearby_tracts.iterrows():
            if row["GEOID"] != tract_dict.get("actual"):
                tract_dict[f"tract{idx}"] = row["GEOID"]

        return tract_dict

    def calculate_score(self):
        indicators = [
            "above_median_Environmental Health Index",
            "above_median_Transit Access Index",
            "above_median_Percent of Population Above the Poverty Level",
            "above_median_Median Income",
            "above_median_Jobs Proximity Index"
        ]

        actual_tract = self.tract_dict.get("actual")
        self.indicators_df["2020 Census Tract"] = self.indicators_df["2020 Census Tract"].astype(str)

        if actual_tract and actual_tract in self.indicators_df["2020 Census Tract"].values:
            actual_data = self.indicators_df[self.indicators_df["2020 Census Tract"] == actual_tract]
            actual_count = actual_data[indicators].sum(axis=1).iloc[0]
        else:
            actual_count = 0

        near_counts = []
        for key, tract in self.tract_dict.items():
            if key == "actual":
                continue
            if tract in self.indicators_df["2020 Census Tract"].values:
                near_data = self.indicators_df[self.indicators_df["2020 Census Tract"] == tract]
                near_counts.append(near_data[indicators].sum(axis=1).iloc[0])

        near_max = max(near_counts) if near_counts else 0

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

        return score

###################################################################################################################################

# --- Housing Needs Characteristics ---
class HousingNeedsCharacteristics(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)

        self.tracts_gdf = kwargs.get("tracts_shp")
        self.census_tract_data_df = kwargs.get("census_tract_data", {})
        self.stable_community_score = kwargs.get("stable_community_score")
        if self.stable_community_score is None:
            try:
                self.stable_community_score = StableCommunities(latitude, longitude, **kwargs).calculate_score()
            except Exception as e:
                print("Warning: Failed to calculate StableCommunities score internally:", e)
                self.stable_community_score = None
        
        # self.revitalization_score = kwargs.get("revitalization_score")
        """ if self.revitalization_score is None:
            try:
                self.revitalization_score = RevitalizationRedevelopmentPlans(latitude, longitude, **kwargs).calculate_score()
            except Exception as e:
                print("Warning: Failed to calculate RevitalizationRedevelopmentPlans score internally:", e)
                self.revitalization_score = None """
        # manually give whether in qct
        self.in_qct = kwargs.get("in_qct", True)

        point = Point(self.longitude, self.latitude)
        match = self.tracts_gdf[self.tracts_gdf.contains(point)]
        if not match.empty:
            geoid = str(match.iloc[0]["GEOID"])
            self.census_tract_data = self.census_tract_data_df.get(geoid, {})
        else:
            self.census_tract_data = {}

    def qualifies_for_housing_need_and_growth(self):
        severe_housing_problem = (self
                                .census_tract_data
                                .get("% of rental units occupied by 80% AMI and below with Severe Housing Problems", 0) >= 45)
        population_growth = (
            self.census_tract_data.get("Is 2021 greater than 2011?", False) and
            self.census_tract_data.get("Average: YoY Growth 2018-2021", 0) > 1
        )
        employment_growth = self.census_tract_data.get("Average change: 2020-2022", 0) > 1
        not_in_qct = not self.in_qct
        return (severe_housing_problem or population_growth or employment_growth) and not_in_qct

    def qualifies_for_stable_or_redevelopment_bonus(self):
        if self.stable_community_score is None:
            raise ValueError("'stable_community_score' must be set externally before calling this method.")
        return self.qualifies_for_housing_need_and_growth() and (
            self.stable_community_score >= 5 #or self.revitalization_score >= 5
        )

    def calculate_score(self):
        score = 0
        if self.qualifies_for_housing_need_and_growth():
            score += 5
        if self.qualifies_for_stable_or_redevelopment_bonus():
            score += 5
        return score

#####################################################################################################################################

# --- Aggregator ---
class AggregateScoringSystem:
    def __init__(self, latitude, longitude, **kwargs):
        self.criteria = [
            CommunityTransportationOptions(latitude, longitude, **kwargs),
            DesirableUndesirableActivities(latitude, longitude, **kwargs),
            QualityEducation(latitude, longitude, **kwargs),
            StableCommunities(latitude, longitude, **kwargs),
            HousingNeedsCharacteristics(latitude, longitude, **kwargs),
        ]

    def calculate_total_score(self):
        return sum(criterion.calculate_score() for criterion in self.criteria)

####################################################################################################################################

