let latestPlan = null;

let latestPdfFilename = null;

let map = null;

let routeLayer = null;

let stationMarkers = [];


// =====================================================
// DOM
// =====================================================

const $ = (id) =>
    document.getElementById(id);


// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        setupSegmentedControls();

        setupSwap();

        setupFoodToggle();

        setupPlanButton();

        setupPdfButton();

        setupEmailButton();

    }
);


// =====================================================
// SEGMENTED CONTROLS
// =====================================================

function setupSegmentedControls() {

    document
        .querySelectorAll(".segmented")
        .forEach(group => {

            group
                .querySelectorAll("button")
                .forEach(button => {

                    button.addEventListener(
                        "click",
                        () => {

                            group
                                .querySelectorAll("button")
                                .forEach(btn =>
                                    btn.classList.remove(
                                        "active"
                                    )
                                );


                            button.classList.add(
                                "active"
                            );

                        }
                    );

                });

        });

}


// =====================================================
// GET SEGMENT VALUE
// =====================================================

function getSegmentValue(groupName) {

    const group =
        document.querySelector(
            `.segmented[data-group="${groupName}"]`
        );


    const active =
        group?.querySelector(
            "button.active"
        );


    return active
        ? active.dataset.value
        : "Medium";

}


// =====================================================
// SWAP
// =====================================================

function setupSwap() {

    $("swapButton")
        .addEventListener(
            "click",
            () => {

                const from =
                    $("from");

                const to =
                    $("to");


                const temp =
                    from.value;


                from.value =
                    to.value;


                to.value =
                    temp;

            }
        );

}


// =====================================================
// FOOD TOGGLE
// =====================================================

function setupFoodToggle() {

    const checkbox =
        $("food_required");

    const radius =
        $("radiusContainer");


    function update() {

        if (
            checkbox.checked
        ) {

            radius.classList.add(
                "enabled"
            );

        } else {

            radius.classList.remove(
                "enabled"
            );

        }

    }


    checkbox.addEventListener(
        "change",
        update
    );


    update();

}


// =====================================================
// PLAN BUTTON
// =====================================================

function setupPlanButton() {

    $("planButton")
        .addEventListener(
            "click",
            planJourney
        );

}


// =====================================================
// VALIDATE INPUT
// =====================================================

function validateInputs() {

    const from =
        $("from").value.trim();

    const to =
        $("to").value.trim();


    if (!from) {

        alert(
            "Please enter the starting location."
        );

        $("from").focus();

        return false;

    }


    if (!to) {

        alert(
            "Please enter the destination."
        );

        $("to").focus();

        return false;

    }


    const range =
        Number(
            $("ev_range").value
        );


    if (
        !range ||
        range <= 0
    ) {

        alert(
            "Please enter a valid EV range."
        );

        return false;

    }


    const battery =
        Number(
            $("battery_percent").value
        );


    if (
        battery < 1 ||
        battery > 100
    ) {

        alert(
            "Battery percentage must be between 1 and 100."
        );

        return false;

    }


    return true;

}


// =====================================================
// BUILD PAYLOAD
// =====================================================

function buildPayload() {

    return {

        from:
            $("from").value.trim(),

        to:
            $("to").value.trim(),

        ev_range:
            Number(
                $("ev_range").value
            ),

        battery_percent:
            Number(
                $("battery_percent").value
            ),

        budget:
            Number(
                $("budget").value || 0
            ),

        distance_priority:
            getSegmentValue(
                "distance"
            ),

        speed_priority:
            getSegmentValue(
                "speed"
            ),

        food_required:
            $("food_required").checked,

        food_radius:
            Number(
                $("food_radius").value || 2000
            ),

        avoid_tolls:
            $("avoid_tolls").checked,

        connector:
            $("connector").value,

        departure:
            $("departure").value,

        minimum_power:
            $("minimum_power").value,

        max_stops:
            $("max_stops").value

    };

}


// =====================================================
// PLAN JOURNEY
// =====================================================

async function planJourney() {

    if (
        !validateInputs()
    ) {
        return;
    }


    const button =
        $("planButton");


    const loading =
        $("loading");


    const results =
        $("results");


    button.disabled =
        true;


    results.classList.add(
        "hidden"
    );


    loading.classList.remove(
        "hidden"
    );


    window.scrollTo({
        top: loading.offsetTop - 100,
        behavior: "smooth"
    });


    startLoadingAnimation();


    try {

        const payload =
            buildPayload();


        const response =
            await fetch(
                "/plan",
                {

                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        )

                }
            );


        let result;


        try {

            result =
                await response.json();

        } catch {

            throw new Error(
                "Server returned an invalid response."
            );

        }


        if (
            !response.ok
        ) {

            throw new Error(
                result.error ||
                "Journey planning failed."
            );

        }


        latestPlan =
            result;


        finishLoading();


        renderResults(
            result
        );


    } catch (error) {

        console.error(
            error
        );


        loading.classList.add(
            "hidden"
        );


        alert(
            "ChargePilot Error:\n\n"
            +
            error.message
        );

    } finally {

        button.disabled =
            false;

    }

}


// =====================================================
// LOADING ANIMATION
// =====================================================

let loadingTimer = null;


function startLoadingAnimation() {

    const messages = [

        "Collecting route and charging station data...",

        "Analyzing available charging stations...",

        "Gemini AI is evaluating your preferences...",

        "Building the final EV journey recommendation..."

    ];


    let index = 0;


    $("progressBar").style.width =
        "8%";


    document
        .querySelectorAll(
            ".loading-steps span"
        )
        .forEach(
            item =>
                item.classList.remove(
                    "active"
                )
        );


    $("step1").classList.add(
        "active"
    );


    $("loadingText").textContent =
        messages[0];


    loadingTimer =
        setInterval(
            () => {

                index =
                    Math.min(
                        index + 1,
                        messages.length - 1
                    );


                $("loadingText")
                    .textContent =
                    messages[index];


                $("progressBar")
                    .style.width =
                    `${(index + 1) * 25}%`;


                const steps = [
                    "step1",
                    "step2",
                    "step3",
                    "step4"
                ];


                steps
                    .slice(
                        0,
                        index + 1
                    )
                    .forEach(
                        id =>
                            $(id)
                                .classList
                                .add("active")
                    );


            },
            1800
        );

}


function finishLoading() {

    if (loadingTimer) {

        clearInterval(
            loadingTimer
        );

        loadingTimer =
            null;

    }


    $("progressBar")
        .style.width =
        "100%";


    document
        .querySelectorAll(
            ".loading-steps span"
        )
        .forEach(
            item =>
                item.classList.add(
                    "active"
                )
        );


    setTimeout(
        () => {

            $("loading")
                .classList
                .add("hidden");

        },
        500
    );

}


// =====================================================
// RENDER RESULTS
// =====================================================

function renderResults(
    result
) {

    $("results")
        .classList
        .remove("hidden");


    $("journeySummary")
        .textContent =
        result.journey_summary ||
        "AI-generated journey analysis completed.";


    $("routeDistance")
        .textContent =
        formatNumber(
            result.route_distance
        )
        + " km";


    $("chargingStops")
        .textContent =
        result.charging_stops ??
        "0";


    $("chargingCost")
        .textContent =
        formatCurrency(
            result.charging_cost
        );


    $("chargingTime")
        .textContent =
        formatChargingTime(
            result.charging_time
        );


    $("recommendedStation")
        .textContent =
        result.recommended_station ||
        "AI-selected charging plan";


    $("recommendation")
        .textContent =
        result.recommendation ||
        "ChargePilot generated the journey recommendation.";


    $("batteryAnalysis")
        .textContent =
        result.battery_range_analysis ||
        "Battery analysis unavailable.";


    const travelMinutes =
        Number(
            result.travel_time_minutes || 0
        );


    const travelHours =
        Number(
            result.travel_time_hours ||
            travelMinutes / 60
        );


    $("travelOverview")
        .textContent =
        `Estimated driving time: ${formatDuration(
            travelMinutes
        )
        }\n\n` +

        `Approximate journey duration: ${travelHours.toFixed(1)
        } hours.\n\n` +

        `Charging stops and charging time are shown separately from the base driving time.`;


    renderStations(
        result.stations || [],
        result.recommended_station
    );


    renderMap(
        result
    );


    $("results")
        .scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

}


// =====================================================
// FORMAT NUMBER
// =====================================================

function formatNumber(
    value
) {

    const number =
        Number(value);


    if (
        !Number.isFinite(number)
    ) {
        return "0";
    }


    return number.toFixed(
        number % 1 === 0
            ? 0
            : 1
    );

}


// =====================================================
// FORMAT CURRENCY
// =====================================================

function formatCurrency(
    value
) {

    const number =
        Number(value);


    if (
        !Number.isFinite(number)
    ) {

        return "₹0";

    }


    return (
        "₹"
        +
        number.toLocaleString(
            "en-IN",
            {
                maximumFractionDigits: 0
            }
        )
    );

}


// =====================================================
// FORMAT TIME
// =====================================================

function formatChargingTime(
    value
) {

    if (
        typeof value === "string"
        &&
        value.trim()
    ) {

        return value;

    }


    const minutes =
        Number(value);


    if (
        !Number.isFinite(minutes)
        ||
        minutes <= 0
    ) {

        return "0 min";

    }


    return formatDuration(
        minutes
    );

}


function formatDuration(
    minutes
) {

    minutes =
        Math.round(
            Number(minutes)
        );


    if (
        !Number.isFinite(minutes)
        ||
        minutes <= 0
    ) {

        return "0 min";

    }


    const hours =
        Math.floor(
            minutes / 60
        );


    const mins =
        minutes % 60;


    if (
        hours === 0
    ) {

        return `${mins} min`;

    }


    if (
        mins === 0
    ) {

        return `${hours} hr`;

    }


    return `${hours} hr ${mins} min`;

}


// =====================================================
// STATIONS
// =====================================================

function renderStations(
    stations,
    recommendedName
) {

    const container =
        $("stations");


    container.innerHTML =
        "";


    $("stationCount")
        .textContent =
        `${stations.length} station${stations.length === 1 ? "" : "s"}`;


    if (
        !stations.length
    ) {

        container.innerHTML = `

            <div class="station-card">

                <div class="station-name">
                    No charging stations found
                </div>

                <div class="station-address">
                    OpenChargeMap did not return stations
                    for this route.
                </div>

            </div>

        `;

        return;

    }


    stations
        .slice(0, 12)
        .forEach(
            (station, index) => {

                const card =
                    createStationCard(
                        station,
                        recommendedName,
                        index
                    );


                container.appendChild(
                    card
                );

            }
        );

}


// =====================================================
// STATION CARD
// =====================================================

function createStationCard(
    station,
    recommendedName,
    index
) {

    const card =
        document.createElement(
            "div"
        );


    const stationName =
        station.name ||
        "Charging Station";


    const isRecommended =
        recommendedName
        &&
        stationName
            .toLowerCase()
            .includes(
                String(
                    recommendedName
                )
                    .toLowerCase()
                    .slice(0, 20)
            );


    card.className =
        "station-card"
        +
        (
            isRecommended
                ? " recommended"
                : ""
        );


    const status =
        station.status ||
        "Live status unavailable";


    const statusLower =
        status.toLowerCase();


    const statusClass =
        statusLower.includes(
            "available"
        )
            ? "available"
            : (
                statusLower.includes(
                    "unavailable"
                )
                    ? "unavailable"
                    : ""
            );


    const power =
        Number(
            station.max_power_kw || 0
        );


    const detour =
        station.detour_km;


    const connectors =
        station.connectors || [];


    const connectorNames =
        connectors
            .map(
                c =>
                    c.type
                    || "Unknown"
            )
            .filter(Boolean)
            .slice(0, 3)
            .join(", ");


    const restaurants =
        station.restaurants || [];


    let restaurantHTML =
        "";


    if (
        restaurants.length
    ) {

        restaurantHTML = `

            <div class="restaurant-list">

                <div class="restaurant-title">
                    Nearby food
                </div>

                ${restaurants
                .slice(0, 3)
                .map(
                    r => `
                            <div class="restaurant-item">
                                • ${escapeHTML(
                        r.name ||
                        "Restaurant"
                    )
                        }
                            </div>
                        `
                )
                .join("")}

            </div>

        `;

    }


    card.innerHTML = `

        <div class="station-top">

            <div>

                <div class="station-name">
                    ${escapeHTML(stationName)}
                </div>

                <div class="station-address">

                    ${escapeHTML(
        station.address ||
        station.town ||
        "Address unavailable"
    )}

                </div>

            </div>


            <div
                class="station-status ${statusClass}"
            >
                ${escapeHTML(status)}
            </div>

        </div>


        <div class="station-metrics">

            <div class="metric">

                <span>
                    POWER
                </span>

                <strong>
                    ${power > 0
            ? power + " kW"
            : "—"
        }
                </strong>

            </div>


            <div class="metric">

                <span>
                    DETOUR
                </span>

                <strong>
                    ${detour !== null &&
            detour !== undefined
            ? Number(detour).toFixed(1) + " km"
            : "—"
        }
                </strong>

            </div>


            <div class="metric">

                <span>
                    CONNECTOR
                </span>

                <strong>
                    ${escapeHTML(
            connectorNames ||
            "Any"
        )
        }
                </strong>

            </div>

        </div>


        ${isRecommended
            ? `
                    <div class="station-tag">
                        ✦ AI RECOMMENDED
                    </div>
                `
            : ""
        }


        ${restaurantHTML}

    `;


    return card;

}


// =====================================================
// MAP
// =====================================================

function renderMap(
    result
) {

    const geometry =
        result.route_geometry || [];


    if (
        !geometry.length
    ) {

        return;

    }


    if (
        map
    ) {

        map.remove();

        map = null;

    }


    map =
        L.map(
            "map",
            {
                zoomControl: true
            }
        );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                '&copy; OpenStreetMap contributors'
        }
    )
        .addTo(map);


    const routeLatLngs =
        geometry.map(
            point => [
                Number(point[0]),
                Number(point[1])
            ]
        );


    routeLayer =
        L.polyline(
            routeLatLngs,
            {
                color: "#28d866",

                weight: 5,

                opacity: 0.9
            }
        )
            .addTo(map);


    map.fitBounds(
        routeLayer.getBounds(),
        {
            padding: [
                35,
                35
            ]
        }
    );


    // -------------------------------------------------
    // START
    // -------------------------------------------------

    const first =
        routeLatLngs[0];


    L.marker(
        first
    )
        .addTo(map)
        .bindPopup(
            "<strong>Start</strong>"
        );


    // -------------------------------------------------
    // DESTINATION
    // -------------------------------------------------

    const last =
        routeLatLngs[
        routeLatLngs.length - 1
        ];


    L.marker(
        last
    )
        .addTo(map)
        .bindPopup(
            "<strong>Destination</strong>"
        );


    // -------------------------------------------------
    // STATIONS
    // -------------------------------------------------

    const stations =
        result.stations || [];


    const recommended =
        String(
            result.recommended_station ||
            ""
        ).toLowerCase();


    stationMarkers = [];


    stations
        .slice(0, 20)
        .forEach(
            station => {

                if (
                    station.latitude === undefined
                    ||
                    station.longitude === undefined
                ) {

                    return;

                }


                const stationName =
                    station.name ||
                    "Charging Station";


                const isRecommended =
                    recommended
                    &&
                    stationName
                        .toLowerCase()
                        .includes(
                            recommended.slice(
                                0,
                                20
                            )
                        );


                const marker =
                    L.circleMarker(
                        [
                            Number(
                                station.latitude
                            ),
                            Number(
                                station.longitude
                            )
                        ],
                        {

                            radius:
                                isRecommended
                                    ? 9
                                    : 7,

                            color:
                                isRecommended
                                    ? "#ffffff"
                                    : "#39e66f",

                            weight:
                                2,

                            fillColor:
                                isRecommended
                                    ? "#39e66f"
                                    : "#148a42",

                            fillOpacity:
                                0.95

                        }
                    )
                        .addTo(map);


                const popup = `

                    <div>

                        <strong>
                            ${escapeHTML(
                    stationName
                )}
                        </strong>

                        <br>

                        <span>
                            ${station.max_power_kw
                        ? station.max_power_kw + " kW"
                        : "Power unavailable"
                    }
                        </span>

                        <br>

                        <span>
                            ${escapeHTML(
                        station.status ||
                        "Live status unavailable"
                    )
                    }
                        </span>

                    </div>

                `;


                marker.bindPopup(
                    popup
                );


                stationMarkers.push(
                    marker
                );

            }
        );

}


// =====================================================
// PDF
// =====================================================

function setupPdfButton() {

    $("pdfButton")
        .addEventListener(
            "click",
            generatePDF
        );

}


async function generatePDF() {

    if (
        !latestPlan
    ) {

        alert(
            "Please plan a journey first."
        );

        return;

    }


    const button =
        $("pdfButton");


    button.disabled =
        true;


    button.textContent =
        "Generating PDF...";


    try {

        const response =
            await fetch(
                "/generate-pdf",
                {

                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            latestPlan
                        )

                }
            );


        const result =
            await response.json();


        if (
            !response.ok
        ) {

            throw new Error(
                result.error ||
                "PDF generation failed."
            );

        }


        latestPdfFilename =
            result.filename;


        window.open(
            `/download-pdf/${encodeURIComponent(result.filename)}`,
            "_blank"
        );


        $("pdfMessage")
            .textContent =
            "PDF generated successfully.";


    } catch (error) {

        alert(
            "PDF Error:\n\n"
            + error.message
        );

    } finally {

        button.disabled =
            false;

        button.textContent =
            "↓ Download PDF";

    }

}


// =====================================================
// EMAIL
// =====================================================

function setupEmailButton() {

    $("emailButton")
        .addEventListener(
            "click",
            sendEmail
        );

}


async function sendEmail() {

    const email =
        $("email").value.trim();


    if (
        !email
    ) {

        alert(
            "Please enter an email address."
        );

        return;

    }


    if (
        !latestPlan
    ) {

        alert(
            "Please plan a journey first."
        );

        return;

    }


    const button =
        $("emailButton");


    button.disabled =
        true;


    button.textContent =
        "Preparing PDF...";


    try {

        // Generate PDF if it does not
        // already exist.

        if (
            !latestPdfFilename
        ) {

            const pdfResponse =
                await fetch(
                    "/generate-pdf",
                    {

                        method:
                            "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify(
                                latestPlan
                            )

                    }
                );


            const pdfResult =
                await pdfResponse.json();


            if (
                !pdfResponse.ok
            ) {

                throw new Error(
                    pdfResult.error ||
                    "Could not generate PDF."
                );

            }


            latestPdfFilename =
                pdfResult.filename;

        }


        button.textContent =
            "Sending...";


        const response =
            await fetch(
                "/send-email",
                {

                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({

                            email:
                                email,

                            pdf_filename:
                                latestPdfFilename

                        })

                }
            );


        const result =
            await response.json();


        if (
            !response.ok
        ) {

            throw new Error(
                result.error ||
                "Email sending failed."
            );

        }


        $("pdfMessage")
            .textContent =
            "✓ Journey plan sent successfully.";


    } catch (error) {

        $("pdfMessage")
            .textContent =
            error.message;

        alert(
            "Email Error:\n\n"
            + error.message
        );

    } finally {

        button.disabled =
            false;

        button.textContent =
            "Send PDF";

    }

}


// =====================================================
// HTML ESCAPE
// =====================================================

function escapeHTML(
    value
) {

    return String(
        value ?? ""
    )
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}