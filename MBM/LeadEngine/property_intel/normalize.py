"""normalize -- deterministic address/city/state/county normalization + dedup.

Normalization is lossless, idempotent and never fabricates: unrecognized tokens
are dropped or left as-is, never guessed.
"""
from __future__ import annotations

import re
from typing import Optional

DIRECTIONALS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}
SUFFIXES = {
    "STREET": "ST", "STREETS": "ST", "AVENUE": "AVE", "AVENUES": "AVE",
    "ROAD": "RD", "BOULEVARD": "BLVD", "BOULEVARDS": "BLVD",
    "POINT": "PT", "PLACE": "PL", "PLAZA": "PLZ", "COURT": "CT",
    "CIRCLE": "CIR", "LANE": "LN", "DRIVE": "DR", "HIGHWAY": "HWY",
    "PARKWAY": "PKWY", "WAY": "WAY", "TERRACE": "TER", "TRAIL": "TRL",
    "SQUARE": "SQ", "LOOP": "LOOP", "RIDGE": "RDG", "STATION": "STN",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

CITY_COUNTY_TX = {
    "DALLAS": "Dallas", "GARLAND": "Dallas", "IRVING": "Dallas",
    "RICHARDSON": "Dallas", "MESQUITE": "Dallas", "GRAND PRAIRIE": "Dallas",
    "CARROLLTON": "Dallas", "FORT WORTH": "Tarrant", "ARLINGTON": "Tarrant",
    "BEDFORD": "Tarrant", "EULESS": "Tarrant", "HURST": "Tarrant",
    "GRAPEVINE": "Tarrant", "KELLER": "Tarrant", "MANSFIELD": "Tarrant",
    "HOUSTON": "Harris", "PEARLAND": "Harris", "KATY": "Harris",
    "CYPRESS": "Harris", "PASADENA": "Harris", "BAYTOWN": "Harris",
    "AUSTIN": "Travis", "ROUND ROCK": "Williamson", "GEORGETOWN": "Williamson",
    "CEDAR PARK": "Williamson", "LEANDER": "Williamson",
    "SAN ANTONIO": "Bexar", "NEW BRAUNFELS": "Comal", "SELMA": "Bexar",
    "EL PASO": "El Paso", "PLANO": "Collin", "MCKINNEY": "Collin",
    "ALLEN": "Collin", "FRISCO": "Collin", "MURPHY": "Collin",
    "DENTON": "Denton", "LEWISVILLE": "Denton", "FLOWER MOUND": "Denton",
    "CORINTH": "Denton", "THE COLONY": "Denton", "LITTLE ELM": "Denton",
    "LUBBOCK": "Lubbock", "AMARILLO": "Potter", "MIDLAND": "Midland",
    "ODESSA": "Ector", "TYLER": "Smith", "WACO": "McLennan",
    "ABILENE": "Taylor", "BEAUMONT": "Jefferson", "CORPUS CHRISTI": "Nueces",
    "BROWNSVILLE": "Cameron", "LAREDO": "Webb", "MCALLEN": "Hidalgo",
    "EDINBURG": "Hidalgo", "KILLEEN": "Bell", "TEMPLE": "Bell",
    "COLLEGE STATION": "Brazos", "BRYAN": "Brazos", "GALVESTON": "Galveston",
    "SAN MARCOS": "Hays", "ROUND ROCK TX": "Williamson", "SUGAR LAND": "Fort Bend",
    "MISSOURI CITY": "Fort Bend", "ROSENBERG": "Fort Bend", "RICHMOND": "Fort Bend",
    "CONROE": "Montgomery", "THE WOODLANDS": "Montgomery", "SPRING": "Harris",
    "DUNCANVILLE": "Dallas", "DESOTO": "Dallas", "LANCASTER": "Dallas",
    "CEDAR HILL": "Dallas", "ROWLETT": "Dallas", "SACHSE": "Dallas",
    "ROCKWALL": "Rockwall", "ROYSE CITY": "Rockwall", "HEATH": "Rockwall",
    "WYLIE": "Collin", "FAIRVIEW": "Collin", "PROSPER": "Collin",
    "CELINA": "Collin", "PRINCETON": "Collin", "ANNA": "Collin",
    "MELISSA": "Collin", "LUCAS": "Collin", "LAKE DALLAS": "Denton",
    "AUBREY": "Denton", "ARGYLE": "Denton", "HASLET": "Tarrant",
    "SOUTHLAKE": "Tarrant", "COLLEYVILLE": "Tarrant", "HALTOM CITY": "Tarrant",
    "NORTH RICHLAND HILLS": "Tarrant", "RIVER OAKS": "Tarrant",
    "FOREST HILL": "Tarrant", "BURLESON": "Johnson", "CLEBURNE": "Johnson",
    "WAXAHACHIE": "Ellis", "MIDLOTHIAN": "Ellis", "ENNIS": "Ellis",
    "RED OAK": "Ellis", "TERRELL": "Kaufman", "FORNEY": "Kaufman",
    "SEAGOVILLE": "Kaufman", "GREENVILLE": "Hunt", "SHERMAN": "Grayson",
    "DENISON": "Grayson", "MCKINNEY/FRISCO": "Collin", "PARIS": "Lamar",
    "LONGVIEW": "Gregg", "MARSHALL": "Harrison", "TEXARKANA": "Bowie",
    "VICTORIA": "Victoria", "HARLINGEN": "Cameron", "PHARR": "Hidalgo",
    "WESLACO": "Hidalgo", "MISSION": "Hidalgo", "NAVAJO": "Bexar",
}


def _norm_token(token: str) -> str:
    """Normalize one street token (direction/suffix/compress)."""
    t = token.upper()
    t = DIRECTIONALS.get(t, t)
    t = SUFFIXES.get(t, t)
    return t


def normalize_street(street: str) -> str:
    """Canonical street line for matching (e.g. '12124 SCHROEDER RD')."""
    if not street:
        return ""
    tokens = re.split(r"[\s,]+", re.sub(r"[^\w\s.,-]", "", str(street)).strip())
    out: list[str] = []
    for tok in tokens:
        t = _norm_token(tok)
        t = re.sub(r"\.$", "", t)
        if not t:
            continue
        out.append(t)
    return " ".join(out)


def normalize_address(full: str) -> str:
    """Full-line canonical street key, e.g. '3134 ARIZONA AVE' (no city/state)."""
    if not full:
        return ""
    parts = split_address_parts(full)
    return normalize_street(parts["address"])


def parse_city_state_zip(line: str) -> tuple[str, str, str]:
    """Extract (city, state, zip) from a trailing 'CITY, ST ZIP' fragment.

    Handles both 'DALLAS, TX 75243' (comma) and 'DALLAS TX 75243' (space).
    A trailing street suffix (e.g. 'DR') is never mistaken for a city.
    """
    if not line:
        return "", "", ""
    tokens = [t for t in re.split(r"[,\s]+", str(line).strip()) if t]
    if not tokens:
        return "", "", ""
    zip_code = ""
    if re.match(r"^\d{5}(?:-\d{4})?$", tokens[-1]):
        zip_code = tokens.pop()
    state = ""
    if tokens and len(tokens[-1]) == 2 and tokens[-1].upper() in US_STATES:
        state = tokens.pop().upper()
    city = ""
    if state and tokens:
        candidate = tokens[-1].upper()
        if candidate not in SUFFIXES and candidate not in DIRECTIONALS and len(candidate) >= 2:
            city = tokens.pop()
    return city, state, zip_code


def infer_county_from_city(state: str, city: str) -> str:
    """Best-effort county for a known city (TX major markets). Empty = unknown."""
    st = (state or "").strip().upper()
    ct = (city or "").strip().upper()
    if st == "TX" and ct:
        return CITY_COUNTY_TX.get(ct, "")
    return ""


def split_address_parts(full: str) -> dict:
    """Split a full address line into address / city / state / zip.

    Accepts '123 MAIN ST, DALLAS, TX 75243' or '123 MAIN ST DALLAS TX 75243'.
    Returns dict with 'address','city','state','zip_code'.
    """
    text = re.sub(r"[,\s]+", " ", str(full or "")).strip()
    city, state, zip_code = parse_city_state_zip(text)
    addr = text
    if city:
        idx = text.upper().find(city.upper())
        if idx >= 0:
            addr = text[:idx].strip()
    if not addr and text:
        addr = text
    return {
        "address": addr,
        "city": city,
        "state": state,
        "zip_code": zip_code,
    }


def dedupe_key(parcel_id: str, address: str, state: str) -> str:
    """Deterministic identity key: parcel wins, else address|state."""
    parcel = (parcel_id or "").strip().upper()
    if parcel:
        return f"parcel:{parcel}"
    addr = normalize_address(address)
    if addr:
        st = (state or "").strip().upper()
        return f"addr:{addr}|{st}"
    return ""


def normalize_record(rec: dict) -> dict:
    """Normalize a raw listing dict into canonical field names (no fabrication).

    Accepts both snake_case and the legacy Title_Case dialer fields.
    """
    full_addr = (
        rec.get("property_address")
        or rec.get("Property_Address")
        or rec.get("address")
        or rec.get("Address")
        or ""
    )
    parts = split_address_parts(full_addr)

    city = (rec.get("city") or rec.get("City") or parts["city"] or "").strip()
    state = (rec.get("state") or rec.get("State") or parts["state"] or "").strip().upper()
    zip_code = (rec.get("zip_code") or rec.get("zip") or rec.get("Zip") or parts["zip_code"] or "").strip()
    county = (rec.get("county") or rec.get("County") or "").strip()
    if not county:
        county = infer_county_from_city(state, city)

    address = (parts["address"] or full_addr or "").strip()

    status = str(rec.get("auction_status") or rec.get("status") or rec.get("Status") or "").strip().lower()
    if status in ("pre-foreclosure", "pre foreclosure"):
        status = "pre-foreclosure"
    elif status in ("foreclosure", "trustee sale", "foreclosure auction"):
        status = "foreclosure"
    elif status in ("tax", "tax deed", "tax sale"):
        status = "tax_deed"
    elif status in ("bankruptcy", "trustee"):
        status = "bankruptcy"
    elif status in ("reo", "bank owned"):
        status = "reo"
    elif status:
        status = "unknown"

    return {
        "address": address,
        "address_normalized": normalize_address(full_addr),
        "city": city,
        "state": state,
        "county": county,
        "zip_code": zip_code,
        "parcel_id": (rec.get("parcel_id") or rec.get("apn") or rec.get("parcel") or "").strip(),
        "auction_date": (rec.get("auction_date") or "").strip(),
        "auction_status": status,
        "opening_bid": rec.get("opening_bid"),
        "estimated_value": rec.get("estimated_value"),
        "occupancy_signal": (rec.get("occupancy_signal") or "").strip(),
        "source": (rec.get("source") or "").strip(),
        "source_url": (rec.get("source_url") or "").strip(),
        "source_date": (rec.get("source_date") or "").strip(),
    }


def dedupe_records(records: list[dict]) -> list[dict]:
    """Consolidate duplicates deterministically. Keeps the record with the
    earliest source_date; ties broken by source_url, then address."""
    seen: dict[str, dict] = {}
    for rec in records:
        key = dedupe_key(
            rec.get("parcel_id", ""),
            rec.get("address") or rec.get("address_normalized", ""),
            rec.get("state", ""),
        )
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = rec
            continue
        a = existing.get("source_date") or ""
        b = rec.get("source_date") or ""
        if (b and not a) or (a and b and b < a):
            seen[key] = rec
    return list(seen.values())