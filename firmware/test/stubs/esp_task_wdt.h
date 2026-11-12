#pragma once
#include <cstdint>
typedef struct { uint32_t timeout_ms; uint32_t idle_core_mask; bool trigger_panic; } esp_task_wdt_config_t;
inline int esp_task_wdt_reconfigure(const esp_task_wdt_config_t*) { return 0; }
inline int esp_task_wdt_init(uint32_t, bool) { return 0; }
inline int esp_task_wdt_add(void*) { return 0; }
inline int esp_task_wdt_reset() { return 0; }
