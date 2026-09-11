/*
 * ============================================================
 *  Amazing Hand  -  [1] Finger / Servo Test
 * ============================================================
 *  Author   : yangjipsa
 *  Company  : TouchLabs (touchlabs.kr)
 *  Version  : 1.0
 *  Date     : 2026-08-25
 *  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
 *  Purpose  : 가장 낮은 층 검증용.
 *             "서보 1개 / 손가락 1개가 원하는 위치로
 *              정확히·부드럽게 가는가"를 확인한다.
 *             (② 모션, ③ 명령 으로 올라가기 전 기초 단계)
 *  Board    : Seeed Studio XIAO ESP32S3
 *  Wiring   : XIAO D6(GPIO43,TX) -> Waveshare 어댑터 RX
 *             XIAO D7(GPIO44,RX) -> Waveshare 어댑터 TX
 *             GND 공통 / 서보 전원 5V (어댑터 UART 모드)
 *  Upload   : Board            = "XIAO_ESP32S3"
 *             USB CDC On Boot  = "Enabled"
 *             (그 외 옵션 기본값. PSRAM 불필요)
 *  Serial   : 115200 baud, 줄끝 개행(LF)
 *     s <id> <pos>          서보 원시위치 (0~1023)   예) s 1 700
 *     n <id>                서보 중립                예) n 1
 *     f <idx> <flex> [sway] 손가락 차동 (idx 0검지 1중지 2약지 3엄지쪽)
 *     N                     전체 중립
 *     t <id> <0|1>          토크 off/on
 *     ?                     도움말
 *  Note     : 외부 라이브러리 불필요 — SCS(scscl) 패킷을 직접 생성.
 *             모든 위치는 중심 ±90°(LIMIT)+물리범위로 자동 클램프.
 * ------------------------------------------------------------
 *  Copyright (c) 2026 TouchLabs.  All rights reserved.
 *
 *  This code is the property of TouchLabs and is provided for
 *  the Amazing Hand product / education kit. Unauthorized
 *  copying, distribution, or modification is prohibited.
 * ============================================================
 */

#include <Arduino.h>

// ───────── 서보 버스 (SCS0009 / scscl) ─────────
#define SERVO_BAUD  1000000
#define PIN_TX      44   // D7 (GPIO44) — PCB 배치에 맞춰 스왑
#define PIN_RX      43   // D6 (GPIO43) — PCB 배치에 맞춰 스왑
#define BUS_GAP_US  700           // 패킷 사이 간격(us) — 어댑터 방향전환 안정화 (이상하면 늘려보기)

void scsWrite(uint8_t id, uint8_t addr, const uint8_t *data, uint8_t n) {
  while (Serial1.available()) Serial1.read();        // 이전 응답 찌꺼기 비우기
  uint8_t len = n + 3;
  uint8_t chk = id + len + 0x03 + addr;              // 0x03 = WRITE
  Serial1.write(0xFF); Serial1.write(0xFF);
  Serial1.write(id);   Serial1.write(len);
  Serial1.write(0x03); Serial1.write(addr);
  for (uint8_t i = 0; i < n; i++) { Serial1.write(data[i]); chk += data[i]; }
  Serial1.write((uint8_t)(~chk));
  Serial1.flush();                                   // 전송 완료까지 대기
  delayMicroseconds(BUS_GAP_US);                     // ★ 버스 안정화 간격 (연속 전송 깨짐 방지)
}
void scsWriteByte(uint8_t id, uint8_t addr, uint8_t val) { scsWrite(id, addr, &val, 1); }
void scsWritePos(uint8_t id, int pos, uint16_t moveTime, uint16_t speed) {
  uint8_t p[6] = {
    (uint8_t)((pos >> 8) & 0xFF), (uint8_t)(pos & 0xFF),
    (uint8_t)((moveTime >> 8) & 0xFF), (uint8_t)(moveTime & 0xFF),
    (uint8_t)((speed >> 8) & 0xFF), (uint8_t)(speed & 0xFF)
  };
  scsWrite(id, 42, p, 6);                            // 42 = Goal Position (big-endian)
}

// ───────── 손 모델 (offsets.py 이식) ─────────
const int MID = 511;
const int OFFSET[9] = { 0, 0, +14, -16, -28, +10, -20, +8, +7 };  // [1..8]
const int LIMIT = 307;               // 중심 ±90° 안전 제한
const int SPEED = 600;

const uint8_t SA[4] = { 1, 3, 5, 7 };   // 손가락 a쪽 서보
const uint8_t SB[4] = { 2, 4, 6, 8 };   // 손가락 b쪽 서보

int  midv(int id)          { return constrain(MID + OFFSET[id], 0, 1023); }
int  clampv(int id, int p) { int m = midv(id); return constrain(constrain(p, m - LIMIT, m + LIMIT), 0, 1023); }
void w(int id, int p)      { scsWritePos(id, clampv(id, p), 0, SPEED); }

void finger(int idx, int flex, int sway = 0) {
  w(SA[idx], midv(SA[idx]) - flex + sway);
  w(SB[idx], midv(SB[idx]) + flex + sway);
}
void allNeutral() { for (int id = 1; id <= 8; id++) w(id, midv(id)); }

// ───────── 명령 파서 ─────────
void help() {
  Serial.println(F("── 명령 ──"));
  Serial.println(F("  s <id> <pos>          서보 원시위치 0~1023"));
  Serial.println(F("  n <id>                서보 중립"));
  Serial.println(F("  f <idx> <flex> [sway] 손가락 차동 (idx 0검지1중지2약지3엄지쪽)"));
  Serial.println(F("  N                     전체 중립"));
  Serial.println(F("  t <id> <0|1>          토크 off/on"));
  Serial.println(F("  ?                     도움말"));
}

void handleLine(char *s) {
  // 첫 토큰(명령)
  char *tok = strtok(s, " \t");
  if (!tok) return;
  char c = tok[0];

  if (c == 'N') { allNeutral(); Serial.println(F("→ 전체 중립")); return; }
  if (c == '?') { help(); return; }

  if (c == 's') {
    int id  = atoi(strtok(NULL, " \t") ?: (char*)"0");
    int pos = atoi(strtok(NULL, " \t") ?: (char*)"0");
    if (id < 1 || id > 8) { Serial.println(F("! id 1~8")); return; }
    w(id, pos);
    Serial.printf("→ 서보 %d = %d (클램프 후 %d)\n", id, pos, clampv(id, pos));
  }
  else if (c == 'n') {
    int id = atoi(strtok(NULL, " \t") ?: (char*)"0");
    if (id < 1 || id > 8) { Serial.println(F("! id 1~8")); return; }
    w(id, midv(id));
    Serial.printf("→ 서보 %d 중립(%d)\n", id, midv(id));
  }
  else if (c == 'f') {
    int idx  = atoi(strtok(NULL, " \t") ?: (char*)"0");
    int flex = atoi(strtok(NULL, " \t") ?: (char*)"0");
    char *sw = strtok(NULL, " \t");
    int sway = sw ? atoi(sw) : 0;
    if (idx < 0 || idx > 3) { Serial.println(F("! idx 0~3")); return; }
    finger(idx, flex, sway);
    Serial.printf("→ 손가락 %d: flex=%d sway=%d\n", idx, flex, sway);
  }
  else if (c == 't') {
    int id = atoi(strtok(NULL, " \t") ?: (char*)"0");
    int on = atoi(strtok(NULL, " \t") ?: (char*)"1");
    if (id < 1 || id > 8) { Serial.println(F("! id 1~8")); return; }
    scsWriteByte(id, 40, on ? 1 : 0);
    Serial.printf("→ 서보 %d 토크 %s\n", id, on ? "ON" : "OFF");
  }
  else {
    Serial.println(F("? 알 수 없는 명령 ('?' 도움말)"));
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, PIN_RX, PIN_TX);
  delay(300);
  for (int id = 1; id <= 8; id++) scsWriteByte(id, 40, 1);   // 토크 ON
  allNeutral();
  Serial.println(F("\n[①] 손가락/서보 시리얼 제어 — 준비 완료"));
  help();
}

void loop() {
  static char buf[64];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (len) {
        buf[len] = 0;
        Serial.print(F("> ")); Serial.println(buf);   // ★ 받은 명령 에코 (입력 확인용)
        handleLine(buf);
        len = 0;
      }
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}
