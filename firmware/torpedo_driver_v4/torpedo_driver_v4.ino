// Torpedo driver v4 firmware - ESP32-C3 SuperMini (Arduino-ESP32 core 2.x or 3.x)
//
// Safety rules enforced here (hardware cannot do them on its own):
//   * every fire pulse is ended by a one-shot hardware timer, never by the main loop; hard cap MAX_PULSE_MS
//   * task watchdog: if the loop stalls for WDT_MS the chip panics and reboots, which releases every output
//   * the board must pass the self-test before it can be armed; the arm window closes on its own (arm_ms)
//   * a channel only fires if its solenoid is connected and the battery is above vmin
//
// Isolated sensing: the ADS1115 sits on the power side. The ESP talks to it through optocouplers:
//   GPIO5 -> U5 (SCL), GPIO6 -> U6 (SDA out), U7 -> GPIO7 (SDA read-back). Output HIGH pulls the line LOW.
//   PC817s are slow (worst edge 142 us in simulation), so the bit-banged I2C uses a 500 us half-bit.
//
// Serial commands (USB, 115200 baud, one per line):
//   STATUS | TEST | ARM | DISARM | FIRE 1|2 [ms] | CAL <volts> | SET VMIN <v> | SET PULSE <ms> | SET ARMTIME <ms> | HELP

#include <Arduino.h>
#include <Preferences.h>
#include <esp_task_wdt.h>
#include "esp_timer.h"

// ------------------------------------------------------------------ pins (see the back silkscreen)
const int PIN_FIRE1 = 1, PIN_FIRE2 = 0, PIN_ARM = 10;
const int PIN_SCL_TX = 5, PIN_SDA_TX = 6, PIN_SDA_RX = 7;
const int PIN_LED = 8;                       // SuperMini blue LED, active low: on while armed

// ------------------------------------------------------------------ limits and defaults
const uint32_t MAX_PULSE_MS = 500;           // hard cap, not configurable over serial
const uint32_t MIN_GAP_MS = 300;             // between pulses: flyback decay and coil cooling
const uint32_t WDT_MS = 2000;
const uint32_t HALF_BIT_US = 500;            // opto I2C half-bit (>= 2x worst simulated edge of 142 us)
const float DIVIDER = 11.0f;                  // 200k / 20k
const float ADC_LSB = 2.048f / 32768.0f;     // ADS1115 PGA +-2.048 V
const float VBAT_MAX = 17.6f;                // above a full 4S (and LiHV) means wrong battery
const float RATIO_IDLE_MIN = 0.30f, RATIO_IDLE_MAX = 0.80f;   // VSW/VBAT disarmed: 0.51 both coils, 0.60 one, 0.76 none
const float RATIO_ARMED_MIN = 0.95f;
const float COIL_OK = 0.85f, COIL_OPEN = 0.20f;               // DxN/VSW disarmed
const float FIRE_LOW = 0.10f;                                 // DxN/VBAT while the MOSFET is on

struct Settings { float gain = 1.0f; float vmin = 14.4f; uint32_t pulse_ms = 200; uint32_t arm_ms = 10000; } cfg;
Preferences prefs;

struct Reading { bool ok = false; float vbat = 0, vsw = 0, d1n = 0, d2n = 0; };
struct TestResult { bool pass = false; bool coil1 = false, coil2 = false; String why; Reading r; };

volatile bool armed = false;
uint32_t armedAt = 0, lastFire = 0;
bool haveFired = false;
String lastFault = "none";
esp_timer_handle_t fireTimer = nullptr, armTimer = nullptr;

// ------------------------------------------------------------------ outputs
void allOff() {
  digitalWrite(PIN_FIRE1, LOW); digitalWrite(PIN_FIRE2, LOW);
  digitalWrite(PIN_ARM, LOW); digitalWrite(PIN_LED, HIGH);
}
void fireOffCb(void*) { digitalWrite(PIN_FIRE1, LOW); digitalWrite(PIN_FIRE2, LOW); }
void armOffCb(void*) { allOff(); armed = false; }

void disarm(const char* why) {
  esp_timer_stop(fireTimer); esp_timer_stop(armTimer);
  allOff(); armed = false;
  if (why && *why) lastFault = why;
}

// ------------------------------------------------------------------ opto-isolated I2C (bit-banged)
inline void wait(uint32_t us) { delayMicroseconds(us); }
inline void sclLow() { digitalWrite(PIN_SCL_TX, HIGH); }     // LED on -> line pulled low
inline void sclRelease() { digitalWrite(PIN_SCL_TX, LOW); }
inline void sdaLow() { digitalWrite(PIN_SDA_TX, HIGH); }
inline void sdaRelease() { digitalWrite(PIN_SDA_TX, LOW); }
inline bool sdaIsHigh() { return digitalRead(PIN_SDA_RX) == HIGH; }

void i2cStart() {            // SDA falls while SCL is high
  sdaRelease(); sclRelease(); wait(HALF_BIT_US);
  sdaLow(); wait(HALF_BIT_US);
  sclLow(); wait(HALF_BIT_US / 2);
}
void i2cStop() {             // SDA rises while SCL is high
  sdaLow(); wait(HALF_BIT_US / 2);
  sclRelease(); wait(HALF_BIT_US);
  sdaRelease(); wait(HALF_BIT_US);
}
// SCL is low on entry and on exit. Data changes only half way through the low phase, so a slow SDA edge
// can never cross a slow SCL edge (that would look like START/STOP to the ADS1115).
bool i2cWriteByte(uint8_t b) {
  for (int i = 7; i >= 0; --i) {
    if (b & (1 << i)) sdaRelease(); else sdaLow();
    wait(HALF_BIT_US / 2);
    sclRelease(); wait(HALF_BIT_US);
    sclLow(); wait(HALF_BIT_US / 2);
  }
  sdaRelease(); wait(HALF_BIT_US / 2);
  sclRelease(); wait(HALF_BIT_US);
  bool ack = !sdaIsHigh();
  sclLow(); wait(HALF_BIT_US / 2);
  return ack;
}
uint8_t i2cReadByte(bool ack) {
  uint8_t v = 0; sdaRelease();
  for (int i = 7; i >= 0; --i) {
    wait(HALF_BIT_US / 2);
    sclRelease(); wait(HALF_BIT_US);
    if (sdaIsHigh()) v |= (1 << i);
    sclLow(); wait(HALF_BIT_US / 2);
  }
  if (ack) sdaLow(); else sdaRelease();
  wait(HALF_BIT_US / 2);
  sclRelease(); wait(HALF_BIT_US);
  sclLow(); wait(HALF_BIT_US / 2);
  sdaRelease();
  return v;
}

// ------------------------------------------------------------------ ADS1115
const uint8_t ADS_ADDR = 0x48;
bool adsWriteReg(uint8_t reg, uint16_t val) {
  i2cStart();
  bool ok = i2cWriteByte(ADS_ADDR << 1) && i2cWriteByte(reg) && i2cWriteByte(val >> 8) && i2cWriteByte(val & 0xFF);
  i2cStop(); return ok;
}
bool adsReadReg(uint8_t reg, int16_t& out) {
  i2cStart();
  bool ok = i2cWriteByte(ADS_ADDR << 1) && i2cWriteByte(reg);
  i2cStop();
  if (!ok) return false;
  i2cStart();
  ok = i2cWriteByte((ADS_ADDR << 1) | 1);
  if (ok) { uint8_t hi = i2cReadByte(true), lo = i2cReadByte(false); out = (int16_t)((hi << 8) | lo); }
  i2cStop(); return ok;
}
// single-shot, AINx vs GND, PGA +-2.048 V, 128 SPS, comparator off
bool adsReadVolts(uint8_t ch, float& v) {
  uint16_t cfgw = 0x8583 | ((uint16_t)(4 + ch) << 12);
  if (!adsWriteReg(0x01, cfgw)) return false;
  delay(10);
  int16_t raw;
  if (!adsReadReg(0x00, raw)) return false;
  v = raw * ADC_LSB * DIVIDER * cfg.gain;
  return true;
}
Reading readAll() {
  Reading r; float v[4];
  for (uint8_t ch = 0; ch < 4; ++ch) {
    if (!adsReadVolts(ch, v[ch])) { r.ok = false; return r; }
    esp_task_wdt_reset();
  }
  r.ok = true; r.vbat = v[0]; r.vsw = v[1]; r.d1n = v[2]; r.d2n = v[3];
  return r;
}

// ------------------------------------------------------------------ self-test (disarmed)
TestResult selfTest() {
  TestResult t; t.r = readAll(); const Reading& r = t.r;
  if (!r.ok) { t.why = "sensor: no answer from ADS1115 (check the logic 5V, optos U5-U7, module)"; return t; }
  if (r.vbat > VBAT_MAX) { t.why = "battery voltage too high: wrong pack?"; return t; }
  if (r.vbat < cfg.vmin) { t.why = "battery below vmin"; return t; }
  float ratio = r.vsw / r.vbat;
  if (ratio > 0.85f) { t.why = "VSW at battery voltage while disarmed: Q3 or U4 shorted"; return t; }
  if (ratio < RATIO_IDLE_MIN) { t.why = "VSW pulled down while disarmed: Q1/Q2 short, stuck opto, or a short on a SOL output"; return t; }
  float c1 = r.d1n / r.vsw, c2 = r.d2n / r.vsw;
  t.coil1 = c1 > COIL_OK; t.coil2 = c2 > COIL_OK;
  if (!t.coil1 && c1 > COIL_OPEN) { t.why = "channel 1 low side reads half way: leakage or damaged Q1/D1"; return t; }
  if (!t.coil2 && c2 > COIL_OPEN) { t.why = "channel 2 low side reads half way: leakage or damaged Q2/D2"; return t; }
  if (!t.coil1 && !t.coil2) { t.why = "no solenoid connected"; return t; }
  if (ratio > RATIO_IDLE_MAX) { t.why = "VSW ratio out of range"; return t; }
  t.pass = true; t.why = "ok"; return t;
}
TestResult lastTest;

// ------------------------------------------------------------------ arm / fire
bool doArm(String& msg) {
  if (armed) { msg = "already armed"; return true; }
  lastTest = selfTest();
  if (!lastTest.pass) { msg = "self-test failed: " + lastTest.why; lastFault = lastTest.why; return false; }
  digitalWrite(PIN_ARM, HIGH); delay(30);
  Reading r = readAll();
  if (!r.ok || r.vsw / r.vbat < RATIO_ARMED_MIN) { disarm("arm switch did not close (Q3/U4/R14)"); msg = "arm failed: " + lastFault; return false; }
  armed = true; armedAt = millis(); digitalWrite(PIN_LED, LOW);
  esp_timer_start_once(armTimer, (uint64_t)cfg.arm_ms * 1000ULL);
  msg = "armed for " + String(cfg.arm_ms) + " ms"; return true;
}
bool doFire(int ch, uint32_t ms, String& msg) {
  if (!armed) { msg = "not armed"; return false; }
  if (ch != 1 && ch != 2) { msg = "channel must be 1 or 2"; return false; }
  if ((ch == 1 && !lastTest.coil1) || (ch == 2 && !lastTest.coil2)) { msg = "solenoid " + String(ch) + " not connected"; return false; }
  if (haveFired && millis() - lastFire < MIN_GAP_MS) { msg = "too soon after the last pulse"; return false; }
  if (ms == 0) ms = cfg.pulse_ms;
  if (ms > MAX_PULSE_MS) ms = MAX_PULSE_MS;
  int pin = (ch == 1) ? PIN_FIRE1 : PIN_FIRE2;
  digitalWrite(pin, HIGH);
  esp_timer_start_once(fireTimer, (uint64_t)ms * 1000ULL);   // the timer, not this function, ends the pulse
  lastFire = millis(); haveFired = true;
  float vdn = 0, vb = lastTest.r.vbat;
  bool ok = adsReadVolts(ch == 1 ? 2 : 3, vdn);              // check the low side while the pulse is still on
  if (!ok) { msg = "fired " + String(ms) + " ms (no read-back)"; return true; }
  if (vdn / vb > FIRE_LOW && digitalRead(pin) == HIGH) { msg = "fired " + String(ms) + " ms but low side stayed high: MOSFET or opto not switching"; lastFault = msg; return false; }
  msg = "fired " + String(ms) + " ms"; return true;
}

// ------------------------------------------------------------------ settings
void loadSettings() {
  prefs.begin("tdv4", true);
  cfg.gain = prefs.getFloat("gain", 1.0f); cfg.vmin = prefs.getFloat("vmin", 14.4f);
  cfg.pulse_ms = prefs.getUInt("pulse", 200); cfg.arm_ms = prefs.getUInt("armms", 10000);
  prefs.end();
  if (cfg.gain < 0.9f || cfg.gain > 1.1f) cfg.gain = 1.0f;
  if (cfg.pulse_ms > MAX_PULSE_MS) cfg.pulse_ms = MAX_PULSE_MS;
}
void saveSettings() {
  prefs.begin("tdv4", false);
  prefs.putFloat("gain", cfg.gain); prefs.putFloat("vmin", cfg.vmin);
  prefs.putUInt("pulse", cfg.pulse_ms); prefs.putUInt("armms", cfg.arm_ms);
  prefs.end();
}

// ------------------------------------------------------------------ serial commands
void printStatus(const Reading& r) {
  Serial.printf("STATUS armed=%d vbat=%.2f vsw=%.2f d1n=%.2f d2n=%.2f coil1=%d coil2=%d vmin=%.2f pulse=%lu gain=%.4f fault=%s\n",
                armed ? 1 : 0, r.vbat, r.vsw, r.d1n, r.d2n, lastTest.coil1, lastTest.coil2, cfg.vmin,
                (unsigned long)cfg.pulse_ms, cfg.gain, lastFault.c_str());
}
void handle(String line) {
  line.trim(); String up = line; up.toUpperCase();
  String msg;
  if (up == "STATUS") { Reading r = readAll(); if (!r.ok) Serial.println("ERR sensor"); else printStatus(r); }
  else if (up == "TEST") { if (armed) { Serial.println("ERR disarm first"); return; } lastTest = selfTest();
    Serial.printf("%s %s\n", lastTest.pass ? "OK" : "ERR", lastTest.why.c_str()); if (lastTest.r.ok) printStatus(lastTest.r); }
  else if (up == "ARM") { bool ok = doArm(msg); Serial.printf("%s %s\n", ok ? "OK" : "ERR", msg.c_str()); }
  else if (up == "DISARM") { disarm(""); Serial.println("OK disarmed"); }
  else if (up.startsWith("FIRE")) {
    int ch = 0; unsigned long ms = 0; sscanf(up.c_str(), "FIRE %d %lu", &ch, &ms);
    bool ok = doFire(ch, (uint32_t)ms, msg); Serial.printf("%s %s\n", ok ? "OK" : "ERR", msg.c_str());
  }
  else if (up.startsWith("CAL ")) {           // CAL <battery volts read on a multimeter>, disarmed
    if (armed) { Serial.println("ERR disarm first"); return; }
    float meas = line.substring(4).toFloat(); cfg.gain = 1.0f; float v;
    if (meas < 10 || meas > 18 || !adsReadVolts(0, v) || v < 5) { Serial.println("ERR give the battery voltage in volts"); return; }
    cfg.gain = meas / v;
    if (cfg.gain < 0.9f || cfg.gain > 1.1f) { cfg.gain = 1.0f; Serial.println("ERR more than 10 % off: check R5/R6"); return; }
    saveSettings(); Serial.printf("OK gain=%.4f\n", cfg.gain);
  }
  else if (up.startsWith("SET VMIN ")) { float v = up.substring(9).toFloat(); if (v < 12.0f || v > 16.5f) { Serial.println("ERR 12.0..16.5"); return; } cfg.vmin = v; saveSettings(); Serial.println("OK"); }
  else if (up.startsWith("SET PULSE ")) { long v = up.substring(10).toInt(); if (v < 10 || v > (long)MAX_PULSE_MS) { Serial.printf("ERR 10..%lu\n", (unsigned long)MAX_PULSE_MS); return; } cfg.pulse_ms = v; saveSettings(); Serial.println("OK"); }
  else if (up.startsWith("SET ARMTIME ")) { long v = up.substring(12).toInt(); if (v < 1000 || v > 60000) { Serial.println("ERR 1000..60000"); return; } cfg.arm_ms = v; saveSettings(); Serial.println("OK"); }
  else Serial.println("CMDS: STATUS | TEST | ARM | DISARM | FIRE 1|2 [ms] | CAL <volts> | SET VMIN <v> | SET PULSE <ms> | SET ARMTIME <ms>");
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  for (int p : {PIN_FIRE1, PIN_FIRE2, PIN_ARM, PIN_SCL_TX, PIN_SDA_TX}) { digitalWrite(p, LOW); pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  pinMode(PIN_LED, OUTPUT); digitalWrite(PIN_LED, HIGH);
  pinMode(PIN_SDA_RX, INPUT);                    // 6.8k pull-up on the board (R19)
  Serial.begin(115200);
  loadSettings();
  esp_timer_create_args_t fa = {}; fa.callback = &fireOffCb; fa.name = "fire_off"; esp_timer_create(&fa, &fireTimer);
  esp_timer_create_args_t aa = {}; aa.callback = &armOffCb; aa.name = "arm_off"; esp_timer_create(&aa, &armTimer);
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t wcfg = {}; wcfg.timeout_ms = WDT_MS; wcfg.idle_core_mask = 0; wcfg.trigger_panic = true;
  esp_task_wdt_reconfigure(&wcfg);
#else
  esp_task_wdt_init(WDT_MS / 1000, true);
#endif
  esp_task_wdt_add(NULL);
  delay(200);
  lastTest = selfTest();
  Serial.printf("torpedo driver v4 ready: self-test %s (%s)\n", lastTest.pass ? "pass" : "FAIL", lastTest.why.c_str());
}

String rx;
uint32_t lastMon = 0;
void loop() {
  esp_task_wdt_reset();
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') { if (rx.length()) handle(rx); rx = ""; }
    else if (rx.length() < 64) rx += c;
  }
  if (!armed && digitalRead(PIN_ARM) == HIGH) allOff();            // arm timer fired: make sure everything is off
  if (armed && millis() - lastMon > 500) {                           // while armed, keep checking the arm switch
    lastMon = millis();
    float vb, vs;
    if (!adsReadVolts(0, vb) || !adsReadVolts(1, vs)) disarm("sensor lost while armed");
    else if (vs / vb < RATIO_ARMED_MIN && millis() - lastFire > cfg.pulse_ms + 50) disarm("switched rail dropped while armed");
  }
}
