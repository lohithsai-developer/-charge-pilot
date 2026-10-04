import math

import os

import time

from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache
from threading import Lock


import requests

from dotenv import load_dotenv



load_dotenv()



OPENCHARGEMAP_API_KEY = os.getenv("OPENCHARGEMAP_API_KEY", "")

CHARGEID_API_KEY = os.getenv("CHARGEID_API_KEY", "")



HEADERS = {
    "User-Agent": "ChargePilot/1.0 (Academic EV Journey Planner)",
    "Accept": "application/json",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_CONTACT_EMAIL = os.getenv("CHARGEPILOT_CONTACT_EMAIL", "").strip()
NOMINATIM_HEADERS = {
    "User-Agent": (
        f"ChargePilot/1.0 (Academic EV Journey Planner; contact: {NOMINATIM_CONTACT_EMAIL})"
        if NOMINATIM_CONTACT_EMAIL
        else "ChargePilot/1.0 (Academic EV Journey Planner)"
    ),
    "Accept": "application/json",
}
NOMINATIM_MIN_INTERVAL_SECONDS = 1.05
_nominatim_lock = Lock()
_last_nominatim_request = 0.0



# =========================================================

# PERFORMANCE / PLANNING SETTINGS

# =========================================================



MIN_CANDIDATE_STATIONS = 3

STATION_BUFFER = 2

MAX_CANDIDATE_STATIONS = 18



# OCM is queried around route zones rather than repeatedly

# searching the same area.

OCM_SEARCH_RADIUS_KM = 40

OCM_EMPTY_ZONE_FALLBACK_RADIUS_KM = 65

OCM_MAX_RESULTS_PER_QUERY = 25

MAX_ZONE_QUERIES = 14



# Exact OSRM detour requests can become expensive on long routes.

# We use a fast geometric estimate for every candidate and exact

# OSRM detours only for the first few candidates.

MAX_EXACT_DETOUR_REQUESTS = 6



# Restaurant calls are also limited to actual candidate stations.

MAX_RESTAURANT_REQUESTS = 2



# Overpass is optional. Render environments can have unreliable access to

# public Overpass instances, so keep it disabled by default for production.

# Set CHARGEPILOT_ENABLE_OVERPASS_RESTAURANTS=true to enable it.

ENABLE_OVERPASS_RESTAURANTS = os.getenv(

    "CHARGEPILOT_ENABLE_OVERPASS_RESTAURANTS",

    "false",

).strip().lower() in ("1", "true", "yes", "on")



# Small pause between public API requests.

API_DELAY_SECONDS = 0.25





# =========================================================

# GENERIC HELPERS

# =========================================================



def safe_float(value, default=0.0):

    try:

        if value is None:

            return default

        return float(value)

    except (TypeError, ValueError):

        return default





def clamp(value, low, high):

    return max(low, min(high, value))





def haversine_km(lat1, lon1, lat2, lon2):

    if any(v is None for v in (lat1, lon1, lat2, lon2)):

        return float("inf")



    lat1 = math.radians(float(lat1))

    lon1 = math.radians(float(lon1))

    lat2 = math.radians(float(lat2))

    lon2 = math.radians(float(lon2))



    dlat = lat2 - lat1

    dlon = lon2 - lon1



    a = (

        math.sin(dlat / 2) ** 2

        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2

    )



    return 6371.0088 * 2 * math.asin(math.sqrt(a))





def normalize_connector_text(value):

    if isinstance(value, list):

        parts = []

        for item in value:

            if isinstance(item, dict):

                parts.append(str(item.get("type", "")))

            else:

                parts.append(str(item))

        return " ".join(parts).lower()

    return str(value or "").lower()





def connector_matches(station, requested):

    requested = str(requested or "Any").strip().lower()

    if requested in ("", "any", "none", "n/a"):

        return True



    text = " ".join(

        [

            normalize_connector_text(station.get("connector", "")),

            normalize_connector_text(station.get("connectors", [])),

        ]

    )



    aliases = {

        "ccs": ["ccs", "ccs1", "ccs2", "combo"],

        "ccs2": ["ccs2", "combo 2", "combo2"],

        "type 2": ["type 2", "type2", "mennekes"],

        "chademo": ["chademo"],

        "gb/t": ["gb/t", "gbt"],

        "tesla": ["tesla"],

    }



    terms = aliases.get(requested, [requested])

    return any(term in text for term in terms)





# =========================================================

# 1. GEOCODING - NOMINATIM

# =========================================================



@lru_cache(maxsize=256)
def geocode_location(location):
    """
    Geocode an Indian location with Nominatim safely.

    Important safeguards:
    - Caches repeated location lookups.
    - Enforces at least 1.05 seconds between real Nominatim requests.
    - Uses an identifiable User-Agent.
    - Handles HTTP 429 without hammering the public service.
    """
    global _last_nominatim_request

    if not location or not str(location).strip():
        raise ValueError("Location cannot be empty.")

    location = str(location).strip()
    params = {
        "q": location,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
    }

    print(f"\n📍 Geocoding: {location}")

    for attempt in range(2):
        # Only real API requests are throttled. Cached calls never enter here.
        with _nominatim_lock:
            elapsed = time.monotonic() - _last_nominatim_request
            wait_time = NOMINATIM_MIN_INTERVAL_SECONDS - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            _last_nominatim_request = time.monotonic()

        try:
            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=NOMINATIM_HEADERS,
                timeout=20,
            )

            print(f"   Nominatim status: {response.status_code}")

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    retry_seconds = max(2.0, min(float(retry_after), 10.0)) if retry_after else 3.0
                except (TypeError, ValueError):
                    retry_seconds = 3.0

                if attempt == 0:
                    print(f"   ⏳ Nominatim rate limit. Waiting {retry_seconds:.1f}s...")
                    time.sleep(retry_seconds)
                    continue

                raise RuntimeError(
                    "Nominatim rate limit reached. Please wait a few seconds "
                    "before planning another trip."
                )

            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError(f"Could not find location: {location}")

            result = data[0]
            result_data = {
                "lat": float(result["lat"]),
                "lon": float(result["lon"]),
                "display_name": result.get("display_name", location),
            }

            print(
                f"   Coordinates: {result_data['lat']:.6f}, "
                f"{result_data['lon']:.6f}"
            )
            return result_data

        except requests.RequestException as error:
            if attempt == 0:
                print(f"   ⚠ Nominatim request failed: {error}")
                time.sleep(2.0)
                continue
            print(f"❌ Nominatim error: {error}")
            raise

    raise RuntimeError("Nominatim geocoding failed unexpectedly.")



# =========================================================

# 2. ROUTING - OSRM

# =========================================================



def get_route_data(from_location, to_location):

    start = geocode_location(from_location)

    time.sleep(API_DELAY_SECONDS)

    end = geocode_location(to_location)



    url = (

        "https://router.project-osrm.org/route/v1/driving/"

        f"{start['lon']},{start['lat']};"

        f"{end['lon']},{end['lat']}"

    )



    response = requests.get(

        url,

        params={

            "overview": "full",

            "geometries": "geojson",

            "steps": "false",

        },

        headers=HEADERS,

        timeout=60,

    )

    response.raise_for_status()



    data = response.json()

    routes = data.get("routes", [])

    if not routes:

        raise ValueError("OSRM did not return a route.")



    route = routes[0]

    geometry = route.get("geometry", {}).get("coordinates", [])



    return {

        "from": start,

        "to": end,

        "distance_km": round(float(route.get("distance", 0)) / 1000, 2),

        "duration_minutes": round(float(route.get("duration", 0)) / 60, 1),

        "duration_hours": round(float(route.get("duration", 0)) / 3600, 2),

        "geometry": geometry,

    }





# Backward-compatible alias.

get_route = get_route_data





# =========================================================

# 3. ROUTE DISTANCE INDEXING

# =========================================================



def build_route_distance_index(route_geometry):

    """Return cumulative road distance for each route coordinate."""

    if not route_geometry:

        return []



    cumulative = [0.0]



    for i in range(1, len(route_geometry)):

        lon1, lat1 = route_geometry[i - 1]

        lon2, lat2 = route_geometry[i]



        segment = haversine_km(lat1, lon1, lat2, lon2)

        if not math.isfinite(segment):

            segment = 0.0



        cumulative.append(cumulative[-1] + segment)



    return cumulative





def route_position_for_station(station, route_geometry, cumulative=None):

    """Approximate the station's position along the route in km."""

    if not route_geometry:

        return None



    lat = station.get("latitude")

    lon = station.get("longitude")

    if lat is None or lon is None:

        return None



    if cumulative is None:

        cumulative = build_route_distance_index(route_geometry)



    best_index = None

    best_distance = float("inf")



    # Sampling every point is accurate enough for the route geometry

    # returned by OSRM and avoids another routing API call.

    for i, point in enumerate(route_geometry):

        try:

            p_lon, p_lat = point

            distance = haversine_km(lat, lon, p_lat, p_lon)

        except (TypeError, ValueError):

            continue



        if distance < best_distance:

            best_distance = distance

            best_index = i



    if best_index is None:

        return None



    return {

        "route_distance_km": round(cumulative[best_index], 2),

        "distance_from_route_km": round(best_distance, 2),

        "route_index": best_index,

    }





def get_route_points(route_geometry, number_of_points):

    """Return points distributed by road distance, not array index."""

    if not route_geometry or number_of_points <= 0:

        return []



    if number_of_points == 1:

        return [route_geometry[len(route_geometry) // 2]]



    if len(route_geometry) <= number_of_points:

        return list(route_geometry)



    cumulative = build_route_distance_index(route_geometry)

    total_distance = cumulative[-1] if cumulative else 0.0



    if total_distance <= 0:

        step = (len(route_geometry) - 1) / (number_of_points - 1)

        return [route_geometry[round(i * step)] for i in range(number_of_points)]



    points = []

    cursor = 0



    for i in range(number_of_points):

        target = total_distance * i / (number_of_points - 1)



        while cursor < len(cumulative) - 1 and cumulative[cursor + 1] < target:

            cursor += 1



        points.append(route_geometry[cursor])



    return points





def calculate_route_zones(route_data, number_of_zones):

    """Create evenly distributed intermediate route points."""

    geometry = route_data.get("geometry", [])

    if not geometry or number_of_zones <= 0:

        return []



    # Include start and destination in the sampled list, then remove them.

    points = get_route_points(geometry, number_of_zones + 2)

    if len(points) <= 2:

        return []



    return points[1:-1]





# =========================================================

# 4. DYNAMIC STOP / CANDIDATE CALCULATION

# =========================================================



def calculate_required_charging_candidates(

    route_distance_km,

    ev_range_km,

    battery_percent=100,

    reserve_percent=15,

    max_stops="Any",

):

    """

    Estimate how many charger candidates are needed from the EV's

    actual usable range. This is a planning estimate, not a final

    charging plan.

    """

    route_distance_km = max(0.0, safe_float(route_distance_km))

    ev_range_km = max(0.0, safe_float(ev_range_km))

    battery_percent = clamp(safe_float(battery_percent, 100), 0, 100)



    if route_distance_km <= 0 or ev_range_km <= 0:

        return MIN_CANDIDATE_STATIONS



    departure_range = ev_range_km * battery_percent / 100

    safe_range = departure_range * (100 - reserve_percent) / 100



    # If the starting battery is low, safe_range can become small.

    safe_range = max(safe_range, ev_range_km * 0.35)



    required_legs = math.ceil(route_distance_km / safe_range)

    required_stops = max(0, required_legs - 1)



    # Always keep a small buffer so the AI has alternatives.

    candidates = max(

        MIN_CANDIDATE_STATIONS,

        required_stops + STATION_BUFFER,

    )



    # Respect an explicit user maximum when it is numeric, but never

    # reduce below one candidate when charging is obviously required.

    if isinstance(max_stops, (int, float)):

        max_stops_value = max(0, int(max_stops))

        if max_stops_value > 0:

            candidates = min(candidates, max_stops_value + STATION_BUFFER)



    return int(clamp(candidates, MIN_CANDIDATE_STATIONS, MAX_CANDIDATE_STATIONS))





# =========================================================

# 5. OPENCHARGEMAP STATION PARSING

# =========================================================



def parse_ocm_station(station):

    address_info = station.get("AddressInfo") or {}

    connections = station.get("Connections") or []



    lat = address_info.get("Latitude")

    lon = address_info.get("Longitude")

    if lat is None or lon is None:

        return None



    connector_list = []

    max_power_kw = 0.0



    for connection in connections:

        if not isinstance(connection, dict):

            continue



        connection_type = connection.get("ConnectionType")

        connector_name = ""



        if isinstance(connection_type, dict):

            connector_name = connection_type.get("Title") or ""

        elif connection_type:

            connector_name = str(connection_type)



        power_kw = safe_float(connection.get("PowerKW"), 0)

        max_power_kw = max(max_power_kw, power_kw)



        connector_list.append({

            "type": connector_name,

            "power_kw": power_kw,

            "quantity": connection.get("Quantity"),

        })



    operator_info = station.get("OperatorInfo") or {}

    operator_name = (

        operator_info.get("Title")

        if isinstance(operator_info, dict)

        else str(operator_info or "")

    )



    return {

        "id": station.get("ID"),

        "name": address_info.get("Title") or "Unknown Charging Station",

        "address": address_info.get("AddressLine1") or "",

        "town": address_info.get("Town") or "",

        "state": address_info.get("StateOrProvince") or "",

        "postcode": address_info.get("Postcode") or "",

        "latitude": float(lat),

        "longitude": float(lon),

        "max_power_kw": round(max_power_kw, 2),

        "power_kw": round(max_power_kw, 2),

        "connectors": connector_list,

        "connector": ", ".join(

            sorted(

                {

                    str(item.get("type"))

                    for item in connector_list

                    if item.get("type")

                }

            )

        ),

        "operator": operator_name,

        "status": "Live status unavailable",

        "live_status": None,

        "restaurants": [],

        "map_url": (

            "https://www.google.com/maps/search/?api=1&query="

            f"{float(lat):.6f},{float(lon):.6f}"

        ),

    }





# =========================================================

# 6. OCM QUERY AROUND ROUTE ZONES

# =========================================================



def query_ocm_near_point(latitude, longitude, radius_km, maxresults=25):

    if not OPENCHARGEMAP_API_KEY:

        print("WARNING: OPENCHARGEMAP_API_KEY is missing.")

        return []



    params = {

        "key": OPENCHARGEMAP_API_KEY,

        "latitude": latitude,

        "longitude": longitude,

        "distance": radius_km,

        "distanceunit": "KM",

        "maxresults": maxresults,

        "compact": "false",

        "verbose": "false",

    }



    try:

        response = requests.get(

            "https://api.openchargemap.io/v3/poi/",

            params=params,

            headers=HEADERS,

            timeout=18,

        )



        if response.status_code != 200:

            print(

                f"OCM request failed: HTTP {response.status_code} "

                f"at {latitude:.5f},{longitude:.5f}"

            )

            return []



        data = response.json()

        if not isinstance(data, list):

            return []



        stations = []

        for raw in data:

            parsed = parse_ocm_station(raw)

            if parsed:

                stations.append(parsed)



        return stations



    except requests.RequestException as error:

        print("OCM network error:", error)

        return []

    except Exception as error:

        print("OCM processing error:", error)

        return []





def deduplicate_stations(stations):

    unique = []

    seen = set()



    for station in stations:

        if not isinstance(station, dict):

            continue



        station_id = station.get("id")

        key = (

            f"id:{station_id}"

            if station_id is not None

            else f"coord:{round(safe_float(station.get('latitude')), 5)}:"

                 f"{round(safe_float(station.get('longitude')), 5)}"

        )



        if key in seen:

            continue



        seen.add(key)

        unique.append(station)



    return unique





def discover_stations_along_route(

    route_data,

    candidate_count,

    minimum_power="Any",

    preferred_connector="Any",

    speed_priority="Medium",

):

    """

    Search chargers in route-distributed zones.



    This is the main fix for long journeys: we no longer ask OCM for

    only four globally-ranked stations. Instead, each route section

    gets its own station search.

    """

    geometry = route_data.get("geometry", [])

    if not geometry:

        return []



    zone_count = int(

        clamp(candidate_count, MIN_CANDIDATE_STATIONS, MAX_ZONE_QUERIES)

    )



    zones = calculate_route_zones(route_data, zone_count)

    if not zones:

        return []



    print()

    print(

        f"Dynamic charger planning: {candidate_count} candidate stations"

    )

    print(

        f"Route-distributed search zones: {len(zones)}"

    )



    all_stations = []

    zone_results = []



    for index, point in enumerate(zones, start=1):

        # OSRM GeoJSON coordinates are [longitude, latitude].

        lon, lat = point



        print(

            f"Charger zone {index}/{len(zones)}: "

            f"lat={lat:.5f}, lon={lon:.5f}"

        )



        stations = query_ocm_near_point(

            lat,

            lon,

            OCM_SEARCH_RADIUS_KM,

            OCM_MAX_RESULTS_PER_QUERY,

        )



        # If a zone is empty, make one wider fallback request.

        if not stations:

            stations = query_ocm_near_point(

                lat,

                lon,

                OCM_EMPTY_ZONE_FALLBACK_RADIUS_KM,

                OCM_MAX_RESULTS_PER_QUERY,

            )



        for station in stations:

            station["search_zone"] = index

            station["zone_latitude"] = lat

            station["zone_longitude"] = lon



        zone_results.append(stations)

        all_stations.extend(stations)



        if index < len(zones):

            time.sleep(API_DELAY_SECONDS)



    all_stations = deduplicate_stations(all_stations)



    if not all_stations:

        print("No charging stations found along route.")

        return []



    # Build route position information once.

    cumulative = build_route_distance_index(geometry)

    for station in all_stations:

        position = route_position_for_station(

            station,

            geometry,

            cumulative,

        )



        if position:

            station.update(position)



    # Remove obvious candidates that do not satisfy an explicit minimum

    # power requirement when enough alternatives exist.

    min_power = None

    if str(minimum_power).strip().lower() not in ("", "any", "none", "n/a"):

        try:

            min_power = float(minimum_power)

        except (TypeError, ValueError):

            min_power = None



    preferred = []

    fallback = []



    for station in all_stations:

        power = safe_float(station.get("max_power_kw"), 0)

        connector_ok = connector_matches(station, preferred_connector)

        power_ok = min_power is None or power >= min_power



        if connector_ok and power_ok:

            preferred.append(station)

        else:

            fallback.append(station)



    pool = preferred if preferred else fallback



    # Group candidates by route zone. One strong candidate per zone is

    # selected first so the final list remains geographically distributed.

    by_zone = {}

    for station in pool:

        zone = station.get("search_zone")

        by_zone.setdefault(zone, []).append(station)



    speed_priority = str(speed_priority or "Medium").lower()



    def station_score(station, zone):

        zone_lat = station.get("zone_latitude")

        zone_lon = station.get("zone_longitude")

        zone_distance = haversine_km(

            station.get("latitude"),

            station.get("longitude"),

            zone_lat,

            zone_lon,

        )

        power = safe_float(station.get("max_power_kw"), 0)



        # Higher power gets more weight for High speed priority.

        if speed_priority == "high":

            power_weight = 4.0

        elif speed_priority == "low":

            power_weight = 1.0

        else:

            power_weight = 2.0



        return (

            zone_distance

            - power_weight * min(power, 150) / 20

        )



    selected = []

    selected_ids = set()



    # First pass: one candidate from each route zone.

    for zone in sorted(by_zone.keys(), key=lambda x: (x is None, x)):

        choices = by_zone.get(zone, [])

        choices.sort(key=lambda s: station_score(s, zone))



        if not choices:

            continue



        station = choices[0]

        station_id = station.get("id") or station.get("name")

        if station_id in selected_ids:

            continue



        selected.append(station)

        selected_ids.add(station_id)



        if len(selected) >= candidate_count:

            break



    # Second pass: fill any missing slots with the best remaining stations

    # sorted by route position, keeping the list distributed.

    remaining = [

        station

        for station in pool

        if (station.get("id") or station.get("name")) not in selected_ids

    ]



    def remaining_score(station):

        power = safe_float(station.get("max_power_kw"), 0)

        position = safe_float(station.get("route_distance_km"), 10**9)

        return (

            position,

            -power,

        )



    remaining.sort(key=remaining_score)



    for station in remaining:

        station_id = station.get("id") or station.get("name")

        if station_id in selected_ids:

            continue



        selected.append(station)

        selected_ids.add(station_id)



        if len(selected) >= candidate_count:

            break



    # Final route ordering is essential for the AI and frontend timeline.

    selected.sort(

        key=lambda station: safe_float(

            station.get("route_distance_km"),

            10**9,

        )

    )



    print()

    print("=" * 60)

    print("ROUTE CHARGER CANDIDATES")

    print("=" * 60)

    print(f"Stations discovered              : {len(all_stations)}")

    print(f"Route-distributed candidates     : {len(selected)}")

    print()



    for i, station in enumerate(selected, start=1):

        lat = safe_float(station.get("latitude"), 0)

        lon = safe_float(station.get("longitude"), 0)

        route_pos = station.get("route_distance_km")

        off_route = station.get("distance_from_route_km")

        detour = station.get("detour_km")

        power = station.get("max_power_kw", station.get("power_kw", 0))

        connector = station.get("connector") or "Unknown"

        status = station.get("status") or "Status unavailable"



        print(f"Candidate {i}: {station.get('name')}")

        print(f"  Coordinates   : {lat:.6f}, {lon:.6f}")

        print(f"  Route position: {route_pos} km from start")

        print(f"  Off route     : {off_route} km")

        print(f"  Detour        : {detour} km")

        print(f"  Charger       : {power} kW")

        print(f"  Connector     : {connector}")

        print(f"  Status        : {status}")

        print(f"  Address       : {station.get('address') or station.get('town') or 'N/A'}")

        print(f"  Google Maps   : {station.get('map_url', 'N/A')}")

        print("-")



    return selected





# Backward-compatible name used by older code.

def get_charging_stations(route_data, candidate_count=None, **kwargs):

    if candidate_count is None:

        candidate_count = MIN_CANDIDATE_STATIONS



    return discover_stations_along_route(

        route_data,

        candidate_count,

        **kwargs,

    )





# =========================================================

# 7. FAST / EXACT STATION DETOURS

# =========================================================



def estimate_station_detour(station, route_data):

    """

    Fast detour estimate based on perpendicular distance from the route.

    A station 2 km off-route is approximated as roughly 4 km of extra

    driving. This is used before exact OSRM enrichment.

    """

    distance_from_route = station.get("distance_from_route_km")

    if distance_from_route is None:

        geometry = route_data.get("geometry", [])

        position = route_position_for_station(station, geometry)

        distance_from_route = (

            position.get("distance_from_route_km")

            if position

            else 0

        )



    distance_from_route = max(0.0, safe_float(distance_from_route))

    return round(distance_from_route * 2, 2)





def get_exact_station_detour(route_data, station):

    """Calculate an exact-ish OSRM detour through the station."""

    start = route_data.get("from", {})

    end = route_data.get("to", {})



    if not start or not end:

        return estimate_station_detour(station, route_data)



    try:

        url = (

            "https://router.project-osrm.org/route/v1/driving/"

            f"{start['lon']},{start['lat']};"

            f"{station['longitude']},{station['latitude']};"

            f"{end['lon']},{end['lat']}"

        )



        response = requests.get(

            url,

            params={"overview": "false", "steps": "false"},

            headers=HEADERS,

            timeout=20,

        )

        response.raise_for_status()



        routes = response.json().get("routes", [])

        if not routes:

            return estimate_station_detour(station, route_data)



        via_distance = safe_float(routes[0].get("distance")) / 1000

        base_distance = safe_float(route_data.get("distance_km"))



        return round(max(0.0, via_distance - base_distance), 2)



    except Exception as error:

        print(

            f"Exact detour failed for {station.get('name')}: {error}"

        )

        return estimate_station_detour(station, route_data)





def enrich_station_detours(route_data, stations, maximum=None):

    if not stations:

        return stations



    candidates = list(stations)

    if maximum is not None:

        candidates = candidates[: int(maximum)]



    # First provide an immediate detour value to every candidate.

    for station in candidates:

        station["detour_km"] = estimate_station_detour(

            station,

            route_data,

        )

        station["detour_source"] = "geometric_estimate"



    # Exact OSRM only for the first few geographically relevant stations.

    exact_count = min(

        MAX_EXACT_DETOUR_REQUESTS,

        len(candidates),

    )



    for index in range(exact_count):

        station = candidates[index]

        station["detour_km"] = get_exact_station_detour(

            route_data,

            station,

        )

        station["detour_source"] = "OSRM"



        if index < exact_count - 1:

            time.sleep(API_DELAY_SECONDS)



    return stations





# =========================================================

# 8. CHARGEID LIVE STATUS

# =========================================================



def get_chargeid_status(station_id):

    if not CHARGEID_API_KEY or not station_id:

        return {

            "status": "Live status unavailable",

            "source": "ChargeID API key not configured",

        }



    url = (

        "https://chargeid.in/api/v1/"

        f"stations/{station_id}/status"

    )



    try:

        response = requests.get(

            url,

            headers={

                **HEADERS,

                "Authorization": f"Bearer {CHARGEID_API_KEY}",

            },

            timeout=10,

        )

        response.raise_for_status()

        data = response.json()



        return {

            "status": data.get("status", "Unknown"),

            "source": "ChargeID",

            "raw": data,

        }

    except Exception as error:

        return {

            "status": "Live status unavailable",

            "source": f"ChargeID error: {error}",

        }





def enrich_live_status(stations, maximum=None):

    if not stations:

        return stations



    candidates = stations

    if maximum is not None:

        candidates = stations[: int(maximum)]



    # Live calls are deliberately limited for performance.

    for index, station in enumerate(candidates):

        result = get_chargeid_status(station.get("id"))

        station["live_status"] = result

        station["status"] = result.get(

            "status",

            "Live status unavailable",

        )



        if index < len(candidates) - 1:

            time.sleep(API_DELAY_SECONDS)



    return stations





# =========================================================

# 9. RESTAURANTS - OVERPASS

# =========================================================



def get_nearby_restaurants(latitude, longitude, radius=2000):

    """Best-effort restaurant lookup that can be disabled in production."""

    if latitude is None or longitude is None:

        return []



    # IMPORTANT: restaurant data is optional. On Render, public Overpass

    # endpoints may be unreachable or slow. Never let that block /plan.

    if not ENABLE_OVERPASS_RESTAURANTS:

        return []



    radius = max(100, safe_float(radius, 2000))



    query = f"""

    [out:json][timeout:4];

    (

      node[amenity=restaurant](around:{radius},{latitude},{longitude});

      way[amenity=restaurant](around:{radius},{latitude},{longitude});

      relation[amenity=restaurant](around:{radius},{latitude},{longitude});

    );

    out center tags;

    """



    endpoints = [

        "https://overpass-api.de/api/interpreter",

        "https://overpass.kumi.systems/api/interpreter",

    ]



    for endpoint in endpoints:

        try:

            response = requests.post(

                endpoint,

                data=query,

                headers=HEADERS,

                timeout=4,

            )



            if response.status_code != 200:

                print(

                    f"Overpass failed ({response.status_code}) at {endpoint}"

                )

                continue



            data = response.json()

            if not isinstance(data, dict):

                print(f"Overpass returned invalid JSON at {endpoint}")

                continue



            elements = data.get("elements", [])

            if not isinstance(elements, list):

                return []



            restaurants = []



            for item in elements[:20]:

                if not isinstance(item, dict):

                    continue



                tags = item.get("tags", {}) or {}

                item_lat = item.get("lat")

                item_lon = item.get("lon")



                if item_lat is None or item_lon is None:

                    center = item.get("center", {}) or {}

                    item_lat = center.get("lat")

                    item_lon = center.get("lon")



                if item_lat is None or item_lon is None:

                    continue



                restaurants.append({

                    "name": tags.get("name", "Restaurant"),

                    "latitude": item_lat,

                    "longitude": item_lon,

                    "cuisine": tags.get("cuisine", ""),

                    "address": tags.get("addr:street", ""),

                })



            return restaurants[:20]



        except requests.RequestException as error:

            print(

                f"Overpass network error at {endpoint}: {error}"

            )

        except (ValueError, TypeError) as error:

            print(

                f"Overpass response processing error at {endpoint}: {error}"

            )

        except Exception as error:

            print(

                f"Restaurant lookup error at {endpoint}: {error}"

            )



        # Do not add a long delay between failed endpoints.

        # The second endpoint is already a fallback.



    print("Restaurant lookup unavailable; continuing without food data.")

    return []





def attach_restaurants_to_stations(stations, radius=2000, maximum=None):

    """

    Attach nearby restaurants on a best-effort basis.



    Food is an optional enhancement, so failure of Overpass must never

    fail the complete journey-planning request. Only a small number of

    top charging candidates are queried to keep Render response time low.

    """

    if not stations:

        return stations



    # Always initialize the field so the frontend can safely render it.

    for station in stations:

        station["restaurants"] = []

        station["restaurant_count"] = 0



    candidates = stations

    if maximum is not None:

        try:

            candidates = stations[:max(0, int(maximum))]

        except (TypeError, ValueError):

            candidates = stations



    # Hard safety cap. Restaurant lookup is optional and should never

    # consume the entire Gunicorn request timeout.

    candidates = candidates[:MAX_RESTAURANT_REQUESTS]



    if not candidates:

        return stations



    print()

    print(

        f"Searching restaurants for {len(candidates)} charging candidates..."

    )



    for index, station in enumerate(candidates, start=1):

        print(

            f"Restaurant search {index}/{len(candidates)}: "

            f"{station.get('name')}"

        )



        try:

            station["restaurants"] = get_nearby_restaurants(

                station.get("latitude"),

                station.get("longitude"),

                radius,

            ) or []

        except Exception as error:

            # Defensive fallback: restaurant lookup must never break /plan.

            print(

                f"Restaurant lookup skipped for "

                f"{station.get('name', 'Unknown')}: {error}"

            )

            station["restaurants"] = []



        station["restaurant_count"] = len(

            station["restaurants"]

        )



        if index < len(candidates):

            time.sleep(API_DELAY_SECONDS)



    return stations





# Backward-compatible alias.

attach_restaurants = attach_restaurants_to_stations





# =========================================================

# 10. COMPLETE TRIP DATA

# =========================================================



def get_trip_data(

    from_location,

    to_location,

    food_required=False,

    food_radius=2000,

    ev_range_km=300,

    battery_percent=100,

    minimum_power="Any",

    preferred_connector="Any",

    speed_priority="Medium",

    max_stops="Any",

):

    """

    Main ChargePilot data pipeline.



    The number of charging candidates is calculated dynamically from

    route distance + EV range + starting battery, then chargers are

    discovered across the route instead of globally truncating to four.

    """



    # 1. Route.

    route = get_route_data(

        from_location,

        to_location,

    )



    route_distance = safe_float(route.get("distance_km"))

    route_duration = safe_float(route.get("duration_minutes"))



    # Console route summary: this is intentionally verbose so the

    # terminal shows exactly how the route and charger search were built.

    start = route.get("from", {}) or {}

    destination = route.get("to", {}) or {}



    print()

    print("=" * 60)

    print("CHARGEPILOT ROUTE INFORMATION")

    print("=" * 60)

    print(f"Start location      : {from_location}")

    print(

        f"Start coordinates   : "

        f"{safe_float(start.get('lat')):.6f}, "

        f"{safe_float(start.get('lon')):.6f}"

    )

    print(f"Destination         : {to_location}")

    print(

        f"Destination coords  : "

        f"{safe_float(destination.get('lat')):.6f}, "

        f"{safe_float(destination.get('lon')):.6f}"

    )

    print(f"Route distance      : {route_distance:.2f} km")

    print(f"Travel time         : {route_duration:.1f} minutes")



    departure_range = max(0.0, safe_float(ev_range_km)) * clamp(

        safe_float(battery_percent, 100), 0, 100

    ) / 100.0

    safe_range = max(

        departure_range * 0.85,

        max(0.0, safe_float(ev_range_km)) * 0.35,

    )

    required_legs = (

        math.ceil(route_distance / safe_range)

        if safe_range > 0 and route_distance > 0

        else 0

    )

    required_stops = max(0, required_legs - 1)



    print(f"EV range            : {safe_float(ev_range_km):.2f} km")

    print(f"Starting battery    : {clamp(safe_float(battery_percent, 100), 0, 100):.1f}%")

    print(f"Available range     : {departure_range:.2f} km")

    print(f"Safe planning range : {safe_range:.2f} km")

    print(f"Estimated stops     : {required_stops}")

    print("=" * 60)



    # 2. Dynamic candidate count.

    candidate_count = calculate_required_charging_candidates(

        route_distance_km=route_distance,

        ev_range_km=ev_range_km,

        battery_percent=battery_percent,

        max_stops=max_stops,

    )



    print()

    print(

        f"Route distance: {route_distance:.2f} km"

    )

    print(

        f"Dynamic station candidate count: {candidate_count}"

    )



    # 3. Route-distributed OCM discovery.

    stations = discover_stations_along_route(

        route,

        candidate_count,

        minimum_power=minimum_power,

        preferred_connector=preferred_connector,

        speed_priority=speed_priority,

    )



    # 4. Detours. All candidates get a fast estimate; only a limited

    # number get exact OSRM enrichment.

    stations = enrich_station_detours(

        route,

        stations,

        maximum=len(stations),

    )



    # 5. Live status. This is optional and only active if ChargeID key exists.

    stations = enrich_live_status(

        stations,

        maximum=len(stations),

    )



    # 6. Restaurants only when requested.

    if food_required:

        stations = attach_restaurants_to_stations(

            stations,

            radius=food_radius,

            maximum=len(stations),

        )



    # Keep final stations route ordered.

    stations.sort(

        key=lambda station: safe_float(

            station.get("route_distance_km"),

            10**9,

        )

    )



    print()

    print("=" * 60)

    print("FINAL CHARGER ROUTE ORDER")

    print("=" * 60)

    if stations:

        for i, station in enumerate(stations, start=1):

            print(

                f"Stop candidate {i}: "

                f"{station.get('name')} | "

                f"{station.get('route_distance_km')} km from start | "

                f"{station.get('power_kw', station.get('max_power_kw', 0))} kW | "

                f"{station.get('detour_km', 0)} km detour"

            )

    else:

        print("No final charger candidates available.")

    print("=" * 60)



    return {

        "route": route,

        "stations": stations,

        "planning": {

            "candidate_count_requested": candidate_count,

            "candidate_count_found": len(stations),

            "route_distance_km": route_distance,

        },

    }





# Backward-compatible wrapper.

def get_complete_trip_data(

    from_location,

    to_location,

    food_required=False,

    food_radius=2000,

    ev_range_km=300,

    battery_percent=100,

):

    return get_trip_data(

        from_location,

        to_location,

        food_required,

        food_radius,

        ev_range_km,

        battery_percent,

    )





# =========================================================

# 11. TEST ROUTE

# =========================================================



def test_route():

    print("\n========================================")

    print("ChargePilot Route API Test")

    print("========================================")



    route = get_route_data("Hyderabad", "Vijayawada")



    print("\nRESULT:")

    print(f"Distance: {route['distance_km']} km")

    print(f"Travel time: {route['duration_minutes']} minutes")

    print(f"Route points: {len(route['geometry'])}")

    return route





if __name__ == "__main__":

    try:

        test_route()

    except Exception as error:

        print("\nRoute test failed:")

        print(error)
