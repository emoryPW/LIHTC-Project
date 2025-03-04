from collections import defaultdict

class QualityEducationScoring:
    def __init__(self, school_data):
        """Initialize with a dictionary containing school details."""
        self.school_data = school_data
        self.processed_district_data = self.aggregate_district_grades()
    
    def aggregate_district_grades(self):
        """Aggregate grades at the district level to ensure each grade is counted once per district."""
        district_grades = defaultdict(set)
        
        for school in self.school_data:
            district = school.get("district_id")
            grade_cluster = school.get("grade_cluster")
            grades = set(range(school.get("start_grade", 0), school.get("end_grade", 0) + 1))
            
            district_grades[(district, grade_cluster)].update(grades)
        
        return {key: len(grades) for key, grades in district_grades.items()}
    
    def is_eligible_school(self, school):
        """Check if a school meets the basic eligibility criteria."""
        return (
            not school.get("district_wide_enrollment", False)
            and not school.get("selective_admission", False)
        )
    
    def meets_ccrpi_criteria(self, school):
        """Check if school meets College and Career Readiness Performance Index (CCRPI) criteria. Only scores since the 2018 update qualify."""
        """Only scores posted since the 2018 CCRPI update qualify under this section."""
        recent_scores = [score for year, score in enumerate(school.get("ccrpi_scores", []), start=2015) if year >= 2018]
        
        if recent_scores:
            avg_score = sum(recent_scores) / len(recent_scores)
            return avg_score > school.get("state_avg_ccrpi", 0)
        return False
    
    def meets_beating_the_odds(self, school):
        """Check if School receives 2018 or more recent “Beating the Odds” designation."""
        return school.get("beating_the_odds_year", 0) >= 2018
    
    def meets_performance_trends(self, school):
        """Check if the school shows a positive CCRPI trend from 2015-2019 (excluding 2017-2018)."""
        ccrpi_changes = school.get("ccrpi_yearly_changes", [])
        if len(ccrpi_changes) < 4:
            return False  # Ensure at least four years of data are available
        
        # Exclude 2017-2018 change and calculate the average year-over-year change
        filtered_changes = [ccrpi_changes[i] for i in range(len(ccrpi_changes)) if i != 2]
        avg_change = sum(filtered_changes) / len(filtered_changes) if filtered_changes else 0
        
        return avg_change > 0
    
    def calculate_points(self, school):
        """Calculate the Quality Education Area points based on the number of grades that qualify under A, B, or C at the district-wide level."""
        if not self.is_eligible_school(school):
            return 0
        
        district = school.get("district_id")
        grade_cluster = school.get("grade_cluster")
        unique_grades = self.processed_district_data.get((district, grade_cluster), 0)
        
        tenancy_type = school.get("tenancy_type", "All tenancies")
        
        if tenancy_type == "All tenancies":
            if unique_grades >= 7:
                return 1.5
            elif unique_grades >= 3:
                return 1
        elif tenancy_type == "HFOP, Elderly, Other":
            if unique_grades >= 12:
                return 2
        elif tenancy_type == "Family":
            if unique_grades >= 12:
                return 3
        
        return 0
    
    def evaluate_schools(self):
        """Evaluate and return scores for all schools in the dataset."""
        return [{
            "name": school["name"],
            "latitude": school.get("latitude"),
            "longitude": school.get("longitude"),
            "points": self.calculate_points(school)
        } for school in self.school_data]

# Example school dataset
school_data = [
    {"name": "ABC High School", "district_id": 101, "grade_cluster": "H", "start_grade": 9, "end_grade": 12,
     "district_wide_enrollment": False, "selective_admission": False, "ccrpi_scores": [82, 85, 88], "state_avg_ccrpi": 80, 
     "beating_the_odds_year": 2019, "ccrpi_yearly_changes": [2, 3, 4], "latitude": 33.7490, "longitude": -84.3880, "tenancy_type": "All tenancies"},
    
    {"name": "XYZ Middle School", "district_id": 101, "grade_cluster": "M", "start_grade": 6, "end_grade": 8,
     "district_wide_enrollment": False, "selective_admission": False, "ccrpi_scores": [75, 78, 80], "state_avg_ccrpi": 80, 
     "beating_the_odds_year": 2017, "ccrpi_yearly_changes": [1, -1, 2], "latitude": 34.0522, "longitude": -118.2437, "tenancy_type": "Family"},
]

scoring_system = QualityEducationScoring(school_data)
print(scoring_system.evaluate_schools())
