from geopy.distance import geodesic
import requests
import re
from thefuzz import process, fuzz
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# --- Base class for shared geolocation and flexible input ---
class ScoringCriterion:
    def __init__(self, latitude, longitude, **kwargs):
        self.latitude = latitude
        self.longitude = longitude
        self.extra = kwargs

    def calculate_score(self):
        raise NotImplementedError("Must implement in subclass")

#####################################################################################################################################

# --- Community Transportation Options (refactored with functional logic) ---
class CommunityTransportationOptions(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.stops_df = kwargs.get("stops_df")
        self.routes_df = kwargs.get("routes_df")
        self.dca_pool = kwargs.get("dca_pool", "Metro")
        self.transit_service_days = kwargs.get("transit_service_days", 5)
        self.is_fixed_route = kwargs.get("is_fixed_route", True)
        self.is_site_owned_by_transit_agency = kwargs.get("is_site_owned_by_transit_agency", False)

    def find_nearest_transit_stop(self):
        self.stops_df["distance_miles"] = self.stops_df.apply(
            lambda row: geodesic((self.latitude, self.longitude), (row["stop_lat"], row["stop_lon"])).miles,
            axis=1
        )
        nearest_stop = self.stops_df.loc[self.stops_df["distance_miles"].idxmin()]
        return {
            "stop_id": nearest_stop["stop_id"],
            "stop_name": nearest_stop["stop_name"],
            "stop_lat": nearest_stop["stop_lat"],
            "stop_lon": nearest_stop["stop_lon"],
            "distance_miles": nearest_stop["distance_miles"],
        }

    def verify_transit_hub(self, stop_id):
        stop_routes = self.routes_df[self.routes_df["route_id"] == stop_id]
        return len(stop_routes) >= 3

    def calculate_score(self):
        nearest_stop = self.find_nearest_transit_stop()
        distance = nearest_stop["distance_miles"]
        stop_id = nearest_stop["stop_id"]
        is_hub = self.verify_transit_hub(stop_id)

        expected_score = 0.0

        if self.dca_pool == "Metro":
            if self.is_site_owned_by_transit_agency and is_hub and self.transit_service_days == 7:
                expected_score = 6.0  # A.1
            elif is_hub and self.transit_service_days >= 5:
                if distance <= 0.25:
                    expected_score = 5.0
                elif distance <= 0.5:
                    expected_score = 4.5
                elif distance <= 1.0:
                    expected_score = 4.0

        # Subsection B: General Public Transit Access
        if self.dca_pool == "Metro" and self.is_fixed_route and self.transit_service_days >= 5:
            if distance <= 0.25:
                expected_score = max(expected_score, 3.0)
            elif distance <= 0.5:
                expected_score = max(expected_score, 2.0)
            elif distance <= 1.0:
                expected_score = max(expected_score, 1.0)

        return expected_score

####################################################################################################################################

# --- Desirable/Undesirable Activities ---
class DesirableUndesirableActivities(ScoringCriterion):
    #API_KEY = "AIzaSyBysEHCW8xEMCylTBT-rKUDCldDCAgT2sg"

    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.amenities_df = kwargs.get("amenities_df")
        self.undesirable_df = kwargs.get("undesirable_df")
        self.DESIRABLE_AMENITIES = kwargs.get("DESIRABLE_AMENITIES", {})

    def get_distance(self, lat1, lon1, lat2, lon2):
        return geodesic((lat1, lon1), (lat2, lon2)).miles

    def assign_points(self, distance, group):
        if group == 1:
            if distance <= 0.5:
                return 2.5
            elif distance <= 1:
                return 2
            elif distance <= 1.5:
                return 1.5
        elif group == 2:
            if distance <= 0.5:
                return 2
            elif distance <= 1:
                return 1.5
            elif distance <= 2.5:
                return 1
        return 0

    def calculate_score(self):
        total_points = 0
        deductions = 0

        for _, row in self.amenities_df.iterrows():
            amenity_type = row["amenity_type"]
            if amenity_type in self.DESIRABLE_AMENITIES:
                distance = self.get_distance(self.latitude, self.longitude, row["latitude"], row["longitude"])
                group = self.DESIRABLE_AMENITIES[amenity_type]["group"]
                points = self.assign_points(distance, group)
                total_points += points

        for _, row in self.undesirable_df.iterrows():
            distance = self.get_distance(self.latitude, self.longitude, row["latitude"], row["longitude"])
            if distance <= 0.25:
                deductions += 2

        final_score = max(0, total_points - deductions)
        return final_score

#####################################################################################################################################

# --- Quality Education ---
class QualityEducation(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)
        self.school_df = kwargs.get("school_df")
        self.state_avg_by_year = kwargs.get("state_avg_by_year")

        # Automatically find matching area using shapefile
        gdf = gpd.read_file("../../data/raw/shapefiles/APSBoundaries.json").to_crs(epsg=4326)
        point = Point(self.longitude, self.latitude)  # Note: (lon, lat) order for Point
        self.matching_area = gdf[gdf.contains(point)]

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
        cleaned_names = filtered_df["School Name "].apply(self.preprocess_school_name).tolist()
        best_match, score = process.extractOne(cleaned_input, cleaned_names, scorer=fuzz.token_set_ratio)

        if score > 80:
            return filtered_df[filtered_df["School Name "].apply(self.preprocess_school_name) == best_match].iloc[0]
        return None

    def qualifies_by_A(self, school):
        years = [y for y in [2018, 2019] if y in self.state_avg_by_year and y in school.index and not pd.isna(school[y])]
        if not years:
            return False
        school_avg = school[years].mean()
        state_avg = sum(self.state_avg_by_year[y] for y in years) / len(years)
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

        elementary = self.matching_area.iloc[0].get("Elementary")
        middle = self.matching_area.iloc[0].get("Middle")
        high = self.matching_area.iloc[0].get("High")

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
        self.tracts_gdf = gpd.read_file("../../data/raw/shapefiles/census_tracts.json")
        self.tract_dict = self.find_census_tracts()

    def find_census_tracts(self):
        point = Point(self.latitude, self.longitude)
        gdf_wgs = self.tracts_gdf.to_crs(epsg=4326)
        actual_tract = gdf_wgs[gdf_wgs.contains(point)]

        gdf_meters = self.tracts_gdf.to_crs(epsg=3857)
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
# We didnt do the revitalization score in this project
# "Not located in a Qualified Census Tract" condition missing

# --- Housing Needs Characteristics ---
class HousingNeedsCharacteristics(ScoringCriterion):
    def __init__(self, latitude, longitude, **kwargs):
        super().__init__(latitude, longitude, **kwargs)

        # All required inputs must be passed dynamically
        if "census_tract_data" not in kwargs or "county_data" not in kwargs:
            raise ValueError("'census_tract_data' and 'county_data' must be provided via kwargs")

        self.census_tract_data = kwargs["census_tract_data"]
        self.county_data = kwargs["county_data"]
        self.stable_community_score = None  # To be set externally after StableCommunities score is computed
        self.revitalization_score = kwargs.get("revitalization_score", 0)
        # self.in_qct = kwargs.get("in_qct", True)

    def qualifies_for_housing_need_and_growth(self):
        severe_housing_problem = self.census_tract_data.get("severe_housing_problem", 0) >= 45
        population_growth = (
            self.county_data.get("ten_year_population_growth", False) and
            self.county_data.get("three_year_avg_growth_rate", 0) > 1
        )
        employment_growth = self.county_data.get("employment_growth_rate", 0) > 1
        return severe_housing_problem and (population_growth or employment_growth)

    def qualifies_for_stable_or_redevelopment_bonus(self):
        if self.stable_community_score is None:
            raise ValueError("'stable_community_score' must be set externally before calling this method.")
        return self.qualifies_for_housing_need_and_growth() and (
            self.stable_community_score >= 5 or self.revitalization_score >= 5
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

