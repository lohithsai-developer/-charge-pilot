from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory
)

import os
import uuid
import traceback


from tools import get_trip_data
from agent import analyze_journey


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)


# =========================================================
# GENERATED FILES
# =========================================================

GENERATED_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "generated"
)

os.makedirs(
    GENERATED_DIR,
    exist_ok=True
)


# =========================================================
# HELPERS
# =========================================================

def parse_bool(value, default=False):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()

        if value in (
            "true",
            "1",
            "yes",
            "on"
        ):
            return True

        if value in (
            "false",
            "0",
            "no",
            "off"
        ):
            return False

    return bool(value)


def safe_float(value, default=0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return default

            if value.lower() in (
                "any",
                "none",
                "n/a",
                "na"
            ):
                return default

        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return default

            if value.lower() in (
                "any",
                "none",
                "n/a",
                "na"
            ):
                return default

        return int(float(value))

    except (
        TypeError,
        ValueError
    ):
        return default


def clean_max_stops(value):
    """
    Preserve "Any" but convert numeric values safely.
    """

    if value is None:
        return "Any"

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return "Any"

        if value.lower() in (
            "any",
            "none",
            "n/a",
            "na"
        ):
            return "Any"

    try:
        number = int(float(value))

        if number < 0:
            return 0

        return number

    except (
        TypeError,
        ValueError
    ):
        return "Any"


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    return render_template(
        "index.html"
    )


# =========================================================
# PLAN JOURNEY
# =========================================================

@app.route(
    "/plan",
    methods=["POST"]
)
def plan_journey():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:
            return jsonify({
                "error":
                    "No journey data received."
            }), 400

        # -------------------------------------------------
        # LOCATIONS
        # -------------------------------------------------

        from_location = str(
            data.get(
                "from",
                ""
            )
        ).strip()

        to_location = str(
            data.get(
                "to",
                ""
            )
        ).strip()

        if not from_location:
            return jsonify({
                "error":
                    "Starting location is required."
            }), 400

        if not to_location:
            return jsonify({
                "error":
                    "Destination is required."
            }), 400

        # -------------------------------------------------
        # EV INPUTS
        # -------------------------------------------------

        ev_range = safe_float(
            data.get(
                "ev_range",
                0
            ),
            0
        )

        battery_percent = safe_float(
            data.get(
                "battery_percent",
                80
            ),
            80
        )

        # IMPORTANT:
        # Reject 0 instead of silently replacing it.
        # This prevents the frontend from showing a fake
        # 0 km EV range.
        if ev_range <= 0:
            return jsonify({
                "error":
                    "EV range must be greater than 0 km."
            }), 400

        battery_percent = max(
            0,
            min(
                100,
                battery_percent
            )
        )

        # -------------------------------------------------
        # PREFERENCES
        # -------------------------------------------------

        distance_priority = str(
            data.get(
                "distance_priority",
                "Medium"
            )
        )

        speed_priority = str(
            data.get(
                "speed_priority",
                "Medium"
            )
        )

        food_required = parse_bool(
            data.get(
                "food_required",
                False
            ),
            False
        )

        food_radius = safe_float(
            data.get(
                "food_radius",
                2000
            ),
            2000
        )

        food_radius = max(
            0,
            food_radius
        )

        avoid_tolls = parse_bool(
            data.get(
                "avoid_tolls",
                False
            ),
            False
        )

        connector = str(
            data.get(
                "connector",
                "Any"
            )
        )

        departure = str(
            data.get(
                "departure",
                "Now"
            )
        )

        minimum_power = data.get(
            "minimum_power",
            "Any"
        )

        max_stops = clean_max_stops(
            data.get(
                "max_stops",
                "Any"
            )
        )

        # -------------------------------------------------
        # DIRECT RANGE VALUE
        # -------------------------------------------------
        #
        # This is deliberately included in the API response
        # so the frontend does not need to infer EV range from
        # the AI text.
        #

        available_range_km = (
            ev_range
            * battery_percent
            / 100
        )

        # -------------------------------------------------
        # REQUEST LOG
        # -------------------------------------------------

        print()
        print("=" * 60)
        print("CHARGEPILOT JOURNEY REQUEST")
        print("=" * 60)

        print(
            f"From        : {from_location}"
        )

        print(
            f"To          : {to_location}"
        )

        print(
            f"EV Range    : {ev_range} km"
        )

        print(
            f"Battery     : {battery_percent}%"
        )

        print(
            f"Available   : "
            f"{available_range_km:.2f} km"
        )

        print(
            f"Distance    : {distance_priority}"
        )

        print(
            f"Fast Charge : {speed_priority}"
        )

        print(
            f"Food        : {food_required}"
        )

        print(
            f"Food Radius : {food_radius} m"
        )

        print(
            f"Avoid Tolls : {avoid_tolls}"
        )

        print(
            f"Connector   : {connector}"
        )

        print(
            f"Departure   : {departure}"
        )

        print(
            f"Min Power   : {minimum_power}"
        )

        print(
            f"Max Stops   : {max_stops}"
        )

        print("=" * 60)

        # =================================================
        # GET ROUTE + STATIONS
        # =================================================

        print()
        print(
            "Collecting route and charging station data..."
        )

        trip_data = get_trip_data(
            from_location=from_location,
            to_location=to_location,
            food_required=food_required,
            food_radius=food_radius,
            ev_range_km=ev_range,
            battery_percent=battery_percent,
            minimum_power=minimum_power,
            preferred_connector=connector,
            speed_priority=speed_priority,
            max_stops=max_stops
        )

        if not isinstance(
            trip_data,
            dict
        ):
            raise RuntimeError(
                "Trip data service returned invalid data."
            )

        route = trip_data.get(
            "route",
            {}
        )

        stations = trip_data.get(
            "stations",
            []
        )

        planning_data = trip_data.get(
            "planning",
            {}
        )

        if not isinstance(planning_data, dict):
            planning_data = {}

        if not isinstance(
            route,
            dict
        ):
            route = {}

        if not isinstance(
            stations,
            list
        ):
            stations = []

        route_distance = safe_float(
            route.get(
                "distance_km",
                0
            ),
            0
        )

        route_duration = safe_float(
            route.get(
                "duration_minutes",
                0
            ),
            0
        )

        print()
        print(
            f"Route distance: "
            f"{route_distance} km"
        )

        print(
            f"Travel time: "
            f"{route_duration} minutes"
        )

        print(
            f"Stations found: "
            f"{len(stations)}"
        )

        print(
            f"Dynamic candidates requested: "
            f"{planning_data.get('candidate_count_requested', len(stations))}"
        )

        start_info = route.get("from", {}) or {}
        destination_info = route.get("to", {}) or {}

        print()
        print("=" * 60)
        print("CHARGERS ALONG ROUTE")
        print("=" * 60)
        print(
            f"START      : {start_info.get('lat', 'N/A')}, "
            f"{start_info.get('lon', 'N/A')}"
        )
        print(
            f"DESTINATION: {destination_info.get('lat', 'N/A')}, "
            f"{destination_info.get('lon', 'N/A')}"
        )
        print()

        for index, station in enumerate(stations, start=1):
            print(
                f"Charger {index}: {station.get('name', 'Unknown')}"
            )
            print(
                f"  Coordinates : "
                f"{station.get('latitude', 'N/A')}, "
                f"{station.get('longitude', 'N/A')}"
            )
            print(
                f"  Route km    : "
                f"{station.get('route_distance_km', 'N/A')} km"
            )
            print(
                f"  Charger     : "
                f"{station.get('power_kw', station.get('max_power_kw', 0))} kW"
            )
            print(
                f"  Detour      : "
                f"{station.get('detour_km', 0)} km"
            )
            print(
                f"  Connector   : "
                f"{station.get('connector', 'Unknown')}"
            )
            print(
                f"  Status      : "
                f"{station.get('status', 'Unavailable')}"
            )
            print()

        print("=" * 60)

        # =================================================
        # AI INPUT
        # =================================================

        user_input = {

            "from":
                from_location,

            "to":
                to_location,

            "ev_range":
                ev_range,

            "battery_percent":
                battery_percent,

            "distance_priority":
                distance_priority,

            "speed_priority":
                speed_priority,

            "food_required":
                food_required,

            "food_radius":
                food_radius,

            "avoid_tolls":
                avoid_tolls,

            "connector":
                connector,

            "departure":
                departure,

            "minimum_power":
                minimum_power,

            "max_stops":
                max_stops
        }

        # =================================================
        # GROQ AI ANALYSIS
        # =================================================

        print()
        print(
            "Sending journey to Groq AI..."
        )

        ai_result = analyze_journey(
            user_input,
            route,
            stations
        )

        # Preserve charger power and connector details on every charging leg.
        if isinstance(ai_result, dict):
            station_by_name = {
                str(s.get("name", "")).strip().lower(): s
                for s in stations
                if isinstance(s, dict) and s.get("name")
            }
            for leg in ai_result.get("journey_legs", []) or []:
                if not isinstance(leg, dict):
                    continue
                if str(leg.get("action", "")).upper() != "CHARGE":
                    continue
                station_name = str(
                    leg.get("charging_station") or leg.get("to") or ""
                ).strip().lower()
                station = station_by_name.get(station_name, {})
                if station:
                    leg["charger_power_kw"] = station.get(
                        "power_kw",
                        station.get("max_power_kw", leg.get("charger_power_kw", 0))
                    )
                    leg["connector"] = station.get(
                        "connector", leg.get("connector", "")
                    )

        if not isinstance(
            ai_result,
            dict
        ):
            raise RuntimeError(
                "Groq returned invalid analysis data."
            )

        print()
        print(
            "Groq analysis completed."
        )

        # =================================================
        # NORMALIZE RESULT
        # =================================================

        charging_required = ai_result.get(
            "charging_required",
            False
        )

        estimated_stops = ai_result.get(
            "estimated_stops",
            0
        )

        charging_cost = ai_result.get(
            "estimated_charging_cost",
            0
        )

        charging_time = ai_result.get(
            "estimated_charging_time_minutes",
            0
        )

        recommended_station = ai_result.get(
            "recommended_station",
            "No recommendation"
        )

        recommendation = ai_result.get(
            "recommendation",
            ""
        )

        journey_summary = ai_result.get(
            "journey_summary",
            ""
        )

        battery_analysis = ai_result.get(
            "battery_range_analysis",
            ""
        )

        planning_status = ai_result.get(
            "planning_status",
            "complete"
        )

        journey_legs = ai_result.get(
            "journey_legs",
            []
        )

        station_comparison = ai_result.get(
            "station_comparison",
            []
        )

        if not isinstance(
            journey_legs,
            list
        ):
            journey_legs = []

        if not isinstance(
            station_comparison,
            list
        ):
            station_comparison = []

        # =================================================
        # IMPORTANT SAFETY CHECK
        # =================================================
        #
        # If the journey is longer than the departure range
        # and there are no charging legs, don't let the API
        # present "0 stops" as a complete plan.
        #

        if (
            route_distance > available_range_km
            and charging_required
            and len([
                leg for leg in journey_legs
                if isinstance(leg, dict)
                and str(
                    leg.get("action", "")
                ).upper() == "CHARGE"
            ]) == 0
        ):
            planning_status = (
                "insufficient_station_coverage"
            )

        # =================================================
        # RESPONSE
        # =================================================

        response = {

            # ------------------------------------------------
            # ROUTE
            # ------------------------------------------------

            "route_distance":
                round(
                    route_distance,
                    2
                ),

            "travel_time_minutes":
                round(
                    route_duration,
                    1
                ),

            "travel_time_hours":
                round(
                    route_duration / 60,
                    2
                ),

            "route_geometry":
                route.get(
                    "geometry",
                    []
                ),

            # ------------------------------------------------
            # EXPLICIT EV RANGE
            # ------------------------------------------------

            "ev_range_km":
                round(
                    ev_range,
                    2
                ),

            "battery_percent":
                round(
                    battery_percent,
                    2
                ),

            "available_range_km":
                round(
                    available_range_km,
                    2
                ),

            "range_remaining_after_route_km":
                round(
                    available_range_km
                    - route_distance,
                    2
                ),

            # ------------------------------------------------
            # AI PLAN
            # ------------------------------------------------

            "planning_status":
                planning_status,

            "charging_required":
                charging_required,

            "charging_stops":
                estimated_stops,

            "charging_cost":
                charging_cost,

            "charging_time":
                charging_time,

            "recommended_station":
                recommended_station,

            "recommendation":
                recommendation,

            "journey_summary":
                journey_summary,

            "battery_range_analysis":
                battery_analysis,

            # ------------------------------------------------
            # MULTI-STOP JOURNEY
            # ------------------------------------------------

            "journey_legs":
                journey_legs,

            # ------------------------------------------------
            # CANDIDATE STATIONS
            # ------------------------------------------------

            "station_comparison":
                station_comparison,

            "stations":
                stations,

            # ------------------------------------------------
            # DYNAMIC STATION PLANNING
            # ------------------------------------------------

            "station_planning":
                planning_data,

            "stations_found":
                len(stations),

            # ------------------------------------------------
            # COMPLETE AI RESULT
            # ------------------------------------------------

            "ai_result":
                ai_result,

            # ------------------------------------------------
            # ORIGINAL INPUT
            # ------------------------------------------------

            "trip_input":
                user_input
        }

        print()
        print("=" * 60)
        print("CHARGEPILOT PLAN READY")
        print("=" * 60)

        print(
            "Planning status:",
            planning_status
        )

        print(
            "Charging required:",
            charging_required
        )

        print(
            "Estimated stops:",
            estimated_stops
        )

        print(
            "Journey legs:",
            len(journey_legs)
        )

        print(
            "Recommended station:",
            recommended_station
        )

        print("=" * 60)

        return jsonify(
            response
        )

    except Exception as error:

        print()
        print("=" * 60)
        print("CHARGEPILOT ERROR")
        print("=" * 60)

        print(
            str(error)
        )

        traceback.print_exc()

        return jsonify({
            "error":
                str(error)
        }), 500


# =========================================================
# GENERATE PDF
# =========================================================

@app.route(
    "/generate-pdf",
    methods=["POST"]
)
def generate_pdf_route():

    try:

        from pdf_generator import (
            generate_pdf
        )

        data = request.get_json(
            silent=True
        )

        if not data:
            return jsonify({
                "error":
                    "No journey data received."
            }), 400

        if not isinstance(
            data,
            dict
        ):
            return jsonify({
                "error":
                    "Journey data must be a JSON object."
            }), 400

        filename = (
            "chargepilot_"
            + uuid.uuid4().hex[:8]
            + ".pdf"
        )

        output_path = os.path.join(
            GENERATED_DIR,
            filename
        )

        generated_file = generate_pdf(
            data,
            output_path
        )

        if generated_file:
            output_path = os.path.abspath(
                str(generated_file)
            )

            filename = os.path.basename(
                output_path
            )

        if not os.path.exists(
            output_path
        ):
            return jsonify({
                "error":
                    "PDF generator completed but the PDF file was not created."
            }), 500

        print()
        print("=" * 60)
        print("PDF GENERATED")
        print("=" * 60)

        print(
            f"Filename: {filename}"
        )

        print(
            f"Path: {output_path}"
        )

        print("=" * 60)

        return jsonify({
            "success":
                True,

            "filename":
                filename,

            "message":
                "PDF generated successfully."
        })

    except Exception as error:

        print()
        print(
            "PDF GENERATION ERROR:"
        )

        print(
            str(error)
        )

        traceback.print_exc()

        return jsonify({
            "error":
                str(error)
        }), 500


# =========================================================
# DOWNLOAD PDF
# =========================================================

@app.route(
    "/download-pdf/<filename>"
)
def download_pdf(filename):

    try:

        filename = os.path.basename(
            filename
        )

        pdf_path = os.path.join(
            GENERATED_DIR,
            filename
        )

        if not os.path.exists(
            pdf_path
        ):
            return jsonify({
                "error":
                    "PDF file not found."
            }), 404

        return send_from_directory(
            GENERATED_DIR,
            filename,
            as_attachment=True
        )

    except Exception as error:

        traceback.print_exc()

        return jsonify({
            "error":
                str(error)
        }), 500


# =========================================================
# SEND EMAIL
# =========================================================

@app.route(
    "/send-email",
    methods=["POST"]
)
def send_email():

    try:

        from email_service import (
            send_email_with_attachment
        )

        data = request.get_json(
            silent=True
        )

        if not data:
            return jsonify({
                "error":
                    "No email data received."
            }), 400

        email = str(
            data.get(
                "email",
                ""
            )
        ).strip()

        pdf_filename = str(
            data.get(
                "pdf_filename",
                ""
            )
        ).strip()

        if not email:
            return jsonify({
                "error":
                    "Email address is required."
            }), 400

        if not pdf_filename:
            return jsonify({
                "error":
                    "PDF must be generated first."
            }), 400

        pdf_filename = os.path.basename(
            pdf_filename
        )

        pdf_path = os.path.join(
            GENERATED_DIR,
            pdf_filename
        )

        if not os.path.exists(
            pdf_path
        ):
            return jsonify({
                "error":
                    "PDF file not found."
            }), 404

        send_email_with_attachment(
            to_email=email,
            pdf_path=pdf_path,
            subject="ChargePilot EV Journey Plan",
            body=(
                "Hello,\n\n"
                "Please find attached your "
                "ChargePilot AI-powered EV "
                "journey plan.\n\n"
                "The charging cost, charging time "
                "and battery values are estimates "
                "based on the supplied journey and "
                "available station data.\n\n"
                "Safe travels!\n\n"
                "ChargePilot"
            )
        )

        return jsonify({
            "success":
                True,

            "message":
                "Journey plan sent successfully."
        })

    except Exception as error:

        print()
        print("EMAIL ERROR:")
        print(
            str(error)
        )

        traceback.print_exc()

        return jsonify({
            "error":
                str(error)
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route(
    "/health"
)
def health():

    return jsonify({

        "status":
            "online",

        "service":
            "ChargePilot",

        "ai_provider":
            "Groq",

        "ai_model":
            "openai/gpt-oss-20b",

        "message":
            "Backend is running."
    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("⚡ CHARGEPILOT")
    print("AI-Powered EV Journey & Charging Planner")
    print("=" * 60)

    print()
    print(
        "AI Provider: Groq"
    )

    print(
        "AI Model: openai/gpt-oss-20b"
    )

    print()
    print(
        "Server starting..."
    )

    print(
        "Open in browser:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print()

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=(port == 5000)
    )
