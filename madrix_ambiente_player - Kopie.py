from flask import Flask, request, redirect, render_template_string
import requests
import threading
import time
import random
import json
import os

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from waitress import serve

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

running = False
worker_thread = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "madrix_ambiente_config.json")

settings = {
    "pc1": "http://192.168.0.10",
    "pc2": "http://192.168.0.11",
    "deck": "A",
    "storage_bank": 1,
    "scan_from": 1,
    "scan_to": 256,
    "effects": "S1P1,S1P2,S1P3",
    "interval": 15,
    "mode": "random"
}

# =========================================================
# SETTINGS SAVE / LOAD
# =========================================================

def load_settings():
    global settings

    print(f"Config file: {CONFIG_FILE}")

    if not os.path.exists(CONFIG_FILE):
        print("⚠️ No config file found, using default settings")
        return

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)

        settings.update(saved)

        print("✅ Settings loaded from config file")

    except Exception as e:
        print(f"❌ Could not load settings: {e}")


def save_settings():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)

        print(f"✅ Settings saved to config file: {CONFIG_FILE}")

    except Exception as e:
        print(f"❌ Could not save settings: {e}")

# =========================================================
# HTML
# =========================================================

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>MADRIX Ambiente Player</title>

<style>

body {
    background:#111;
    color:#fff;
    font-family:Arial,sans-serif;
    max-width:850px;
    margin:40px auto;
    padding:20px;
}

.box {
    background:#1f1f1f;
    padding:25px;
    border-radius:14px;
    margin-bottom:20px;
}

input, select, button {
    width:100%;
    padding:12px;
    margin-bottom:18px;
    font-size:16px;
    border-radius:8px;
    border:0;
    box-sizing:border-box;
}

input, select {
    background:#333;
    color:#fff;
}

button {
    background:#00c853;
    color:#000;
    font-weight:bold;
    cursor:pointer;
}

button.secondary {
    background:#2196f3;
    color:#fff;
}

.status {
    background:#063;
    padding:15px;
    border-radius:10px;
    margin-bottom:25px;
}

.grid {
    display:grid;
    grid-template-columns:1fr 1fr 1fr;
    gap:15px;
}

small {
    color:#999;
}

footer {
    text-align:center;
    margin-top:25px;
    font-size:0.8em;
    opacity:0.7;
}

a {
    color:#fff;
    text-decoration:none;
}

</style>
</head>

<body>

<h1>MADRIX Ambiente Player</h1>

<div class="status">
✅ Ambiente Player is running automatically
</div>

<div class="box">

<form method="post" action="/save">

<label>MADRIX PC 1</label>
<input name="pc1" value="{{ settings.pc1 }}">

<label>MADRIX PC 2</label>
<input name="pc2" value="{{ settings.pc2 }}">

<label>Deck</label>

<select name="deck">
    <option value="A" {% if settings.deck == "A" %}selected{% endif %}>Deck A</option>
    <option value="B" {% if settings.deck == "B" %}selected{% endif %}>Deck B</option>
</select>

<label>Effects</label>

<input name="effects" value="{{ settings.effects }}">

<small>
Manual list. You can delete unwanted auto-detected effects here.
Example: S1P1,S1P2,S2P5
</small>

<br><br>

<label>Change Interval Seconds</label>

<input type="number" min="1" name="interval" value="{{ settings.interval }}">

<label>Mode</label>

<select name="mode">
    <option value="random" {% if settings.mode == "random" %}selected{% endif %}>Random</option>
    <option value="sequence" {% if settings.mode == "sequence" %}selected{% endif %}>Sequence</option>
</select>

<button type="submit">
Save Settings
</button>

</form>

</div>

<div class="box">

<form method="post" action="/autodetect">

<h2>Auto Detect Effects</h2>

<div class="grid">

<div>
<label>Storage Bank S</label>
<input type="number" min="1" max="999" name="storage_bank" value="{{ settings.storage_bank }}">
</div>

<div>
<label>Scan From P</label>
<input type="number" min="1" max="999" name="scan_from" value="{{ settings.scan_from }}">
</div>

<div>
<label>Scan To P</label>
<input type="number" min="1" max="999" name="scan_to" value="{{ settings.scan_to }}">
</div>

</div>

<small>
Uses MADRIX PC 1 as source and checks which storage places are occupied.
Detected effects are written into the normal Effects field.
</small>

<br><br>

<button class="secondary" type="submit">
Auto Detect Occupied Effects
</button>

</form>

</div>

<footer>
<a href="https://verLEDung.com">
made with ♥ - verLEDung – LED & Veranstaltungstechnik
</a>
</footer>

</body>
</html>
"""

# =========================================================
# LOGGING
# =========================================================

def now():
    return datetime.now().strftime("%H:%M:%S")


def line(char="═", length=90):
    print(char * length)


def banner():
    print("\n")

    print("██╗   ██╗ ███████╗ ██████╗  ██╗      ███████╗ ██████╗  ██╗   ██╗ ███╗   ██╗  ██████╗ ")
    print("██║   ██║ ██╔════╝ ██╔══██╗ ██║      ██╔════╝ ██╔══██╗ ██║   ██║ ████╗  ██║ ██╔════╝ ")
    print("██║   ██║ █████╗   ██████╔╝ ██║      █████╗   ██║  ██║ ██║   ██║ ██╔██╗ ██║ ██║  ███╗")
    print("╚██╗ ██╔╝ ██╔══╝   ██╔══██╗ ██║      ██╔══╝   ██║  ██║ ██║   ██║ ██║╚██╗██║ ██║   ██║")
    print(" ╚████╔╝  ███████╗ ██║  ██║ ███████╗ ███████╗ ██████╔╝ ╚██████╔╝ ██║ ╚████║ ╚██████╔╝")
    print("  ╚═══╝   ╚══════╝ ╚═╝  ╚═╝ ╚══════╝ ╚══════╝ ╚═════╝   ╚═════╝  ╚═╝  ╚═══╝  ╚═════╝ ")

    print("")
    print("                 MADRIX Ambiente Random Effect Player")
    print("        made with love ♥ verLEDung - LED- & Veranstaltungstechnik")
    print("                         www.verLEDung.com")
    print("")

    line("═")


def log_info(msg):
    print(f"[{now()}] ℹ️  {msg}", flush=True)


def log_ok(msg):
    print(f"[{now()}] ✅ {msg}", flush=True)


def log_warn(msg):
    print(f"[{now()}] ⚠️  {msg}", flush=True)


def log_error(msg):
    print(f"[{now()}] ❌ {msg}", flush=True)

# =========================================================
# MADRIX INFO
# =========================================================

def read_madrix_value(base_url, cmd):

    try:
        url = base_url.rstrip("/") + f"/RemoteCommands/?{cmd}"

        r = requests.get(url, timeout=2)

        r.raise_for_status()

        return r.text.strip()

    except Exception:
        return "N/A"


def clean_version(value):

    value = value.replace("MADRIX", "").strip()

    parts = value.split()

    return parts[0] if parts else value


def print_pc_info(name, base_url):

    log_info(f"Reading {name} information...")

    host_label = read_madrix_value(base_url, "GetHostLabel")
    host_name = read_madrix_value(base_url, "GetHostName")
    version = clean_version(read_madrix_value(base_url, "GetVersion"))

    matrix_x = read_madrix_value(base_url, "GetMatrixSizeX")
    matrix_y = read_madrix_value(base_url, "GetMatrixSizeY")
    matrix_z = read_madrix_value(base_url, "GetMatrixSizeZ")

    print("")
    print(f"🖥️  {name}")
    print(f"   URL            : {base_url}")
    print(f"   Host Label     : {host_label}")
    print(f"   Host Name      : {host_name}")
    print(f"   MADRIX Version : {version}")
    print(f"   Matrix Size    : {matrix_x} x {matrix_y} x {matrix_z}")
    print("")


def startup_screen():

    banner()

    log_info("Starting MADRIX Ambiente Player...")

    print_pc_info("PC 1", settings["pc1"])
    print_pc_info("PC 2", settings["pc2"])

    line("─")

    log_ok("Ambiente Player is running automatically.")
    log_ok(f"Deck {settings['deck']} | Mode: {settings['mode']} | Interval: {settings['interval']}s")

    line("─")
    print("")

# =========================================================
# MADRIX COMMANDS
# =========================================================

def build_command(deck, effect):

    deck = deck.upper()

    if deck == "A":
        return f"/RemoteCommands/SetStorageDeckA={effect}"

    if deck == "B":
        return f"/RemoteCommands/SetStorageDeckB={effect}"

    return f"/RemoteCommands/SetStorageDeckA={effect}"


def send_effect_to_pc(base_url, deck, effect):

    url = base_url.rstrip("/") + build_command(deck, effect)

    try:
        response = requests.get(url, timeout=2)

        return response.status_code == 200

    except Exception as e:

        log_error(f"{base_url} -> {e}")

        return False


def send_effect_to_all(effect):

    pcs = [
        settings["pc1"],
        settings["pc2"]
    ]

    deck = settings["deck"]

    log_ok(f"Playing {effect} on Deck {deck}")

    with ThreadPoolExecutor(max_workers=2) as executor:

        for pc in pcs:

            executor.submit(
                send_effect_to_pc,
                pc,
                deck,
                effect
            )

# =========================================================
# AUTO DETECT
# =========================================================

def is_place_occupied(base_url, storage, place):

    value = read_madrix_value(
        base_url,
        f"GetStoragePlaceFullState=S{storage}P{place}"
    )

    return value == "1"


def auto_detect_effects():

    source_pc = settings["pc1"]

    storage = int(settings["storage_bank"])
    scan_from = int(settings["scan_from"])
    scan_to = int(settings["scan_to"])

    detected = []

    log_info(
        f"Auto detecting effects on PC 1: S{storage} P{scan_from} to P{scan_to}"
    )

    for place in range(scan_from, scan_to + 1):

        if is_place_occupied(source_pc, storage, place):

            effect = f"S{storage}P{place}"

            detected.append(effect)

            log_ok(f"Detected {effect}")

        time.sleep(0.03)

    if detected:

        settings["effects"] = ",".join(detected)

        save_settings()

        log_ok(
            f"Auto detect finished. {len(detected)} effects imported."
        )

    else:

        log_warn(
            "Auto detect finished. No occupied effects found."
        )

# =========================================================
# PLAYER LOOP
# =========================================================

def player_loop():

    global running

    index = 0
    last_effect = None

    while running:

        effects = [
            e.strip()
            for e in settings["effects"].split(",")
            if e.strip()
        ]

        if not effects:
            time.sleep(1)
            continue

        if settings["mode"] == "random":

            effect = random.choice(effects)

            if len(effects) > 1:

                while effect == last_effect:
                    effect = random.choice(effects)

        else:

            effect = effects[index % len(effects)]

            index += 1

        last_effect = effect

        send_effect_to_all(effect)

        interval = int(settings["interval"])

        for _ in range(interval):

            if not running:
                break

            time.sleep(1)

# =========================================================
# WEB ROUTES
# =========================================================

@app.route("/")
def index():

    return render_template_string(
        HTML,
        settings=settings
    )


@app.route("/save", methods=["POST"])
def save():

    settings["pc1"] = request.form.get("pc1", "").strip()

    settings["pc2"] = request.form.get("pc2", "").strip()

    settings["deck"] = request.form.get("deck", "A")

    settings["effects"] = request.form.get("effects", "")

    settings["interval"] = int(
        request.form.get("interval", 15)
    )

    settings["mode"] = request.form.get("mode", "random")

    save_settings()

    log_info("Settings updated via web interface.")

    return redirect("/")


@app.route("/autodetect", methods=["POST"])
def autodetect():

    settings["storage_bank"] = int(
        request.form.get("storage_bank", 1)
    )

    settings["scan_from"] = int(
        request.form.get("scan_from", 1)
    )

    settings["scan_to"] = int(
        request.form.get("scan_to", 256)
    )

    auto_detect_effects()

    save_settings()

    return redirect("/")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    load_settings()

    startup_screen()

    running = True

    worker_thread = threading.Thread(
        target=player_loop,
        daemon=True
    )

    worker_thread.start()

    serve(
        app,
        host="0.0.0.0",
        port=5050
    )