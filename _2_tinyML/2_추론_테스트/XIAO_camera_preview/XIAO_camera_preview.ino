/*
 * ============================================================
 *  XIAO ESP32S3 - 카메라 실시간 미리보기 (모델 없음, 가벼움)
 * ============================================================
 *  카메라가 "지금 뭘 보는지"를 브라우저에서 부드러운 영상으로 확인.
 *  → 프레이밍·초점·조명·거리 맞추는 용도. (추론 예측은 gesture_inference 시리얼에서)
 *
 *  왜 분리?  WiFi + 모델추론 + 카메라를 한 보드에서 동시에 돌리면 내부RAM이
 *            빠듯해 크래시 → 미리보기는 모델 없이 가볍게 돌린다.
 *
 *  사용:
 *   1) 업로드 → 시리얼(115200)에 뜨는 핫스팟 확인
 *   2) 노트북/폰 WiFi 를 "TouchLabs-Cam" 에 연결
 *   3) 브라우저  http://192.168.4.1  → 실시간 영상
 *
 *  [Tools]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *           Partition: 기본(Default) 도 OK / USB CDC On Boot: Enabled
 * ============================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

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

const char* AP_SSID = "TouchLabs-Cam";     // ★ 여러 명이면 각자 다르게
const char* AP_PASS = "12345678";
WebServer server(80);

static camera_config_t camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM, .pin_reset = RESET_GPIO_NUM, .pin_xclk = XCLK_GPIO_NUM,
    .pin_sscb_sda = SIOD_GPIO_NUM, .pin_sscb_scl = SIOC_GPIO_NUM,
    .pin_d7 = Y9_GPIO_NUM, .pin_d6 = Y8_GPIO_NUM, .pin_d5 = Y7_GPIO_NUM, .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM, .pin_d2 = Y4_GPIO_NUM, .pin_d1 = Y3_GPIO_NUM, .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM, .pin_href = HREF_GPIO_NUM, .pin_pclk = PCLK_GPIO_NUM,
    .xclk_freq_hz = 20000000, .ledc_timer = LEDC_TIMER_0, .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG, .frame_size = FRAMESIZE_QVGA,   // 320x240
    .jpeg_quality = 12, .fb_count = 2, .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
};

const char* PAGE =
"<!doctype html><meta charset='utf-8'><meta name=viewport content='width=device-width,initial-scale=1'>"
"<body style='margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center'>"
"<h3 style='margin:8px'>TouchLabs WebCam View</h3>"
"<img src='/stream' style='width:100%;max-width:480px;border-radius:8px;transform:scaleY(-1)'>"
"<div style='color:#888;font-size:12px;padding:8px'>모델이 보는 화면 = 이 영상. 이걸로 프레이밍·조명 맞추고, 예측은 추론 스케치(시리얼)에서.</div>";

void handleRoot() { server.send(200, "text/html", PAGE); }

void handleStream() {
    WiFiClient client = server.client();
    client.print("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n");
    while (client.connected()) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) break;
        client.print("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ");
        client.print(fb->len);
        client.print("\r\n\r\n");
        client.write(fb->buf, fb->len);
        client.print("\r\n");
        esp_camera_fb_return(fb);
        if (!client.connected()) break;
    }
}

void setup() {
    Serial.begin(115200);
    if (esp_camera_init(&camera_config) != ESP_OK) {
        Serial.println("❌ 카메라 초기화 실패 (PSRAM=OPI PSRAM 확인, 카메라 재장착)");
    } else {
        Serial.println("✅ 카메라 준비");
    }
    { sensor_t *s = esp_camera_sensor_get(); if (s) s->set_hmirror(s, 1); }  // ★ 캡처(_HW)와 좌우반전 일치(OV2640)
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("핫스팟: '%s' (비번 %s)\n", AP_SSID, AP_PASS);
    Serial.print ("👉 브라우저: http://"); Serial.println(WiFi.softAPIP());
    server.on("/", handleRoot);
    server.on("/stream", handleStream);
    server.begin();
}

void loop() {
    server.handleClient();
}
