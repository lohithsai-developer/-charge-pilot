import os
import json
import time
import re
import random
import math

from dotenv import load_dotenv
from groq import Groq


# =========================================================
# 1. ENVIRONMENT
# =========================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from the .env file.")

client = Groq(api_key=GROQ_API_KEY)

MODEL = "openai/gpt-oss-20b"

# Maximum number of candidate stations supplied to the AI.
MAX_CANDIDATES = 18

# Maximum number of actual charging stops in the plan.
MAX_PLANNED_STOPS = 16


# =========================================================
# 2. SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are ChargePilot, an AI-powered EV Journey and Charging
Break Planner.

Your job is to create a REALISTIC MULTI-STOP charging plan,
not merely recommend one charging station.

IMPORTANT:
The supplied charging stations are candidate stations.
On short trips there may be only a few candidates. On long trips
ChargePilot deliberately supplies a larger route-distributed set.
A candidate station becomes a journey charging stop only if it is
actually needed for a particular leg.

The primary optimization is: use the MINIMUM number of charging stops
that safely completes the route. An extra stop is not mandatory just
because a second candidate exists. If one stop lets the vehicle safely
reach the destination, do not add a second stop.

=========================================================
RANGE LOGIC
=========================================================

Use:

available_range_km =
EV_range_km * current_battery_percent / 100

This is the estimated range available at departure.

For each charging leg:

1. Start with the current battery.
2. Determine how far the vehicle can safely travel.
3. Select a charging station that can be reached.
4. Charge there.
5. Continue from that station.
6. Repeat until the destination is reachable.

Do NOT say that one charging stop is enough simply because
one station is the overall recommendation.

For long journeys, create multiple charging stops only when the
battery/range calculation requires them. Do not add unnecessary stops.

Do NOT invent charging stations.

Only use supplied candidate stations.

=========================================================
CRITICAL LONG-JOURNEY RULE
=========================================================

If:

route_distance_km > available_range_km

then charging_required MUST be true.

If the supplied station data does not contain enough
route-distributed charging stations to safely complete the
journey, DO NOT pretend that the journey is fully covered.

Set:

planning_status = "insufficient_station_coverage"

and explain which part of the journey cannot be covered
with the supplied candidates.

Do not fabricate stations merely to make the plan complete.

=========================================================
BATTERY SAFETY
=========================================================

Avoid planning a leg that requires the vehicle to arrive
with an unsafe or impossible battery level.

Use a practical reserve.

Unless the user gives another requirement, prefer to arrive
at a charging stop with approximately 10% to 20% battery
remaining.

Do not assume the vehicle can use 100% of its theoretical
range in real-world conditions.

The exact battery percentage is an estimate.

=========================================================
CHARGING STRATEGY
=========================================================

At every charging stop consider:

- charger power
- detour
- connector
- station status
- charging speed
- restaurant availability
- distance preference
- fast charging preference
- minimum charger power
- battery safety

Do not automatically choose the highest-power charger.

Do not automatically choose the closest charger.

=========================================================
CHARGING TARGET
=========================================================

When a stop is selected, determine a sensible charge target.

Usually use approximately 70% to 85% for intermediate stops,
unless the journey requires a higher level.

For the final charging stop, charge only as much as is
reasonably required to reach the destination with reserve.

=========================================================
COST AND TIME
=========================================================

Charging cost and charging time are estimates.

If exact tariff information is unavailable:

- do not invent an exact station tariff
- state that the value is estimated or unavailable
- return 0 when a numerical estimate cannot be justified

Charging time depends on charger power, vehicle limits,
battery state, charging curves, temperature and conditions.

=========================================================
LIVE STATUS
=========================================================

Only use live availability when actual live status data is
supplied.

If it is not supplied, say:

"Live charger availability could not be verified."

OpenChargeMap station existence does NOT mean the charger is
currently available.

=========================================================
RESTAURANTS
=========================================================

If food is requested, use only supplied restaurant data.

Do not invent restaurants.

=========================================================
USER PREFERENCES
=========================================================

Respect:

- distance priority
- fast charging priority
- food requirement
- restaurant radius
- avoid tolls
- preferred connector
- minimum charger power
- maximum charging stops
- departure time

=========================================================
MULTI-STOP OUTPUT
=========================================================

Return journey_legs.

Each charging leg must contain:

- step
- from
- to
- leg_distance_km
- departure_battery_percent
- arrival_battery_percent
- action
- charging_station
- charge_from_percent
- charge_to_percent
- estimated_charging_time_minutes
- estimated_charging_cost

Example:

{
  "step": 1,
  "from": "Start",
  "to": "Station A",
  "leg_distance_km": 180,
  "departure_battery_percent": 80,
  "arrival_battery_percent": 18,
  "action": "CHARGE",
  "charging_station": "Station A",
  "charge_from_percent": 18,
  "charge_to_percent": 80,
  "estimated_charging_time_minutes": 35,
  "estimated_charging_cost": 250
}

Then:

{
  "step": 2,
  "from": "Station A",
  "to": "Station B",
  ...
}

The final leg should have:

"action": "ARRIVE"

and:

"charging_station": ""

=========================================================
IMPORTANT CONSISTENCY RULES
=========================================================

- estimated_stops must equal the number of journey_legs whose
  action is "CHARGE".
- journey_legs must be in chronological order.
- Do not report estimated_stops = 0 when charging_required is true
  unless planning_status is "insufficient_station_coverage"
  or another explicit planning limitation explains it.
- recommended_station should be the first or most important
  charging station when charging is required.
- station_comparison must contain no more than 4 candidates.
- The charging_stations input may contain more than 4 candidates on
  long journeys. Use those route-distributed candidates to build the
  complete multi-stop plan.
- Prefer candidates whose route_distance_km values create sensible
  sequential legs.
- Do not create stations not supplied in charging_stations.
- Do not claim a 2,000 km journey is covered by one charger.
- If the supplied candidates are all clustered near the start,
  clearly report insufficient station coverage.

=========================================================
JSON OUTPUT
=========================================================

Return ONLY valid JSON.

Use exactly this structure:

{
    "planning_status": "complete",
    "journey_summary": "",
    "charging_required": true,
    "estimated_stops": 0,
    "recommended_station": "",
    "estimated_charging_cost": 0,
    "estimated_charging_time_minutes": 0,
    "battery_range_analysis": "",
    "recommendation": "",
    "journey_legs": [],
    "station_comparison": []
}
"""


# =========================================================
# 3. JSON CLEANING
# =========================================================

def clean_json(text):
    if not text:
        raise ValueError("Groq returned an empty response.")

    text = str(text).strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "Groq response does not contain a valid JSON object."
        )

    return text[start:end + 1].strip()


# =========================================================
# 4. STATION NORMALIZATION
# =========================================================

def normalize_station(station):
    if not isinstance(station, dict):
        return {
            "name": "Unknown station",
            "power_kw": 0,
            "status": "Unknown",
            "detour_km": 0,
            "route_distance_km": None,
            "estimated_cost": 0,
            "estimated_time_minutes": 0,
            "restaurant_count": 0,
            "connector": "",
        }

    normalized = dict(station)

    normalized["name"] = (
        station.get("name")
        or station.get("title")
        or station.get("station_name")
        or "Unknown station"
    )

    normalized["power_kw"] = (
        station.get("power_kw")
        or station.get("power")
        or station.get("max_power_kw")
        or 0
    )

    normalized["status"] = (
        station.get("status")
        or station.get("availability")
        or station.get("live_status")
        or "Unknown"
    )

    normalized["detour_km"] = (
        station.get("detour_km")
        or station.get("detour")
        or 0
    )

    # Preserve whichever route-position field tools.py provides.
    normalized["route_distance_km"] = (
        station.get("route_distance_km")
        if station.get("route_distance_km") is not None
        else station.get("distance_from_route_start_km")
    )

    normalized["estimated_cost"] = (
        station.get("estimated_cost")
        or station.get("cost")
        or station.get("charging_cost")
        or 0
    )

    normalized["estimated_time_minutes"] = (
        station.get("estimated_time_minutes")
        or station.get("charging_time_minutes")
        or station.get("charging_time")
        or 0
    )

    restaurants = station.get("restaurants", [])
    if not isinstance(restaurants, list):
        restaurants = []

    normalized["restaurant_count"] = station.get(
        "restaurant_count",
        len(restaurants)
    )

    normalized["connector"] = (
        station.get("connector")
        or station.get("connector_type")
        or station.get("connectors")
        or ""
    )

    normalized["map_url"] = station.get("map_url") or ""

    return normalized


def deduplicate_stations(stations):
    unique = []
    seen = set()

    if not isinstance(stations, list):
        return unique

    for station in stations:
        normalized = normalize_station(station)

        name = str(
            normalized.get("name", "")
        ).strip().lower()

        if not name or name in seen:
            continue

        seen.add(name)
        unique.append(normalized)

    return unique


def prepare_stations(stations):
    # Keep the full dynamically selected route-distributed candidate set
    # for planning. The comparison UI is still limited separately to 4.
    return deduplicate_stations(stations)[:MAX_CANDIDATES]


# =========================================================
# 5. GROQ REQUEST
# =========================================================

def ask_groq(prompt, retries=5):
    """
    Call Groq safely for ChargePilot journey planning.

    GPT-OSS supports reasoning + JSON Object Mode, but when JSON mode is
    used with GPT-OSS we explicitly disable returned reasoning content.
    This prevents Groq JSON-validation failures caused by reasoning output
    being mixed with the requested JSON payload.

    A plain-text fallback is also provided. In that mode the model is still
    instructed to return one JSON object and clean_json() extracts it after
    the response is received.
    """

    last_error = None

    for attempt in range(1, retries + 1):
        print()
        print(f"Groq {MODEL} request {attempt}/{retries}")

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": (
                            prompt
                            + "\n\n"
                            + "FINAL RESPONSE RULE: Return exactly one valid JSON "
                            + "object. Do not return Markdown, code fences, reasoning, "
                            + "comments, or any text before or after the JSON object."
                        ),
                    },
                ],
                temperature=0.1,
                reasoning_effort="medium",
                include_reasoning=False,
                max_completion_tokens=8000,
                response_format={
                    "type": "json_object"
                },
            )

            if not response or not response.choices:
                raise RuntimeError("Groq returned no response choices.")

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("Groq returned an empty response.")

            print("Groq response received successfully.")
            print("Model:", MODEL)

            return content

        except Exception as error:
            last_error = error
            error_text = str(error)
            upper = error_text.upper()

            print(f"Groq attempt {attempt} failed:")
            print(error_text)

            json_validation_error = (
                "JSON_VALIDATE_FAILED" in upper
                or "FAILED TO VALIDATE JSON" in upper
                or (
                    "INVALID_REQUEST_ERROR" in upper
                    and "JSON" in upper
                )
            )

            transient = any(
                code in upper
                for code in [
                    "429",
                    "500",
                    "502",
                    "503",
                    "504",
                    "RATE LIMIT",
                    "TOO MANY REQUESTS",
                    "TIMEOUT",
                    "TIMED OUT",
                    "SERVICE UNAVAILABLE",
                    "BAD GATEWAY",
                    "GATEWAY TIMEOUT",
                    "CONNECTION RESET",
                    "CONNECTION ERROR",
                ]
            )

            # -------------------------------------------------
            # JSON-MODE FALLBACK
            # -------------------------------------------------
            # A 400 json_validate_failed is not a transient server error.
            # Try one plain-text generation so clean_json() can recover the
            # JSON object from the returned content.
            if json_validation_error:
                print()
                print("Groq JSON validation failed.")
                print("Retrying with plain-text output mode...")

                try:
                    fallback_response = client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": SYSTEM_PROMPT,
                            },
                            {
                                "role": "user",
                                "content": (
                                    prompt
                                    + "\n\n"
                                    + "IMPORTANT: Return exactly one JSON object. "
                                    + "Do not use Markdown or code fences. "
                                    + "Do not include reasoning or explanation. "
                                    + "The first character must be { and the last "
                                    + "character must be }."
                                ),
                            },
                        ],
                        temperature=0.1,
                        reasoning_effort="medium",
                        include_reasoning=False,
                        max_completion_tokens=8000,
                    )

                    if (
                        fallback_response
                        and fallback_response.choices
                    ):
                        fallback_content = (
                            fallback_response.choices[0].message.content
                        )

                        if fallback_content:
                            print("Groq plain-text fallback succeeded.")
                            return fallback_content

                except Exception as fallback_error:
                    print("Groq fallback failed:")
                    print(str(fallback_error))
                    last_error = fallback_error

                # JSON validation is deterministic enough that immediately
                # repeating the exact same JSON-mode request is usually not
                # useful. Continue with a normal retry only if attempts remain.

            if not transient and not json_validation_error:
                raise RuntimeError(
                    f"Groq API error: {error_text}"
                )

            if attempt < retries:
                delay = min(
                    3 * (2 ** (attempt - 1)),
                    40,
                ) + random.uniform(0.5, 1.5)

                print(
                    f"Retrying Groq in {delay:.1f} seconds..."
                )

                time.sleep(delay)

    raise RuntimeError(
        f"Groq API failed after {retries} attempts: {last_error}"
    )


# =========================================================
# 6. BUILD JOURNEY PROMPT
# =========================================================

def build_journey_prompt(
    user_input,
    route_data,
    stations
):
    selected_stations = prepare_stations(stations)

    ev_range = float(
        user_input.get("ev_range", 0) or 0
    )

    battery = float(
        user_input.get("battery_percent", 0) or 0
    )

    available_range = (
        ev_range * battery / 100
        if ev_range > 0
        else 0
    )

    route_distance = float(
        route_data.get("distance_km", 0) or 0
    )

    prompt_data = {
        "user_requirements": {
            "from": user_input.get("from", ""),
            "to": user_input.get("to", ""),
            "ev_range_km": ev_range,
            "current_battery_percent": battery,
            "available_range_at_departure_km": round(
                available_range,
                2
            ),
            "distance_priority": user_input.get(
                "distance_priority",
                "Medium"
            ),
            "fast_charging_priority": user_input.get(
                "speed_priority",
                "Medium"
            ),
            "food_required": user_input.get(
                "food_required",
                False
            ),
            "food_radius_m": user_input.get(
                "food_radius",
                2000
            ),
            "avoid_tolls": user_input.get(
                "avoid_tolls",
                False
            ),
            "preferred_connector": user_input.get(
                "connector",
                "Any"
            ),
            "departure_time": user_input.get(
                "departure",
                "Now"
            ),
            "minimum_charger_power_kw": user_input.get(
                "minimum_power",
                "Any"
            ),
            "maximum_charging_stops": user_input.get(
                "max_stops",
                "Any"
            )
        },

        "route": {
            "distance_km": route_distance,
            "duration_minutes": route_data.get(
                "duration_minutes",
                0
            ),
            "duration_hours": route_data.get(
                "duration_hours",
                0
            ),
            "from": route_data.get(
                "from",
                {}
            ).get(
                "display_name",
                user_input.get("from", "")
            ),
            "to": route_data.get(
                "to",
                {}
            ).get(
                "display_name",
                user_input.get("to", "")
            )
        },

        "charging_stations": selected_stations,
        "candidate_count": len(selected_stations),
        "candidate_route_positions_km": [
            station.get("route_distance_km")
            for station in selected_stations
        ]
    }

    prompt = f"""
Create a multi-stop ChargePilot EV journey plan.

=========================================================
JOURNEY DATA
=========================================================

{json.dumps(
    prompt_data,
    indent=2,
    ensure_ascii=False,
    default=str
)}

=========================================================
FIRST CHECK
=========================================================

The vehicle's estimated departure range is:

{available_range:.2f} km

The route is:

{route_distance:.2f} km

If the route is longer than the available range, charging
is required.

For a long route, do NOT return only one charging station.
The supplied candidates are distributed across the route. Prefer
sequential route positions so each charging stop advances the trip.

=========================================================
MULTI-STOP PLANNING
=========================================================

Build the journey as sequential legs:

START
→ CHARGING STOP 1
→ CHARGING STOP 2
→ CHARGING STOP 3
→ ...
→ DESTINATION

For every leg, reason about whether the next destination
is reachable with a safe battery reserve.

Use only the supplied charging stations.

When several candidates are available, sort/compare them by their
route_distance_km and construct sequential legs. Do not repeatedly
use a station near the beginning of the route for later legs.

If the supplied candidates do not cover the full journey,
do not invent additional stations.

Instead return:

planning_status = "insufficient_station_coverage"

and explain the coverage problem.

=========================================================
ROUTE-DISTRIBUTION CHECK
=========================================================

Before producing the JSON, inspect the supplied station route positions.
For a long journey, choose a sequence of stations that advances from
the start toward the destination. Each selected charging station must
be reachable from the previous point with a practical battery reserve.
Do not count all supplied candidates as charging stops; select only
those actually needed.

If the route is longer than the available range and there are enough
route-distributed candidates, produce a complete sequence of CHARGE
legs followed by an ARRIVE leg.

=========================================================
OUTPUT REQUIREMENTS
=========================================================

Return:

1. Overall journey summary.
2. Whether charging is required.
3. Number of actual charging stops.
4. First/primary recommended station.
5. Total estimated charging cost.
6. Total estimated charging time.
7. Battery/range analysis.
8. Overall recommendation.
9. A chronological journey_legs array.
10. Comparison of no more than 4 supplied candidate stations.

Remember:

estimated_stops =
number of journey_legs where action == "CHARGE"

Do not return estimated_stops = 0 when charging is required
unless the plan is explicitly incomplete because of insufficient
station coverage.

Return ONLY JSON.
"""

    return prompt


# =========================================================
# 7. RESULT NORMALIZATION
# =========================================================

def _station_name(station):
    return str(
        station.get("name")
        or station.get("title")
        or station.get("station_name")
        or "Charging station"
    ).strip()


def _station_position(station):
    try:
        value = station.get("route_distance_km")
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_leg_km(ev_range, battery_percent, reserve_percent=10.0):
    if ev_range <= 0:
        return 0.0

    battery_percent = max(0.0, min(100.0, battery_percent))
    reserve_percent = max(0.0, min(50.0, reserve_percent))

    return max(
        0.0,
        ev_range * (battery_percent - reserve_percent) / 100.0,
    )


def _estimate_charge_time_minutes(station, charge_from, charge_to, fallback=30.0):
    """Use supplied estimate first; otherwise provide a conservative UI estimate."""
    for key in (
        "estimated_time_minutes",
        "charging_time_minutes",
        "charging_time",
    ):
        value = station.get(key)
        try:
            number = float(value)
            if number > 0:
                return round(number, 1)
        except (TypeError, ValueError):
            pass

    power = 0.0
    for key in ("power_kw", "max_power_kw", "maximum_power"):
        try:
            power = max(power, float(station.get(key) or 0))
        except (TypeError, ValueError):
            pass

    if power >= 100:
        fallback = 25.0
    elif power >= 50:
        fallback = 35.0
    elif power >= 25:
        fallback = 50.0
    elif power > 0:
        fallback = 70.0

    # The exact charging curve is vehicle-specific, so this remains an estimate.
    return round(float(fallback), 1)


def _build_candidate_lookup(stations):
    lookup = {}
    for station in stations:
        if not isinstance(station, dict):
            continue
        normalized = normalize_station(station)
        name = _station_name(normalized)
        lookup[name.lower()] = normalized
    return lookup


def _extract_ai_stops(result, stations):
    lookup = _build_candidate_lookup(stations)
    stops = []

    for leg in result.get("journey_legs", []) or []:
        if not isinstance(leg, dict):
            continue
        if str(leg.get("action", "")).upper() != "CHARGE":
            continue

        requested_name = str(
            leg.get("charging_station")
            or leg.get("to")
            or ""
        ).strip()

        if not requested_name:
            continue

        target = requested_name.lower()
        station = lookup.get(target)

        if station is None:
            for name, candidate in lookup.items():
                if name in target or target in name:
                    station = candidate
                    break

        if station is None:
            continue

        position = _station_position(station)
        if position is None:
            continue

        stops.append({
            "station": station,
            "position": position,
            "charge_to": float(leg.get("charge_to_percent") or 80),
            "charge_time": float(leg.get("estimated_charging_time_minutes") or 0),
            "charge_cost": float(leg.get("estimated_charging_cost") or 0),
        })

    # Remove duplicate stations and sort along the route.
    unique = []
    seen = set()
    for stop in sorted(stops, key=lambda item: item["position"]):
        name = _station_name(stop["station"]).lower()
        if name in seen:
            continue
        seen.add(name)
        unique.append(stop)

    return unique


def _prune_redundant_stops(stops, route_distance, ev_range, battery, reserve_percent=10.0):
    """
    Remove charging stops that are not necessary to reach the next kept
    point/destination with reserve. This directly handles the case where
    the AI returns two stops even though one stop is sufficient.
    """
    stops = list(stops)

    if not stops:
        return stops

    changed = True
    while changed and stops:
        changed = False
        kept = []
        previous_position = 0.0
        previous_battery = float(battery)

        for index, stop in enumerate(stops):
            next_position = (
                stops[index + 1]["position"]
                if index + 1 < len(stops)
                else route_distance
            )

            distance_if_removed = max(
                0.0,
                next_position - previous_position,
            )

            safe_distance = _safe_leg_km(
                ev_range,
                previous_battery,
                reserve_percent,
            )

            if distance_if_removed <= safe_distance + 1.0:
                # Current stop is not required.
                changed = True
                continue

            kept.append(stop)
            previous_position = stop["position"]
            previous_battery = float(
                stop.get("charge_to") or 80.0
            )

        stops = kept

    return stops


def _greedy_minimum_stops(stations, route_distance, ev_range, battery, max_stops="Any"):
    """
    Deterministic fallback: choose the farthest reachable real charger at
    every required stage, stopping immediately once the destination is
    reachable. This minimizes the number of stops for the available candidates.
    """
    candidates = []
    for station in stations:
        if not isinstance(station, dict):
            continue

        normalized = normalize_station(station)
        position = _station_position(normalized)
        if position is None:
            continue
        if position <= 0 or position >= route_distance:
            continue

        candidates.append({
            "station": normalized,
            "position": position,
            "charge_to": 80.0,
            "charge_time": 0.0,
            "charge_cost": 0.0,
        })

    candidates.sort(key=lambda item: item["position"])

    try:
        stop_limit = int(float(max_stops))
        if stop_limit <= 0:
            stop_limit = MAX_PLANNED_STOPS
    except (TypeError, ValueError):
        stop_limit = MAX_PLANNED_STOPS

    stop_limit = min(stop_limit, MAX_PLANNED_STOPS)

    selected = []
    current_position = 0.0
    current_battery = float(battery)

    while current_position < route_distance and len(selected) < stop_limit:
        destination_distance = route_distance - current_position
        safe_distance = _safe_leg_km(
            ev_range,
            current_battery,
            10.0,
        )

        if destination_distance <= safe_distance + 1.0:
            break

        reachable = [
            candidate
            for candidate in candidates
            if candidate["position"] > current_position + 1.0
            and candidate["position"] - current_position <= safe_distance + 1.0
            and all(
                _station_name(candidate["station"]).lower()
                != _station_name(existing["station"]).lower()
                for existing in selected
            )
        ]

        if not reachable:
            break

        # Prefer the furthest reachable station; within a small positional
        # window, prefer stronger chargers and lower detours.
        furthest_position = max(item["position"] for item in reachable)
        shortlist = [
            item for item in reachable
            if item["position"] >= furthest_position - 35
        ]
        shortlist.sort(
            key=lambda item: (
                -item["position"],
                -float(item["station"].get("power_kw") or item["station"].get("max_power_kw") or 0),
                float(item["station"].get("detour_km") or 0),
            )
        )

        chosen = shortlist[0]
        selected.append(chosen)
        current_position = chosen["position"]
        current_battery = 80.0

    return selected


def _is_stop_sequence_feasible(stops, route_distance, ev_range, battery, reserve_percent=10.0):
    current_position = 0.0
    current_battery = float(battery)

    for stop in stops:
        distance = max(0.0, float(stop["position"]) - current_position)
        if distance > _safe_leg_km(ev_range, current_battery, reserve_percent) + 1.0:
            return False
        current_position = float(stop["position"])
        current_battery = float(stop.get("charge_to") or 80.0)

    destination_distance = max(0.0, route_distance - current_position)
    return destination_distance <= _safe_leg_km(
        ev_range, current_battery, reserve_percent
    ) + 1.0


def _rebuild_journey_legs(stops, route_distance, ev_range, battery, result):
    """Create a consistent frontend-ready sequence from the selected stops."""
    legs = []
    current_position = 0.0
    previous_name = "Start"
    current_battery = float(battery)
    total_time = 0.0
    total_cost = 0.0

    # Preserve AI charging details by station name when available.
    ai_by_name = {}
    for leg in result.get("journey_legs", []) or []:
        if not isinstance(leg, dict):
            continue
        if str(leg.get("action", "")).upper() != "CHARGE":
            continue
        name = str(
            leg.get("charging_station")
            or leg.get("to")
            or ""
        ).strip().lower()
        if name:
            ai_by_name[name] = leg

    for index, stop in enumerate(stops, start=1):
        station = stop["station"]
        station_name = _station_name(station)
        position = float(stop["position"])

        leg_distance = max(0.0, position - current_position)
        arrival_battery = (
            current_battery - (leg_distance / ev_range * 100.0)
            if ev_range > 0
            else 0.0
        )
        arrival_battery = max(0.0, min(100.0, arrival_battery))

        ai_leg = ai_by_name.get(station_name.lower(), {})
        charge_to = float(
            ai_leg.get("charge_to_percent")
            or stop.get("charge_to")
            or 80.0
        )
        charge_to = max(55.0, min(90.0, charge_to))

        charge_time = _estimate_charge_time_minutes(
            station,
            arrival_battery,
            charge_to,
            fallback=30.0,
        )
        if ai_leg.get("estimated_charging_time_minutes"):
            try:
                ai_time = float(ai_leg["estimated_charging_time_minutes"])
                if ai_time > 0:
                    charge_time = round(ai_time, 1)
            except (TypeError, ValueError):
                pass

        try:
            charge_cost = float(
                ai_leg.get("estimated_charging_cost")
                or station.get("estimated_cost")
                or station.get("cost")
                or station.get("charging_cost")
                or 0
            )
        except (TypeError, ValueError):
            charge_cost = 0.0

        legs.append({
            "step": index,
            "from": previous_name,
            "to": station_name,
            "leg_distance_km": round(leg_distance, 2),
            "departure_battery_percent": round(current_battery, 1),
            "arrival_battery_percent": round(arrival_battery, 1),
            "action": "CHARGE",
            "charging_station": station_name,
            "charger_power_kw": round(float(
                station.get("power_kw")
                or station.get("max_power_kw")
                or station.get("power")
                or 0
            ), 2),
            "connector": station.get("connector") or "",
            "charge_from_percent": round(arrival_battery, 1),
            "charge_to_percent": round(charge_to, 1),
            "estimated_charging_time_minutes": round(charge_time, 1),
            "estimated_charging_cost": round(charge_cost, 2),
        })

        total_time += charge_time
        total_cost += charge_cost
        current_position = position
        previous_name = station_name
        current_battery = charge_to

    final_distance = max(0.0, route_distance - current_position)
    final_battery = (
        current_battery - (final_distance / ev_range * 100.0)
        if ev_range > 0
        else 0.0
    )
    final_battery = max(0.0, min(100.0, final_battery))

    legs.append({
        "step": len(legs) + 1,
        "from": previous_name,
        "to": "Destination",
        "leg_distance_km": round(final_distance, 2),
        "departure_battery_percent": round(current_battery, 1),
        "arrival_battery_percent": round(final_battery, 1),
        "action": "ARRIVE",
        "charging_station": "",
        "charge_from_percent": 0,
        "charge_to_percent": 0,
        "estimated_charging_time_minutes": 0,
        "estimated_charging_cost": 0,
    })

    return legs, total_time, total_cost


def validate_and_normalize_result(
    result,
    user_input,
    route_data,
    stations
):
    if not isinstance(result, dict):
        result = {}

    ev_range = float(user_input.get("ev_range", 0) or 0)
    battery = float(user_input.get("battery_percent", 0) or 0)
    route_distance = float(route_data.get("distance_km", 0) or 0)

    # 10% practical reserve. The first leg also starts from the actual
    # battery percentage, not a full battery assumption.
    initial_safe_distance = _safe_leg_km(ev_range, battery, 10.0)
    charging_required = route_distance > initial_safe_distance + 1.0

    result.setdefault("planning_status", "complete")
    result.setdefault("journey_summary", "")
    result["charging_required"] = charging_required
    result.setdefault("estimated_stops", 0)
    result.setdefault("recommended_station", "No charging required")
    result.setdefault("estimated_charging_cost", 0)
    result.setdefault("estimated_charging_time_minutes", 0)
    result.setdefault("battery_range_analysis", "")
    result.setdefault("recommendation", "")
    result.setdefault("journey_legs", [])
    result.setdefault("station_comparison", [])

    if not isinstance(result["journey_legs"], list):
        result["journey_legs"] = []
    if not isinstance(result["station_comparison"], list):
        result["station_comparison"] = []

    result["station_comparison"] = result["station_comparison"][:4]

    normalized_stations = []
    for station in stations:
        if isinstance(station, dict):
            normalized_stations.append(normalize_station(station))

    # No charge is required: create a single arrival leg so the frontend
    # always has a complete route card.
    if not charging_required:
        result["journey_legs"] = [{
            "step": 1,
            "from": "Start",
            "to": "Destination",
            "leg_distance_km": round(route_distance, 2),
            "departure_battery_percent": round(battery, 1),
            "arrival_battery_percent": round(
                max(0.0, battery - (route_distance / ev_range * 100.0)),
                1,
            ) if ev_range > 0 else 0,
            "action": "ARRIVE",
            "charging_station": "",
            "charge_from_percent": 0,
            "charge_to_percent": 0,
            "estimated_charging_time_minutes": 0,
            "estimated_charging_cost": 0,
        }]
        result["estimated_stops"] = 0
        result["charging_required"] = False
        result["planning_status"] = "complete"
        result["recommended_station"] = "No charging required"
    else:
        # Prefer Groq's real station choices, then remove any unnecessary
        # extra stops. If Groq omitted legs, use a deterministic fallback.
        ai_stops = _extract_ai_stops(result, normalized_stations)
        ai_stops = _prune_redundant_stops(
            ai_stops,
            route_distance,
            ev_range,
            battery,
            reserve_percent=10.0,
        )

        if ai_stops and _is_stop_sequence_feasible(
            ai_stops,
            route_distance,
            ev_range,
            battery,
            reserve_percent=10.0,
        ):
            stops = ai_stops
        else:
            stops = _greedy_minimum_stops(
                normalized_stations,
                route_distance,
                ev_range,
                battery,
                user_input.get("max_stops", "Any"),
            )

        # If the user explicitly capped stops, obey that cap.
        try:
            max_stop_input = int(float(user_input.get("max_stops")))
            if max_stop_input > 0:
                stops = stops[:max_stop_input]
        except (TypeError, ValueError):
            pass

        legs, total_time, total_cost = _rebuild_journey_legs(
            stops,
            route_distance,
            ev_range,
            battery,
            result,
        )

        result["journey_legs"] = legs
        result["estimated_stops"] = len(stops)
        result["estimated_charging_time_minutes"] = round(total_time, 1)
        result["estimated_charging_cost"] = round(total_cost, 2)

        if stops:
            result["recommended_station"] = _station_name(
                stops[0]["station"]
            )

        # Verify every driving leg against the current charge strategy.
        coverage_ok = True
        current_position = 0.0
        current_battery = battery
        for leg in legs:
            distance = float(leg.get("leg_distance_km") or 0)
            safe_distance = _safe_leg_km(
                ev_range,
                current_battery,
                10.0,
            )
            if distance > safe_distance + 1.5:
                coverage_ok = False
                break

            action = str(leg.get("action", "")).upper()
            current_position += distance
            if action == "CHARGE":
                current_battery = float(
                    leg.get("charge_to_percent") or 80
                )

        result["planning_status"] = (
            "complete" if coverage_ok else "insufficient_station_coverage"
        )

        if stops and not result.get("recommendation"):
            result["recommendation"] = (
                "ChargePilot selected the minimum practical number of charging stops "
                "from the available route-distributed stations."
            )

    # Recalculate from the actual legs after fallback/pruning.
    result["estimated_stops"] = len([
        leg for leg in result["journey_legs"]
        if str(leg.get("action", "")).upper() == "CHARGE"
    ])

    # Explicit values used by the frontend.
    result["departure_ev_range_km"] = round(ev_range, 2)
    result["departure_battery_percent"] = round(battery, 2)
    result["available_range_km"] = round(
        ev_range * battery / 100.0,
        2,
    )
    result["route_distance_km"] = round(route_distance, 2)

    return result


# =========================================================
# 8. MAIN ANALYSIS FUNCTION
# =========================================================

def analyze_journey(
    user_input,
    route_data,
    stations
):
    print()
    print("=" * 60)
    print("ChargePilot AI Analysis Started")
    print("=" * 60)
    print("AI Provider : Groq")
    print("AI Model    :", MODEL)

    selected_stations = prepare_stations(
        stations
    )

    print(
        f"Candidate stations sent to AI: "
        f"{len(selected_stations)}"
    )

    for index, station in enumerate(
        selected_stations,
        start=1
    ):
        print(
            f"Candidate {index}: "
            f"{station.get('name')} | "
            f"Power: {station.get('power_kw', 0)} kW | "
            f"Detour: {station.get('detour_km', 0)} km | "
            f"Route position: "
            f"{station.get('route_distance_km')}"
        )

    ev_range = float(
        user_input.get("ev_range", 0) or 0
    )

    battery = float(
        user_input.get("battery_percent", 0) or 0
    )

    available_range = (
        ev_range * battery / 100
        if ev_range > 0
        else 0
    )

    route_distance = float(
        route_data.get("distance_km", 0) or 0
    )

    print(
        f"EV range: {ev_range} km"
    )

    print(
        f"Battery: {battery}%"
    )

    print(
        f"Available departure range: "
        f"{available_range:.2f} km"
    )

    print(
        f"Route distance: "
        f"{route_distance:.2f} km"
    )

    prompt = build_journey_prompt(
        user_input,
        route_data,
        selected_stations
    )

    print()
    print("Sending journey to Groq AI...")

    raw_response = ask_groq(
        prompt
    )

    cleaned_response = clean_json(
        raw_response
    )

    try:
        result = json.loads(
            cleaned_response
        )
    except json.JSONDecodeError as error:
        print("Groq JSON parsing failed:")
        print(error)
        print(raw_response)

        result = {
            "planning_status":
                "ai_response_error",

            "journey_summary":
                "Groq returned an invalid JSON response.",

            "charging_required":
                route_distance > available_range,

            "estimated_stops":
                0,

            "recommended_station":
                "Unable to determine",

            "estimated_charging_cost":
                0,

            "estimated_charging_time_minutes":
                0,

            "battery_range_analysis":
                "Unable to parse Groq response.",

            "recommendation":
                raw_response,

            "journey_legs":
                [],

            "station_comparison":
                []
        }

    result = validate_and_normalize_result(
        result,
        user_input,
        route_data,
        selected_stations
    )

    print()
    print("ChargePilot AI Analysis Completed.")
    print(
        "Planning status:",
        result.get("planning_status")
    )
    print(
        "Charging required:",
        result.get("charging_required")
    )
    print(
        "Estimated stops:",
        result.get("estimated_stops")
    )
    print(
        "Recommended station:",
        result.get("recommended_station")
    )
    print(
        "Journey legs:",
        len(result.get("journey_legs", []))
    )
    print(
        "Estimated cost:",
        result.get("estimated_charging_cost")
    )
    print(
        "Estimated charging time:",
        result.get("estimated_charging_time_minutes")
    )
    print("=" * 60)

    return result


# =========================================================
# 9. GROQ CONNECTION TEST
# =========================================================

def test_groq():
    print()
    print("=" * 40)
    print("Testing ChargePilot Groq connection...")
    print("Model:", MODEL)
    print("=" * 40)

    test_prompt = """
Return valid JSON only:

{
    "status": "success",
    "message": "ChargePilot Groq connection successful"
}
"""

    response = ask_groq(
        test_prompt
    )

    result = json.loads(
        clean_json(response)
    )

    print()
    print("Groq test response:")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    return result


# =========================================================
# 10. RUN DIRECTLY
# =========================================================

if __name__ == "__main__":
    try:
        test_groq()
    except Exception as error:
        print()
        print("=" * 40)
        print("Groq test failed:")
        print(error)
        print("=" * 40)
