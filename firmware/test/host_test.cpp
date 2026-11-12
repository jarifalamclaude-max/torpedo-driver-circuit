// Behavioural ADS1115 behind the opto link: pin HIGH on GPIO5/6 pulls SCL/SDA low; GPIO7 reads SDA.
#include "Arduino.h"
#include <cmath>
SerialT Serial;
unsigned long g_us = 0;
static int pin[32];
static double node[4] = {16.8, 8.6, 8.6, 8.6};      // VBAT, VSW, D1N, D2N (volts at the board nodes)
static bool brokenQ1 = false;
static int armPinHigh() { return pin[10]; }
struct Slave { bool pull = false; int clk = 0; uint8_t sh = 0; int mode = 0; int byteNo = 0; bool rw = false; bool sel = false;
  uint8_t ptr = 0; uint16_t cfg = 0x8583; uint16_t conv = 0; uint8_t tx = 0; int txByte = 0; bool mack = false; } S;
static int starts = 0, stops = 0, nacks = 0;
static bool sclLine() { return !pin[5]; }
static bool sdaLine() { return !pin[6] && !S.pull; }
static void startConv() { int ch = ((S.cfg >> 12) & 7) - 4; double v = node[ch]; if (armPinHigh() && ch >= 1) v = node[0];
  if (ch == 2 && pin[1] && !brokenQ1) v = 0.02;
  if (ch == 3 && pin[0]) v = 0.02;
  S.conv = (uint16_t)(int16_t)std::lround(v / 11.0 / (2.048 / 32768.0)); }
static uint8_t txByteVal(int n) { uint16_t r = (S.ptr == 0) ? S.conv : S.cfg; return n == 0 ? r >> 8 : r & 0xFF; }
static void onStart() { starts++; S.mode = 1; S.clk = 0; S.sh = 0; S.byteNo = 0; S.pull = false; }
static void onStop() { stops++; S.mode = 0; S.pull = false; }
static void onRise(bool sda) { if (!S.mode) return; S.clk++;
  if (S.mode == 1 && S.clk <= 8) S.sh = (S.sh << 1) | sda;
  if (S.mode == 2 && S.clk == 9) S.mack = !sda; }
static uint16_t wbuf;
static void onFall() { if (!S.mode) return;
  if (S.mode == 1) {
    if (S.clk == 8) {
      if (S.byteNo == 0) { S.sel = ((S.sh >> 1) == 0x48); S.rw = S.sh & 1; if (!S.sel) nacks++; S.pull = S.sel; }
      else { if (S.byteNo == 1) S.ptr = S.sh; else if (S.byteNo == 2) wbuf = S.sh << 8; else if (S.byteNo == 3) { wbuf |= S.sh; if (S.ptr == 1) { S.cfg = wbuf; if (S.cfg & 0x8000) startConv(); } }
             S.pull = true; }
      S.byteNo++;
    } else if (S.clk == 9) { S.pull = false; S.clk = 0;
      if (S.byteNo == 1 && S.rw && S.sel) { S.mode = 2; S.txByte = 0; S.tx = txByteVal(0); S.pull = !(S.tx & 0x80); }
      if (!S.sel) S.mode = 0; }
  } else if (S.mode == 2) {
    if (S.clk < 8) S.pull = !((S.tx >> (7 - S.clk)) & 1);
    else if (S.clk == 8) S.pull = false;
    else if (S.clk == 9) { S.clk = 0; if (S.mack) { S.txByte++; S.tx = txByteVal(S.txByte); S.pull = !(S.tx & 0x80); } else { S.mode = 0; S.pull = false; } }
  } }
void digitalWrite(int p, int v) {
  bool scl0 = sclLine(), sda0 = sdaLine(); pin[p] = v; bool scl1 = sclLine(), sda1 = sdaLine();
  if (p == 5) { if (!scl0 && scl1) onRise(sda1); if (scl0 && !scl1) onFall(); }
  if (p == 6 && scl1) { if (sda0 && !sda1) onStart(); if (!sda0 && sda1) onStop(); } }
int digitalRead(int p) { return p == 7 ? (sdaLine() ? 1 : 0) : pin[p]; }
#include "../torpedo_driver_v4/torpedo_driver_v4.ino"
static void show(const char* name, TestResult t) { printf("%-22s pass=%d coil1=%d coil2=%d ok=%d vbat=%.2f vsw=%.2f d1n=%.2f d2n=%.2f  why=%s\n", name, t.pass, t.coil1, t.coil2,
  t.r.ok, t.r.vbat, t.r.vsw, t.r.d1n, t.r.d2n, t.why.c_str()); }
int main() {
  setup();
  show("idle 16.8 V", selfTest());
  node[1] = 16.8; node[2] = node[3] = 16.8; show("Q3 short", selfTest());
  node[1] = 0.01; node[2] = 0.0; node[3] = 0.01; show("Q1 short", selfTest());
  node[1] = 10.0; node[2] = 0.02; node[3] = 10.0; show("coil 1 open", selfTest());
  node[1] = 8.6; node[2] = 8.6; node[3] = 8.6; node[0] = 13.5; show("battery 13.5 V", selfTest());
  node[0] = 16.8; String m; bool ok = doArm(m); printf("arm: %d %s  armed=%d ARMpin=%d LED=%d\n", ok, m.c_str(), (int)armed, pin[10], pin[8]);
  ok = doFire(1, 0, m); printf("fire1: %d %s FIRE1pin=%d t=%lums\n", ok, m.c_str(), pin[1], millis());
  fireOffCb(nullptr);
  ok = doFire(2, 50, m); printf("fire2 again at once: %d %s\n", ok, m.c_str());
  g_us += 400000; ok = doFire(2, 900, m); printf("fire2 900ms request: %d %s\n", ok, m.c_str()); fireOffCb(nullptr);
  g_us += 400000; brokenQ1 = true; ok = doFire(1, 0, m); printf("fire1 with dead Q1: %d %s\n", ok, m.c_str()); fireOffCb(nullptr);
  ok = doFire(3, 0, m); printf("fire3: %d %s\n", ok, m.c_str());
  disarm(""); printf("disarm: armed=%d ARM=%d FIRE1=%d\n", (int)armed, pin[10], pin[1]);
  printf("bus: starts=%d stops=%d nacks=%d\n", starts, stops, nacks);
  return 0; }
