"""
Golemio Waste Sensor Collector
Stahuje aktuální měření nádob na Kašparově náměstí 350/1 (stanice 5262)
a přidává je do CSV.
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── CONFIG ──────────────────────────────────────────────────────────────────
API_TOKEN   = os.environ.get("GOLEMIO_TOKEN")
STATION_ID  = 5262
STATION_URL = "https://api.golemio.cz/v2/sortedwastestations?latlng=50.11396,14.46900&range=100&limit=5&onlyMonitored=true"

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CSV_FILE    = os.path.join(SCRIPT_DIR, "kasparovo_namesti_odpady.csv")
LOG_FILE    = os.path.join(SCRIPT_DIR, "collect_log.txt")

CSV_HEADER = [
    "collected_at_utc",
    "stanice_id", "stanice_nazev",
    "kontejner_id", "sensor_id", "druh_odpadu",
    "zaplneni_pct", "measured_at_utc", "predikce_utc",
    "posledni_svoz_utc", "dalsi_svoz",
]

# Přesné časy měření každého senzoru (CET) — aktualizuje se každých 6h
# Spouštěj skript ~5 minut po těchto časech pro čerstvá data
SENSOR_SCHEDULE = {
    23270: ["01:11", "07:11", "13:11", "19:11"],   # Papír
    41581: ["00:04", "06:04", "12:04", "18:04"],   # Multikomoditní
    41580: ["04:26", "10:26", "16:26", "22:26"],   # Kovy
    42883: ["02:30", "08:30", "14:30", "20:30"],   # Barevné sklo
}

# ── HELPERS ─────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_station() -> dict:
    req = urllib.request.Request(
        STATION_URL,
        headers={"x-access-token": API_TOKEN, "Accept": "application/json"},
    )
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode())
            break
        except Exception as e:
            if attempt < 3:
                log(f"  Pokus {attempt} selhal ({e}), zkouším znovu za 120s...")
                time.sleep(120)
            else:
                raise
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data["features"]
    elif isinstance(data, list):
        features = data
    else:
        features = [data]
    # Najdi správnou stanici podle ID
    for f in features:
        props = f["properties"] if "properties" in f else f
        if props.get("id") == STATION_ID:
            return props
    raise ValueError(f"Stanice {STATION_ID} nenalezena v odpovědi API")


def ensure_csv_header() -> None:
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)
        log(f"Vytvořen nový CSV soubor: {CSV_FILE}")


def load_last_measurements() -> dict[int, str]:
    """Vrátí {kontejner_id: poslední measured_at_utc} z CSV."""
    last = {}
    if not os.path.exists(CSV_FILE):
        return last
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            # nový formát: collected_at_utc(0), stanice_id(1), stanice_nazev(2),
            # kontejner_id(3), sensor_id(4), druh_odpadu(5), zaplneni_pct(6), measured_at_utc(7)
            if row and row[0].startswith("20") and len(row) >= 8:
                try:
                    last[int(row[3])] = row[7]
                except (ValueError, IndexError):
                    pass
    return last


def append_rows(rows: list[list]) -> None:
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


# ── MAIN ────────────────────────────────────────────────────────────────────

def collect() -> None:
    log("--- Spouštím sběr dat ---")
    ensure_csv_header()
    last = load_last_measurements()
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        props = fetch_station()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log(f"HTTP {e.code} při stahování stanice: {body}")
        sys.exit(1)
    except Exception as e:
        log(f"Chyba při stahování: {e}")
        sys.exit(1)

    station_name = props.get("name", "")
    station_id   = props.get("id", STATION_ID)
    containers   = props.get("containers", [])

    new_rows = []
    skipped  = 0

    for c in containers:
        cid         = c.get("container_id") or c.get("ksnko_id")
        sensor_id   = c.get("sensor_id", "")
        trash_type  = (c.get("trash_type") or {}).get("description", "")
        last_pick   = c.get("last_pick", "")
        next_pick   = (c.get("cleaning_frequency") or {}).get("next_pick", "")
        measurement = c.get("last_measurement") or {}
        measured_at = measurement.get("measured_at_utc", "")
        pct         = measurement.get("percent_calculated", "")
        prediction  = measurement.get("prediction_utc", "")

        # Přeskoč pokud toto měření už máme
        if cid and last.get(cid) == measured_at:
            skipped += 1
            log(f"  [{trash_type}] přeskočeno — stejný timestamp ({measured_at})")
            continue

        new_rows.append([
            collected_at,
            station_id, station_name,
            cid, sensor_id, trash_type,
            pct, measured_at, prediction,
            last_pick, next_pick,
        ])
        log(f"  [{trash_type}] {pct}% — {measured_at}")

    if new_rows:
        append_rows(new_rows)
        log(f"Uloženo {len(new_rows)} nových záznamů, přeskočeno {skipped}.")
    else:
        log(f"Žádná nová data (všechna {skipped} měření jsou stejná jako naposledy).")

    log("--- Hotovo ---")


if __name__ == "__main__":
    collect()
    # Regeneruj HTML po každém sběru
    try:
        import build_html
        build_html.main()
    except Exception as e:
        log(f"build_html selhal: {e}")
        sys.exit(1)
