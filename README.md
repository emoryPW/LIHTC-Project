# Project Documentation

## **Project Structure Overview**
This repository contains data and scripts related to replicating scoring scoring indicators based on the 2024 QAP.


---
## **1️. Data Folder (`data/`)**
This folder contains all datasets used in the project. It is divided into three main subfolders:

### **`data/raw/`**
Contains raw, unprocessed data files.
- **`scoring_indicators/2024stablecommunities.xlsx`**: The original Excel file pulled from the DCA website containing data on poverty level, environmental health indices, job proximity indices, median income, and transit access indices used for the 2024 applications.
- **`shapefiles/tl_2024_13_tract/`**: Contains geographic shapefiles for census tracts. These files represent spatial data and are used for mapping and geospatial analysis.

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
- `desirable_undesirable_activities.ipynb` 
  - Computes scores for desirable and undesirable activities using Google Places API.  
  - Fetches nearby amenities and hazardous locations.

### **`scripts/quality_education/`**
- (Currently empty or for future quality education-related analysis.)

### **🔹 `scripts/stable_communities/`**
- `stable_communities.ipynb` 
  - Main script for analyzing stable community scores.  
  - Uses preprocessed data from `data/processed/scoring_indicators/`.  

- `stable_communities_data_preprocess.ipynb` →  
  - Cleans and prepares the raw data from `data/raw/scoring_indicators/2024stablecommunities.xlsx`.  
  - Outputs the cleaned csvs to dataset to `data/preprocessed/scoring_indicators/`.
  - Creates a merged data set with all scoring indicators, median values, and logic to compute the score for stable communities

<!-- - `stable_communities_grid.ipynb` →  
  - Generates a spatial grid of stable community scores across Georgia.  
  - Uses geographic data from `data/raw/shapefiles/`. -->

---