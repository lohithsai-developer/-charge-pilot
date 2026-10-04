import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


# =========================================================
# DIRECTORIES
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

GENERATED_DIR = os.path.join(
    BASE_DIR,
    "generated"
)

os.makedirs(
    GENERATED_DIR,
    exist_ok=True
)


# =========================================================
# HELPERS
# =========================================================

def safe(value, default="N/A"):

    if value is None:
        return default

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return default

    return value


def fmt(value, decimals=2):

    try:
        return f"{float(value):.{decimals}f}"

    except (TypeError, ValueError):

        return str(
            safe(value)
        )


# =========================================================
# HEADER / FOOTER
# =========================================================

def add_header_footer(
    canvas,
    document
):

    canvas.saveState()

    width, height = A4

    # Header

    canvas.setFont(
        "Helvetica-Bold",
        9
    )

    canvas.setFillColor(
        colors.HexColor("#163A2D")
    )

    canvas.drawString(
        18 * mm,
        height - 12 * mm,
        "ChargePilot"
    )

    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.setFillColor(
        colors.HexColor("#68756F")
    )

    canvas.drawRightString(
        width - 18 * mm,
        height - 12 * mm,
        "AI-Powered EV Journey & Charging Planner"
    )

    # Footer line

    canvas.setStrokeColor(
        colors.HexColor("#D5DFDA")
    )

    canvas.line(
        18 * mm,
        14 * mm,
        width - 18 * mm,
        14 * mm
    )

    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.drawString(
        18 * mm,
        9 * mm,
        "ChargePilot EV Journey Plan"
    )

    canvas.drawRightString(
        width - 18 * mm,
        9 * mm,
        f"Page {document.page}"
    )

    canvas.restoreState()


# =========================================================
# MAIN PDF FUNCTION
# =========================================================

def generate_pdf(
    data,
    output_path=None
):

    """
    Generate ChargePilot PDF.

    IMPORTANT:
    app.py calls:

        generate_pdf(data, output_path)

    Therefore this function accepts exactly:

        data
        output_path
    """

    # -----------------------------------------------------
    # Validate data
    # -----------------------------------------------------

    if not isinstance(
        data,
        dict
    ):

        raise TypeError(
            "PDF data must be a dictionary."
        )


    # -----------------------------------------------------
    # Output path
    # -----------------------------------------------------

    if output_path:

        output_path = os.path.abspath(
            str(output_path)
        )

    else:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output_path = os.path.join(
            GENERATED_DIR,
            f"chargepilot_{timestamp}.pdf"
        )


    os.makedirs(
        os.path.dirname(output_path),
        exist_ok=True
    )


    # -----------------------------------------------------
    # Extract top-level data
    # -----------------------------------------------------

    trip_input = data.get(
        "trip_input",
        {}
    )

    if not isinstance(
        trip_input,
        dict
    ):

        trip_input = {}


    ai_result = data.get(
        "ai_result",
        {}
    )

    if not isinstance(
        ai_result,
        dict
    ):

        ai_result = {}


    stations = data.get(
        "stations",
        []
    )

    if not isinstance(
        stations,
        list
    ):

        stations = []


    station_comparison = data.get(
        "station_comparison",
        []
    )

    if not isinstance(
        station_comparison,
        list
    ):

        station_comparison = []


    # -----------------------------------------------------
    # Styles
    # -----------------------------------------------------

    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(
        "TitleChargePilot",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#163A2D"),
        spaceAfter=5,
    )


    subtitle_style = ParagraphStyle(
        "SubtitleChargePilot",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#68756F"),
        spaceAfter=10,
    )


    section_style = ParagraphStyle(
        "SectionChargePilot",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#163A2D"),
        spaceBefore=12,
        spaceAfter=7,
    )


    body_style = ParagraphStyle(
        "BodyChargePilot",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#26332E"),
        spaceAfter=4,
    )


    small_style = ParagraphStyle(
        "SmallChargePilot",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#68756F"),
    )


    table_style = ParagraphStyle(
        "TableChargePilot",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
    )


    header_style = ParagraphStyle(
        "TableHeaderChargePilot",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.white,
    )


    # -----------------------------------------------------
    # Document
    # -----------------------------------------------------

    document = SimpleDocTemplate(

        output_path,

        pagesize=A4,

        leftMargin=18 * mm,

        rightMargin=18 * mm,

        topMargin=20 * mm,

        bottomMargin=20 * mm,
    )


    story = []


    # =====================================================
    # TITLE
    # =====================================================

    story.append(
        Spacer(
            1,
            6 * mm
        )
    )


    story.append(
        Paragraph(
            "ChargePilot",
            title_style
        )
    )


    story.append(
        Paragraph(
            "AI-Powered EV Journey & Charging Break Planner",
            subtitle_style
        )
    )


    story.append(
        Paragraph(
            "Generated on "
            + datetime.now().strftime(
                "%d %B %Y at %I:%M %p"
            ),
            small_style
        )
    )


    story.append(
        Spacer(
            1,
            4 * mm
        )
    )


    # =====================================================
    # JOURNEY OVERVIEW
    # =====================================================

    story.append(
        Paragraph(
            "1. Journey Overview",
            section_style
        )
    )


    from_location = safe(
        trip_input.get(
            "from",
            "N/A"
        )
    )


    to_location = safe(
        trip_input.get(
            "to",
            "N/A"
        )
    )


    route_distance = data.get(
        "route_distance",
        0
    )


    travel_minutes = data.get(
        "travel_time_minutes",
        0
    )


    travel_hours = data.get(
        "travel_time_hours",
        0
    )


    journey_table_data = [

        [
            Paragraph(
                "<b>From</b>",
                body_style
            ),

            Paragraph(
                str(from_location),
                body_style
            )
        ],

        [
            Paragraph(
                "<b>Destination</b>",
                body_style
            ),

            Paragraph(
                str(to_location),
                body_style
            )
        ],

        [
            Paragraph(
                "<b>Route Distance</b>",
                body_style
            ),

            Paragraph(
                f"{fmt(route_distance)} km",
                body_style
            )
        ],

        [
            Paragraph(
                "<b>Travel Time</b>",
                body_style
            ),

            Paragraph(
                f"{fmt(travel_hours)} hours "
                f"({fmt(travel_minutes, 0)} minutes)",
                body_style
            )
        ],
    ]


    journey_table = Table(
        journey_table_data,
        colWidths=[
            48 * mm,
            122 * mm
        ]
    )


    journey_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EEF5F1")
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D5DFDA")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
        ])
    )


    story.append(
        journey_table
    )


    # =====================================================
    # EV PREFERENCES
    # =====================================================

    story.append(
        Paragraph(
            "2. EV & User Preferences",
            section_style
        )
    )


    ev_rows = [

        [
            Paragraph(
                "<b>EV Range</b>",
                body_style
            ),

            Paragraph(
                f"{safe(trip_input.get('ev_range'))} km",
                body_style
            ),

            Paragraph(
                "<b>Battery</b>",
                body_style
            ),

            Paragraph(
                f"{safe(trip_input.get('battery_percent'))}%",
                body_style
            ),
        ],

        [
            Paragraph(
                "<b>Budget</b>",
                body_style
            ),

            Paragraph(
                f"₹{safe(trip_input.get('budget'))}",
                body_style
            ),

            Paragraph(
                "<b>Connector</b>",
                body_style
            ),

            Paragraph(
                str(
                    safe(
                        trip_input.get(
                            "connector",
                            "Any"
                        )
                    )
                ),
                body_style
            ),
        ],

        [
            Paragraph(
                "<b>Distance Priority</b>",
                body_style
            ),

            Paragraph(
                str(
                    safe(
                        trip_input.get(
                            "distance_priority",
                            "Medium"
                        )
                    )
                ),
                body_style
            ),

            Paragraph(
                "<b>Fast Charging</b>",
                body_style
            ),

            Paragraph(
                str(
                    safe(
                        trip_input.get(
                            "speed_priority",
                            "Medium"
                        )
                    )
                ),
                body_style
            ),
        ],

        [
            Paragraph(
                "<b>Food Required</b>",
                body_style
            ),

            Paragraph(
                "Yes"
                if trip_input.get(
                    "food_required",
                    False
                )
                else "No",
                body_style
            ),

            Paragraph(
                "<b>Restaurant Radius</b>",
                body_style
            ),

            Paragraph(
                f"{safe(trip_input.get('food_radius'))} m",
                body_style
            ),
        ],

        [
            Paragraph(
                "<b>Avoid Tolls</b>",
                body_style
            ),

            Paragraph(
                "Yes"
                if trip_input.get(
                    "avoid_tolls",
                    False
                )
                else "No",
                body_style
            ),

            Paragraph(
                "<b>Minimum Power</b>",
                body_style
            ),

            Paragraph(
                f"{safe(trip_input.get('minimum_power'))} kW",
                body_style
            ),
        ],
    ]


    ev_table = Table(
        ev_rows,
        colWidths=[
            40 * mm,
            43 * mm,
            45 * mm,
            42 * mm
        ]
    )


    ev_table.setStyle(
        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D5DFDA")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F4F7F5")
            ),

            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#F4F7F5")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
        ])
    )


    story.append(
        ev_table
    )


    # =====================================================
    # AI ANALYSIS
    # =====================================================

    story.append(
        Paragraph(
            "3. AI Journey Analysis",
            section_style
        )
    )


    charging_required = ai_result.get(
        "charging_required",
        False
    )


    estimated_stops = ai_result.get(
        "estimated_stops",
        data.get(
            "charging_stops",
            0
        )
    )


    charging_cost = ai_result.get(
        "estimated_charging_cost",
        data.get(
            "charging_cost",
            0
        )
    )


    charging_time = ai_result.get(
        "estimated_charging_time_minutes",
        data.get(
            "charging_time",
            0
        )
    )


    analysis_rows = [

        [
            Paragraph(
                "<b>Charging Required</b>",
                body_style
            ),

            Paragraph(
                "Yes"
                if charging_required
                else "No",
                body_style
            ),

            Paragraph(
                "<b>Estimated Stops</b>",
                body_style
            ),

            Paragraph(
                str(
                    safe(
                        estimated_stops,
                        0
                    )
                ),
                body_style
            ),
        ],

        [
            Paragraph(
                "<b>Estimated Cost</b>",
                body_style
            ),

            Paragraph(
                f"₹{fmt(charging_cost)}",
                body_style
            ),

            Paragraph(
                "<b>Charging Time</b>",
                body_style
            ),

            Paragraph(
                f"{fmt(charging_time, 0)} minutes",
                body_style
            ),
        ],
    ]


    analysis_table = Table(
        analysis_rows,
        colWidths=[
            48 * mm,
            37 * mm,
            45 * mm,
            40 * mm
        ]
    )


    analysis_table.setStyle(
        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D5DFDA")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EEF5F1")
            ),

            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#EEF5F1")
            ),
        ])
    )


    story.append(
        analysis_table
    )


    # =====================================================
    # JOURNEY SUMMARY
    # =====================================================

    story.append(
        Paragraph(
            "Journey Summary",
            section_style
        )
    )


    journey_summary = ai_result.get(
        "journey_summary",
        data.get(
            "journey_summary",
            "No journey summary available."
        )
    )


    story.append(
        Paragraph(
            str(
                safe(
                    journey_summary
                )
            ),
            body_style
        )
    )


    # =====================================================
    # BATTERY ANALYSIS
    # =====================================================

    story.append(
        Paragraph(
            "Battery & Range Analysis",
            section_style
        )
    )


    battery_analysis = ai_result.get(
        "battery_range_analysis",
        data.get(
            "battery_range_analysis",
            "No battery analysis available."
        )
    )


    story.append(
        Paragraph(
            str(
                safe(
                    battery_analysis
                )
            ),
            body_style
        )
    )


    # =====================================================
    # RECOMMENDATION
    # =====================================================

    story.append(
        Paragraph(
            "AI Recommendation",
            section_style
        )
    )


    recommended_station = ai_result.get(
        "recommended_station",
        data.get(
            "recommended_station",
            "Not available"
        )
    )


    recommendation = ai_result.get(
        "recommendation",
        data.get(
            "recommendation",
            "No recommendation available."
        )
    )


    story.append(
        Paragraph(
            "<b>Recommended Station:</b> "
            + str(
                safe(
                    recommended_station
                )
            ),
            body_style
        )
    )


    story.append(
        Paragraph(
            str(
                safe(
                    recommendation
                )
            ),
            body_style
        )
    )


    # =====================================================
    # CHARGING STATIONS
    # =====================================================

    story.append(
        Paragraph(
            "4. Charging Station Comparison",
            section_style
        )
    )


    comparison = station_comparison


    if not comparison:

        comparison = stations


    station_rows = [

        [
            Paragraph(
                "Station",
                header_style
            ),

            Paragraph(
                "Power",
                header_style
            ),

            Paragraph(
                "Status",
                header_style
            ),

            Paragraph(
                "Detour",
                header_style
            ),

            Paragraph(
                "Cost",
                header_style
            ),

            Paragraph(
                "Time",
                header_style
            ),

            Paragraph(
                "Food",
                header_style
            ),
        ]
    ]


    for station in comparison[:15]:

        # -------------------------------------------------
        # IMPORTANT:
        # Prevent 'str' object has no attribute 'get'
        # -------------------------------------------------

        if isinstance(
            station,
            str
        ):

            name = station

            power = "N/A"

            status = "Unknown"

            detour = "N/A"

            cost = "N/A"

            time_value = "N/A"

            food = 0

        elif isinstance(
            station,
            dict
        ):

            name = station.get(
                "name",
                station.get(
                    "station_name",
                    "Unknown"
                )
            )

            power = station.get(
                "power_kw",
                station.get(
                    "power",
                    station.get(
                        "max_power_kw",
                        "N/A"
                    )
                )
            )

            status = station.get(
                "status",
                "Unknown"
            )

            detour = station.get(
                "detour_km",
                "N/A"
            )

            cost = station.get(
                "estimated_cost",
                station.get(
                    "cost",
                    "N/A"
                )
            )

            time_value = station.get(
                "estimated_time_minutes",
                station.get(
                    "charging_time_minutes",
                    "N/A"
                )
            )

            food = station.get(
                "restaurant_count",
                len(
                    station.get(
                        "restaurants",
                        []
                    )
                    if isinstance(
                        station.get(
                            "restaurants",
                            []
                        ),
                        list
                    )
                    else []
                )
            )

        else:

            name = str(station)

            power = "N/A"

            status = "Unknown"

            detour = "N/A"

            cost = "N/A"

            time_value = "N/A"

            food = 0


        station_rows.append(

            [

                Paragraph(
                    str(
                        safe(
                            name,
                            "Unknown"
                        )
                    ),
                    table_style
                ),

                Paragraph(
                    f"{safe(power)} kW",
                    table_style
                ),

                Paragraph(
                    str(
                        safe(
                            status,
                            "Unknown"
                        )
                    ),
                    table_style
                ),

                Paragraph(
                    f"{safe(detour)} km",
                    table_style
                ),

                Paragraph(
                    f"₹{safe(cost)}",
                    table_style
                ),

                Paragraph(
                    f"{safe(time_value)} min",
                    table_style
                ),

                Paragraph(
                    str(
                        safe(
                            food,
                            0
                        )
                    ),
                    table_style
                ),
            ]
        )


    if len(station_rows) == 1:

        station_rows.append(

            [

                Paragraph(
                    "No charging station data available.",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),

                Paragraph(
                    "-",
                    table_style
                ),
            ]
        )


    station_table = Table(

        station_rows,

        colWidths=[
            43 * mm,
            20 * mm,
            27 * mm,
            21 * mm,
            20 * mm,
            22 * mm,
            20 * mm
        ],

        repeatRows=1
    )


    station_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#163A2D")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#D2DAD6")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
        ])
    )


    story.append(
        station_table
    )


    # =====================================================
    # RESTAURANTS
    # =====================================================

    story.append(
        Paragraph(
            "5. Restaurant Information",
            section_style
        )
    )


    restaurant_found = False


    for station in stations[:15]:

        if not isinstance(
            station,
            dict
        ):
            continue


        restaurants = station.get(
            "restaurants",
            []
        )


        if not isinstance(
            restaurants,
            list
        ):

            continue


        if not restaurants:
            continue


        restaurant_found = True


        station_name = station.get(
            "name",
            "Charging Station"
        )


        story.append(
            Paragraph(
                f"<b>{station_name}</b>",
                body_style
            )
        )


        for restaurant in restaurants[:5]:

            if isinstance(
                restaurant,
                dict
            ):

                restaurant_name = restaurant.get(
                    "name",
                    "Restaurant"
                )

                distance = restaurant.get(
                    "distance_m",
                    ""
                )

                if distance:

                    text = (
                        f"{restaurant_name} "
                        f"({distance} m)"
                    )

                else:

                    text = str(
                        restaurant_name
                    )

            else:

                text = str(
                    restaurant
                )


            story.append(
                Paragraph(
                    text,
                    body_style
                )
            )


    if not restaurant_found:

        story.append(
            Paragraph(
                "No restaurant information was available "
                "for the selected charging stations.",
                body_style
            )
        )


    # =====================================================
    # DISCLAIMER
    # =====================================================

    story.append(
        Paragraph(
            "6. Important Note",
            section_style
        )
    )


    story.append(
        Paragraph(
            "Charging cost, charging time and battery "
            "consumption are estimates. Actual values may "
            "vary depending on vehicle efficiency, traffic, "
            "weather, battery condition, charging curves, "
            "station tariffs and charger availability.",
            small_style
        )
    )


    story.append(
        Spacer(
            1,
            4 * mm
        )
    )


    story.append(
        Paragraph(
            "Live charger availability is shown only when "
            "live-status data is available. OpenChargeMap "
            "station information may not represent real-time "
            "charger occupancy.",
            small_style
        )
    )


    # =====================================================
    # BUILD
    # =====================================================

    document.build(

        story,

        onFirstPage=add_header_footer,

        onLaterPages=add_header_footer
    )


    # =====================================================
    # VERIFY
    # =====================================================

    if not os.path.isfile(
        output_path
    ):

        raise RuntimeError(
            "PDF generation failed: output file was not created."
        )


    print()
    print("=" * 60)
    print("PDF GENERATED SUCCESSFULLY")
    print("=" * 60)
    print(
        f"PDF: {output_path}"
    )
    print("=" * 60)


    return output_path


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    test_data = {

        "route_distance": 268.76,

        "travel_time_minutes": 211.3,

        "travel_time_hours": 3.52,

        "charging_stops": 1,

        "charging_cost": 0,

        "charging_time": 0,

        "recommended_station":
            "Blaze Fast Charger For 2 Ev Wheeler",

        "recommendation":
            "Test ChargePilot recommendation.",

        "journey_summary":
            "Test journey from Vijayawada.",

        "battery_range_analysis":
            "Charging may be required.",

        "station_comparison": [],

        "stations": [

            {
                "name":
                    "Blaze Fast Charger For 2 Ev Wheeler",

                "max_power_kw":
                    60,

                "status":
                    "Live status unavailable",

                "detour_km":
                    2.5,

                "restaurants": []
            }
        ],

        "ai_result": {

            "charging_required":
                True,

            "estimated_stops":
                1,

            "estimated_charging_cost":
                0,

            "estimated_charging_time_minutes":
                0,

            "recommended_station":
                "Blaze Fast Charger For 2 Ev Wheeler",

            "journey_summary":
                "Test journey.",

            "battery_range_analysis":
                "Test battery analysis.",

            "recommendation":
                "Test recommendation.",

            "station_comparison":
                []
        },

        "trip_input": {

            "from":
                "Vijayawada",

            "to":
                "Hyderabad",

            "ev_range":
                300,

            "battery_percent":
                80,

            "budget":
                1000,

            "distance_priority":
                "Medium",

            "speed_priority":
                "High",

            "food_required":
                True,

            "food_radius":
                2000,

            "avoid_tolls":
                False,

            "connector":
                "Any",

            "departure":
                "Now",

            "minimum_power":
                "Any",

            "max_stops":
                2
        }
    }


    generate_pdf(
        test_data
    )