// =====================================================
// CHARGEPILOT - FRONTEND APPLICATION
// =====================================================


// =====================================================
// BACKEND CONFIGURATION
// =====================================================

// Local Flask backend

const API_BASE_URL = "https://charge-pilot.onrender.com";


// =====================================================
// APPLICATION STATE
// =====================================================

let latestPlan = null;

let latestPdfFilename = null;

let map = null;

let routeLayer = null;

let stationMarkers = [];


// =====================================================
// DOM HELPER
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
// SWAP LOCATIONS
// =====================================================

function setupSwap() {

    const swapButton = $("swapButton");

    if (!swapButton) {
        return;
    }


    swapButton.addEventListener(
        "click",
        () => {

            const from =
                $("from");

            const to =
                $("to");


            if (!from || !to) {
                return;
            }


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


    if (!checkbox || !radius) {
        return;
    }


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

    const button =
        $("planButton");

    if (!button) {
        return;
    }


    button.addEventListener(
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


        $("ev_range").focus();


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


        $("battery_percent").focus();


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

        top:
            loading.offsetTop - 100,

        behavior:
            "smooth"

    });


    startLoadingAnimation();


    try {

        const payload =
            buildPayload();


        console.log(
            "Sending journey request to:",
            `${API_BASE_URL}/plan`
        );


        console.log(
            "Journey payload:",
            payload
        );


        const response =
            await fetch(
                `${API_BASE_URL}/plan`,
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

        } catch (jsonError) {

            throw new Error(
                `Backend returned an invalid response. HTTP status: ${response.status}`
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
            "ChargePilot error:",
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

let loadingInterval = null;


function startLoadingAnimation() {

    const loadingText =
        $("loadingText");


    if (!loadingText) {
        return;
    }


    const messages = [

        "Collecting route and charging station data...",

        "Analyzing available charging stations...",

        "Groq AI is evaluating your preferences...",

        "Building the final EV journey recommendation..."

    ];


    let index = 0;


    loadingText.textContent =
        messages[index];


    clearInterval(
        loadingInterval
    );


    loadingInterval =
        setInterval(
            () => {

                index =
                    (
                        index + 1
                    )
                    %
                    messages.length;


                loadingText.textContent =
                    messages[index];

            },
            2500
        );

}


// =====================================================
// FINISH LOADING
// =====================================================

function finishLoading() {

    clearInterval(
        loadingInterval
    );


    const loading =
        $("loading");


    if (loading) {

        loading.classList.add(
            "hidden"
        );

    }

}


// =====================================================
// RENDER RESULTS
// =====================================================

function renderResults(result) {

    const results =
        $("results");


    if (!results) {
        return;
    }


    results.classList.remove(
        "hidden"
    );


    /*
        Keep your existing result-rendering logic
        below this point if your current app.js contains
        additional render functions.
    */

    if (
        typeof renderJourneySummary === "function"
    ) {

        renderJourneySummary(
            result
        );

    }


    if (
        typeof renderJourneyTimeline === "function"
    ) {

        renderJourneyTimeline(
            result
        );

    }


    if (
        typeof renderStations === "function"
    ) {

        renderStations(
            result
        );

    }


    if (
        typeof renderMap === "function"
    ) {

        renderMap(
            result
        );

    }

}


// =====================================================
// PDF
// =====================================================

function setupPdfButton() {

    const button =
        $("pdfButton");


    if (!button) {
        return;
    }


    button.addEventListener(
        "click",
        generatePDF
    );

}


// =====================================================
// GENERATE PDF
// =====================================================

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

        console.log(
            "Generating PDF using:",
            `${API_BASE_URL}/generate-pdf`
        );


        const response =
            await fetch(
                `${API_BASE_URL}/generate-pdf`,
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


        let result;


        try {

            result =
                await response.json();

        } catch {

            throw new Error(
                `Backend returned an invalid PDF response. HTTP status: ${response.status}`
            );

        }


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

            `${API_BASE_URL}/download-pdf/${encodeURIComponent(
                result.filename
            )}`,

            "_blank"

        );


        const pdfMessage =
            $("pdfMessage");


        if (pdfMessage) {

            pdfMessage.textContent =
                "PDF generated successfully.";

        }


    } catch (error) {

        console.error(
            "PDF Error:",
            error
        );


        alert(
            "PDF Error:\n\n"
            +
            error.message
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

    const button =
        $("emailButton");


    if (!button) {
        return;
    }


    button.addEventListener(
        "click",
        sendEmail
    );

}


// =====================================================
// SEND EMAIL
// =====================================================

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

        // -------------------------------------------------
        // GENERATE PDF IF REQUIRED
        // -------------------------------------------------

        if (
            !latestPdfFilename
        ) {

            const pdfResponse =
                await fetch(
                    `${API_BASE_URL}/generate-pdf`,
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


            let pdfResult;


            try {

                pdfResult =
                    await pdfResponse.json();

            } catch {

                throw new Error(
                    `Backend returned an invalid PDF response. HTTP status: ${pdfResponse.status}`
                );

            }


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


        // -------------------------------------------------
        // SEND EMAIL
        // -------------------------------------------------

        button.textContent =
            "Sending...";


        const response =
            await fetch(
                `${API_BASE_URL}/send-email`,
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


        let result;


        try {

            result =
                await response.json();

        } catch {

            throw new Error(
                `Backend returned an invalid email response. HTTP status: ${response.status}`
            );

        }


        if (
            !response.ok
        ) {

            throw new Error(
                result.error ||
                "Email sending failed."
            );

        }


        const pdfMessage =
            $("pdfMessage");


        if (pdfMessage) {

            pdfMessage.textContent =
                "✓ Journey plan sent successfully.";

        }


    } catch (error) {

        console.error(
            "Email Error:",
            error
        );


        const pdfMessage =
            $("pdfMessage");


        if (pdfMessage) {

            pdfMessage.textContent =
                error.message;

        }


        alert(
            "Email Error:\n\n"
            +
            error.message
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