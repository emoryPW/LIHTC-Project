import pandas as pd

class QualityEducationScoring:
    def __init__(self, df, tenancy_type):
        """
        df: pandas DataFrame with structure as shown
        tenancy_type: 'elderly', 'family', or 'other'
        """
        self.df = df
        self.tenancy_type = tenancy_type

    def qualifies_by_A(self, school, state_avg_by_year):
        # Use only available years in state averages
        years = [y for y in [2018, 2019] if y in state_avg_by_year and y in school.index and not pd.isna(school[y])]
        if not years:
            return False
        school_avg = school[years].mean()
        state_avg = sum(state_avg_by_year[y] for y in years) / len(years)
        return school_avg > state_avg

    def qualifies_by_B(self, school):
        # Placeholder: update logic if you have this data
        return school.get('Beating the Odds', False)

    def qualifies_by_C(self, school):
        # Exclude 2017–2018; use 'YoY Average' and percentile
        try:
            return (
                float(school['YoY Average']) > 0 and
                float(school['Average score']) >= float(school['Applicable 25th Percentile'])
            )
        except (ValueError, TypeError, KeyError):
            return False

    def calculate_points(self):
        total_qualified_grades = set()

        for _, school in self.df.iterrows():
            if (
                self.qualifies_by_A(school, state_avg_by_year={2018: 72.1, 2019: 74.2}) or
                self.qualifies_by_B(school) or
                self.qualifies_by_C(school)
            ):
                # Assume Grade Cluster maps to grades
                cluster = school.get('Grade Cluster', '')
                grades = self.grade_cluster_to_grades(cluster)
                total_qualified_grades.update(grades)

        grade_count = len(total_qualified_grades)
        if grade_count == 0:
            return 0
        elif grade_count == 3:
            return 1
        elif grade_count == 7:
            return 1.5
        elif grade_count == 13:
            return 3 if self.tenancy_type in ['family'] else 2
        elif 3 < grade_count < 7:
            return 1
        elif 7 < grade_count < 13:
            return 1.5
        return 0

    def grade_cluster_to_grades(self, cluster):
        # Map grade clusters to actual grade numbers
        mapping = {
            'E': list(range(0, 6)),   # Elementary: K–5
            'M': list(range(6, 9)),   # Middle: 6–8
            'H': list(range(9, 13)),  # High: 9–12
        }
        return mapping.get(cluster.upper(), [])
