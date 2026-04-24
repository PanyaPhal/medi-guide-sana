from __future__ import annotations

import io
import math
import os
from dataclasses import dataclass, field, asdict
from typing import NamedTuple

import folium
import matplotlib
matplotlib.use("Agg")          # headless — no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler

# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

class LatLng(NamedTuple):
    """Immutable geographic coordinate — used as dict keys and array rows."""
    lat: float
    lng: float


@dataclass
class Hospital:
    """
    Rich hospital record.
    `score` is computed at runtime by the ML model.
    """
    id:           str
    name:         str
    address:      str
    phone:        str
    lat:          float
    lng:          float
    status:       str                   # best | available | busy
    tags:         list[str] = field(default_factory=list)
    distance_km:  float     = 0.0      # filled in by KNN
    eta_min:      int       = 0        # filled in by KNN
    score:        float     = 0.0      # ML urgency-weighted score (0–1)
    maps_query:   str       = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────
# HOSPITAL DATA  (mirrors app.js hospitals[])
# ─────────────────────────────────────────────

HOSPITALS: list[Hospital] = [
    Hospital(
        id="calmette",
        name="Calmette Hospital",
        address="Monivong Blvd, Phnom Penh",
        phone="023 426 948",
        lat=11.5638, lng=104.9238,
        status="best",
        tags=["ER Open", "Cardiac", "Blood Bank"],
        maps_query="Calmette+Hospital,+Phnom+Penh,+Cambodia",
    ),
    Hospital(
        id="royal",
        name="Royal Phnom Penh Hospital",
        address="Russian Blvd, Phnom Penh",
        phone="023 991 000",
        lat=11.5726, lng=104.9160,
        status="available",
        tags=["ER Open", "General", "ICU"],
        maps_query="Royal+Phnom+Penh+Hospital,+Cambodia",
    ),
    Hospital(
        id="sunrise",
        name="Sunrise Japan Hospital",
        address="Mao Tse Tung Blvd, Phnom Penh",
        phone="023 999 111",
        lat=11.5549, lng=104.9282,
        status="busy",
        tags=["High Load", "ICU"],
        maps_query="Sunrise+Japan+Hospital,+Phnom+Penh,+Cambodia",
    ),
    Hospital(
        id="khmer-soviet",
        name="Khmer Soviet Friendship Hospital",
        address="Confederation de la Russie Blvd",
        phone="023 883 712",
        lat=11.5800, lng=104.9100,
        status="available",
        tags=["ER Open", "General"],
        maps_query="Khmer+Soviet+Friendship+Hospital,+Phnom+Penh",
    ),
    Hospital(
        id="kossamak",
        name="Kossamak Hospital",
        address="Monivong Blvd, Phnom Penh",
        phone="023 880 484",
        lat=11.5615, lng=104.9165,
        status="available",
        tags=["ER Open", "General", "Pediatrics"],
        maps_query="Kossamak+Hospital,+Phnom+Penh,+Cambodia",
    ),
]

# Adjacency-style capacity dict  (Data Structure)
HOSPITAL_CAPACITY: dict[str, dict] = {
    "calmette":     {"beds": 400, "er_beds": 30, "load_pct": 65},
    "royal":        {"beds": 220, "er_beds": 20, "load_pct": 50},
    "sunrise":      {"beds": 150, "er_beds": 15, "load_pct": 90},
    "khmer-soviet": {"beds": 500, "er_beds": 40, "load_pct": 55},
    "kossamak":     {"beds": 300, "er_beds": 25, "load_pct": 45},
}

# ─────────────────────────────────────────────
# GEO UTILITIES
# ─────────────────────────────────────────────

def haversine(a: LatLng, b: LatLng) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi  = math.radians(b.lat - a.lat)
    dlam  = math.radians(b.lng - a.lng)
    h = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(h))


def eta_minutes(dist_km: float, avg_speed_kmh: float = 30.0) -> int:
    """Estimate urban driving time."""
    return max(1, round((dist_km / avg_speed_kmh) * 60))


# ─────────────────────────────────────────────
# MACHINE LEARNING  — KNN + urgency scoring
# ─────────────────────────────────────────────

# Status penalty: busy hospitals are deprioritised
STATUS_PENALTY: dict[str, float] = {"best": 0.0, "available": 0.1, "busy": 0.4}
TAG_BONUS: dict[str, float] = {
    "Cardiac": 0.15, "ICU": 0.10, "Blood Bank": 0.08,
    "ER Open": 0.05, "Pediatrics": 0.05,
}

def build_feature_matrix(user: LatLng) -> tuple[np.ndarray, list[str]]:
    """
    Build the feature matrix used by KNN.
    Features per hospital: [lat, lng, load_pct_norm, tag_bonus, status_penalty]
    """
    rows, ids = [], []
    for h in HOSPITALS:
        cap   = HOSPITAL_CAPACITY.get(h.id, {"load_pct": 50})
        bonus = sum(TAG_BONUS.get(t, 0) for t in h.tags)
        rows.append([h.lat, h.lng, cap["load_pct"] / 100, bonus, STATUS_PENALTY[h.status]])
        ids.append(h.id)
    return np.array(rows, dtype=float), ids


def rank_hospitals_knn(user: LatLng, k: int = 5, situation: str = "general") -> list[Hospital]:
    """
    MACHINE LEARNING — K-Nearest Neighbours.

    1. Build feature matrix (geo + capacity + tag bonuses)
    2. Normalise with MinMaxScaler so all features share the same range
    3. Fit KNN on the normalised matrix
    4. Query with the user's location
    5. Sort by a composite urgency score = distance_score − tag_bonus + load_penalty
    """
    X, ids = build_feature_matrix(user)

    # Scale features  (MinMaxScaler = Data Manipulation)
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit KNN
    k_actual = min(k, len(HOSPITALS))
    knn = NearestNeighbors(n_neighbors=k_actual, algorithm="ball_tree",
                           metric="haversine")
    # KNN metric='haversine' expects radians
    coords_rad = np.radians(X[:, :2])
    knn.fit(coords_rad)

    user_rad = np.radians([[user.lat, user.lng]])
    distances_rad, indices = knn.kneighbors(user_rad)
    distances_km = distances_rad[0] * 6371.0   # convert to km

    ranked: list[Hospital] = []
    for dist_km, idx in zip(distances_km, indices[0]):
        h = HOSPITALS[idx]
        cap = HOSPITAL_CAPACITY.get(h.id, {"load_pct": 50})

        # Urgency score: lower = better
        load_score   = cap["load_pct"] / 100            # 0→1
        status_pen   = STATUS_PENALTY[h.status]
        tag_bon      = sum(TAG_BONUS.get(t, 0) for t in h.tags)
        dist_norm    = min(dist_km / 10.0, 1.0)         # normalise to ~10 km max
        urgency      = dist_norm + load_score * 0.4 + status_pen - tag_bon

        import copy
        hospital = copy.deepcopy(h)
        hospital.distance_km = round(dist_km, 2)
        hospital.eta_min     = eta_minutes(dist_km)
        hospital.score       = round(max(0.0, 1.0 - urgency), 3)   # 0–1, higher=better
        ranked.append(hospital)

    ranked.sort(key=lambda x: -x.score)
    return ranked


# ─────────────────────────────────────────────
# DATA VISUALIZATION  — Folium map + matplotlib chart
# ─────────────────────────────────────────────

MAP_OUTPUT  = os.path.join(os.path.dirname(__file__), "hospital_map.html")
CHART_OUTPUT = os.path.join(os.path.dirname(__file__), "map_chart.png")


def build_folium_map(user: LatLng, ranked: list[Hospital]) -> str:
    """
    DATA VISUALIZATION — Folium interactive map.
    Exports to hospital_map.html (also served via /api/hospitals/map).
    """
    m = folium.Map(
        location=[user.lat, user.lng],
        zoom_start=14,
        tiles="CartoDB dark_matter",
    )

    # User location marker
    folium.CircleMarker(
        location=[user.lat, user.lng],
        radius=10,
        color="#00c9b1", fill=True, fill_color="#00c9b1", fill_opacity=0.9,
        tooltip="📍 Your Location",
    ).add_to(m)

    # Distance rings at 1 km, 2 km, 5 km
    for radius_km, opacity in [(1000, 0.08), (2000, 0.06), (5000, 0.04)]:
        folium.Circle(
            location=[user.lat, user.lng],
            radius=radius_km,
            color="#00c9b1", fill=True, fill_color="#00c9b1",
            fill_opacity=opacity, weight=1,
        ).add_to(m)

    # Hospital markers
    color_map = {"best": "#00c9b1", "available": "#3d9be9", "busy": "#ff4757"}
    rank_icon  = {0: "★ #1", 1: "★ #2", 2: "#3", 3: "#4", 4: "#5"}

    for rank, h in enumerate(ranked):
        color = color_map.get(h.status, "#8eafd4")
        cap   = HOSPITAL_CAPACITY.get(h.id, {"load_pct": 50, "er_beds": 20, "beds": 200})

        popup_html = f"""
        <div style="font-family:sans-serif;min-width:180px;">
          <b style="color:{color};">{rank_icon.get(rank,'')} {h.name}</b><br>
          <small>{h.address}</small><br><hr style="margin:6px 0;">
          🕐 {h.distance_km} km &nbsp;·&nbsp; ~{h.eta_min} min<br>
          📊 Load: {cap['load_pct']}%  |  ER beds: {cap['er_beds']}<br>
          ⭐ Score: {h.score}<br>
          📞 {h.phone}<br><br>
          <a href="https://www.google.com/maps/dir/{user.lat},{user.lng}/{h.maps_query}"
             target="_blank"
             style="background:{color};color:#0b1e3d;padding:5px 10px;
                    border-radius:6px;text-decoration:none;font-weight:bold;">
            🗺 Directions
          </a>
        </div>"""

        folium.Marker(
            location=[h.lat, h.lng],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{rank_icon.get(rank,'')} {h.name}  ({h.distance_km} km)",
            icon=folium.Icon(color="red" if h.status == "busy" else
                             ("green" if h.status == "best" else "blue"),
                             icon="plus-sign"),
        ).add_to(m)

        # Dashed line from user to hospital
        folium.PolyLine(
            locations=[[user.lat, user.lng], [h.lat, h.lng]],
            color=color, weight=1.5, opacity=0.5, dash_array="6 4",
            tooltip=f"{h.distance_km} km",
        ).add_to(m)

    m.save(MAP_OUTPUT)
    return MAP_OUTPUT


def build_distance_chart(user: LatLng, ranked: list[Hospital]) -> str:
    """
    DATA VISUALIZATION — matplotlib bar + scatter chart.
    Shows distance, ETA and ML score side-by-side.
    Saved to map_chart.png and served via /api/hospitals/chart.
    """
    names   = [h.name.split()[0] + "\n" + h.name.split()[1] if len(h.name.split()) > 1
               else h.name for h in ranked]
    dists   = [h.distance_km  for h in ranked]
    etas    = [h.eta_min       for h in ranked]
    scores  = [h.score         for h in ranked]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.patch.set_facecolor("#0b1e3d")

    COLORS = ["#00c9b1", "#3d9be9", "#f5a623", "#ff4757", "#a78bfa"]
    bar_colors = [COLORS[i % len(COLORS)] for i in range(len(ranked))]

    # ── Chart 1: Distance ────────────────────────────────
    ax1 = axes[0]
    ax1.set_facecolor("#132843")
    bars = ax1.barh(names[::-1], dists[::-1], color=bar_colors[::-1], height=0.5)
    ax1.set_xlabel("Distance (km)", color="#8eafd4")
    ax1.set_title("Distance from You (km)", color="#f0f6ff", fontweight="bold")
    ax1.tick_params(colors="#8eafd4")
    for spine in ax1.spines.values(): spine.set_edgecolor("#1a3354")
    for bar, val in zip(bars, dists[::-1]):
        ax1.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                 f"{val} km", va="center", color="#f0f6ff", fontsize=8)

    # ── Chart 2: ETA ─────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor("#132843")
    bars2 = ax2.barh(names[::-1], etas[::-1], color=bar_colors[::-1], height=0.5)
    ax2.set_xlabel("ETA (minutes)", color="#8eafd4")
    ax2.set_title("Estimated Drive Time (min)", color="#f0f6ff", fontweight="bold")
    ax2.tick_params(colors="#8eafd4")
    for spine in ax2.spines.values(): spine.set_edgecolor("#1a3354")
    for bar, val in zip(bars2, etas[::-1]):
        ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                 f"{val} min", va="center", color="#f0f6ff", fontsize=8)

    # ── Chart 3: ML Urgency Score ─────────────────────────
    ax3 = axes[2]
    ax3.set_facecolor("#132843")
    x = np.arange(len(ranked))
    sc = ax3.scatter(x, scores, s=120, c=bar_colors, zorder=3, edgecolors="white", linewidths=0.6)
    ax3.plot(x, scores, color="#8eafd4", linewidth=1.2, linestyle="--", alpha=0.6)
    ax3.fill_between(x, scores, alpha=0.12, color="#00c9b1")
    ax3.set_xticks(x)
    ax3.set_xticklabels([n.replace("\n", " ").split()[0] for n in names], color="#8eafd4", fontsize=8)
    ax3.set_ylabel("Recommendation Score", color="#8eafd4")
    ax3.set_title("ML Recommendation Score (0-1)", color="#f0f6ff", fontweight="bold")
    ax3.tick_params(colors="#8eafd4")
    for spine in ax3.spines.values(): spine.set_edgecolor("#1a3354")
    ax3.set_ylim(0, 1.1)
    for xi, yi, name in zip(x, scores, names):
        ax3.annotate(f"{yi:.2f}", (xi, yi + 0.05), ha="center",
                     color="#f0f6ff", fontsize=8)

    fig.suptitle("MediGuide 2026  |  Hospital Distance & ML Analysis", color="#f0f6ff",
                 fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig(CHART_OUTPUT, dpi=130, bbox_inches="tight", facecolor="#0b1e3d")
    plt.close(fig)
    return CHART_OUTPUT


# ─────────────────────────────────────────────
# FLASK REST API  (Web concept)
# ─────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

DEFAULT_USER = LatLng(lat=11.5564, lng=104.9282)   # Phnom Penh city centre


def _parse_user(req) -> LatLng:
    """Extract lat/lng from query-string, fallback to default."""
    try:
        lat = float(req.args.get("lat", DEFAULT_USER.lat))
        lng = float(req.args.get("lng", DEFAULT_USER.lng))
        return LatLng(lat, lng)
    except (TypeError, ValueError):
        return DEFAULT_USER


# ── GET /api/hospitals ────────────────────────────────────────
@app.route("/api/hospitals", methods=["GET"])
def get_hospitals():
    """
    Return all hospitals with distance and ETA filled in for the user's position.
    ?lat=11.55&lng=104.92
    """
    user = _parse_user(request)
    results = []
    for h in HOSPITALS:
        import copy
        hc = copy.deepcopy(h)
        dist = haversine(user, LatLng(h.lat, h.lng))
        hc.distance_km = round(dist, 2)
        hc.eta_min     = eta_minutes(dist)
        results.append(hc.to_dict())
    results.sort(key=lambda x: x["distance_km"])
    return jsonify(results)


# ── GET /api/hospitals/nearest ────────────────────────────────
@app.route("/api/hospitals/nearest", methods=["GET"])
def nearest_hospitals():
    """
    ML-ranked nearest hospitals.
    ?lat=11.55&lng=104.92&k=5&situation=cardiac
    """
    user      = _parse_user(request)
    k         = int(request.args.get("k", 5))
    situation = request.args.get("situation", "general")
    ranked    = rank_hospitals_knn(user, k=k, situation=situation)
    return jsonify([h.to_dict() for h in ranked])


# ── GET /api/hospitals/map ────────────────────────────────────
@app.route("/api/hospitals/map", methods=["GET"])
def hospital_map_page():
    """
    Generate and serve the Folium interactive map.
    ?lat=11.55&lng=104.92
    """
    user   = _parse_user(request)
    ranked = rank_hospitals_knn(user)
    path   = build_folium_map(user, ranked)
    return send_file(path, mimetype="text/html")


# ── GET /api/hospitals/chart ──────────────────────────────────
@app.route("/api/hospitals/chart", methods=["GET"])
def hospital_chart():
    """
    Generate and serve the matplotlib distance/score chart as PNG.
    ?lat=11.55&lng=104.92
    """
    user   = _parse_user(request)
    ranked = rank_hospitals_knn(user)
    path   = build_distance_chart(user, ranked)
    return send_file(path, mimetype="image/png")


# ── POST /api/hospitals/route ─────────────────────────────────
@app.route("/api/hospitals/route", methods=["POST"])
def get_route():
    """
    Return route details between user and a hospital.
    Body: { "hospital_id": "calmette", "user_lat": 11.55, "user_lng": 104.92 }
    """
    data = request.get_json(force=True)
    hospital_id = data.get("hospital_id")
    hospital = next((h for h in HOSPITALS if h.id == hospital_id), None)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    user     = LatLng(float(data.get("user_lat", DEFAULT_USER.lat)),
                      float(data.get("user_lng", DEFAULT_USER.lng)))
    dist     = haversine(user, LatLng(hospital.lat, hospital.lng))
    eta      = eta_minutes(dist)
    cap      = HOSPITAL_CAPACITY.get(hospital_id, {})
    gmaps    = (f"https://www.google.com/maps/dir/"
                f"{user.lat},{user.lng}/{hospital.maps_query}")

    return jsonify({
        "hospital":    hospital.to_dict(),
        "distance_km": round(dist, 2),
        "eta_min":     eta,
        "capacity":    cap,
        "google_maps": gmaps,
    })


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Pre-generate map + chart at startup
    print("Generating hospital map and chart...")
    ranked = rank_hospitals_knn(DEFAULT_USER)
    build_folium_map(DEFAULT_USER, ranked)
    build_distance_chart(DEFAULT_USER, ranked)
    print(f"  ✓ Map  → {MAP_OUTPUT}")
    print(f"  ✓ Chart → {CHART_OUTPUT}")
    print("=" * 55)
    print("  MediGuide — Hospital Map API")
    print("  http://localhost:5002")
    print("  Endpoints:")
    print("    GET  /api/hospitals")
    print("    GET  /api/hospitals/nearest?lat=&lng=")
    print("    GET  /api/hospitals/map?lat=&lng=")
    print("    GET  /api/hospitals/chart?lat=&lng=")
    print("    POST /api/hospitals/route")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5002, debug=True)