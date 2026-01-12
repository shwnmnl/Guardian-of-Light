# GUARDIAN OF LIGHT - MISSIVE FROM ABOVE
import os
import time
import random
import serial
from openai import OpenAI

PORT = os.getenv("ARDUINO_PORT")
BAUD = 9600

COLS = 16
ROWS = 2
OUTFILE = "latest_lcd.txt"

client = OpenAI()

def wrap_16x2(text: str, cols: int = 16, rows: int = 2) -> str:
    text = " ".join(text.replace("\n", " ").split())
    words = text.split(" ")

    lines = []
    current = ""

    for w in words:
        if not w:
            continue

        if len(w) > cols:
            w = w[:cols]

        candidate = w if current == "" else current + " " + w
        if len(candidate) <= cols:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
            if len(lines) == rows:
                break

    if len(lines) < rows and current:
        lines.append(current)

    while len(lines) < rows:
        lines.append("")

    return "\n".join(lines[:rows])

def build_prompt(state: str, value: int) -> str:
    vibe_by_state = {
        "NIGHT":  "nightfall, hush, shadows",
        "DUSK":   "twilight, fading, in between",
        "DAY":    "daybreak, return, awake",
        "BRIGHT": "glare, blaze, too much sun",
    }
    vibe = vibe_by_state.get(state, "light shift")

    return (
        "You are a gothic observer: a polite villain with grave, playful wit.\n"
        "Write text for a 16x2 character LCD.\n"
        "\n"
        "Output rules (must follow exactly):\n"
        "Return EXACTLY 2 lines.\n"
        "Each line must be 16 characters or fewer (count spaces and punctuation).\n"
        "Total across both lines must be 32 characters or fewer, plus exactly one newline.\n"
        "Use only plain ASCII.\n"
        "No emojis. No quotes. No extra text.\n"
        "Prefer short words. If unsure, make it shorter.\n"
        "\n"
        "Voice rules:\n"
        "Calm, slightly ominous, dryly amused.\n"
        "Old-fashioned but readable. No modern slang.\n"
        "Short sentences or fragments. Strong verbs.\n"
        "\n"
        "Example format:\n"
        "Night creeps in\n"
        "As expected\n"
        "\n"
        f"State: {state}\n"
        f"Light value: {value}\n"
        f"Vibe: {vibe}\n"
        "\n"
        "Now write the LCD text.\n"
    )

def generate_llm_text(state: str, value: int) -> str:
    resp = client.responses.create(
        model="gpt-5.2",
        input=build_prompt(state, value),
        reasoning={"effort": "none"},
        temperature=0.9,
        max_output_tokens=60,
    )
    return resp.output_text.strip()

def write_file(text: str) -> None:
    with open(OUTFILE, "w", encoding="utf-8") as f:
        f.write(text)

def read_file() -> str:
    with open(OUTFILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def send_to_arduino(ser: serial.Serial, text_2_lines: str) -> None:
    payload = text_2_lines + "|"
    ser.write(payload.encode("utf-8"))

def main():
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        time.sleep(2)

        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            print("ARDUINO:", line)

            if line.startswith("STATE:"):
                parts = line.split(":")
                if len(parts) != 3:
                    continue

                state = parts[1].strip()
                try:
                    value = int(parts[2].strip())
                except ValueError:
                    continue

                raw = generate_llm_text(state, value)
                formatted = wrap_16x2(raw, COLS, ROWS)

                write_file(formatted)

                file_text = read_file()
                send_to_arduino(ser, file_text)

if __name__ == "__main__":
    main()
