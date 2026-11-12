#pragma once
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <cctype>
#include <initializer_list>
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define ESP_ARDUINO_VERSION_MAJOR 3
inline void pinMode(int, int) {}
void digitalWrite(int pin, int v);
int digitalRead(int pin);
extern unsigned long g_us;
inline void delay(unsigned long ms) { g_us += ms * 1000; }
inline void delayMicroseconds(unsigned us) { g_us += us; }
inline unsigned long millis() { return g_us / 1000; }
class String {
 public:
  std::string s;
  String() {} String(const char* c) : s(c) {} String(const std::string& x) : s(x) {}
  String(int v) : s(std::to_string(v)) {} String(unsigned v) : s(std::to_string(v)) {}
  String(long v) : s(std::to_string(v)) {} String(unsigned long v) : s(std::to_string(v)) {}
  String operator+(const String& o) const { return String(s + o.s); }
  friend String operator+(const char* a, const String& b) { return String(std::string(a) + b.s); }
  String& operator+=(char c) { s += c; return *this; }
  bool operator==(const char* c) const { return s == c; }
  void trim() { while (!s.empty() && isspace(s.back())) s.pop_back(); while (!s.empty() && isspace(s.front())) s.erase(0, 1); }
  void toUpperCase() { for (auto& ch : s) ch = toupper(ch); }
  bool startsWith(const char* p) const { return s.rfind(p, 0) == 0; }
  String substring(size_t a) const { return String(s.substr(std::min(a, s.size()))); }
  float toFloat() const { return atof(s.c_str()); }
  long toInt() const { return atol(s.c_str()); }
  const char* c_str() const { return s.c_str(); }
  size_t length() const { return s.size(); }
};
struct SerialT { void begin(long) {} int available() { return 0; } int read() { return -1; }
  template <class... A> void printf(const char* f, A... a) { std::printf(f, a...); } void println(const char* x) { std::puts(x); } };
extern SerialT Serial;
