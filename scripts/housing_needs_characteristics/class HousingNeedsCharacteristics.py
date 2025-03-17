class HousingNeedsCharacteristics:
    def __init__(self, census_tract_data, county_data, stable_community_score, revitalization_score):
        """
        Initializes the Housing Needs Characteristics scoring system.
        :param census_tract_data: Dictionary containing HUD-defined severe housing problems for the Census Tract.
        :param county_data: Dictionary containing population and employment growth statistics for the county.
        :param stable_community_score: Integer score for Stable Communities criteria.
        :param revitalization_score: Integer score for Revitalization/Redevelopment Plans criteria.
        """
        self.census_tract_data = census_tract_data
        self.county_data = county_data
        self.stable_community_score = stable_community_score
        self.revitalization_score = revitalization_score
    
    def qualifies_for_housing_need_and_growth(self):
        """
        Determines if the project qualifies for Housing Need and Growth points (5 points).
        :return: Boolean
        """
        severe_housing_problem = self.census_tract_data.get("severe_housing_problem", 0) >= 45
        population_growth = (
            self.county_data.get("ten_year_population_growth", False) and
            self.county_data.get("three_year_avg_growth_rate", 0) > 1
        )
        employment_growth = self.county_data.get("employment_growth_rate", 0) > 1
        
        return severe_housing_problem or population_growth or employment_growth
    
    def qualifies_for_stable_or_redevelopment_bonus(self):
        """
        Determines if the project qualifies for additional points based on Stable Communities or Revitalization Plans.
        :return: Boolean
        """
        return self.qualifies_for_housing_need_and_growth() and (
            self.stable_community_score >= 5 or self.revitalization_score >= 5
        )
    
    def calculate_total_score(self):
        """
        Calculates the total Housing Needs Characteristics score.
        :return: Integer (0 to 10 points)
        """
        score = 0
        if self.qualifies_for_housing_need_and_growth():
            score += 5
        if self.qualifies_for_stable_or_redevelopment_bonus():
            score += 5
        return score

# Example Usage:
census_tract_data = {"severe_housing_problem": 50}  # 50% severe housing problem
county_data = {"ten_year_population_growth": True, "three_year_avg_growth_rate": 1.2, "employment_growth_rate": 1.5}
stable_community_score = 5
revitalization_score = 4

housing_needs = HousingNeedsCharacteristics(census_tract_data, county_data, stable_community_score, revitalization_score)
print("Total Score:", housing_needs.calculate_total_score())