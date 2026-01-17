#include <LiquidCrystal.h>

// ============================
// User Config (edit here)
// ============================
namespace Config {
  // LCD wiring (parallel)
  constexpr uint8_t LCD_RS = 7;
  constexpr uint8_t LCD_EN = 8;
  constexpr uint8_t LCD_D4 = 9;
  constexpr uint8_t LCD_D5 = 10;
  constexpr uint8_t LCD_D6 = 11;
  constexpr uint8_t LCD_D7 = 12;

  constexpr uint8_t LCD_COLS = 16;
  constexpr uint8_t LCD_ROWS = 2;

  constexpr uint8_t SENSOR_PIN = A0;

  constexpr unsigned long BAUD = 9600;
  constexpr uint16_t LOOP_DELAY_MS = 200;

  constexpr int HYST = 30;

  constexpr size_t INBUF_SIZE = 96;
  constexpr char MSG_END = '|';

  constexpr const char* BOOT_LINE_1 = "Guardian awakens";
  constexpr const char* BOOT_LINE_2 = "Watching light";

  // Define your states from darkest to brightest.
  // Rename freely.
  constexpr const char* STATE_NAMES[] = {
    "NIGHT",
    "DUSK",
    "DAY",
    "BRIGHT"
  };

  // Define the boundaries between adjacent states.
  // Must be strictly increasing.
  // Length must be (number of states - 1).
  constexpr int BOUNDARIES[] = {
    220,  // between STATE_NAMES[0] and [1]
    350,  // between STATE_NAMES[1] and [2]
    450   // between STATE_NAMES[2] and [3]
  };

  // Choose the startup state index (0..N-1)
  constexpr uint8_t START_STATE_INDEX = 2; // "DAY"
}

// ============================
// Compile time checks
// ============================
constexpr size_t STATE_COUNT = sizeof(Config::STATE_NAMES) / sizeof(Config::STATE_NAMES[0]);
constexpr size_t BOUNDARY_COUNT = sizeof(Config::BOUNDARIES) / sizeof(Config::BOUNDARIES[0]);

static_assert(STATE_COUNT >= 2, "Need at least 2 states.");
static_assert(BOUNDARY_COUNT + 1 == STATE_COUNT, "BOUNDARIES must have (states - 1) entries.");

LiquidCrystal lcd(
  Config::LCD_RS, Config::LCD_EN,
  Config::LCD_D4, Config::LCD_D5, Config::LCD_D6, Config::LCD_D7
);

char inBuf[Config::INBUF_SIZE];
uint8_t inPos = 0;

uint8_t stateIndex = Config::START_STATE_INDEX;

void clearRow(uint8_t row) {
  lcd.setCursor(0, row);
  for (uint8_t i = 0; i < Config::LCD_COLS; i++) lcd.print(' ');
}

void displayTwoLineMessage(const char* s) {
  lcd.clear();
  clearRow(0);
  clearRow(1);

  uint8_t row = 0;
  uint8_t col = 0;
  lcd.setCursor(0, 0);

  for (size_t i = 0; s[i] != '\0'; i++) {
    char c = s[i];
    if (c == '\r') continue;

    if (c == '\n') {
      row = 1;
      col = 0;
      lcd.setCursor(0, 1);
      continue;
    }

    if (col >= Config::LCD_COLS) {
      if (row == 0) {
        row = 1;
        col = 0;
        lcd.setCursor(0, 1);
      } else {
        break;
      }
    }

    lcd.print(c);
    col++;
  }
}

// Generic hysteresis update for any number of ordered states.
// stateIndex ranges 0..STATE_COUNT-1.
// BOUNDARIES[i] is boundary between state i and state i+1.
uint8_t updateStateWithHysteresis(uint8_t current, int v) {
  const int h = Config::HYST;

  // Move down if we're below the lower boundary minus hysteresis
  if (current > 0) {
    int lowerBoundary = Config::BOUNDARIES[current - 1];
    if (v <= lowerBoundary - h) return current - 1;
  }

  // Move up if we're above the upper boundary plus hysteresis
  if (current < STATE_COUNT - 1) {
    int upperBoundary = Config::BOUNDARIES[current];
    if (v >= upperBoundary + h) return current + 1;
  }

  return current;
}

void emitStateChange(uint8_t idx, int v) {
  Serial.print("STATE:");
  Serial.print(Config::STATE_NAMES[idx]);
  Serial.print(":");
  Serial.println(v);
}

void readSerialMessageAndDisplay() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;

    if (c == Config::MSG_END) {
      inBuf[inPos] = '\0';
      inPos = 0;
      if (inBuf[0] != '\0') displayTwoLineMessage(inBuf);
    } else if (inPos < Config::INBUF_SIZE - 1) {
      inBuf[inPos++] = c;
    } else {
      inPos = 0;
    }
  }
}

void setup() {
  lcd.begin(Config::LCD_COLS, Config::LCD_ROWS);
  Serial.begin(Config::BAUD);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(Config::BOOT_LINE_1);
  lcd.setCursor(0, 1);
  lcd.print(Config::BOOT_LINE_2);
  delay(1500);

  // Clamp start state in case someone edits arrays
  if (stateIndex >= STATE_COUNT) stateIndex = 0;
}

void loop() {
  int v = analogRead(Config::SENSOR_PIN);

  uint8_t newIndex = updateStateWithHysteresis(stateIndex, v);
  if (newIndex != stateIndex) {
    stateIndex = newIndex;
    emitStateChange(stateIndex, v);
  }

  readSerialMessageAndDisplay();
  delay(Config::LOOP_DELAY_MS);
}
