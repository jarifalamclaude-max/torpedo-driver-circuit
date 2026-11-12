#pragma once
#include <cstdint>
typedef struct esp_timer* esp_timer_handle_t;
typedef void (*esp_timer_cb_t)(void*);
typedef enum { ESP_TIMER_TASK = 0 } esp_timer_dispatch_t;
typedef struct { esp_timer_cb_t callback; void* arg; esp_timer_dispatch_t dispatch_method; const char* name; bool skip_unhandled_events; } esp_timer_create_args_t;
inline int esp_timer_create(const esp_timer_create_args_t*, esp_timer_handle_t*) { return 0; }
inline int esp_timer_start_once(esp_timer_handle_t, uint64_t) { return 0; }
inline int esp_timer_stop(esp_timer_handle_t) { return 0; }
