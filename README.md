# Project Documentation

## **Project Structure Overview**
This repository contains data and scripts related to replicating and mapping scoring indicators based on the 2024 QAP.

---
## **1️. Data Folder (`data/`)**
This folder contains all datasets used in the project. It is divided into three main subfolders:

### **`data/raw/`**
Contains raw, unprocessed data files.
- **`scoring_indicators`**: The original Excel file pulled from the DCA website containing data on poverty level, environmental health indices, job proximity indices, median income, and transit access indices used for the 2024 applications.
- **`shapefiles/`**: Contains geographic shapefiles for census tracts. These files represent spatial data and are used for mapping and geospatial analysis.


### **`data/preprocessed/`**: contains data put into csv format for further processing and analysis. 
- **`scoring_indicators/`**: contains prepocessed data related to calculating scores. 
  - `above_poverty_level_2024.csv`: Contains data on the percentage of the population above the poverty level for each census tract.  
  - `data_sources_2024.csv`: Lists sources for all indicators used in the analysis.  
  - `environmental_health_index_2024.csv`: Environmental health scores for each census tracts.  
  - `jobs_proximity_index_2024.csv`: Measures how close a census tract is to job opportunities for each tract. 
  - `median_income_2024.csv`: Median income data for each census tract. 
  - `percentiles_2024.csv`: Contains percentile rankings for various indicators.  
  - `transit_access_index_2024.csv`: Measures access to public transportation for each census tract.  

### **`data/processed/`**: Contains final processed datasets ready for use in analysis.
- **`scoring_indicators/`**: Contains final processed datasets to be used to calculate scores for each criteria. 
- **`stable_communities_2024_processed.csv`**  
  - The final dataset containing the processed stable communities scoring indicators.
---

## **2. Scripts Folder (`scripts/`)**: Contains Jupyter Notebooks for running analyses and processing data.

### **`scripts/desirable_undesirable_activities/`**
- `desirable_data_preprocess.ipynb` 
  - Collects desirable amenities across Georgia using the Google Places API using a systematic geographic grid search 
  - Applies filters based on QAP criteria to identify relevant amenities
  - Saves each desirable amenity along with its coordinates and google places type to a csv here: `../../data/preprocessed/scoring_indicators/DesirableUndesirableActivities.ga_desirable_rough.csv`
    - This is the main dataset; test runs for individual counties are also appended to this CSV in the following step
- `desirable_data_processing.ipynb` 
  - Concatenates all csvs from the preprocessing step into a single csv and removes duplicates
  - Saves the final csv to: `../../data/processed/scoring_indicators/desirable_activities_google_places_v2.csv`
- `undesirable_data_preprocess.ipynb` 
  - Aggregates multiple environmental and facility datasets (e.g., RCRA, FRS, TRI, CDR) to identify undesirable or hazardous site locations across Georgia
  - Cleans, merges, and geocodes these datasets as needed and saves them to CSV and GeoPackage files
  - Additionally, uses the Google Places API to identify undesirable amenities (e.g., auto repair shops, nightclubs, airports) through a geographic grid crawl
  - Saves facility datasets (RCRA, FRS, TRI, CDR) to `../../data/preprocessed/scoring_indicators/DesirableUndesirableActivities/*.csv`
  - Saves wetlands shapefile to `../../data/preprocessed/scoring_indicators/ga_wetlands_cleaned.gpkg`
  - Saves Google Places data to `../../data/preprocessed/scoring_indicators/DesirableUndesirableActivities/ga_undesirable_rough.csv`
- `undesirable_data_processing.ipynb` 
  - Merges and standardizes data from multiple sources to build a comprehensive dataset of undesirable activities across Georgia
  - Sources include hazardous site inventories (HSI), toxic chemical releases (TRI), heavy chemical manufacturing (CDR), hazardous waste handling (RCRA), and Google Places API data
  - Final dataset saved to `../../data/processed/scoring_indicators/undesirable_hsi_tri_cdr_rcra_google_places.csv`
- `desirable_undesirable_scoring.ipynb` 
  - Computes a composite score for a proposed LIHTC (Low-Income Housing Tax Credit) site based on nearby desirable and undesirable features, in line with Georgia QAP scoring guidelines
  - Key components include: 
    - Haversine and Manhattan distance functions for location scoring
    - Food desert checks using USDA data and grocery store proximity
    - Deduction logic for nearby undesirable facilities and contaminated sites

- `desirable_undesirable_activities.ipynb` 
  - Computes scores for desirable and undesirable activities using Google Places API.  
  - Fetches nearby amenities and hazardous locations.

### **`scripts/quality_education/`**
- (Currently empty or for future quality education-related analysis.)

### **`scripts/stable_communities/`**
- `stable_communities.ipynb` 
  - Main script for analyzing stable community scores.  
  - Uses preprocessed data from `data/processed/scoring_indicators/`.  

- `stable_communities_data_preprocess.ipynb` →  
  - Cleans and prepares the raw data from `data/raw/scoring_indicators/2024stablecommunities.xlsx`.  
  - Outputs the cleaned csvs to dataset to `data/preprocessed/scoring_indicators/`.
  - Creates a merged data set with all scoring indicators, median values, and logic to compute the score for stable communities
- `stable_communities.ipynb` 
  - Computes a Stable Communities score for a given location based on nearby census tract indicators, using Georgia’s LIHTC scoring criteria
  - Identifies the actual census tract and neighboring tracts within 0.25 miles of a site
  - Uses pre-processed indicator data (e.g., Environmental Health, Transit Access, Median Income) to determine how many indicators are above the 50th percentile
  - Designed to be called via get_stable_communities_score(lat, lon, score_type) with score_type as "use_only_actual_tract" or "use_nearby_tract"


<!-- - `stable_communities_grid.ipynb` →  
  - Generates a spatial grid of stable community scores across Georgia.  
  - Uses geographic data from `data/raw/shapefiles/`. -->

---