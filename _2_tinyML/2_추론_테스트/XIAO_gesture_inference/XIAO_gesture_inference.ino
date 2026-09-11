/*
 * XIAO ESP32S3 - Edge Impulse 손동작 인식 (온디바이스 추론)
 * ★ 라이브러리 수정 불필요! 모든 수정이 이 스케치 안에 있음 (교육용)
 *
 * 핵심: EI의 ei_malloc/ei_calloc(weak 심볼)을 여기서 PSRAM 버전으로 덮어써서
 *       모델 메모리(arena)를 내부RAM이 아닌 8MB PSRAM에 할당 → 크래시 방지
 *
 * [Tools]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *          Partition: Maximum APP (7.9MB) / USB CDC On Boot: Enabled
 * [라이브러리]  Edge Impulse에서 받은 '..._inferencing' 그대로 (수정 X)
 */

#include <rsp_test_inferencing.h>
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include <cstring>

// ===== ★ EI 메모리를 PSRAM에 할당 (라이브러리 weak 심볼 오버라이드) =====
// extern "C" 없이 = 라이브러리 C++ 링크와 일치 (그래야 오버라이드가 먹음)
void *ei_malloc(size_t size) {
    return heap_caps_aligned_alloc(16, size, MALLOC_CAP_SPIRAM);
}
void *ei_calloc(size_t nitems, size_t size) {
    void *p = heap_caps_aligned_alloc(16, nitems * size, MALLOC_CAP_SPIRAM);
    if (p) memset(p, 0, nitems * size);
    return p;
}
void ei_free(void *ptr) {
    heap_caps_free(ptr);
}

// ===== 카메라 모델: XIAO ESP32S3 =====
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

#define EI_CAMERA_RAW_FRAME_BUFFER_COLS  320
#define EI_CAMERA_RAW_FRAME_BUFFER_ROWS  240
#define EI_CAMERA_FRAME_BYTE_SIZE        3

static bool debug_nn = false;
static bool is_initialised = false;
uint8_t *snapshot_buf;

static camera_config_t camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM,
    .pin_reset = RESET_GPIO_NUM,
    .pin_xclk = XCLK_GPIO_NUM,
    .pin_sscb_sda = SIOD_GPIO_NUM,
    .pin_sscb_scl = SIOC_GPIO_NUM,
    .pin_d7 = Y9_GPIO_NUM,
    .pin_d6 = Y8_GPIO_NUM,
    .pin_d5 = Y7_GPIO_NUM,
    .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM,
    .pin_d2 = Y4_GPIO_NUM,
    .pin_d1 = Y3_GPIO_NUM,
    .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM,
    .pin_href = HREF_GPIO_NUM,
    .pin_pclk = PCLK_GPIO_NUM,
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_QVGA,
    .jpeg_quality = 12,
    .fb_count = 1,
    .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
};

bool ei_camera_init(void);
bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf);
static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr);

void setup() {
    Serial.begin(115200);
    while (!Serial);
    Serial.println("Edge Impulse Inferencing Demo");
    if (ei_camera_init() == false) ei_printf("Failed to initialize Camera!\r\n");
    else ei_printf("Camera initialized\r\n");
    ei_printf("\nStarting continious inference in 2 seconds...\n");
    ei_sleep(2000);
}

void loop() {
    if (ei_sleep(5) != EI_IMPULSE_OK) return;

    // 카메라 캡처 버퍼도 PSRAM에 (ps_malloc)
    snapshot_buf = (uint8_t*)ps_malloc(EI_CAMERA_RAW_FRAME_BUFFER_COLS * EI_CAMERA_RAW_FRAME_BUFFER_ROWS * EI_CAMERA_FRAME_BYTE_SIZE);
    if (snapshot_buf == nullptr) {
        ei_printf("ERR: Failed to allocate snapshot buffer!\n");
        return;
    }

    ei::signal_t signal;
    signal.total_length = EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
    signal.get_data = &ei_camera_get_data;

    if (ei_camera_capture((size_t)EI_CLASSIFIER_INPUT_WIDTH, (size_t)EI_CLASSIFIER_INPUT_HEIGHT, snapshot_buf) == false) {
        ei_printf("Failed to capture image\r\n");
        free(snapshot_buf);
        return;
    }

    ei_impulse_result_t result = { 0 };
    EI_IMPULSE_ERROR err = run_classifier(&signal, &result, debug_nn);
    if (err != EI_IMPULSE_OK) {
        ei_printf("ERR: Failed to run classifier (%d)\n", err);
        free(snapshot_buf);
        return;
    }

    // 가장 확률 높은 손동작 찾기
    int best = 0;
    for (uint16_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        if (result.classification[i].value > result.classification[best].value) best = i;
    }

    ei_printf("Predictions (DSP: %d ms., Classification: %d ms.):\r\n",
              result.timing.dsp, result.timing.classification);
    for (uint16_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        ei_printf("  %s%s: %.2f\r\n",
                  (i == best) ? "-> " : "   ",
                  ei_classifier_inferencing_categories[i], result.classification[i].value);
    }
    ei_printf(">>> %s (%.0f%%)\r\n\n",
              ei_classifier_inferencing_categories[best],
              result.classification[best].value * 100.0f);

    free(snapshot_buf);
}

bool ei_camera_init(void) {
    if (is_initialised) return true;
    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return false;
    }
    sensor_t *s = esp_camera_sensor_get();
    if (s->id.PID == OV3660_PID) {
        s->set_vflip(s, 1);
        s->set_brightness(s, 1);
        s->set_saturation(s, 0);
    }
    s->set_hmirror(s, 1);   // ★ 캡처(_HW)와 좌우반전 일치 = 학습 데이터와 방향 맞춤(OV2640)
    is_initialised = true;
    return true;
}

bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf) {
    bool do_resize = false;
    if (!is_initialised) { ei_printf("ERR: Camera is not initialized\r\n"); return false; }

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) { ei_printf("Camera capture failed\n"); return false; }

    bool converted = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, snapshot_buf);
    esp_camera_fb_return(fb);
    if (!converted) { ei_printf("Conversion failed\n"); return false; }

    if ((img_width != EI_CAMERA_RAW_FRAME_BUFFER_COLS) || (img_height != EI_CAMERA_RAW_FRAME_BUFFER_ROWS)) {
        do_resize = true;
    }
    if (do_resize) {
        ei::image::processing::crop_and_interpolate_rgb888(
            out_buf, EI_CAMERA_RAW_FRAME_BUFFER_COLS, EI_CAMERA_RAW_FRAME_BUFFER_ROWS,
            out_buf, img_width, img_height);
    }
    return true;
}

static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr) {
    size_t pixel_ix = offset * 3;
    size_t pixels_left = length;
    size_t out_ptr_ix = 0;
    while (pixels_left != 0) {
        out_ptr[out_ptr_ix] = (snapshot_buf[pixel_ix + 2] << 16) + (snapshot_buf[pixel_ix + 1] << 8) + snapshot_buf[pixel_ix];
        out_ptr_ix++;
        pixel_ix += 3;
        pixels_left--;
    }
    return 0;
}

#if !defined(EI_CLASSIFIER_SENSOR) || EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_CAMERA
#error "Invalid model for current sensor"
#endif