#!/usr/bin/env python3
"""
fetch_ratings.py
Laeuft in GitHub Actions (monatlicher Cron).
Liest PE_API_ID und PE_API_KEY aus den GitHub Secrets (Env-Vars).
Schreibt das Ergebnis in ratings.json im Repo-Root.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

API_ID       = os.environ.get("PE_API_ID", "")
API_KEY      = os.environ.get("PE_API_KEY", "")
API_BASE     = "https://www.provenexpert.com/api/v1"
RATINGS_FILE = Path("ratings.json")


def pe_post(endpoint: str, payload: dict | None = None) -> dict:
    r = requests.post(
        f"{API_BASE}/{endpoint}",
        auth=(API_ID, API_KEY),
        json=payload or {},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def load() -> list:
    if RATINGS_FILE.exists():
        try:
            return json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save(history: list) -> None:
    RATINGS_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def src_val(sources: list, name: str) -> tuple[float, int]:
    """Extrahiert Score und neue Bewertungen fuer eine Plattform."""
    for s in sources:
        if name.lower() in s.get("name", "").lower():
            try:
                score = float(s.get("average_rating", 0))
                new_n = int(
                    s.get("new_count", 0)
                    or s.get("count_new", 0)
                    or s.get("rating_count_new", 0)
                    or 0
                )
                return score, new_n
            except (TypeError, ValueError):
                pass
    return 0.0, 0


def main() -> None:
    if not API_ID or not API_KEY:
        print("Fehler: PE_API_ID und PE_API_KEY als GitHub Secrets setzen.")
        sys.exit(1)

    month = datetime.now().strftime("%Y-%m")
    print(f"Lade Bewertungen fuer {month}...")

    try:
        result = pe_post("rating/summary/get")
    except requests.HTTPError as exc:
        print(f"HTTP-Fehler: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Verbindungsfehler: {exc}")
        sys.exit(1)

    if result.get("status") != "success":
        print(f"API-Fehler: {result.get('errors', result)}")
        sys.exit(1)

    rating  = result.get("rating", {})
    overall = float(rating.get("average_rating", 0))
    sources = rating.get("external_ratings", [])

    g, gn = src_val(sources, "google")
    a, an = src_val(sources, "amazon")
    t, tn = src_val(sources, "trustpilot")

    if not overall and g and a and t:
        overall = round((g + a + t) / 3, 2)

    entry = {
        "m":  month,
        "g":  g,
        "a":  a,
        "t":  t,
        "o":  overall,
        "gn": gn,
        "an": an,
        "tn": tn,
    }

    history = load()
    history = [e for e in history if e["m"] != month]
    history.append(entry)
    history.sort(key=lambda e: e["m"])
    save(history)

    print(
        f"Gesamt: {overall:.2f} | "
        f"Google: {g:.2f} (+{gn}) | "
        f"Amazon: {a:.2f} (+{an}) | "
        f"Trustpilot: {t:.2f} (+{tn})"
    )
    print("ratings.json aktualisiert.")


if __name__ == "__main__":
    main()
