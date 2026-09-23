"""Comprehensive niche and city expansion registry for Lead Radar.

Contains:
- BUSINESS_NICHES: 100+ localized SMB search keywords covering Fitness, Retail & Gadgets,
  Personal Care & Salons, Home & Decor, Healthcare, Automotive, and Events.
- CITY_BOUNDING_BOXES: Geographic bounding boxes prioritizing Karnataka first, followed
  by high-density national tier-1/tier-2 hubs.
- get_next_search_target(): Rotator pairing an unexhausted city/zone with an SMB category.
"""

from itertools import cycle
import random
from typing import Iterator

BUSINESS_NICHES: list[str] = [
    # Fitness & Sports
    "gyms",
    "fitness center",
    "unisex gym",
    "crossfit box",
    "yoga studio",
    "power yoga center",
    "pilates studio",
    "swimming pool academy",
    "indoor badminton court",
    "tennis academy",
    "martial arts academy",
    "karate classes",
    "kickboxing club",
    "boxing gym",
    "personal training studio",
    "zumba dance studio",
    # Retail & Gadgets
    "mobile phone store",
    "smartphone repair center",
    "iphone repair shop",
    "laptop service center",
    "computer hardware shop",
    "gaming pc builder",
    "electrical supply store",
    "hardware sanitary store",
    "electronics showroom",
    "home appliance repair",
    "ac repair and service",
    "cctv camera installation",
    "solar panel dealer",
    "led lighting showroom",
    "battery inverter shop",
    "audio video equipment store",
    # Personal Care & Salons
    "unisex salon",
    "luxury beauty parlour",
    "luxury day spa",
    "ayurvedic spa and massage",
    "nail art studio",
    "tattoo studio",
    "piercing studio",
    "men barber shop",
    "bridal makeup artist",
    "hair styling studio",
    "skin care clinic",
    "hair transplant clinic",
    "eyelash extension studio",
    "cosmetic laser clinic",
    "aesthetic wellness center",
    # Home & Decor
    "interior designers",
    "modular kitchen showroom",
    "home interior decorators",
    "architecture firm",
    "marble and granite dealers",
    "tile showroom",
    "wooden furniture store",
    "customized sofa manufacturer",
    "curtains and upholstery shop",
    "false ceiling contractor",
    "painting contractor",
    "bathroom fittings showroom",
    "architectural glass supplier",
    "landscape garden designer",
    "home automation systems",
    # Healthcare
    "multispeciality clinic",
    "dental clinic",
    "pediatric clinic",
    "orthopedic clinic",
    "diagnostic pathology lab",
    "physiotherapy center",
    "eye hospital and clinic",
    "optician optical store",
    "dermatology clinic",
    "ent specialist clinic",
    "gynecology clinic",
    "ayurvedic clinic",
    "homeopathy clinic",
    "fertility ivf center",
    "cardiology clinic",
    "veterinary clinic and pet hospital",
    "mental health therapy counseling",
    "speech and hearing clinic",
    # Automotive
    "car detailing studio",
    "ceramic coating studio",
    "multi brand car service center",
    "car repair workshop",
    "two wheeler service center",
    "royal enfield service specialist",
    "car dry wash and cleaning",
    "tyre alignment and balancing",
    "car windshield repair",
    "car audio and accessories shop",
    "denting and painting workshop",
    "battery and electrical car service",
    "bike modification shop",
    "authorized car service workshop",
    # Events & Hospitality
    "banquet hall",
    "wedding venue",
    "party hall",
    "wedding caterers",
    "wedding photographer",
    "candid wedding videography",
    "event management company",
    "corporate event planner",
    "sound and light rental",
    "luxury floral decorator",
    "party decorator and planner",
    "birthday party hall",
    "stage setup and audio visual rental",
    "dj sound system rental",
]

# Geographic bounding boxes represented as polygons [(lat, lng), ...]
# Priority 1: Karnataka (Bengaluru zones, tier-2 hubs)
# Priority 2: Secondary National metropolitan hubs
CITY_BOUNDING_BOXES: dict[str, list[tuple[float, float]]] = {
    # Primary: Karnataka
    # Bengaluru Zonal breakdowns
    "bengaluru_central": [
        (12.99, 77.56),
        (12.99, 77.63),
        (12.94, 77.63),
        (12.94, 77.56),
    ],
    "bengaluru_south": [
        (12.94, 77.54),
        (12.94, 77.63),
        (12.87, 77.63),
        (12.87, 77.54),
    ],
    "bengaluru_east": [
        (13.00, 77.63),
        (13.00, 77.76),
        (12.91, 77.76),
        (12.91, 77.63),
    ],
    "bengaluru_north": [
        (13.12, 77.54),
        (13.12, 77.64),
        (12.99, 77.64),
        (12.99, 77.54),
    ],
    # Full Bengaluru bounding box (preserves backward compatibility)
    "bengaluru": [
        (12.85, 77.50),
        (13.12, 77.50),
        (13.12, 77.76),
        (12.85, 77.76),
    ],
    "mysuru": [
        (12.37, 76.60),
        (12.37, 76.71),
        (12.26, 76.71),
        (12.26, 76.60),
    ],
    "mangaluru": [
        (12.94, 74.82),
        (12.94, 74.91),
        (12.83, 74.91),
        (12.83, 74.82),
    ],
    "hubballi_dharwad": [
        (15.48, 75.05),
        (15.48, 75.20),
        (15.30, 75.20),
        (15.30, 75.05),
    ],
    "belagavi": [
        (15.90, 74.47),
        (15.90, 74.56),
        (15.82, 74.56),
        (15.82, 74.47),
    ],
    "shivamogga": [
        (13.98, 75.52),
        (13.98, 75.62),
        (13.88, 75.62),
        (13.88, 75.52),
    ],
    "davanagere": [
        (14.51, 75.87),
        (14.51, 75.96),
        (14.42, 75.96),
        (14.42, 75.87),
    ],
    "tumakuru": [
        (13.38, 77.06),
        (13.38, 77.16),
        (13.30, 77.16),
        (13.30, 77.06),
    ],
    "udupi_manipal": [
        (13.38, 74.72),
        (13.38, 74.82),
        (13.31, 74.82),
        (13.31, 74.72),
    ],
    # Secondary: National
    "hyderabad": [
        (17.50, 78.30),
        (17.50, 78.55),
        (17.32, 78.55),
        (17.32, 78.30),
    ],
    "pune": [
        (18.60, 73.75),
        (18.60, 73.98),
        (18.44, 73.98),
        (18.44, 73.75),
    ],
    "chennai": [
        (13.15, 80.18),
        (13.15, 80.32),
        (12.95, 80.32),
        (12.95, 80.18),
    ],
    "mumbai": [
        (19.25, 72.80),
        (19.25, 72.98),
        (18.90, 72.98),
        (18.90, 72.80),
    ],
    "ahmedabad": [
        (23.10, 72.48),
        (23.10, 72.65),
        (22.95, 72.65),
        (22.95, 72.48),
    ],
    "coimbatore": [
        (11.08, 76.90),
        (11.08, 77.05),
        (10.95, 77.05),
        (10.95, 76.90),
    ],
    "kochi": [
        (10.05, 76.24),
        (10.05, 76.38),
        (9.90, 76.38),
        (9.90, 76.24),
    ],
}

# Add normalized aliases for hyphenated and spaced keys
_ALIASES = {
    "bengaluru-central": "bengaluru_central",
    "bengaluru central": "bengaluru_central",
    "bengaluru-south": "bengaluru_south",
    "bengaluru south": "bengaluru_south",
    "bengaluru-east": "bengaluru_east",
    "bengaluru east": "bengaluru_east",
    "bengaluru-north": "bengaluru_north",
    "bengaluru north": "bengaluru_north",
    "hubballi-dharwad": "hubballi_dharwad",
    "hubballi dharwad": "hubballi_dharwad",
    "udupi-manipal": "udupi_manipal",
    "udupi manipal": "udupi_manipal",
}
for alias, target in _ALIASES.items():
    CITY_BOUNDING_BOXES[alias] = CITY_BOUNDING_BOXES[target]

# Stateful sequential iterator over (city, niche) pairs
def _create_target_cycle() -> Iterator[tuple[str, str]]:
    # Primary Karnataka zones prioritized first, then secondary
    karnataka_cities = [
        "bengaluru_central",
        "bengaluru_south",
        "bengaluru_east",
        "bengaluru_north",
        "mysuru",
        "mangaluru",
        "hubballi_dharwad",
        "belagavi",
        "shivamogga",
        "davanagere",
        "tumakuru",
        "udupi_manipal",
    ]
    national_cities = [
        "hyderabad",
        "pune",
        "chennai",
        "mumbai",
        "ahmedabad",
        "coimbatore",
        "kochi",
    ]
    all_ordered_cities = karnataka_cities + national_cities

    pairs = [
        (city, niche)
        for city in all_ordered_cities
        for niche in BUSINESS_NICHES
    ]
    return cycle(pairs)


_SEQUENTIAL_ROTATOR = _create_target_cycle()


def get_next_search_target(mode: str = "sequential") -> tuple[str, str]:
    """Return the next (city_or_zone, business_niche) pair.

    Args:
        mode: "sequential" to cycle through prioritized targets deterministically,
              or "random" to sample randomly.

    Returns:
        tuple of (city_name, niche_query)
    """
    if mode == "random":
        cities = [
            "bengaluru_central",
            "bengaluru_south",
            "bengaluru_east",
            "bengaluru_north",
            "mysuru",
            "mangaluru",
            "hubballi_dharwad",
            "belagavi",
            "shivamogga",
            "davanagere",
            "tumakuru",
            "udupi_manipal",
            "hyderabad",
            "pune",
            "chennai",
            "mumbai",
            "ahmedabad",
            "coimbatore",
            "kochi",
        ]
        return random.choice(cities), random.choice(BUSINESS_NICHES)

    return next(_SEQUENTIAL_ROTATOR)
