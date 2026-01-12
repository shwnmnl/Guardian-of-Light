// GUARDIAN OF LIGHT - FINITE STATE MACHINE
#include <LiquidCrystal.h>

LiquidCrystal lcd(7, 8, 9, 10, 11, 12);
const int sensorPin = A0;

const int T_NIGHT  = 220;
const int T_DUSK   = 350;
const int T_BRIGHT = 750;

const int H = 30;

enum LightState { NIGHT, DUSK, DAY, BRIGHT };
LightState state = DAY;

const char* stateName(LightState s) {
  switch (s) {
    case NIGHT:  return "NIGHT";
    case DUSK:   return "DUSK";
    case DAY:    return "DAY";
    case BRIGHT: return "BRIGHT";
  }
  return "DAY";
}

// Incoming message buffer from PC
// Message ends with '|' so we can include '\n' inside the message for row 2.
char inBuf[96];
byte inPos = 0;

void clearRow(byte row) {
  lcd.setCursor(0, row);
  for (byte i = 0; i < 16; i++) lcd.print(' ');
}

void displayTwoLineMessage(const char* s) {
  lcd.clear();
  clearRow(0);
  clearRow(1);

  lcd.setCursor(0, 0);

  byte row = 0;
  byte col = 0;

  for (int i = 0; s[i] != '\0'; i++) {
    char c = s[i];
    if (c == '\r') continue;

    if (c == '\n') {
      row = 1;
      col = 0;
      lcd.setCursor(0, 1);
      continue;
    }

    if (col >= 16) {
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

LightState updateStateWithHysteresis(LightState current, int v) {
  if (current == NIGHT) {
    if (v >= T_NIGHT + H) return DUSK;
    return NIGHT;
  }

  if (current == DUSK) {
    if (v <= T_NIGHT - H) return NIGHT;
    if (v >= T_DUSK + H)  return DAY;
    return DUSK;
  }

  if (current == DAY) {
    if (v <= T_DUSK - H)    return DUSK;
    if (v >= T_BRIGHT + H)  return BRIGHT;
    return DAY;
  }

  if (v <= T_BRIGHT - H) return DAY;
  return BRIGHT;
}

void setup() {
  lcd.begin(16, 2);
  Serial.begin(9600);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Guardian awakens");
  lcd.setCursor(0, 1);
  lcd.print("Watching light");

  delay(1500);
}

void loop() {
  int v = analogRead(sensorPin);

  LightState newState = updateStateWithHysteresis(state, v);

  if (newState != state) {
    state = newState;
    Serial.print("STATE:");
    Serial.print(stateName(state));
    Serial.print(":");
    Serial.println(v);
  }

  // Read message from PC until '|' terminator
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;

    if (c == '|') {
      inBuf[inPos] = '\0';
      inPos = 0;

      if (inBuf[0] != '\0') {
        displayTwoLineMessage(inBuf);
      }
    } else if (inPos < sizeof(inBuf) - 1) {
      inBuf[inPos++] = c;
    } else {
      // overflow protection, reset buffer
      inPos = 0;
    }
  }

  delay(200);
}
