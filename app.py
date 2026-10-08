from flask import Flask, jsonify, request, send_from_directory

import requests

from engine import (
    generate_plan,
    graph_info,
    find_critical_bottlenecks,
    detect_road_status_from_location,
    apply_automatic_road_detection as engine_apply_automatic_road_detection,
    NODES,
    EDGES,
)



from ml import model as ml



from backend.propagation.propagation_engine import propagate

from backend.explain import explain_plan









# ============================================================

# FLASK APP

# ============================================================



app = Flask(

    __name__,

    static_folder="frontend",

    static_url_path=""

)





# ============================================================

# VALIDATION

# ============================================================



def validate_seed(seed):

    """

    Validate and normalize the disaster seed.

    """



    if not isinstance(seed, dict):

        raise ValueError(

            "Request body must be a JSON object."

        )



    required = [

        "disaster",

        "population",

        "damage",

        "water",

        "food",

        "medical",

        "shelter_capacity"

    ]



    missing = [

        key

        for key in required

        if key not in seed

    ]



    if missing:

        raise ValueError(

            "Missing fields: " + ", ".join(missing)

        )



    seed = dict(seed)



    # --------------------------------------------------------

    # Blocked roads

    # --------------------------------------------------------



    seed["blocked"] = list(

        seed.get("blocked", [])

    )



    # --------------------------------------------------------

    # Latitude validation

    # --------------------------------------------------------



    if seed.get("latitude") is not None:



        try:

            seed["latitude"] = float(

                seed["latitude"]

            )

        except (TypeError, ValueError):

            raise ValueError(

                "Latitude must be a valid number."

            )



        if not -90 <= seed["latitude"] <= 90:

            raise ValueError(

                "Latitude must be between -90 and 90."

            )



    # --------------------------------------------------------

    # Longitude validation

    # --------------------------------------------------------



    if seed.get("longitude") is not None:



        try:

            seed["longitude"] = float(

                seed["longitude"]

            )

        except (TypeError, ValueError):

            raise ValueError(

                "Longitude must be a valid number."

            )



        if not -180 <= seed["longitude"] <= 180:

            raise ValueError(

                "Longitude must be between -180 and 180."

            )



    return seed





# ============================================================

# AUTOMATIC ROAD DETECTION

# ============================================================



def apply_automatic_road_detection(seed):
    """Use the real Bengaluru road dataset for automatic road status."""
    return engine_apply_automatic_road_detection(seed)


# FULL PLAN

# ============================================================



def full_plan(seed):

    """

    Complete SeedRescue pipeline:



        Disaster Seed

             ↓

        Validation

             ↓

        Automatic Road Detection

             ↓

        ML Prediction

             ↓

        Adaptive Recovery Engine

             ↓

        Explanation Engine

             ↓

        Final Recovery Plan

    """



    # --------------------------------------------------------

    # Validate

    # --------------------------------------------------------



    seed = validate_seed(seed)



    # --------------------------------------------------------

    # Automatic road detection

    # --------------------------------------------------------



    seed = apply_automatic_road_detection(

        seed

    )



    # --------------------------------------------------------

    # ML prediction

    # --------------------------------------------------------



    prediction = ml.predict(

        seed

    )



    # --------------------------------------------------------

    # Generate adaptive recovery plan

    # --------------------------------------------------------



    plan = generate_plan(

        seed,

        prediction

    )



    # --------------------------------------------------------

    # Attach ML information

    # --------------------------------------------------------



    plan["ml"] = prediction



    # --------------------------------------------------------

    # Generate explanation

    # --------------------------------------------------------



    plan["explanation"] = explain_plan(

        seed,

        plan

    )



    # --------------------------------------------------------

    # Automatic road information

    # --------------------------------------------------------



    plan["road_detection"] = seed.get(

        "road_detection",

        {}

    )



    plan["location"] = {

        "latitude": seed.get("latitude"),

        "longitude": seed.get("longitude")

    }



    plan["blocked_roads"] = sorted(

        seed.get("blocked", [])

    )



    plan["orange_roads"] = sorted(

        seed.get("orange_roads", [])

    )



    plan["yellow_roads"] = sorted(

        seed.get("yellow_roads", [])

    )



    return plan





# ============================================================

# HOME PAGE

# ============================================================



@app.get("/")

def home():



    return send_from_directory(

        "frontend",

        "index.html"

    )





# ============================================================

# GRAPH API

# ============================================================



@app.get("/api/graph")
def graph():
    """Return a browser-sized view of the real Bengaluru network."""
    try:
        limit = request.args.get("limit", default=5000, type=int)
        return jsonify(graph_info(limit=limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 500





# ============================================================

# HEALTH CHECK

# ============================================================



@app.get("/api/health")

def health():



    return jsonify({

        "status": "ok",

        "version":

            "SeedRescue Adaptive v4 - "

            "Automatic Road Detection + Weather"

    })





# ============================================================

# MODEL INFORMATION

# ============================================================



@app.get("/api/model-info")

def model_info():



    return jsonify(

        ml.info()

        or {

            "error": "model not trained yet"

        }

    )





# ============================================================

# AUTOMATIC ROAD DETECTION API

# ============================================================



@app.post("/api/detect-blocked-roads")

def detect_blocked_roads_api():



    try:



        data = request.get_json(

            force=True

        )



        if not data:

            raise ValueError(

                "JSON request body is required."

            )



        latitude = data.get(

            "latitude"

        )



        longitude = data.get(

            "longitude"

        )



        if latitude is None:

            raise ValueError(

                "latitude is required."

            )



        if longitude is None:

            raise ValueError(

                "longitude is required."

            )



        latitude = float(

            latitude

        )



        longitude = float(

            longitude

        )



        if not -90 <= latitude <= 90:

            raise ValueError(

                "Latitude must be between -90 and 90."

            )



        if not -180 <= longitude <= 180:

            raise ValueError(

                "Longitude must be between -180 and 180."

            )



        result = detect_road_status_from_location(
            latitude=latitude,
            longitude=longitude,
            blocked_radius_km=float(data.get("blocked_radius_km", 0.35)),
            orange_radius_km=float(data.get("orange_radius_km", 0.75)),
            yellow_radius_km=float(data.get("yellow_radius_km", 1.25)),
        )



        return jsonify(

            result

        )



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# MAIN RECOVERY PLAN API

# ============================================================



@app.post("/api/plan")

def plan():



    try:



        data = request.get_json(

            force=True

        )



        result = full_plan(

            data

        )



        return jsonify(

            result

        )



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# STATE API

# ============================================================



@app.post("/api/state")

def state():



    try:



        data = request.get_json(

            force=True

        )



        p = full_plan(

            data

        )



        return jsonify({



            "state": p.get(

                "accessibility",

                p.get("access")

            ),



            "risk": p["risk"],



            "recovery_score":

                p["recovery_score"],



            "fairness_score":

                p["fairness_score"]



        })



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# PROPAGATION API

# ============================================================



@app.post("/api/propagate")

def propagate_api():



    try:



        data = request.get_json(

            force=True

        )



        if not isinstance(data, dict):

            raise ValueError(

                "Request body must be a JSON object."

            )



        if "a" not in data:

            raise ValueError(

                "Scenario 'a' is required."

            )



        if "b" not in data:

            raise ValueError(

                "Scenario 'b' is required."

            )



        a = validate_seed(

            data["a"]

        )



        b = validate_seed(

            data["b"]

        )



        plan_a = full_plan(

            a

        )



        plan_b = full_plan(

            b

        )



        result = propagate(

            a,

            b,

            plan_a,

            plan_b

        )



        return jsonify(

            result

        )



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# SCENARIO COMPARISON API

# ============================================================



@app.post("/api/compare")

def compare():



    try:



        data = request.get_json(

            force=True

        )



        if not isinstance(data, dict):

            raise ValueError(

                "Request body must be a JSON object."

            )



        if "a" not in data:

            raise ValueError(

                "Scenario 'a' is required."

            )



        if "b" not in data:

            raise ValueError(

                "Scenario 'b' is required."

            )



        # ----------------------------------------------------

        # Validate scenarios

        # ----------------------------------------------------



        a = validate_seed(

            data["a"]

        )



        b = validate_seed(

            data["b"]

        )



        # ----------------------------------------------------

        # Generate plans

        # ----------------------------------------------------



        plan_a = full_plan(

            a

        )



        plan_b = full_plan(

            b

        )



        # ----------------------------------------------------

        # Propagation analysis

        # ----------------------------------------------------



        propagation_result = propagate(

            a,

            b,

            plan_a,

            plan_b

        )



        # ----------------------------------------------------

        # Metrics

        # ----------------------------------------------------



        keys = [

            "risk",

            "recovery_score",

            "displaced",

            "sheltered",

            "unsheltered",

            "accessible_roads",

            "fairness_score"

        ]



        delta = {}



        for key in keys:



            delta[key] = round(

                float(

                    plan_b.get(key, 0)

                )

                -

                float(

                    plan_a.get(key, 0)

                ),

                2

            )



        # ----------------------------------------------------

        # Medical demand

        # ----------------------------------------------------



        delta["medical_demand"] = round(

            float(

                plan_b["demand"]["medical"]

            )

            -

            float(

                plan_a["demand"]["medical"]

            ),

            2

        )



        # ----------------------------------------------------

        # Water shortage

        # ----------------------------------------------------



        delta["water_shortage"] = round(

            float(

                plan_b["shortage"]["water"]

            )

            -

            float(

                plan_a["shortage"]["water"]

            ),

            2

        )



        # ----------------------------------------------------

        # Explain differences

        # ----------------------------------------------------



        why = propagation_result.get(

            "consequences",

            []

        )



        # ----------------------------------------------------

        # Top priority comparison

        # ----------------------------------------------------



        priority_a = (

            plan_a["priorities"][0]["name"]

            if plan_a.get("priorities")

            else None

        )



        priority_b = (

            plan_b["priorities"][0]["name"]

            if plan_b.get("priorities")

            else None

        )



        top_priority_changed = (

            priority_a != priority_b

        )



        # ----------------------------------------------------

        # Response

        # ----------------------------------------------------



        return jsonify({



            "a": plan_a,



            "b": plan_b,



            "delta": delta,



            "why": why,



            "propagation":

                propagation_result,



            "top_priority_changed":

                top_priority_changed



        })



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# CRITICAL BOTTLENECK API

# ============================================================



@app.post("/api/bottlenecks")

def bottlenecks():



    """

    Simulates road failures and identifies

    critical single-point-of-failure roads.

    """



    try:



        seed_data = request.get_json(

            force=True

        )



        seed_data = validate_seed(

            seed_data

        )



        results = find_critical_bottlenecks(

            seed_data

        )



        return jsonify({

            "critical_roads": results

        })



    except Exception as e:



        return jsonify({

            "error": str(e)

        }), 400





# ============================================================

# LIVE WEATHER API

# ============================================================



@app.get("/api/live-weather")

def live_weather():



    """

    Fetch live weather from Open-Meteo

    and convert it into a SeedRescue

    disaster seed.



    Default location:

        Bengaluru, Karnataka

    """



    # --------------------------------------------------------

    # Coordinates

    # --------------------------------------------------------



    lat = request.args.get(

        "lat",

        default=12.9716,

        type=float

    )



    lon = request.args.get(

        "lon",

        default=77.5946,

        type=float

    )



    # --------------------------------------------------------

    # Validate coordinates

    # --------------------------------------------------------



    if not -90 <= lat <= 90:



        return jsonify({

            "status": "error",

            "message":

                "Latitude must be between -90 and 90."

        }), 400



    if not -180 <= lon <= 180:



        return jsonify({

            "status": "error",

            "message":

                "Longitude must be between -180 and 180."

        }), 400



    # --------------------------------------------------------

    # Open-Meteo

    # --------------------------------------------------------



    url = (

        "https://api.open-meteo.com/v1/forecast"

    )



    params = {



        "latitude": lat,



        "longitude": lon,



        "current": (

            "temperature_2m,"

            "precipitation,"

            "wind_speed_10m,"

            "wind_gusts_10m"

        ),



        "daily": (

            "precipitation_sum,"

            "wind_speed_10m_max,"

            "wind_gusts_10m_max"

        ),



        "forecast_days": 1,



        "timezone": "auto"

    }



    try:



        response = requests.get(

            url,

            params=params,

            timeout=10

        )



        response.raise_for_status()



        data = response.json()



        # ----------------------------------------------------

        # Extract weather

        # ----------------------------------------------------



        current = data.get(

            "current",

            {}

        )



        daily = data.get(

            "daily",

            {}

        )



        temperature = float(

            current.get(

                "temperature_2m",

                0

            )

        )



        current_rain = float(

            current.get(

                "precipitation",

                0

            )

        )



        wind = float(

            current.get(

                "wind_speed_10m",

                0

            )

        )



        gust = float(

            current.get(

                "wind_gusts_10m",

                0

            )

        )



        precipitation_sum = (

            daily.get(

                "precipitation_sum",

                [0]

            )

            or [0]

        )



        wind_max_values = (

            daily.get(

                "wind_speed_10m_max",

                [0]

            )

            or [0]

        )



        gust_max_values = (

            daily.get(

                "wind_gusts_10m_max",

                [0]

            )

            or [0]

        )



        daily_rain = float(

            precipitation_sum[0]

        )



        daily_max_wind = float(

            wind_max_values[0]

        )



        daily_max_gust = float(

            gust_max_values[0]

        )



        # ----------------------------------------------------

        # Weather → Disaster Seed

        # ----------------------------------------------------



        if (

            daily_rain >= 50

            or current_rain >= 30

        ):



            disaster = "flood"



            damage = min(

                80,

                max(

                    40,

                    round(

                        25 + daily_rain * 0.5

                    )

                )

            )



        elif (

            daily_max_gust >= 60

            or gust >= 60

        ):



            disaster = "cyclone"



            damage = min(

                80,

                max(

                    30,

                    round(

                        25

                        + daily_max_gust * 0.4

                    )

                )

            )



        elif daily_rain >= 20:



            disaster = "flood"



            damage = 35



        else:



            disaster = "flood"



            damage = 25



        # ----------------------------------------------------

        # Suggested seed

        # ----------------------------------------------------



        suggested_seed = {



            "disaster": disaster,



            "damage": damage,



            "population": 12000,



            "latitude": lat,



            "longitude": lon



        }



        # ----------------------------------------------------

        # Response

        # ----------------------------------------------------



        return jsonify({



            "status": "success",



            "location": {



                "latitude": lat,



                "longitude": lon

            },



            "weather": {



                "temperature_c":

                    round(

                        temperature,

                        1

                    ),



                "current_rain_mm":

                    round(

                        current_rain,

                        2

                    ),



                "daily_rain_mm":

                    round(

                        daily_rain,

                        2

                    ),



                "wind_kmh":

                    round(

                        wind,

                        2

                    ),



                "wind_gust_kmh":

                    round(

                        gust,

                        2

                    ),



                "daily_max_wind_kmh":

                    round(

                        daily_max_wind,

                        2

                    ),



                "daily_max_gust_kmh":

                    round(

                        daily_max_gust,

                        2

                    )

            },



            "suggested_seed":

                suggested_seed



        })



    except requests.exceptions.Timeout:



        return jsonify({



            "status": "error",



            "message":

                "Open-Meteo request timed out."



        }), 504



    except requests.exceptions.RequestException as e:



        return jsonify({



            "status": "error",



            "message":

                "Could not reach Open-Meteo: "

                + str(e)



        }), 502



    except Exception as e:



        return jsonify({



            "status": "error",



            "message": str(e)



        }), 500





# ============================================================

# RUN SERVER

# ============================================================



if __name__ == "__main__":



    app.run(

        debug=True,

        port=5000

    )