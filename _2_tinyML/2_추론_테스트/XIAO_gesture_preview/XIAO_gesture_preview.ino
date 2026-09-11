/*
 * ============================================================
 *  XIAO ESP32S3 - 제스처 추론 + 웹 미리보기 (v2, 안정화)
 * ============================================================
 *  · 웹페이지: 카메라 실시간 화면 (천천히라도)
 *  · 시리얼:   추론 예측 (rock/paper/scissors + %)
 *  · 둘이 동시에 — 추론은 '별도 태스크(큰 스택)', 웹은 저장된 프레임만 서빙.
 *    (매 프레임 malloc 안 함 = 메모리 단편화·스택오버플로 방지)
 *
 *  사용:
 *   1) 업로드 → 시리얼(115200)에 핫스팟/주소 확인
 *   2) 노트북·폰 WiFi 를 "TouchLabs-Cam" 연결 → 브라우저 http://192.168.4.1
 *   3) 화면 보며 손 제스처 → 시리얼에 예측이 뜬다
 *
 *  [Tools]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *           Partition: Maximum APP (7.9MB) / USB CDC On Boot: Enabled
 *  [라이브러리]  EI 라이브러리(overflow 200 패치본). #include 를 내 것으로.
 * ============================================================
 */

#include <rsp_test_inferencing.h>          // ★ 내 EI 라이브러리 이름
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include <WiFi.h>
#include <WebServer.h>
#include <cstring>

// ===== EI 메모리 PSRAM 오버라이드 =====
void *ei_malloc(size_t size)           { return heap_caps_aligned_alloc(16, size, MALLOC_CAP_SPIRAM); }
void *ei_calloc(size_t n, size_t size) { void *p = heap_caps_aligned_alloc(16, n*size, MALLOC_CAP_SPIRAM); if (p) memset(p,0,n*size); return p; }
void  ei_free(void *ptr)               { heap_caps_free(ptr); }

// ===== 카메라 핀: XIAO ESP32S3 =====
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 10
#define SIOD_GPIO_NUM 40
#define SIOC_GPIO_NUM 39
#define Y9_GPIO_NUM 48
#define Y8_GPIO_NUM 11
#define Y7_GPIO_NUM 12
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 16
#define Y4_GPIO_NUM 18
#define Y3_GPIO_NUM 17
#define Y2_GPIO_NUM 15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM 47
#define PCLK_GPIO_NUM 13

#define RAW_W 320
#define RAW_H 240

#define CONF_TH        0.60f   // 이 확률 이상만 "확정 후보"로 인정
#define STABLE_NEEDED  3       // 연속 몇 프레임 같은 라벨이어야 확정

const char* AP_SSID = "TouchLabs-Cam";     // ★ 여러 명이면 각자 다르게
const char* AP_PASS = "12345678";
WebServer server(80);

// ── 공유 버퍼 (setup 에서 1회 할당) ──
uint8_t *rgb_buf  = nullptr;               // 추론용 RGB888 (RAW_W*RAW_H*3)
uint8_t *jpg_buf  = nullptr;               // 미리보기 JPEG 사본
volatile size_t jpg_len = 0;
char pred_str[64] = "준비 중...";

static camera_config_t camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM, .pin_reset = RESET_GPIO_NUM, .pin_xclk = XCLK_GPIO_NUM,
    .pin_sscb_sda = SIOD_GPIO_NUM, .pin_sscb_scl = SIOC_GPIO_NUM,
    .pin_d7 = Y9_GPIO_NUM, .pin_d6 = Y8_GPIO_NUM, .pin_d5 = Y7_GPIO_NUM, .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM, .pin_d2 = Y4_GPIO_NUM, .pin_d1 = Y3_GPIO_NUM, .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM, .pin_href = HREF_GPIO_NUM, .pin_pclk = PCLK_GPIO_NUM,
    .xclk_freq_hz = 20000000, .ledc_timer = LEDC_TIMER_0, .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG, .frame_size = FRAMESIZE_QVGA,
    .jpeg_quality = 12, .fb_count = 1, .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
};

// ── EI signal → rgb_buf 에서 읽기 ──
static int get_data(size_t offset, size_t length, float *out_ptr) {
    size_t px = offset*3, o = 0, left = length;
    while (left) { out_ptr[o++] = (rgb_buf[px+2]<<16)+(rgb_buf[px+1]<<8)+rgb_buf[px]; px += 3; left--; }
    return 0;
}

// ── 웹 ──
const char* PAGE =
"<!doctype html><meta charset='utf-8'><meta name=viewport content='width=device-width,initial-scale=1'>"
"<body style='margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center'>"
"<h3 style='margin:8px'>TouchLabs WebCam View</h3>"
"<img id=v style='width:100%;max-width:480px;border-radius:8px'>"
"<div id=p style='font-size:22px;font-weight:700;padding:10px'>...</div>"
"<div style='padding:6px'>"
"<button onclick='fy()' style='font-size:16px;padding:8px 14px;margin:4px;border-radius:8px'>↕ 상하</button>"
"<button onclick='fx()' style='font-size:16px;padding:8px 14px;margin:4px;border-radius:8px'>↔ 좌우</button>"
"</div>"
"<script>"
"var sx=1,sy=1;try{sx=+localStorage.gx||1;sy=+localStorage.gy||1;}catch(e){}"
"function ap(){document.getElementById('v').style.transform='scaleX('+sx+') scaleY('+sy+')';try{localStorage.gx=sx;localStorage.gy=sy;}catch(e){}}"
"function fx(){sx=-sx;ap();}function fy(){sy=-sy;ap();}ap();"
"setInterval(()=>{document.getElementById('v').src='/frame?'+Date.now();"
"fetch('/pred').then(r=>r.text()).then(t=>document.getElementById('p').innerText=t);},500);</script>";

void handleRoot()  { server.send(200, "text/html", PAGE); }
void handlePred()  { server.send(200, "text/plain", pred_str); }
void handleFrame() {
    size_t n = jpg_len;
    if (!jpg_buf || !n) { server.send(503, "text/plain", "no frame"); return; }
    WiFiClient c = server.client();
    c.print("HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: ");
    c.print(n); c.print("\r\nConnection: close\r\n\r\n");
    c.write(jpg_buf, n);
}

// ── 추론 태스크 (카메라 접근은 여기서만) ──
void inferenceTask(void *pv) {
    for (;;) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) { vTaskDelay(pdMS_TO_TICKS(30)); continue; }

        if (jpg_buf && fb->len <= 45000) { memcpy(jpg_buf, fb->buf, fb->len); jpg_len = fb->len; }   // 미리보기 사본

        bool ok = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, rgb_buf);
        esp_camera_fb_return(fb);
        if (ok) {
            if ((uint32_t)EI_CLASSIFIER_INPUT_WIDTH != RAW_W || (uint32_t)EI_CLASSIFIER_INPUT_HEIGHT != RAW_H)
                ei::image::processing::crop_and_interpolate_rgb888(rgb_buf, RAW_W, RAW_H, rgb_buf,
                                                                   EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT);
            ei::signal_t signal; signal.total_length = EI_CLASSIFIER_INPUT_WIDTH*EI_CLASSIFIER_INPUT_HEIGHT; signal.get_data = &get_data;
            ei_impulse_result_t result = { 0 };
            if (run_classifier(&signal, &result, false) == EI_IMPULSE_OK) {
                int best = 0;
                for (uint16_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++)
                    if (result.classification[i].value > result.classification[best].value) best = i;
                float conf = result.classification[best].value;
                // ── 임계값 + 안정화(연속 STABLE_NEEDED 프레임 같은 라벨 & ≥CONF_TH) ──
                static int last = -1, streak = 0, confirmed = -1;
                if (conf >= CONF_TH) { if (best == last) streak++; else { last = best; streak = 1; } }
                else                 { last = -1; streak = 0; }
                if (streak >= STABLE_NEEDED) confirmed = best;
                if (confirmed >= 0 && best == confirmed && conf >= CONF_TH)
                    snprintf(pred_str, sizeof(pred_str), "✅ %s  %.0f%%",
                             ei_classifier_inferencing_categories[confirmed], conf*100.0f);
                else   // 아직 미확정: 뭘 보는 중인지 + 낮은 신뢰도 그대로 노출
                    snprintf(pred_str, sizeof(pred_str), "… %s  %.0f%%",
                             ei_classifier_inferencing_categories[best], conf*100.0f);
                Serial.printf(">>> %s\n", pred_str);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(30));   // 웹/시스템에 양보
    }
}

void setup() {
    Serial.begin(115200);
    if (esp_camera_init(&camera_config) != ESP_OK) { Serial.println("❌ 카메라 초기화 실패"); }
    else                                            { Serial.println("✅ 카메라 준비"); }
    { sensor_t *s = esp_camera_sensor_get(); if (s) s->set_hmirror(s, 1); }  // ★ 캡처(_HW)와 좌우반전 일치(OV2640)

    rgb_buf = (uint8_t*)ps_malloc(RAW_W*RAW_H*3);   // 1회 할당
    jpg_buf = (uint8_t*)ps_malloc(45000);
    if (!rgb_buf || !jpg_buf) { Serial.println("❌ 버퍼 할당 실패"); }

    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("핫스팟: '%s' (비번 %s)\n", AP_SSID, AP_PASS);
    Serial.print ("👉 브라우저: http://"); Serial.println(WiFi.softAPIP());
    server.on("/", handleRoot);
    server.on("/pred", handlePred);
    server.on("/frame", handleFrame);
    server.begin();

    // 추론은 큰 스택의 별도 태스크로 (core 1)
    xTaskCreatePinnedToCore(inferenceTask, "infer", 16384, nullptr, 1, nullptr, 1);
}

void loop() {
    server.handleClient();      // 웹만 담당
    delay(1);
}

#if !defined(EI_CLASSIFIER_SENSOR) || EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_CAMERA
#error "Invalid model for current sensor"
#endif
