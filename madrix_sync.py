import time
import requests
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

MASTER = "http://192.168.0.11/RemoteCommands"
SLAVE  = "http://192.168.0.10/RemoteCommands"

REQUEST_TIMEOUT = 2.0
REQUEST_DELAY = 0.08

EFFECT_POLL_INTERVAL = 1.0
PARAMETER_POLL_INTERVAL = 3.0
STARTUP_RETRY_DELAY = 1.5
STARTUP_MAX_RETRIES = 20

# =========================================================
# INTERNAL
# =========================================================

last_values = {}
last_effect_poll = 0
last_parameter_poll = 0
error_count = 0

session = requests.Session()

# =========================================================
# STYLE / LOGGING
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
    print("                      MADRIX Deck B Sync Tool")
    print("        made with love ♥ verLEDung - LED- & Veranstaltungstechnik")
    print("                         www.verLEDung.com")
    print("")
    line("═")
    print("")


def log_ok(msg):
    print(f"[{now()}] ✅ {msg}", flush=True)


def log_info(msg):
    print(f"[{now()}] ℹ️  {msg}", flush=True)


def log_warn(msg):
    print(f"[{now()}] ⚠️  {msg}", flush=True)


def log_error(msg):
    print(f"[{now()}] ❌ {msg}", flush=True)

# =========================================================
# HTTP HELPERS
# =========================================================

def is_invalid_response(value):
    lower = value.lower()
    return "<html" in lower or "<!doctype" in lower


def request_value(base_url, cmd, retries=2):
    url = f"{base_url}/?{cmd}"

    last_error = None

    for attempt in range(retries + 1):
        try:
            time.sleep(REQUEST_DELAY)

            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()

            value = r.text.strip()

            if is_invalid_response(value):
                raise ValueError(f"Invalid MADRIX response for {cmd}")

            return value

        except Exception as e:
            last_error = e
            time.sleep(0.25)

    raise last_error


def set_value(base_url, cmd, retries=2):
    url = f"{base_url}/{cmd}"

    last_error = None

    for attempt in range(retries + 1):
        try:
            time.sleep(REQUEST_DELAY)

            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()

            return r.text.strip()

        except Exception as e:
            last_error = e
            time.sleep(0.25)

    raise last_error


def get_master(cmd):
    return request_value(MASTER, cmd)


def get_slave(cmd):
    return request_value(SLAVE, cmd)


def set_slave(cmd):
    return set_value(SLAVE, cmd)


def changed(key, value):
    old = last_values.get(key)

    if old != value:
        last_values[key] = value
        return True

    return False

# =========================================================
# MADRIX INFO
# =========================================================

def clean_version(value):
    value = value.replace("MADRIX", "").strip()
    parts = value.split()
    return parts[0] if parts else value


def read_info_value(base_url, cmd):
    try:
        return request_value(base_url, cmd, retries=3)
    except Exception:
        return None


def get_info_data(base_url):
    commands = {
        "Host Label": "GetHostLabel",
        "Host Name": "GetHostName",
        "Version": "GetVersion",
        "Matrix X": "GetMatrixSizeX",
        "Matrix Y": "GetMatrixSizeY",
        "Matrix Z": "GetMatrixSizeZ",
    }

    info = {}

    for label, cmd in commands.items():
        info[label] = read_info_value(base_url, cmd)
        time.sleep(0.2)

    required = ["Host Label", "Version"]
    success = all(info.get(key) for key in required)

    return success, info


def wait_for_info(name, base_url):
    for attempt in range(1, STARTUP_MAX_RETRIES + 1):
        log_info(f"Reading {name} system information... attempt {attempt}/{STARTUP_MAX_RETRIES}")

        success, info = get_info_data(base_url)

        if success:
            version = clean_version(info.get("Version", "N/A"))

            print("")
            print(f"🖥️  {name}")
            print(f"   Host Label     : {info.get('Host Label') or 'N/A'}")
            print(f"   Host Name      : {info.get('Host Name') or 'N/A'}")
            print(f"   MADRIX Version : {version}")
            print(f"   Matrix Size    : {info.get('Matrix X') or 'N/A'} x {info.get('Matrix Y') or 'N/A'} x {info.get('Matrix Z') or 'N/A'}")
            print("")

            return True

        log_warn(f"{name} not ready yet.")
        time.sleep(STARTUP_RETRY_DELAY)

    log_error(f"{name} information could not be read.")
    return False


def startup_info():
    log_info("Starting MADRIX connection check...")
    print("")

    master_ok = wait_for_info("PC A / MASTER", MASTER)
    slave_ok = wait_for_info("PC B / SLAVE", SLAVE)

    line("─")

    if master_ok and slave_ok:
        log_ok("Both MADRIX systems are online.")
    else:
        log_warn("One or both MADRIX systems had startup issues. Sync will still keep trying.")

    log_ok("Sync ready. Deck B is now being mirrored.")
    line("─")
    print("")

# =========================================================
# SYNC FUNCTIONS
# =========================================================

def sync_value(key, get_cmd_name, set_cmd_name, label):
    value = get_master(get_cmd_name)

    if changed(key, value):
        set_slave(f"{set_cmd_name}={value}")
        log_ok(f"{label:<24} → {value}")


def sync_storage_deck_b():
    storage = get_master("GetStorageDeckB")
    place = get_master("GetStoragePlaceDeckB")

    state = f"S{storage}P{place}"

    if changed("storage_deck_b", state):
        set_slave(f"SetStorageDeckB={state}")
        log_ok(f"{'Deck B Effect':<24} → {state}")


def sync_speed_pause():
    master_value = get_master("GetStorageSpeedPauseDeckB")

    if changed("deck_b_speed_pause", master_value):
        slave_value = get_slave("GetStorageSpeedPauseDeckB")

        if slave_value != master_value:
            set_slave("SetStorageSpeedPauseToggleDeckB")
            state = "PAUSE" if master_value == "1" else "PLAY"
            log_ok(f"{'Deck B Speed State':<24} → {state}")


def sync_effects_only():
    sync_storage_deck_b()


def sync_parameters():
    sync_value(
        "deck_b_brightness",
        "GetSubmasterDeckB",
        "SetSubmasterDeckB",
        "Deck B Brightness"
    )

    sync_value(
        "deck_b_speed",
        "GetStorageSpeedDeckB",
        "SetStorageSpeedDeckB",
        "Deck B Speed"
    )

    sync_speed_pause()

    sync_value(
        "deck_b_filter",
        "GetFilterDeckB",
        "SetFilterDeckB",
        "Deck B Filter"
    )

    sync_value(
        "deck_b_filter_red",
        "GetStorageFilterRedDeckB",
        "SetStorageFilterRedDeckB",
        "Deck B Filter Red"
    )

    sync_value(
        "deck_b_filter_green",
        "GetStorageFilterGreenDeckB",
        "SetStorageFilterGreenDeckB",
        "Deck B Filter Green"
    )

    sync_value(
        "deck_b_filter_blue",
        "GetStorageFilterBlueDeckB",
        "SetStorageFilterBlueDeckB",
        "Deck B Filter Blue"
    )

    sync_value(
        "deck_b_filter_white",
        "GetStorageFilterWhiteDeckB",
        "SetStorageFilterWhiteDeckB",
        "Deck B Filter White"
    )

    sync_value(
        "effect_brightness",
        "GetStoragePlaceSubmasterDeckB",
        "SetStoragePlaceSubmasterDeckB",
        "Effect Brightness"
    )

    sync_value(
        "effect_filter",
        "GetStoragePlaceFilterDeckB",
        "SetStoragePlaceFilterDeckB",
        "Effect Filter"
    )

    sync_value(
        "effect_pitch",
        "GetStoragePlacePitchDeckB",
        "SetStoragePlacePitchDeckB",
        "Effect Pitch"
    )

# =========================================================
# MAIN
# =========================================================

banner()
startup_info()

while True:
    try:
        current_time = time.monotonic()

        if current_time - last_effect_poll >= EFFECT_POLL_INTERVAL:
            sync_effects_only()
            last_effect_poll = current_time

        if current_time - last_parameter_poll >= PARAMETER_POLL_INTERVAL:
            sync_parameters()
            last_parameter_poll = current_time

        error_count = 0
        time.sleep(0.05)

    except KeyboardInterrupt:
        print("")
        line("─")
        log_warn("Sync stopped. Bye :(")
        line("─")
        break

    except Exception as e:
        error_count += 1

        if error_count == 1 or error_count % 10 == 0:
            log_error(f"Sync error: {e}")

        time.sleep(1.0)