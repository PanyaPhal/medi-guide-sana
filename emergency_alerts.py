"""
How to integrate with the HTML app
-----------------------------------
  python emergency_alerts.py          # starts Flask on port 5001
  Then in index.html / emergency-contacts.html, the JS fetch() calls hit:
    POST /api/alerts/send       → send alerts to all / specific contacts
    GET  /api/contacts          → list contacts
    POST /api/contacts          → add a contact
    DELETE /api/contacts/<id>   → remove a contact
    GET  /api/alerts/log        → last-N alert history
    GET  /api/alerts/stats      → Pandas-powered analytics summary
"""

from __future__ import annotations

import heapq
import json
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass(order=True)
class Contact:
    """
    A single emergency contact.
    Implements ordering so contacts can be stored in a min-heap
    (priority queue) — lowest priority number = notified first.
    """
    priority: int                          # 1 = highest priority
    name:     str     = field(compare=False)
    relation: str     = field(compare=False)
    phone:    str     = field(compare=False)
    id:       str     = field(compare=False, default_factory=lambda: str(uuid.uuid4())[:8])
    color:    str     = field(compare=False, default="#00c9b1")
    notified: bool    = field(compare=False, default=False)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertEvent:
    """One fired alert — stored in a fixed-size deque (ring buffer)."""
    contact_id:   str
    contact_name: str
    situation:    str
    location:     str
    timestamp:    str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    status:       str = "sent"          # sent | failed | pending


class ContactRegistry:
    """
    Core data structure layer.

    Internally keeps:
      • A dict[id → Contact]       for O(1) look-up
      • A min-heap[Contact]        for priority-ordered dispatch
      • A deque(maxlen=50)         as a ring-buffer alert log
      • A Pandas DataFrame         for analytics & manipulation
    """

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._heap: list[Contact] = []          # min-heap by priority
        self._log: deque[AlertEvent] = deque(maxlen=50)
        self._df: pd.DataFrame = self._empty_df()

    # ── DataFrame schema ──────────────────────────────────────
    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "id", "name", "relation", "phone", "priority", "color", "notified"
        ])

    # ── CRUD ──────────────────────────────────────────────────
    def add(self, contact: Contact) -> Contact:
        self._contacts[contact.id] = contact
        heapq.heappush(self._heap, contact)
        self._sync_df()
        return contact

    def remove(self, contact_id: str) -> bool:
        if contact_id not in self._contacts:
            return False
        del self._contacts[contact_id]
        # Rebuild heap after deletion (heapq has no remove)
        self._heap = list(self._contacts.values())
        heapq.heapify(self._heap)
        self._sync_df()
        return True

    def get_all(self) -> list[Contact]:
        """Return contacts in priority order (heap-sorted copy)."""
        return sorted(self._contacts.values(), key=lambda c: c.priority)

    def get(self, contact_id: str) -> Optional[Contact]:
        return self._contacts.get(contact_id)

    # ── Priority-queue dispatch ────────────────────────────────
    def dispatch_in_order(self) -> list[Contact]:
        """
        Return all contacts sorted by priority using heapq.nsmallest —
        O(n log n), preserves the original heap.
        """
        return heapq.nsmallest(len(self._heap), self._heap)

    # ── DataFrame sync & analytics ────────────────────────────
    def _sync_df(self) -> None:
        """Rebuild the Pandas DataFrame from the dict — called on every mutation."""
        rows = [asdict(c) for c in self._contacts.values()]
        self._df = pd.DataFrame(rows) if rows else self._empty_df()

    def analytics(self) -> dict:
        """
        DATA MANIPULATION with Pandas:
        Return a summary dict used by GET /api/alerts/stats.
        """
        if self._df.empty:
            return {"total": 0, "by_relation": {}, "notified_pct": 0.0}

        by_relation = (
            self._df.groupby("relation")["id"]
            .count()
            .rename("count")
            .to_dict()
        )

        notified_pct = float(
            self._df["notified"].mean() * 100
        ) if "notified" in self._df.columns else 0.0

        priority_dist = (
            self._df["priority"]
            .value_counts()
            .sort_index()
            .to_dict()
        )

        return {
            "total":          len(self._contacts),
            "by_relation":    by_relation,
            "notified_pct":   round(notified_pct, 1),
            "priority_dist":  {str(k): int(v) for k, v in priority_dist.items()},
            "avg_priority":   round(float(self._df["priority"].mean()), 2),
        }

    # ── Alert log ─────────────────────────────────────────────
    def log_alert(self, event: AlertEvent) -> None:
        self._log.appendleft(event)

    def get_log(self, n: int = 20) -> list[dict]:
        return [asdict(e) for e in list(self._log)[:n]]

    def alert_log_df(self) -> pd.DataFrame:
        """Return alert history as a DataFrame for further analysis."""
        return pd.DataFrame([asdict(e) for e in self._log]) if self._log else pd.DataFrame()


# ─────────────────────────────────────────────
# PRE-SEED DEFAULT CONTACTS (mirrors app.js)
# ─────────────────────────────────────────────
registry = ContactRegistry()

_defaults = [
    Contact(priority=1, name="Sokha Doeun",     relation="Spouse",       phone="+855 12 345 678", color="#00c9b1"),
    Contact(priority=2, name="Dr. Vichet Chan", relation="Cardiologist", phone="+855 23 456 789", color="#3d9be9"),
    Contact(priority=3, name="Dara Doeun",       relation="Sibling",      phone="+855 17 890 123", color="#f5a623"),
]
for _c in _defaults:
    registry.add(_c)


# ─────────────────────────────────────────────
# ALERT SENDER (simulated — plug in Twilio / email here)
# ─────────────────────────────────────────────

def build_message(contact: Contact, situation: str, location: str, user_name: str = "John Doeun") -> str:
    """Compose the SMS / notification body."""
    return (
        f"🚨 EMERGENCY ALERT from MediGuide\n\n"
        f"{user_name} is experiencing: {situation}\n"
        f"📍 Location: {location}\n\n"
        f"Please call or come immediately.\n"
        f"— Sent automatically via MediGuide 2026"
    )


def send_alert(contact: Contact, situation: str, location: str) -> AlertEvent:
    """
    Simulate sending.  Replace the print() with:
        • Twilio SMS: client.messages.create(to=contact.phone, ...)
        • Email:      smtplib / SendGrid
        • Push:       Firebase Cloud Messaging
    """
    msg = build_message(contact, situation, location)
    print(f"[ALERT] → {contact.name} ({contact.phone})\n{msg}\n{'─'*50}")

    event = AlertEvent(
        contact_id=contact.id,
        contact_name=contact.name,
        situation=situation,
        location=location,
    )
    contact.notified = True
    registry._sync_df()
    registry.log_alert(event)
    return event


def send_all_alerts(situation: str, location: str) -> list[AlertEvent]:
    """
    Send alerts in priority order using the heap-based dispatcher.
    Returns a list of AlertEvent objects for the API response.
    """
    ordered = registry.dispatch_in_order()
    events  = [send_alert(c, situation, location) for c in ordered]
    return events


# ─────────────────────────────────────────────
# FLASK REST API  (Web concept)
# ─────────────────────────────────────────────
app = Flask(__name__)
CORS(app)   # allow cross-origin requests from the HTML front-end


# ── GET /api/contacts ─────────────────────────────────────────
@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    """Return all contacts sorted by priority."""
    return jsonify([c.to_dict() for c in registry.get_all()])


# ── POST /api/contacts ────────────────────────────────────────
@app.route("/api/contacts", methods=["POST"])
def add_contact():
    """
    Body (JSON):
        { "name": "...", "relation": "...", "phone": "...", "priority": 1 }
    """
    data = request.get_json(force=True)
    required = {"name", "relation", "phone", "priority"}
    if not required.issubset(data):
        return jsonify({"error": f"Missing fields: {required - data.keys()}"}), 400

    contact = Contact(
        name=data["name"],
        relation=data["relation"],
        phone=data["phone"],
        priority=int(data["priority"]),
        color=data.get("color", "#00c9b1"),
    )
    registry.add(contact)
    return jsonify(contact.to_dict()), 201


# ── DELETE /api/contacts/<id> ─────────────────────────────────
@app.route("/api/contacts/<contact_id>", methods=["DELETE"])
def delete_contact(contact_id: str):
    if registry.remove(contact_id):
        return jsonify({"deleted": contact_id})
    return jsonify({"error": "Contact not found"}), 404


# ── POST /api/alerts/send ─────────────────────────────────────
@app.route("/api/alerts/send", methods=["POST"])
def send_alerts():
    """
    Body (JSON):
        {
          "situation": "Cardiac Event",
          "location": "11.5564, 104.9282",
          "contact_id": "abc123"   ← optional; omit to alert ALL contacts
        }
    """
    data      = request.get_json(force=True)
    situation = data.get("situation", "Medical Emergency")
    location  = data.get("location",  "Phnom Penh, Cambodia")
    cid       = data.get("contact_id")

    if cid:
        contact = registry.get(cid)
        if not contact:
            return jsonify({"error": "Contact not found"}), 404
        events = [send_alert(contact, situation, location)]
    else:
        events = send_all_alerts(situation, location)

    return jsonify({
        "alerts_sent": len(events),
        "events": [asdict(e) for e in events],
    })


# ── GET /api/alerts/log ───────────────────────────────────────
@app.route("/api/alerts/log", methods=["GET"])
def alert_log():
    n = int(request.args.get("n", 20))
    return jsonify(registry.get_log(n))


# ── GET /api/alerts/stats ─────────────────────────────────────
@app.route("/api/alerts/stats", methods=["GET"])
def alert_stats():
    """Pandas-powered analytics on the contact registry."""
    return jsonify(registry.analytics())


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  MediGuide — Emergency Alert API")
    print("  http://localhost:5001")
    print("  Endpoints:")
    print("    GET  /api/contacts")
    print("    POST /api/contacts")
    print("    DELETE /api/contacts/<id>")
    print("    POST /api/alerts/send")
    print("    GET  /api/alerts/log")
    print("    GET  /api/alerts/stats")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5001, debug=True)