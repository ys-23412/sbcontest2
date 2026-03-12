dash_pattern = r"[\u002d\u2013\u2014\u2012\u2015\u200b]"

unrelated_phrases = [
    "Frozen Food",
    "Hygiene Products", 
    "Routeware Contract Extension",
    "Physician Billing",
    "Cloud Solution",
    "Venture Capital",
    "Tax Credit Program",
    "Roof replacement",
    "Free Growing Surveys",
    "Silviculture Surveys",
    "Prime Consultant Services",
    "Drainage Improvements"
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
]
health_stuff = [
    "Personal Care Products",
    "Wound care products",
    "Medical Equipment and Accessories and Supplies",
    # "Mammography x ray units",
]

economic_stuff = [
    "Economic analysis",
    "Environmental economics advisory services",
    "Management advisory services"
]

forestry_stuff = [
    "Silviculture"
]

unrelated_commodities = [
    "Commercial painting service",
    "Snow Removal Services",
    "Security Guard Services",
    "Security and protection software",
    "Motor Vehicles",
    "Passenger motor vehicles",
    "Live animals",
    "Notebook computer",
    "Transportation and Storage and Mail Services",
    "Architectural engineering",
    "Roof systems",
    "Roofing materials",
    "Golf equipment",
    "Parking lot or road maintenance or repairs or services",
    "Automation control devices and components and accessories",
    "Process control or packaged automation systems",
    "Laboratory and scientific equipment",
    *economic_stuff,
    *technical_stuff,
    *economic_stuff,
    *health_stuff,
    *cloud_offerings,
    *forestry_stuff,
]