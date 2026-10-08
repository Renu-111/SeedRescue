let map = null;
let mapLayers = [];
let baseGraph = null;

let incidentLocation = null;
let locationSelected = false;
let updatingLocationInputs = false;
let hazardCircle = null;
let hazardMarker = null;

async function checkBackend() {
    const status = document.getElementById("backendStatus");

    try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error("Backend unavailable");
        }

        await response.json();

        status.textContent = "● Backend Online";
        status.className = "status online";

    } catch (error) {
        status.textContent = "● Backend Offline";
        status.className = "status offline";
    }
}

function setIncidentLocation(
    latitude,
    longitude,
    source = "manual"
) {
    const lat = Number(latitude);
    const lng = Number(longitude);

    if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lng)
    ) {
        return false;
    }

    if (
        lat < -90 ||
        lat > 90 ||
        lng < -180 ||
        lng > 180
    ) {
        return false;
    }

    incidentLocation = {
        latitude: lat,
        longitude: lng,
        source: source
    };

    locationSelected = true;

    updatingLocationInputs = true;

    const latInput =
        document.getElementById("latitude");

    const lngInput =
        document.getElementById("longitude");

    if (latInput) {
        latInput.value = lat.toFixed(6);
    }

    if (lngInput) {
        lngInput.value = lng.toFixed(6);
    }

    updatingLocationInputs = false;

    updateLocationVisual();

    return true;
}

function clearIncidentLocation() {
    incidentLocation = null;
    locationSelected = false;

    updatingLocationInputs = true;

    const latInput =
        document.getElementById("latitude");

    const lngInput =
        document.getElementById("longitude");

    if (latInput) {
        latInput.value = "";
    }

    if (lngInput) {
        lngInput.value = "";
    }

    updatingLocationInputs = false;

    if (hazardCircle && map) {
        map.removeLayer(hazardCircle);
        hazardCircle = null;
    }

    if (hazardMarker && map) {
        map.removeLayer(hazardMarker);
        hazardMarker = null;
    }
}

function updateLocationVisual() {
    if (!map || !incidentLocation) {
        return;
    }

    if (hazardCircle) {
        map.removeLayer(hazardCircle);
    }

    if (hazardMarker) {
        map.removeLayer(hazardMarker);
    }

    const point = [
        incidentLocation.latitude,
        incidentLocation.longitude
    ];

    hazardCircle = L.circle(
        point,
        {
            radius: 2200,
            color: "#dc2626",
            fillColor: "#dc2626",
            fillOpacity: 0.18,
            weight: 2
        }
    ).addTo(map);

    hazardMarker = L.marker(point)
        .addTo(map)
        .bindPopup(
            "<strong>Selected incident location</strong><br>" +
            incidentLocation.latitude.toFixed(6) +
            ", " +
            incidentLocation.longitude.toFixed(6)
        );

    map.setView(point, 14);
}

function wireLocationInputs() {
    const latInput =
        document.getElementById("latitude");

    const lngInput =
        document.getElementById("longitude");

    function handleManualLocationInput() {
        if (updatingLocationInputs) {
            return;
        }

        const lat = Number(latInput?.value);
        const lng = Number(lngInput?.value);

        if (
            Number.isFinite(lat) &&
            Number.isFinite(lng) &&
            latInput?.value !== "" &&
            lngInput?.value !== ""
        ) {
            setIncidentLocation(
                lat,
                lng,
                "manual_input"
            );
        }
    }

    if (latInput) {
        latInput.addEventListener(
            "input",
            handleManualLocationInput
        );
    }

    if (lngInput) {
        lngInput.addEventListener(
            "input",
            handleManualLocationInput
        );
    }
}

function getScenarioData(prefix = "") {
    const data = {
        disaster:
            document.getElementById(
                prefix + "disaster"
            ).value,

        population:
            Number(
                document.getElementById(
                    prefix + "population"
                ).value
            ),

        damage:
            Number(
                document.getElementById(
                    prefix + "damage"
                ).value
            ),

        water:
            Number(
                document.getElementById(
                    prefix + "water"
                ).value
            ),

        food:
            Number(
                document.getElementById(
                    prefix + "food"
                ).value
            ),

        medical:
            Number(
                document.getElementById(
                    prefix + "medical"
                ).value
            ),

        shelter_capacity:
            Number(
                document.getElementById(
                    prefix + "shelter"
                )?.value ||
                document.getElementById(
                    prefix + "shelter_capacity"
                )?.value
            )
    };

    /*
     * Do NOT send the latitude/longitude fields merely because
     * the HTML contains default values.
     *
     * They are sent only after the user selects a real location.
     */
    if (
        locationSelected &&
        incidentLocation
    ) {
        data.latitude =
            incidentLocation.latitude;

        data.longitude =
            incidentLocation.longitude;

        data.hazard_radius_km = 2.2;
        data.facility_display_radius_km = 3.0;
        data.facility_display_limit = 20;
        data.shelter_candidates = 6;
    }

    return data;
}

async function generatePlan() {
    const loading =
        document.getElementById("loading");

    const dashboard =
        document.getElementById("dashboard");

    const errorBox =
        document.getElementById("errorBox");

    errorBox.classList.add("hidden");
    dashboard.classList.add("hidden");
    loading.classList.remove("hidden");

    try {
        const seed =
            getScenarioData();

        const response = await fetch(
            "/api/plan",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body:
                    JSON.stringify(seed)
            }
        );

        const data =
            await response.json();
        displayZonePriorities(data.zone_priorities);

        function displayZonePriorities(priorities) {

    const container =
        document.getElementById("zonePriorityList");

    if (!container) {
        return;
    }

    if (!priorities || priorities.length === 0) {
        container.innerHTML =
            "<p>No zone priority data available.</p>";
        return;
    }

    container.innerHTML = "";

    priorities.forEach(zone => {

        const card = document.createElement("div");

        card.className =
            "zone-priority-card " +
            zone.priority_level.toLowerCase();

        card.innerHTML = `
            <div class="priority-rank">
                #${zone.rank}
            </div>

            <div class="priority-info">

                <h3>${zone.zone_name}</h3>

                <span class="priority-level">
                    ${zone.priority_level}
                </span>

                <p>
                    Priority Score:
                    <strong>
                        ${zone.priority_score}
                    </strong>/100
                </p>

                <p>
                    Need:
                    <strong>${zone.need}</strong>
                </p>

                <p>
                    Unsheltered:
                    <strong>${zone.unsheltered}</strong>
                </p>

            </div>

            <button
                class="why-zone-btn"
                onclick='showWhyZone(${JSON.stringify(zone)})'>
                Why this zone?
            </button>
        `;

        container.appendChild(card);
    });
}

function showWhyZone(zone) {

    let message =
        `WHY ${zone.zone_name}?\n\n`;

    if (zone.reasons && zone.reasons.length > 0) {

        zone.reasons.forEach((reason, index) => {

            message +=
                `${index + 1}. ${reason}\n`;

        });

    } else {

        message +=
            "No major priority factors identified.";

    }

    message +=
        `\nPriority Score: ${zone.priority_score}/100`;

    alert(message);
}

        if (
            !response.ok ||
            data.error
        ) {
            throw new Error(
                data.error ||
                "Unable to generate plan"
            );
        }

        window.currentPlan = data;

        displayPlan(data);

        dashboard.classList.remove(
            "hidden"
        );

        await new Promise(
            resolve =>
                setTimeout(
                    resolve,
                    100
                )
        );

        await loadGraph(data);

    } catch (error) {
        errorBox.textContent =
            "Error: " +
            error.message;

        errorBox.classList.remove(
            "hidden"
        );

    } finally {
        loading.classList.add(
            "hidden"
        );
    }
}

async function loadGraph(plan) {
    try {
        const response =
            await fetch("/api/graph");

        if (!response.ok) {
            throw new Error(
                "Unable to load disaster network"
            );
        }

        const graph =
            await response.json();

        baseGraph = graph;

        drawMap(
            graph,
            plan
        );

    } catch (error) {
        console.error(
            "Map loading error:",
            error
        );
    }
}

async function initializeMap() {
    try {
        const response =
            await fetch("/api/graph");

        if (!response.ok) {
            throw new Error(
                "Unable to load disaster network"
            );
        }

        baseGraph =
            await response.json();

        drawMap(
            baseGraph,
            null
        );

    } catch (error) {
        console.error(
            "Initial map loading error:",
            error
        );
    }
}

function drawMap(
    graph,
    plan = null
) {
    if (
        typeof L === "undefined"
    ) {
        return;
    }

    const nodes =
        graph.nodes || {};

    const edges =
        graph.edges || [];

    const roadNodes =
        Object.values(nodes).filter(
            node =>
                node &&
                (
                    node.type === "road" ||
                    !node.type
                )
        );

    const latValues =
        roadNodes
            .map(
                node =>
                    Number(node.lat)
            )
            .filter(
                Number.isFinite
            );

    const lngValues =
        roadNodes
            .map(
                node =>
                    Number(node.lng)
            )
            .filter(
                Number.isFinite
            );

    if (
        !latValues.length ||
        !lngValues.length
    ) {
        return;
    }

    const planLat =
        plan?.location?.latitude;

    const planLng =
        plan?.location?.longitude;

    const currentLat =
        Number.isFinite(
            Number(planLat)
        )
            ? Number(planLat)
            : incidentLocation?.latitude;

    const currentLng =
        Number.isFinite(
            Number(planLng)
        )
            ? Number(planLng)
            : incidentLocation?.longitude;

    const center =
        (
            Number.isFinite(currentLat) &&
            Number.isFinite(currentLng)
        )
            ? [
                currentLat,
                currentLng
              ]
            : [
                average(latValues),
                average(lngValues)
              ];

    if (!map) {
        map = L.map(
            "map",
            {
                center: center,
                zoom: 13,
                zoomControl: true
            }
        );

        L.tileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                maxZoom: 19,
                attribution:
                    "&copy; OpenStreetMap contributors"
            }
        ).addTo(map);

        /*
         * Clicking the map now establishes the incident location.
         */
        map.on(
            "click",
            async event => {
                setIncidentLocation(
                    event.latlng.lat,
                    event.latlng.lng,
                    "map_click"
                );

                await generatePlan();
            }
        );

    } else {
        map.setView(
            center,
            locationSelected
                ? 14
                : 13
        );

        mapLayers.forEach(
            layer =>
                map.removeLayer(layer)
        );

        mapLayers = [];
    }

    setTimeout(
        () => {
            if (!map) {
                return;
            }

            map.invalidateSize();

            if (
                locationSelected &&
                incidentLocation
            ) {
                map.setView(
                    [
                        incidentLocation.latitude,
                        incidentLocation.longitude
                    ],
                    14
                );
            }
        },
        200
    );

    const detection =
        plan?.road_detection || {};

    const roadDetails =
        detection.road_details || [];

    const roadStatus = {};

    roadDetails.forEach(
        road => {
            roadStatus[road.id] =
                road.status;
        }
    );

    // Draw real road network.
    edges.forEach(
        edge => {
            const a = nodes[edge.a];
            const b = nodes[edge.b];

            if (!a || !b) {
                return;
            }

            const status =
                roadStatus[edge.id] ||
                "safe";

            const line =
                L.polyline(
                    [
                        [a.lat, a.lng],
                        [b.lat, b.lng]
                    ],
                    {
                        color:
                            getRoadColor(status),

                        weight:
                            status === "blocked"
                                ? 7
                                : 4,

                        opacity: 0.85
                    }
                ).addTo(map);

            line.bindPopup(
                `
                <strong>${escapeHtml(edge.id)}</strong><br>
                ${escapeHtml(a.name)}
                →
                ${escapeHtml(b.name)}<br>
                Status:
                <strong>${formatStatus(status)}</strong>
                `
            );

            mapLayers.push(line);
        }
    );

    // Draw evacuation routes.
    (
        plan?.assignments || []
    ).forEach(
        assignment => {
            if (
                !assignment.path ||
                !assignment.path.length
            ) {
                return;
            }

            const coordinates =
                assignment.path
                    .map(id => nodes[id])
                    .filter(Boolean)
                    .map(
                        node => [
                            node.lat,
                            node.lng
                        ]
                    );

            if (
                coordinates.length < 2
            ) {
                return;
            }

            const route =
                L.polyline(
                    coordinates,
                    {
                        color: "#16a34a",
                        weight: 6,
                        opacity: 0.9
                    }
                ).addTo(map);

            route.bindPopup(
                `
                <strong>Evacuation route</strong><br>
                ${escapeHtml(
                    assignment.shelter_name ||
                    assignment.shelter ||
                    "Shelter"
                )}<br>
                People:
                ${Number(
                    assignment.people || 0
                ).toLocaleString()}
                `
            );

            mapLayers.push(route);
        }
    );

    // Draw supply routes.
    (
        plan?.supply_routes || []
    ).forEach(
        routeRecord => {
            if (
                !routeRecord.path ||
                !routeRecord.path.length
            ) {
                return;
            }

            const coordinates =
                routeRecord.path
                    .map(id => nodes[id])
                    .filter(Boolean)
                    .map(
                        node => [
                            node.lat,
                            node.lng
                        ]
                    );

            if (
                coordinates.length < 2
            ) {
                return;
            }

            const route =
                L.polyline(
                    coordinates,
                    {
                        color: "#2563eb",
                        weight: 4,
                        dashArray: "6 8",
                        opacity: 0.85
                    }
                ).addTo(map);

            route.bindPopup(
                `
                <strong>Supply route</strong><br>
                ${escapeHtml(
                    routeRecord.zone_name ||
                    routeRecord.zone ||
                    ""
                )}<br>
                Distance:
                ${Number(
                    routeRecord.km || 0
                ).toFixed(2)}
                km
                `
            );

            mapLayers.push(route);
        }
    );

    // Draw only the affected real population cells.
    (
        plan?.zones || []
    ).forEach(
        zone => {
            const color =
                zone.hazard_zone === "RED"
                    ? "#dc2626"
                    : zone.hazard_zone === "ORANGE"
                        ? "#f97316"
                        : "#eab308";

            const marker =
                L.circleMarker(
                    [
                        zone.latitude,
                        zone.longitude
                    ],
                    {
                        radius: 8,
                        fillColor: color,
                        color: "#ffffff",
                        weight: 2,
                        fillOpacity: 0.85
                    }
                ).addTo(map);

            marker.bindPopup(
                `
                <strong>
                    ${escapeHtml(zone.name)}
                </strong><br>

                Population:
                ${Number(
                    zone.population || 0
                ).toLocaleString()}<br>

                Need:
                ${Number(
                    zone.need || 0
                ).toLocaleString()}<br>

                Hazard zone:
                ${escapeHtml(
                    zone.hazard_zone || "—"
                )}<br>

                Sheltered:
                ${Number(
                    zone.sheltered || 0
                ).toLocaleString()}<br>

                Unsheltered:
                ${Number(
                    zone.unsheltered || 0
                ).toLocaleString()}
                `
            );

            mapLayers.push(marker);
        }
    );

    /*
     * THIS IS THE IMPORTANT FIX.
     *
     * Do not draw every shelter/hospital from /api/graph.
     * Only draw the facilities returned for the selected
     * incident location.
     */
    if (
        plan?.geographic_plan_ready &&
        Array.isArray(
            plan.relevant_facilities
        )
    ) {
        plan.relevant_facilities.forEach(
            facility => {

                const type =
                    facility.type ||
                    facility.facility_type ||
                    "facility";

                const icon =
                    type === "hospital"
                        ? "🏥"
                        : type ===
                          "temporary_shelter"
                            ? "🏫"
                            : "🏠";

                const marker =
                    L.marker(
                        [
                            facility.lat,
                            facility.lng
                        ],
                        {
                            icon:
                                L.divIcon(
                                    {
                                        html:
                                            `<div style="font-size:24px">${icon}</div>`,

                                        className:
                                            "",

                                        iconSize:
                                            [28, 28]
                                    }
                                )
                        }
                    ).addTo(map);

                let popup = `
                    <strong>
                        ${escapeHtml(
                            facility.name ||
                            "Unnamed facility"
                        )}
                    </strong><br>
                `;

                if (
                    type === "hospital"
                ) {
                    popup += `
                        Type: Hospital<br>
                        Distance from incident:
                        ${Number(
                            facility.distance_from_hazard_km || 0
                        ).toFixed(2)}
                        km
                    `;

                } else {
                    popup += `
                        Type:
                        ${escapeHtml(
                            facility.facility_type ||
                            type
                        )}<br>

                        Status:
                        ${escapeHtml(
                            facility.shelter_status ||
                            "—"
                        )}<br>

                        Capacity:
                        ${Number(
                            facility.capacity || 0
                        ).toLocaleString()}
                        (
                        ${escapeHtml(
                            facility.capacity_source ||
                            "unknown"
                        )}
                        )<br>

                        Distance from incident:
                        ${Number(
                            facility.distance_from_hazard_km || 0
                        ).toFixed(2)}
                        km<br>

                        Source:
                        ${escapeHtml(
                            facility.source_dataset ||
                            "dataset"
                        )}
                    `;
                }

                marker.bindPopup(
                    popup
                );

                mapLayers.push(marker);
            }
        );
    }

    if (
        plan?.location?.latitude != null &&
        plan?.location?.longitude != null
    ) {
        incidentLocation = {
            latitude:
                Number(
                    plan.location.latitude
                ),

            longitude:
                Number(
                    plan.location.longitude
                ),

            source:
                "plan_response"
        };

        locationSelected = true;
    }

    if (
        incidentLocation &&
        locationSelected
    ) {
        updateLocationVisual();
    }
}

function resetForm() {
    document.getElementById(
        "disaster"
    ).value = "flood";

    document.getElementById(
        "population"
    ).value = 10000;

    document.getElementById(
        "damage"
    ).value = 40;

    document.getElementById(
        "water"
    ).value = 100000;

    document.getElementById(
        "food"
    ).value = 10000;

    document.getElementById(
        "medical"
    ).value = 1000;

    document.getElementById(
        "shelter_capacity"
    ).value = 5000;

    clearIncidentLocation();

    document.getElementById(
        "dashboard"
    )?.classList.add("hidden");

    window.currentPlan = null;

    if (baseGraph) {
        drawMap(
            baseGraph,
            null
        );
    }
}

/*
 * The rest of your original display, road detection,
 * zones, priorities, explanation, scenario comparison,
 * formatting and helper functions are preserved in the
 * complete file linked above.
 */

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        checkBackend();

        setInterval(
            checkBackend,
            10000
        );

        wireLocationInputs();

        // Load the real road network.
        // Do NOT generate a geographic plan yet.
        await initializeMap();
    }
);   