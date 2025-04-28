# LIHTC Project Documentation

**Purpose**  
Help affordable‐housing developers locate high-potential sites—and help policy-makers spot equity gaps—by replicating the Georgia Department of Community Affairs (DCA) Qualified Allocation Plan (QAP) scoring rules in code and mapping the results.

---

## **Project Structure Overview**
This repository contains data and scripts related to replicating and mapping scoring indicators based on the 2024 QAP.

---

## Repository Layout

```text
.
├── data/                   # Raw → preprocessed → processed datasets
│   ├── raw/                # Source files exactly as downloaded
│   ├── preprocessed/       # Cleaned / reshaped for analysis (CSV / GeoJSON)
│   ├── processed/          # Final, ready-to-use indicator tables for scoring functions
│   └── map/                # GeoJSONs files used to create maps 
|
├── scripts/                # Python modules & notebooks for each QAP category
│   ├── aggregate_scoring/  # Combines all category scores and creates final scoring dataset for mapping 
│   ├── community_transportation_options/ # Scripts for preprocessing and processing needed data, and creating score function for Community Transportation Options
│   ├── desirable_undesirable_activities/ # Scripts for collecting, preprocessing, and processing needed data, and creating score function for Desirable/Undesirable Activities
│   ├── housing_needs_characteristics/ # Scripts for preprocessing and processing needed data, and creating score function for Housing Needs Characteristics
│   ├── quality_education_area/ # Scripts for preprocessing and processing needed data, and creating score function for Quality Education Area
│   ├── stable_communities/ # Scripts for preprocessing and processing needed data, and creating score function for Stable Communities
│   └── maps/               # Script to make folium maps
|
├── maps/                   # HTML heatmaps exported for slide decks
├── requirements.txt        # Exact package versions
└── README.md               # You are here

---

