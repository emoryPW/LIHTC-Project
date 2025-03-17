class EconomicDevelopmentProximity:
    def __init__(self, pool_type, distance, net_new_jobs, letter_provided, google_maps_verified):
        self.pool_type = pool_type  # "Rural" or "Other Metro"
        self.distance = distance  # Distance in miles
        self.net_new_jobs = net_new_jobs  # Number of new jobs
        self.letter_provided = letter_provided  # Boolean: Has the economic development letter been provided?
        self.google_maps_verified = google_maps_verified  # Boolean: Has Google Maps verification been done?
    
    def is_eligible(self):
        # Define the eligibility criteria
        criteria = {
            "Rural": {"max_distance": 30, "min_jobs": 90},
            "Other Metro": {"max_distance": 20, "min_jobs": 250}
        }
        
        if self.pool_type not in criteria:
            return False, "Invalid pool type. Only 'Rural' and 'Other Metro' are eligible."
        
        # Check if the project meets the requirements
        requirements = criteria[self.pool_type]
        
        if self.distance > requirements["max_distance"]:
            return False, f"Distance exceeds allowed limit of {requirements['max_distance']} miles."
        
        if self.net_new_jobs < requirements["min_jobs"]:
            return False, f"Net new jobs are below the required minimum of {requirements['min_jobs']}."
        
        if not self.letter_provided:
            return False, "Letter from the Local Economic Development Authority is missing."
        
        if not self.google_maps_verified:
            return False, "Google Maps verification is required."
        
        return True, "Project is eligible for Economic Development Proximity Scoring."
    
    def get_score(self):
        eligible, message = self.is_eligible()
        return 1 if eligible else 0, message

# Example Usage:
economic_development = EconomicDevelopmentProximity(pool_type="Rural", distance=25, net_new_jobs=100, letter_provided=True, google_maps_verified=True)
score, message = economic_development.get_score()
print(f"Score: {score}, Message: {message}")