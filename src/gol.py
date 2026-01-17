# GUARDIAN OF LIGHT - RESTORED API SERVER
import os
import json
import time
import serial
import hashlib
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from openai import OpenAI

# --- ORIGINAL CONFIG & PATHS ---
PORT = os.getenv("ARDUINO_PORT")
BAUD = 9600
API_PORT = 8080

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
WEB_OUTFILE = os.path.join(ROOT_DIR, "latest.json")
LCD_OUTFILE = os.path.join(ROOT_DIR, "latest_lcd.txt")
AUDIO_DIR = os.path.join(ROOT_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Clients
client = OpenAI()
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Constants
COLS, ROWS = 16, 2
STABLE_SECONDS = 3.5
COOLDOWN_SECONDS = 20.0
REARM_SAME_STATE = 20.0
CACHE_TTL = 120.0

VOICE_BY_STATE = {
    "NIGHT": "XjdmlV0OFXfXE6Mg2Sb7",
    "DUSK": "ruirxsoakN0GWmGNIo04",
    "DAY": "wo6udizrrtpIxWGp2qJk",
    "BRIGHT": "wo6udizrrtpIxWGp2qJk",
}

# --- GLOBAL STATE ---
SYSTEM_STATE = {
    "telemetry": {"value": 0, "state": "NIGHT", "ts": None},
    "missive": {
        "msg_id": 0,
        "state": "NIGHT",
        "scroll": "The guardian awakens. Waiting for a shift in the light...",
        "audio": None,
        "ts": None
    },
    "live": True,
    "heartbeat_ts": None
}

# Internals
msg_counter = 0
last_fired_at = 0.0
last_fired_state = None
state_cache = {}
audio_cache = {}

# --- UTILITIES ---
def log(*args):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *args, flush=True)

def iso_utc():
    return datetime.now(timezone.utc).isoformat()

def now_s():
    return time.monotonic()

def wrap_16x2(text: str, cols: int = 16, rows: int = 2) -> str:
    text = " ".join((text or "").replace("\n", " ").split())
    words = text.split(" ")
    lines, current = [], ""
    for w in words:
        if not w: continue
        if len(w) > cols: w = w[:cols]
        candidate = w if current == "" else current + " " + w
        if len(candidate) <= cols: current = candidate
        else:
            if current: lines.append(current)
            current = w
            if len(lines) == rows: break
    if len(lines) < rows and current: lines.append(current)
    while len(lines) < rows: lines.append("")
    return "\n".join(lines[:rows])

# --- API SERVER ---
class GuardianAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            SYSTEM_STATE["heartbeat_ts"] = iso_utc()
            self.wfile.write(json.dumps(SYSTEM_STATE).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args): return

def run_server():
    server = HTTPServer(('0.0.0.0', API_PORT), GuardianAPI)
    log(f"WEB: API Server active at http://localhost:{API_PORT}/status")
    server.serve_forever()

# --- NARRATIVE LOGIC ---
def build_prompt(state: str, value: int) -> str:
    vibe_by_state = {"NIGHT": "nightfall...", "DUSK": "twilight...", "DAY": "daybreak...", "BRIGHT": "glare..."}
    return (
        "You are a gothic observer: a polite villain with grave, playful wit.\n"
        "Output ONLY valid JSON.\n"
        "Schema: {\"lcd\": \"LINE1\\nLINE2\", \"scroll\": \"2-3 sentences\"}\n"
        "Rules for lcd:\n"
        "Exactly 2 lines separated by a single newline.\n"
        "Each line length must be 1 to 16 characters.\n"
        "ASCII only.\n"
        "\n"
        "Rules for scroll:\n"
        "Exactly 2 or 3 sentences.\n"
        "ASCII only.\n"
        "Old fashioned but readable. Calm, slightly ominous, dryly amused.\n"
        "\n"
        f"Inputs for atmosphere only: scene={state}, sensor={value}, vibe={vibe_by_state.get(state, 'unknown')}.\n"
        "Never mention the sensor or include numbers.\n"
    )

def generate_llm_bundle(state: str, value: int) -> dict:
    log(f"LLM: Requesting narrative for {state} (Sensor: {value})")
    try:
        # Use ChatCompletion with explicit JSON mode
        resp = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "You are a gothic observer. Output ONLY valid JSON."},
                {"role": "user", "content": build_prompt(state, value)}
            ],
            response_format={ "type": "json_object" }
        )
        
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        
        # Validation: Ensure keys exist so get_tts doesn't receive 'None'
        if "scroll" not in data or "lcd" not in data:
            raise KeyError("Missing 'scroll' or 'lcd' in LLM response")
            
        return data
        
    except Exception as e:
        log(f"LLM: Error - {e}")
        # Fallback bundle to prevent the whole fire() sequence from crashing
        return {
            "lcd": "The stars align\nin silence.",
            "scroll": "The void offers no words for this light. I remain, watching and waiting."
        }
        
    except Exception as e:
        log(f"LLM: Detailed Error: {str(e)}")
        # Return a fallback bundle so the script doesn't stop
        return {
            "lcd": "Signal falters\nTry again",
            "scroll": "The void is silent for now. Perhaps the light is not yet right."
        }
    
    
def get_tts(state: str, text: str, msg_id: int) -> str:
    voice_id = VOICE_BY_STATE.get(state)
    if not voice_id:
        log(f"TTS: No voice ID found for state {state}")
        return None
    if not ELEVEN_API_KEY:
        log("TTS: Missing API Key")
        return None

    # Ensure text is clean and not empty
    clean_text = text.strip()
    if not clean_text:
        log("TTS: Skipped (empty text)")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY, 
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    
    # We use a standard model and lower stability for more 'gothic' expression
    payload = {
        "text": clean_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req) as resp:
            audio_bytes = resp.read()
        
        filename = f"msg_{msg_id}.mp3"
        path = os.path.join(AUDIO_DIR, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        
        log(f"TTS: Success! Saved to {filename}")
        return f"audio/{filename}"
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        log(f"TTS: HTTP Error {e.code}: {error_body}") # This tells us EXACTLY why it's 'Bad Request'
        return None
    except Exception as e:
        log(f"TTS: Unexpected Error: {e}")
        return None

def fire(ser, state, value):
    global msg_counter, last_fired_at, last_fired_state
    log("FIRE: Start sequence for", state)
    
    try:
        # 1. Generate Narrative
        bundle = generate_llm_bundle(state, value)
        
        # 2. Extract and sanitize
        lcd_text = bundle.get("lcd", "Signal Lost")
        scroll_text = bundle.get("scroll", "The guardian is silent.")
        
        # 3. Handle LCD / Serial
        lcd_wrapped = wrap_16x2(lcd_text, COLS, ROWS)
        with open(LCD_OUTFILE, "w") as f: 
            f.write(lcd_wrapped)
            
        # Send to Arduino with the | terminator
        ser.write((lcd_wrapped.replace("\n", " ") + "|").encode())
        log("SERIAL: LCD updated")

        # 4. Handle TTS (Only if scroll_text is valid)
        msg_counter += 1
        audio_file = None
        if scroll_text.strip():
            audio_file = get_tts(state, scroll_text, msg_counter)
        else:
            log("TTS: Skipped - Scroll text empty")

        # 5. Atomic State Update
        SYSTEM_STATE["missive"] = {
            "msg_id": msg_counter,
            "state": state,
            "scroll": scroll_text,
            "audio": audio_file,
            "ts": iso_utc()
        }
        
        # Sync to disk for web fallback
        with open(WEB_OUTFILE, "w") as f: 
            json.dump(SYSTEM_STATE, f)

        # 6. Cooldown management
        last_fired_at = now_s()
        last_fired_state = state
        log(f"FIRE: Complete. ID: {msg_counter}, State: {state}")
        
    except Exception as e:
        log("FIRE: Critical Failure -", e)

# --- MAIN LOOP ---
def main():
    if not PORT: raise RuntimeError("ARDUINO_PORT not set")
    threading.Thread(target=run_server, daemon=True).start()

    with serial.Serial(PORT, BAUD, timeout=0.1) as ser:
        log("SERIAL: connected", PORT)
        time.sleep(2)

        pending_state, pending_value, pending_since = None, None, 0

        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if line.startswith("STATE:"):
                log("ARDUINO:", line)
                parts = line.split(":")
                if len(parts) == 3:
                    st, val = parts[1].upper(), int(parts[2])
                    SYSTEM_STATE["telemetry"] = {"value": val, "state": st, "ts": iso_utc()}
                    
                    if st != pending_state:
                        log("CANDIDATE:", st, "value", val)
                        pending_state, pending_value, pending_since = st, val, now_s()

            if pending_state:
                if (now_s() - pending_since) >= STABLE_SECONDS:
                    can_fire = (now_s() - last_fired_at) > COOLDOWN_SECONDS
                    is_diff = pending_state != last_fired_state
                    
                    if can_fire and is_diff:
                        fire(ser, pending_state, pending_value)
                    elif not can_fire:
                        log("SKIP: cooldown active")
                    pending_state = None

            time.sleep(0.01)

if __name__ == "__main__":
    main()