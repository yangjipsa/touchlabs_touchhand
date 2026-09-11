/*
 * ============================================================
 *  XIAO ESP32S3 Sense - 제스처 인식 → 로봇 손 따라하기 (TinyML 통합)
 * ============================================================
 *  Author  : yangjipsa / TouchLabs (touchlabs.kr)
 *  개요    : 카메라로 사람 손 제스처를 Edge Impulse 모델로 인식하고,
 *            그 제스처를 로봇 손이 그대로 따라 한다. (한 보드로 완결)
 *  5클래스 : 바위(rock) · 보(paper) · 가위(scissors) · 따봉(thumbsup) · 브이(v)
 *
 *  ★ 두 가지를 한 보드(XIAO ESP32S3 Sense)가 동시에:
 *     - 카메라 추론 (Edge Impulse, PSRAM 사용)
 *     - 서보 구동  (Serial1 → Waveshare 점퍼 A → SCS0009 ×8, Day1 방식)
 *
 *  [Tools]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *           Partition: Maximum APP (7.9MB) / USB CDC On Boot: Enabled
 *  [배선]   XIAO D6(GPIO43,TX)→Waveshare RX · D7(GPIO44,RX)→Waveshare TX · GND 공통
 *           서보 전원 5V, Waveshare 점퍼 A(UART)
 *
 *  ※ 아래 #include 와 라벨(GES[])을 "내가 학습시킨 EI 프로젝트"에 맞게 바꿀 것!
 * ============================================================
 */

// ─────────────────────────────────────────────────────────
//  ① Edge Impulse 라이브러리  ← 내 프로젝트 이름으로 교체
//     (Arduino 라이브러리 매니저에 .zip 추가하면 이름이 <프로젝트명_inferencing.h>)
// ─────────────────────────────────────────────────────────
#include <rsp_test_inferencing.h>
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include <cstring>

// ===== ★ EI 모델 메모리를 PSRAM 에 할당 (라이브러리 weak 심볼 오버라이드) =====
//   내부 RAM은 작아서 모델 arena를 못 잡고 크래시 → 8MB PSRAM으로 돌림
void *ei_malloc(size_t size)              { return heap_caps_aligned_alloc(16, size, MALLOC_CAP_SPIRAM); }
void *ei_calloc(size_t n, size_t size)    { void *p = heap_caps_aligned_alloc(16, n*size, MALLOC_CAP_SPIRAM); if (p) memset(p,0,n*size); return p; }
void  ei_free(void *ptr)                  { heap_caps_free(ptr); }

// =========================================================================
//  손 구동부 (Day1 day1_3_command 과 동일한 서보 라이브러리)
// =========================================================================
#define SERVO_BAUD  1000000
#define PIN_TX      44        // D7(GPIO44) → Waveshare RX  (PCB 배치 맞춰 스왑 가능)
#define PIN_RX      43        // D6(GPIO43) → Waveshare TX
#define BUS_GAP_US  700

void scsWrite(uint8_t id, uint8_t addr, const uint8_t *data, uint8_t n) {
  while (Serial1.available()) Serial1.read();
  uint8_t len = n + 3;
  uint8_t chk = id + len + 0x03 + addr;
  Serial1.write(0xFF); Serial1.write(0xFF);
  Serial1.write(id);   Serial1.write(len);
  Serial1.write(0x03); Serial1.write(addr);
  for (uint8_t i = 0; i < n; i++) { Serial1.write(data[i]); chk += data[i]; }
  Serial1.write((uint8_t)(~chk));
  Serial1.flush();
  delayMicroseconds(BUS_GAP_US);
}
void scsWriteByte(uint8_t id, uint8_t addr, uint8_t val) { scsWrite(id, addr, &val, 1); }
void scsWritePos(uint8_t id, int pos, uint16_t moveTime, uint16_t speed) {
  uint8_t p[6] = { (uint8_t)((pos>>8)&0xFF),(uint8_t)(pos&0xFF),
                   (uint8_t)((moveTime>>8)&0xFF),(uint8_t)(moveTime&0xFF),
                   (uint8_t)((speed>>8)&0xFF),(uint8_t)(speed&0xFF) };
  scsWrite(id, 42, p, 6);
}

#define HAND_LEFT
const int SDIR = +1;                                   // 왼손(+1)/오른손(-1)
const int BDIR = +1;
const uint8_t SA[4] = { 7, 1, 3, 5 };                  // [엄지,검지,중지약지,새끼] a쪽
const uint8_t SB[4] = { 8, 2, 4, 6 };                  //                          b쪽
#define THUMB 0
#define INDEX 1
#define MIDDLE 2
#define PINKY 3
const int MID = 511;
const int OFFSET[9] = { 0, 0,+14,-16,-28,+10,-20,+8,+7 };
const int LIMIT = 307;
const int SPEED = 600;
const int FLEX = 300, EXT = 80, SWAY = 110, SPREAD = 65;
const int THUMB_FLEX = 180, THUMB_TUCK = 120;

int  midv(int id)          { return constrain(MID + OFFSET[id], 0, 1023); }
int  clampv(int id, int p) { int m = midv(id); return constrain(constrain(p, m-LIMIT, m+LIMIT), 0, 1023); }
void w(int id, int p)      { scsWritePos(id, clampv(id, p), 0, SPEED); }
void finger(int idx, int flex, int sway = 0) {
  flex *= BDIR; sway *= SDIR;
  w(SA[idx], midv(SA[idx]) - flex + sway);
  w(SB[idx], midv(SB[idx]) + flex + sway);
}
void handOpen() { finger(THUMB,-EXT); finger(INDEX,-EXT); finger(MIDDLE,-EXT); finger(PINKY,-EXT); }

// ── 5클래스 손 포즈 (사람 제스처를 손이 그대로) ──
void poseRock()     { finger(INDEX,FLEX); finger(MIDDLE,FLEX); finger(PINKY,FLEX); delay(150);
                      finger(THUMB,THUMB_FLEX,THUMB_TUCK); }                                   // 바위 = 주먹
void posePaper()    { handOpen(); }                                                            // 보 = 펴기
void poseScissors() { finger(THUMB,FLEX); finger(INDEX,-EXT); finger(MIDDLE,-EXT); finger(PINKY,FLEX); } // 가위
void poseThumbsUp() { finger(THUMB,-EXT); finger(INDEX,FLEX); finger(MIDDLE,FLEX); finger(PINKY,FLEX); } // 따봉
void poseV()        { int v=SPREAD/2; finger(THUMB,FLEX); finger(INDEX,-EXT,-v); finger(MIDDLE,-EXT,+v); finger(PINKY,FLEX); } // 브이

// ── EI 라벨 → 손동작 매핑 ──  ★ 왼쪽 문자열을 "학습 때 쓴 클래스 이름"과 정확히 일치시킬 것
struct Gesture { const char* label; void (*pose)(); const char* ko; };
Gesture GES[] = {
  { "rock",     poseRock,     "바위" },
  { "paper",    posePaper,    "보"   },
  { "scissors", poseScissors, "가위" },
  { "thumbsup", poseThumbsUp, "따봉" },
  { "v",        poseV,        "브이" },
};
const int N_GES = sizeof(GES)/sizeof(GES[0]);

void applyGesture(const char* label) {
  for (int i = 0; i < N_GES; i++)
    if (strcmp(label, GES[i].label) == 0) { GES[i].pose(); return; }
  // 목록에 없는 라벨(_noise/_unknown 등)은 무시
}

// =========================================================================
//  카메라부 (XIAO ESP32S3 Sense)  — gesture_inference 와 동일
// =========================================================================
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  10
#define SIOD_GPIO_NUM  40
#define SIOC_GPIO_NUM  39
#define Y9_GPIO_NUM    48
#define Y8_GPIO_NUM    11
#define Y7_GPIO_NUM    12
#define Y6_GPIO_NUM    14
#define Y5_GPIO_NUM    16
#define Y4_GPIO_NUM    18
#define Y3_GPIO_NUM    17
#define Y2_GPIO_NUM    15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM  47
#define PCLK_GPIO_NUM  13

#define EI_CAMERA_RAW_FRAME_BUFFER_COLS 320
#define EI_CAMERA_RAW_FRAME_BUFFER_ROWS 240
#define EI_CAMERA_FRAME_BYTE_SIZE       3

// ── 인식 안정화(오작동 방지) ──
#define CONF_TH        0.60f   // 이 확률 이상일 때만 인정
#define STABLE_NEEDED  3       // 같은 결과가 연속 N번 나와야 손 움직임
#define HOLD_MS        1200    // 한 번 움직이면 이 시간 동안 유지(연속 떨림 방지)

static bool is_initialised = false;
uint8_t *snapshot_buf;

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

bool ei_camera_init(void);
bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf);
static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr);

void setup() {
  Serial.begin(115200);

  // 손(서보) 준비
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, PIN_RX, PIN_TX);
  delay(300);
  for (int id = 1; id <= 8; id++) scsWriteByte(id, 40, 1);   // 토크 ON
  handOpen();                                                // 편 손으로 시작

  // 카메라 준비
  if (!ei_camera_init()) ei_printf("Camera init 실패!\r\n");
  else                   ei_printf("Camera 준비 완료\r\n");
  ei_printf("제스처를 카메라에 보여주세요 (바위/보/가위/따봉/브이)\n");
}

void loop() {
  static char    lastShown[32] = "";
  static int     stable = 0;
  static uint32_t holdUntil = 0;

  if (ei_sleep(5) != EI_IMPULSE_OK) return;

  snapshot_buf = (uint8_t*)ps_malloc(EI_CAMERA_RAW_FRAME_BUFFER_COLS*EI_CAMERA_RAW_FRAME_BUFFER_ROWS*EI_CAMERA_FRAME_BYTE_SIZE);
  if (!snapshot_buf) { ei_printf("ERR: snapshot buffer 할당 실패\n"); return; }

  ei::signal_t signal;
  signal.total_length = EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
  signal.get_data = &ei_camera_get_data;

  if (!ei_camera_capture((size_t)EI_CLASSIFIER_INPUT_WIDTH, (size_t)EI_CLASSIFIER_INPUT_HEIGHT, snapshot_buf)) {
    ei_printf("캡처 실패\r\n"); free(snapshot_buf); return;
  }

  ei_impulse_result_t result = { 0 };
  if (run_classifier(&signal, &result, false) != EI_IMPULSE_OK) { free(snapshot_buf); return; }

  // 가장 확률 높은 클래스
  int best = 0;
  for (uint16_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++)
    if (result.classification[i].value > result.classification[best].value) best = i;
  const char* label = ei_classifier_inferencing_categories[best];
  float conf = result.classification[best].value;

  ei_printf(">>> %s (%.0f%%)\n", label, conf*100.0f);

  // 안정화: 같은 라벨이 연속 STABLE_NEEDED 번 + 확률 충분 + 유지시간 지남 → 손 움직임
  if (conf >= CONF_TH && strcmp(label, lastShown) == 0) stable++;
  else stable = (conf >= CONF_TH) ? 1 : 0;
  strncpy(lastShown, label, sizeof(lastShown)-1);

  static char applied[32] = "";
  if (stable >= STABLE_NEEDED && millis() > holdUntil && strcmp(label, applied) != 0) {
    applyGesture(label);
    strncpy(applied, label, sizeof(applied)-1);
    holdUntil = millis() + HOLD_MS;
    ei_printf("✋ 손동작: %s\n", label);
  }

  free(snapshot_buf);
}

// ── 카메라 헬퍼 (gesture_inference 와 동일) ──
bool ei_camera_init(void) {
  if (is_initialised) return true;
  if (esp_camera_init(&camera_config) != ESP_OK) { Serial.println("Camera init 실패"); return false; }
  sensor_t *s = esp_camera_sensor_get();
  if (s->id.PID == OV3660_PID) { s->set_vflip(s,1); s->set_brightness(s,1); s->set_saturation(s,0); }
  s->set_hmirror(s, 1);   // ★ 캡처(_HW)와 좌우반전 일치 = 학습 데이터와 방향 맞춤(OV2640)
  is_initialised = true;
  return true;
}
bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf) {
  if (!is_initialised) { ei_printf("ERR: Camera 미초기화\r\n"); return false; }
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { ei_printf("캡처 실패\n"); return false; }
  bool ok = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, snapshot_buf);
  esp_camera_fb_return(fb);
  if (!ok) { ei_printf("변환 실패\n"); return false; }
  if ((img_width != EI_CAMERA_RAW_FRAME_BUFFER_COLS) || (img_height != EI_CAMERA_RAW_FRAME_BUFFER_ROWS))
    ei::image::processing::crop_and_interpolate_rgb888(out_buf, EI_CAMERA_RAW_FRAME_BUFFER_COLS, EI_CAMERA_RAW_FRAME_BUFFER_ROWS,
                                                       out_buf, img_width, img_height);
  return true;
}
static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr) {
  size_t pixel_ix = offset * 3, out_ix = 0, left = length;
  while (left) { out_ptr[out_ix++] = (snapshot_buf[pixel_ix+2]<<16)+(snapshot_buf[pixel_ix+1]<<8)+snapshot_buf[pixel_ix]; pixel_ix += 3; left--; }
  return 0;
}

#if !defined(EI_CLASSIFIER_SENSOR) || EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_CAMERA
#error "Invalid model for current sensor"
#endif
