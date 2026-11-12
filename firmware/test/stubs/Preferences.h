#pragma once
struct Preferences { bool begin(const char*, bool) { return true; } void end() {}
  float getFloat(const char*, float d) { return d; } unsigned getUInt(const char*, unsigned d) { return d; }
  void putFloat(const char*, float) {} void putUInt(const char*, unsigned) {} };
