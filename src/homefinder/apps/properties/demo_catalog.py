from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from homefinder.apps.users.models import User, UserRole

from .models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus

DEMO_LISTING_TITLE_PREFIX = "Demo Catalog | "


@dataclass(frozen=True, slots=True)
class DemoCatalogAgentSeed:
    email: str
    full_name: str
    role: str


@dataclass(frozen=True, slots=True)
class DemoCatalogPropertySeed:
    title: str
    description: str
    category: str
    status: str
    city: str
    area: str
    address_line: str
    price: str
    bedrooms: int | None
    bathrooms: str | None
    listed_by_email: str
    amenities: tuple[str, ...]
    image_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DemoCatalogSeedSummary:
    properties: int
    amenities: int
    images: int
    category_counts: dict[str, int]
    status_counts: dict[str, int]


DEMO_CATALOG_AGENTS: tuple[DemoCatalogAgentSeed, ...] = (
    DemoCatalogAgentSeed(
        email="residential.agent@demo.homefinder.local",
        full_name="Demo Residential Agent",
        role=UserRole.USER,
    ),
    DemoCatalogAgentSeed(
        email="commercial.agent@demo.homefinder.local",
        full_name="Demo Commercial Agent",
        role=UserRole.SUPERVISOR,
    ),
    DemoCatalogAgentSeed(
        email="rentals.agent@demo.homefinder.local",
        full_name="Demo Rentals Agent",
        role=UserRole.USER,
    ),
)

_UNSPLASH_COMMERCIAL_URLS: tuple[str, ...] = (
    "https://plus.unsplash.com/premium_photo-1680281937048-735543c5c0f7?w=500&auto=format&fit=crop&q=60",
    "https://plus.unsplash.com/premium_photo-1676657954811-9409c4830467?w=500&auto=format&fit=crop&q=60",
)

DEMO_CATALOG_PROPERTIES: tuple[DemoCatalogPropertySeed, ...] = (
    DemoCatalogPropertySeed(
        title="Demo Catalog | Athens Family Apartment",
        description="Bright family apartment close to schools and public transit.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.AVAILABLE,
        city="Athens",
        area="Pangrati",
        address_line="28 Archimidous Street",
        price="235000.00",
        bedrooms=3,
        bathrooms="2.0",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Balcony", "Elevator", "Storage Room", "Pet Friendly"),
        image_urls=(
            "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Thessaloniki Seaview Penthouse",
        description="Top-floor penthouse with large terrace and panoramic sea exposure.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.AVAILABLE,
        city="Thessaloniki",
        area="Kalamaria",
        address_line="14 Nikolaou Plastira Avenue",
        price="495000.00",
        bedrooms=4,
        bathrooms="2.5",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Sea View", "Parking", "Security System", "Pool", "Roof Terrace"),
        image_urls=(
            "https://images.unsplash.com/photo-1584738766473-61c083514bf4?w=500&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1464146072230-91cabc968266?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Patra Renovation Condo",
        description="Condo unit suitable for value-add renovation projects.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.UNAVAILABLE,
        city="Patra",
        area="Agios Andreas",
        address_line="7 Riga Feraiou Street",
        price="98000.00",
        bedrooms=2,
        bathrooms="1.0",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Elevator", "Balcony"),
        image_urls=(
            "https://images.unsplash.com/photo-1628624747186-a941c476b7ef?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Larisa Historic Townhouse",
        description="Townhouse with restoration potential in a heritage district.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.REMOVED,
        city="Larisa",
        area="Alkazar",
        address_line="3 Piniou Street",
        price="175000.00",
        bedrooms=3,
        bathrooms="1.5",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Garden", "Storage Room", "Fireplace"),
        image_urls=(
            "https://images.unsplash.com/photo-1668911494509-14baf3b42fda?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Kifisia Modern Villa",
        description="Architect-designed villa with private pool and landscaped grounds.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.AVAILABLE,
        city="Athens",
        area="Kifisia",
        address_line="42 Drosini Street",
        price="680000.00",
        bedrooms=5,
        bathrooms="3.5",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Pool", "Garden", "Parking", "Smart Home", "Security System", "Air Conditioning"),
        image_urls=(
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Glyfada Beachside Maisonette",
        description="Two-level maisonette steps from the southern Athens coastline.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.AVAILABLE,
        city="Glyfada",
        area="Asteras",
        address_line="6 Poseidonos Avenue",
        price="410000.00",
        bedrooms=4,
        bathrooms="2.5",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Sea View", "Balcony", "Parking", "Air Conditioning"),
        image_urls=(
            "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Korinthos Country Home",
        description="Detached country home with olive grove and quiet rural surroundings.",
        category=PropertyCategory.RESIDENTIAL,
        status=PropertyStatus.AVAILABLE,
        city="Korinthos",
        area="Examilia",
        address_line="22 Olive Grove Lane",
        price="145000.00",
        bedrooms=3,
        bathrooms="1.5",
        listed_by_email="residential.agent@demo.homefinder.local",
        amenities=("Garden", "Fireplace", "Solar Panels", "Storage Room"),
        image_urls=(
            "https://images.unsplash.com/photo-1588880331179-bc9b93a8cb5e?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Marousi Office Floor",
        description="Open-plan office floor with meeting-room and reception space.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.AVAILABLE,
        city="Marousi",
        area="Business District",
        address_line="102 Kifisias Avenue",
        price="740000.00",
        bedrooms=None,
        bathrooms="3.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Elevator", "Parking", "Security System", "Conference Room"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Piraeus Retail Corner",
        description="High-visibility street-level retail unit near ferry traffic.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.AVAILABLE,
        city="Piraeus",
        area="Port Gate",
        address_line="49 Akti Miaouli",
        price="320000.00",
        bedrooms=None,
        bathrooms="1.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Parking", "Security System", "Storage Room"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Heraklion Warehouse Complex",
        description="Logistics-focused warehouse with truck access and loading infrastructure.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.UNAVAILABLE,
        city="Heraklion",
        area="Industrial Zone",
        address_line="12 Minos Logistics Park",
        price="1200000.00",
        bedrooms=None,
        bathrooms="2.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Parking", "Security System", "Loading Dock"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Volos Co-Working Loft",
        description="Adaptable commercial loft configured for co-working layouts.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.REMOVED,
        city="Volos",
        area="City Center",
        address_line="11 Dimitriados Avenue",
        price="210000.00",
        bedrooms=None,
        bathrooms="1.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Furnished", "Elevator", "Gym", "Co-Working Space"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Halandri Boutique Storefront",
        description="Street-facing boutique retail unit on a high-footfall commercial strip.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.AVAILABLE,
        city="Halandri",
        area="Pefki Border",
        address_line="58 Pentelis Avenue",
        price="380000.00",
        bedrooms=None,
        bathrooms="1.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Air Conditioning", "Storage Room", "Security System"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Athens Central Office Suite",
        description="Premium office suite overlooking Syntagma square with concierge service.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.AVAILABLE,
        city="Athens",
        area="Syntagma",
        address_line="18 Mitropoleos Street",
        price="550000.00",
        bedrooms=None,
        bathrooms="2.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Elevator", "Security System", "Conference Room", "Air Conditioning"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Thessaloniki Hotel Building",
        description="Full hotel building with 24 keys and waterfront-adjacent street presence.",
        category=PropertyCategory.COMMERCIAL,
        status=PropertyStatus.UNAVAILABLE,
        city="Thessaloniki",
        area="Ladadika",
        address_line="3 Katouni Street",
        price="1500000.00",
        bedrooms=None,
        bathrooms="6.0",
        listed_by_email="commercial.agent@demo.homefinder.local",
        amenities=("Elevator", "Parking", "Security System", "Conference Room", "Gym"),
        image_urls=_UNSPLASH_COMMERCIAL_URLS,
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Nea Smyrni Studio Rental",
        description="Compact furnished studio with rapid access to central Athens.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.AVAILABLE,
        city="Athens",
        area="Nea Smyrni",
        address_line="5 El Venizelou Street",
        price="650.00",
        bedrooms=1,
        bathrooms="1.0",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Furnished", "Pet Friendly", "Elevator"),
        image_urls=(
            "https://plus.unsplash.com/premium_photo-1678903964473-1271ecfb0288?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Chania Villa Rental",
        description="Seasonal villa rental with outdoor living spaces and sea access.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.AVAILABLE,
        city="Chania",
        area="Old Harbor",
        address_line="31 Akti Kountourioti",
        price="2800.00",
        bedrooms=3,
        bathrooms="2.0",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Pool", "Garden", "Sea View", "Parking"),
        image_urls=(
            "https://images.unsplash.com/photo-1592595896616-c37162298647?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Kalamata Beachfront Rental",
        description="Mid-term rental near the waterfront with flexible lease windows.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.UNAVAILABLE,
        city="Kalamata",
        area="Navarinou Coast",
        address_line="88 Navarinou Avenue",
        price="1400.00",
        bedrooms=2,
        bathrooms="1.5",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Sea View", "Furnished", "Pet Friendly"),
        image_urls=(
            "https://images.unsplash.com/photo-1576941089067-2de3c901e126?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Ioannina Student Rental",
        description="Budget-friendly student rental close to university campuses.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.REMOVED,
        city="Ioannina",
        area="University District",
        address_line="9 Dodonis Avenue",
        price="420.00",
        bedrooms=1,
        bathrooms="1.0",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Furnished", "Balcony"),
        image_urls=(
            "https://images.unsplash.com/photo-1625602812206-5ec545ca1231?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Mykonos Summer Rental",
        description="Cycladic-style summer rental with private terrace and sea-edge views.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.AVAILABLE,
        city="Mykonos",
        area="Ornos",
        address_line="14 Ornos Bay Path",
        price="4500.00",
        bedrooms=3,
        bathrooms="2.5",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Sea View", "Pool", "Furnished", "Air Conditioning", "Roof Terrace"),
        image_urls=(
            "https://plus.unsplash.com/premium_photo-1661876449499-26de7959878f?w=500&auto=format&fit=crop&q=60",
        ),
    ),
    DemoCatalogPropertySeed(
        title="Demo Catalog | Patra Family Rental",
        description="Family-sized rental with enclosed yard and quiet residential setting.",
        category=PropertyCategory.RENTAL,
        status=PropertyStatus.REMOVED,
        city="Patra",
        area="Vrachneika",
        address_line="44 Akti Dymaion",
        price="750.00",
        bedrooms=3,
        bathrooms="1.5",
        listed_by_email="rentals.agent@demo.homefinder.local",
        amenities=("Garden", "Pet Friendly", "Storage Room"),
        image_urls=(
            "https://images.unsplash.com/photo-1721815693498-cc28507c0ba2?w=500&auto=format&fit=crop&q=60",
        ),
    ),
)

DEMO_CATALOG_AMENITIES: tuple[str, ...] = tuple(
    sorted({amenity for property_seed in DEMO_CATALOG_PROPERTIES for amenity in property_seed.amenities})
)
DEMO_CATALOG_BASELINE_COUNTS = DemoCatalogSeedSummary(
    properties=len(DEMO_CATALOG_PROPERTIES),
    amenities=len(DEMO_CATALOG_AMENITIES),
    images=sum(len(property_seed.image_urls) for property_seed in DEMO_CATALOG_PROPERTIES),
    category_counts=dict(Counter(property_seed.category for property_seed in DEMO_CATALOG_PROPERTIES)),
    status_counts=dict(Counter(property_seed.status for property_seed in DEMO_CATALOG_PROPERTIES)),
)


@transaction.atomic
def seed_demo_catalog_dataset() -> DemoCatalogSeedSummary:
    _remove_non_seeded_demo_catalog_listings()
    _deduplicate_seed_titles()

    agents_by_email = _upsert_demo_agents()
    amenities_by_name = _upsert_demo_amenities()

    for property_seed in DEMO_CATALOG_PROPERTIES:
        property_obj, _created = Property.objects.update_or_create(
            title=property_seed.title,
            defaults={
                "description": property_seed.description,
                "category": property_seed.category,
                "status": property_seed.status,
                "city": property_seed.city,
                "area": property_seed.area,
                "address_line": property_seed.address_line,
                "price": Decimal(property_seed.price),
                "bedrooms": property_seed.bedrooms,
                "bathrooms": Decimal(property_seed.bathrooms) if property_seed.bathrooms is not None else None,
                "listed_by": agents_by_email[property_seed.listed_by_email],
            },
        )
        property_obj.amenities.set([amenities_by_name[name] for name in property_seed.amenities])
        property_obj.images.all().delete()
        PropertyImage.objects.bulk_create(
            [
                PropertyImage(property=property_obj, image_url=image_url)
                for image_url in property_seed.image_urls
            ]
        )

    return DEMO_CATALOG_BASELINE_COUNTS


def _remove_non_seeded_demo_catalog_listings() -> None:
    expected_titles = {property_seed.title for property_seed in DEMO_CATALOG_PROPERTIES}
    Property.objects.filter(title__startswith=DEMO_LISTING_TITLE_PREFIX).exclude(title__in=expected_titles).delete()


def _deduplicate_seed_titles() -> None:
    for property_seed in DEMO_CATALOG_PROPERTIES:
        duplicate_ids = list(Property.objects.filter(title=property_seed.title).order_by("id").values_list("id", flat=True)[1:])
        if duplicate_ids:
            Property.objects.filter(id__in=duplicate_ids).delete()


def _upsert_demo_agents() -> dict[str, User]:
    users_by_email: dict[str, User] = {}
    for agent_seed in DEMO_CATALOG_AGENTS:
        user_obj, _created = User.objects.update_or_create(
            email=agent_seed.email,
            defaults={
                "full_name": agent_seed.full_name,
                "role": agent_seed.role,
                "is_active": True,
                "is_staff": agent_seed.role in {UserRole.SUPERVISOR, UserRole.ADMIN},
            },
        )
        users_by_email[agent_seed.email] = user_obj
    return users_by_email


def _upsert_demo_amenities() -> dict[str, Amenity]:
    amenities_by_name: dict[str, Amenity] = {}
    for amenity_name in DEMO_CATALOG_AMENITIES:
        amenity_obj, _created = Amenity.objects.get_or_create(name=amenity_name)
        amenities_by_name[amenity_name] = amenity_obj
    return amenities_by_name
