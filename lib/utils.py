import csv
import re

dash_pattern = r"[\u002d\u2013\u2014\u2012\u2015\u200b]"

unrelated_phrases = [
    "Frozen Food",
    "Hygiene Products", 
    "Routeware Contract Extension",
    "Physician Billing",
    "Cloud Solution",
    "Venture Capital",
    "Tax Credit Program",
    "Free Growing Surveys",
    "Silviculture Surveys",
    "Prime Consultant Services",
    "Child and Family Services Building",
    "Canoe Procurement",
    "Geohazard Overview and Mapping",
    "Public Washrooms",
    "RIH Diswasher",
    "Electric Bear Fencing",
    "Parking Lot Paving",
    "Yard Parking Lot Paving",
    "Engineered Structure Assessment Services",
    "HEARTH Operator Services",
    "Pavement Rehabilitation",
    "Debris Removal",
    "Chiller Replacement RFP",
    "Overhead Door Maintenance",
    "Plumbing Maintenance and Repair Services",
    "Transit Shelter Design",
    "Consulting Services Sanitary Upgrades",
    "Tree Removal RFQ",
    "Long Life Coolant",
    "Fuel Dispenser",
]

# these are the bc commodities
cloud_offerings = [
    "Cloud backup as a service",
    "Cloud network devices as a service",
    "Cloud storage as a service",
    "Cloud-based hardware as a service",
    "Cloud-based infrastructure as a service",
    "Cloud-based platform as a service",
    "Cloud-based software as a service",
    "Software or hardware engineering",
]

technical_stuff = [
    "Software",
    "Laboratory and scientific equipment",
    "Networking software",
    "Network switches",
    "Contact center software",
    "Data services",
]
health_stuff = [
    "Personal Care Products",
    "Wound care products",
    "Medical Equipment and Accessories and Supplies",
    "Healthcare Services",
    "Health service planning",
    "Disease prevention textiles"
    # "Mammography x ray units",
]

economic_stuff = [
    "Economic analysis",
    "Environmental economics advisory services",
    "Management advisory services",
    "Management and Business Professionals and Administrative Services"
]

forestry_stuff = [
    "Silviculture",
    "Forestry management",
]

unrelated_commodities = [
    "Commercial painting service",
    "Snow Removal Services",
    "Security Guard Services",
    "Security and protection software",
    "Passenger motor vehicles",
    "Live animals",
    "Notebook computer",
    "Transportation and Storage and Mail Services",
    "Golf equipment",
    "Parking lot or road maintenance or repairs or services",
    "Automation control devices and components and accessories",
    "Process control or packaged automation systems",
    "Laboratory and scientific equipment",
    "Environmental Services",
    "Light trucks or sport utility vehicles",
    "Culvert",
    "Refuse collection and disposal",
    "Electronic Components and Supplies",
    "Employee assistance programs",
    "Cleaning and janitorial services",
    "Archaeological services",
    "Respiration air supplying self contained breathing apparatus or accessories",
    "Building cleaning services",
    "Information Technology Service Delivery",
    "HVAC mechanical construction service",
    "Chemical fertilizers and plant nutrients",
    "Environmental monitoring",
    "Forest monitoring or evaluation",
    "Parks and gardens and orchards",
    "Forest resources management services",
    "Drainage services",
    "Investigative Service",
    "Traveling water screens",
    "Water treatment and supply equipment",
    "Asphalt/pavement crack sealing equipment",
    "Noise pollution",
    "Mailing or mail pick up or delivery services",
    "Printed publications",
    "Fire protection",
    "Firefighter uniform",
    "Aids for medical training",
    "Personal protection equipment, power and water supply",
    "Personal communication devices",
    "Hazardous waste disposal",
    "Workplace safety training aids and materials",
    "Personal protective equipment",
    "Electrical Systems and Lighting and Components and Accessories and Supplies",
    "Forestry harvesting",
    *economic_stuff,
    *technical_stuff,
    *health_stuff,
    *cloud_offerings,
    *forestry_stuff,
]

unrelated_organizations = [
    "City of Vancouver",
    "Greater Vancouver Regional District",
    "Greater Vancouver Regional District (Metro Vancouver)",
    "City of Richmond",
    "City of White Rock",
    "City of Delta",
    "City of Pitt Meadows",
    "City of Abbotsford",
    "City of Delta",
    "City of Penticton",
]

regional_districts = [
    "Alberni-Clayoquot",
    "Capital",
    "Central Coast",
    "Comox Valley",
    "Cowichan Valley",
    "Mount Waddington",
    "Nanaimo",
    "qathet",
    "Strathcona"
]

target_organizations = [
    "City of Langford",
    "City of Nanaimo",
    "City of Parksville",
    "City of Port Alberni",
    "City of Victoria",
    "District of Central Saanich",
    "District of North Saanich",
    "District of Sooke",
    "Town of Comox",
    "Town of Ladysmith",
    "Town of Qualicum Beach",
    "Town of Sidney",
    "Town of View Royal",
    "Village of Cumberland",
    "School District 61 Greater Victoria",
    "School District 62 Sooke",
    "School District 63 Saanich",
    'Corporation of the District of Saanich'
]

DEFAULT_CITY = "victoria"


def load_city_mapping(filepath="data/city.csv") -> dict:
    """Loads city.csv into a dictionary mapped by city_name -> city_id."""
    city_mapping = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                city_mapping[row['city_name'].strip()] = row['city_id'].strip()
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return city_mapping


def find_bcbid_city_match(tender_record: dict, city_mapping: dict) -> str:
    """
    Searches for a valid city name in the 'Organization (Issued for)' or 
    'Organization (Issued by)' fields. Falls back to 'Opportunity Description'.
    """
    check_fields = [
        tender_record.get('Organization (Issued for)', ''),
        tender_record.get('Organization (Issued by)', ''),
        tender_record.get('Opportunity Description', '')
    ]
    
    # Sort cities by length descending so "North Vancouver" matches before "Vancouver"
    sorted_cities = sorted(city_mapping.keys(), key=len, reverse=True)
    
    for field in check_fields:
        if not field or not isinstance(field, str):
            continue
            
        field_lower = field.lower()
        for city_name in sorted_cities:
            # Use regex boundaries \b to ensure we don't match 'Hope' inside 'Hopewell'
            if re.search(rf'\b{re.escape(city_name.lower())}\b', field_lower):
                return city_name
                
    return DEFAULT_CITY

def scan_text_for_cities(text: str, city_mapping: dict) -> str:
    """
    Scans a raw body of text (like page_source) for any city names 
    defined in the mapping.
    """
    if not text:
        return "victoria"

    # Sort by length descending to catch "North Vancouver" before "Vancouver"
    sorted_cities = sorted(city_mapping.keys(), key=len, reverse=True)
    text_lower = text.lower()

    for city_name in sorted_cities:
        # \b ensures we match the whole word only
        if re.search(rf'\b{re.escape(city_name.lower())}\b', text_lower):
            return city_name
            
    return DEFAULT_CITY
