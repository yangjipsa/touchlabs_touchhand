/*
 * ============================================================
 *  Amazing Hand  -  [2] Pose / Motion Library
 * ============================================================
 *  Author   : yangjipsa
 *  Company  : TouchLabs (touchlabs.kr)
 *  Version  : 1.1
 *  Date     : 2026-08-25
 *  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
 *  Purpose  : ①(서보 제어)이 검증된 위에 포즈/모션을 얹는다.
 *             파이썬/LLM 없이 ESP 단독으로 시리얼 메뉴에서
 *             골라 동작을 확인·튜닝하는 단계.
 *  Fingers  : 4개를 [엄지, 검지, 중지약지, 새끼] 로 표현
 *             (중지+약지를 한 손가락으로 취급, 새끼 포함)
 *  Board    : Seeed Studio XIAO ESP32S3
 *  Wiring   : XIAO D6(GPIO43,TX) -> Waveshare 어댑터 RX
 *             XIAO D7(GPIO44,RX) -> Waveshare 어댑터 TX
 *             GND 공통 / 서보 전원 5V (어댑터 UART 모드)
 *  Upload   : Board            = "XIAO_ESP32S3"
 *             USB CDC On Boot  = "Enabled"
 *  Serial   : 115200 baud, 줄끝 개행(LF)
 *     p <n>   포즈 실행 (0~9)     예) p5  = 주먹
 *     m <n>   모션 실행 (1~)      예) m1  = 노노  (STEP3에서 m2~6 추가)
 *     N       중립
 *     ?       목록
 *  Hand     : 왼손/오른손은 SDIR 상수로. 굽힘은 양손 동일.
 *  Note     : 외부 라이브러리 불필요 — SCS(scscl) 패킷을 직접 생성.
 *             ③ 명령(최종본)은 이 라이브러리를 그대로 쓰고
 *             입력만 P/M/F/N(기계용)으로 바꾼다.
 * ------------------------------------------------------------
 *  Copyright (c) 2026 TouchLabs.  All rights reserved.
 *
 *  This code is the property of TouchLabs and is provided for
 *  the Amazing Hand product / education kit. Unauthorized
 *  copying, distribution, or modification is prohibited.
 * ============================================================
 */

#include <Arduino.h>

// ───────── 서보 버스 ─────────
#define SERVO_BAUD  1000000
#define PIN_TX      44   // D7 (GPIO44) — PCB 배치에 맞춰 스왑
#define PIN_RX      43   // D6 (GPIO43) — PCB 배치에 맞춰 스왑
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
  uint8_t p[6] = {
    (uint8_t)((pos >> 8) & 0xFF), (uint8_t)(pos & 0xFF),
    (uint8_t)((moveTime >> 8) & 0xFF), (uint8_t)(moveTime & 0xFF),
    (uint8_t)((speed >> 8) & 0xFF), (uint8_t)(speed & 0xFF)
  };
  scsWrite(id, 42, p, 6);
}

// ───────── 손 방향 (왼손/오른손) — 아래 한 줄만 선택 ─────────
//#define HAND_RIGHT
#define HAND_LEFT
#ifdef HAND_LEFT
  const int SDIR = +1;            // 왼손 (실측 확인)
#else
  const int SDIR = -1;            // 오른손 (거울상)
#endif
const int BDIR = +1;              // 굽힘 방향 (양손 동일)

// ───────── 손가락 = 서보쌍 매핑 (물리 배선) ─────────
//  손가락 순서:  0=엄지  1=검지  2=중지약지  3=새끼
//  실측 매핑:  검지=서보1,2 / 중지약지=3,4 / 새끼=5,6 / 엄지=7,8
const uint8_t SA[4] = { 7, 1, 3, 5 };   // 엄지, 검지, 중지약지, 새끼 (a쪽 서보)
const uint8_t SB[4] = { 8, 2, 4, 6 };   //                          (b쪽 서보)
#define THUMB  0
#define INDEX  1
#define MIDDLE 2                          // 중지약지
#define PINKY  3

// ───────── 손 모델 ─────────
const int MID = 511;
const int OFFSET[9] = { 0, 0, +14, -16, -28, +10, -20, +8, +7 };
const int LIMIT = 307;
const int SPEED = 600;
const int FLEX = 300, EXT = 80, SWAY = 110, SPREAD = 65;
const int THUMB_FLEX = 180, THUMB_TUCK = 120;

int  gSpeed = SPEED;
int  midv(int id)          { return constrain(MID + OFFSET[id], 0, 1023); }
int  clampv(int id, int p) { int m = midv(id); return constrain(constrain(p, m - LIMIT, m + LIMIT), 0, 1023); }
void w(int id, int p)      { scsWritePos(id, clampv(id, p), 0, gSpeed); }

void finger(int idx, int flex, int sway = 0) {
  flex *= BDIR; sway *= SDIR;
  w(SA[idx], midv(SA[idx]) - flex + sway);
  w(SB[idx], midv(SB[idx]) + flex + sway);
}
// 순서 = [엄지, 검지, 중지약지, 새끼]
void poseSet(int fT, int fI, int fM, int fP, int sT = 0, int sI = 0, int sM = 0, int sP = 0) {
  finger(THUMB, fT, sT); finger(INDEX, fI, sI); finger(MIDDLE, fM, sM); finger(PINKY, fP, sP);
}

// ───────── 포즈 (0~9) ─────────
void pOpen() { poseSet(-EXT, -EXT, -EXT, -EXT); }
void pFist() {   // 네 손가락 먼저 말고 → 엄지를 위로 (엄지·검지 간섭 방지)
  finger(INDEX, FLEX); finger(MIDDLE, FLEX); finger(PINKY, FLEX);
  delay(150);
  finger(THUMB, THUMB_FLEX, THUMB_TUCK);
}
void pCount(int n) {
  const int order[4] = { INDEX, MIDDLE, PINKY, THUMB };
  bool up[4] = { false, false, false, false };
  for (int i = 0; i < n && i < 4; i++) up[order[i]] = true;
  for (int i = 0; i < 4; i++) finger(i, up[i] ? -EXT : FLEX);
}

const char* poseName(int n) {
  switch (n) {
    case 0: return "중립";  case 1: return "하나";  case 2: return "둘";
    case 3: return "셋";    case 4: return "넷";
    default: return NULL;
  }
}
bool doPose(int n) {
  switch (n) {
    case 0:  poseSet(0, 0, 0, 0); break;
    case 1:  pCount(1); break;
    case 2:  pCount(2); break;
    case 3:  pCount(3); break;
    case 4:  pCount(4); break;
    default: return false;
  }
  return true;
}

// ───────── 모션 (기본 1개 = 노노) ─────────  poseSet 순서 = [엄지, 검지, 중지약지, 새끼]
//  STEP 3(바이브 코딩)에서 m2~m6 을 여기(함수 + doMotion/motionName)에 추가한다.
void mNo() {   // 검지 세우고 좌우로 "노노"
  finger(THUMB,FLEX); finger(INDEX,-EXT); finger(MIDDLE,FLEX); finger(PINKY,FLEX); delay(400);
  for (int r=0;r<4;r++){ finger(INDEX,-EXT,SWAY); delay(180); finger(INDEX,-EXT,-SWAY); delay(180);}
  finger(INDEX,-EXT,0); delay(200); pOpen();
}

const char* motionName(int n) {
  switch (n) {
    case 1: return "노노";
    // ↓ STEP 3(바이브 코딩)에서 case 2~6 추가
    default: return NULL;
  }
}
bool doMotion(int n) {
  switch (n) {
    case 1: mNo(); break;
    // ↓ STEP 3(바이브 코딩)에서 case 2~6 추가
    default: return false;
  }
  return true;
}

// ───────── 시리얼 메뉴 ─────────
void listAll() {
  Serial.println(F("─────────────────────────────────────────────"));
  Serial.println(F("포즈 p: 0중립 1하나 2둘 3셋 4넷"));
  Serial.println(F("모션 m: 1노노   (STEP3 바이브 코딩으로 2~6 추가)"));
  Serial.println(F("기타  : N중립  ?목록   (예: p5 / m1)"));
}

void handleLine(char *s) {
  char c = s[0];
  char *rest = s + 1;
  while (*rest == ' ' || *rest == '\t') rest++;
  int n = atoi(rest);
  if (c == 'N') { doPose(0); Serial.println(F("▶ 중립")); return; }
  if (c == '?') { return; }        // 메뉴는 실행 후 자동으로 다시 뜸
  if (c == 'p') {
    if (doPose(n)) Serial.printf("▶ 포즈 %d · %s\n", n, poseName(n));
    else           Serial.println(F("! 없는 포즈 번호"));
  } else if (c == 'm') {
    const char *nm = motionName(n);
    if (nm) { Serial.printf("▶ 모션 %d · %s ...\n", n, nm); doMotion(n); Serial.println(F("  (완료)")); }
    else    Serial.println(F("! 없는 모션 번호"));
  } else {
    Serial.println(F("? p<n> / m<n> / N / ?"));
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, PIN_RX, PIN_TX);
  delay(300);
  for (int id = 1; id <= 8; id++) scsWriteByte(id, 40, 1);   // 토크 ON
  doPose(0);
  Serial.println(F("\n[②] 포즈/모션 + 시리얼 메뉴 — 준비 완료"));
  listAll();
}

void loop() {
  static char buf[64];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (len) {
        buf[len] = 0;
        Serial.print(F("> ")); Serial.println(buf);
        handleLine(buf);
        listAll();                 // 실행 후 메뉴 다시 표시
        len = 0;
      }
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}
