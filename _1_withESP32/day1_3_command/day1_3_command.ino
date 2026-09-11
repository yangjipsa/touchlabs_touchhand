/*
 * ============================================================
 *  Amazing Hand  -  [3] USB Command Firmware  (최종본)
 * ============================================================
 *  Author   : yangjipsa
 *  Company  : TouchLabs (touchlabs.kr)
 *  Version  : 1.1
 *  Date     : 2026-08-25
 *  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
 *  Purpose  : PC(파이썬)가 USB 시리얼로 보내는 명령을 받아
 *             포즈/모션을 실행하는 최종 펌웨어.
 *  Fingers  : 4개를 사람 손처럼 [엄지, 검지, 중지약지, 새끼] 로 표현
 *             (중지+약지를 한 손가락으로 취급, 새끼 포함)
 *  Board    : Seeed Studio XIAO ESP32S3
 *  Wiring   : XIAO D6(GPIO43,TX) -> Waveshare 어댑터 RX
 *             XIAO D7(GPIO44,RX) -> Waveshare 어댑터 TX
 *             GND 공통 / 서보 전원 5V (어댑터 UART 모드)
 *  Upload   : Board            = "XIAO_ESP32S3"
 *             USB CDC On Boot  = "Enabled"
 *  Protocol : PC -> XIAO (한 줄 = 한 명령, 개행으로 끝)
 *     P<n>                        포즈 (0~4)      예) P3
 *     M<n>                        모션 (1~6)      예) M1 = 노노
 *     F b0,b1,b2,b3,s0,s1,s2,s3   자유 포즈(굽힘4+좌우4)
 *                                 순서=[엄지,검지,중지약지,새끼]
 *     N                           중립
 *   XIAO -> PC : 실행 끝나면 "OK", 잘못된 명령이면 "ERR" (부팅 시 "READY")
 *  Hand     : 왼손/오른손은 HAND_RIGHT / HAND_LEFT 한 줄로 선택.
 *  Note     : 외부 라이브러리 불필요 — SCS(scscl) 패킷 직접 생성.
 *             손가락↔서보 매핑은 SA/SB 표에서 조정.
 *             파이썬:  day1_4_command.py (직접 제어)
 *                      day1_5_LLM_select.py (LLM 선택)
 *                      day1_6_LLM_create.py (LLM 각도생성)
 * ------------------------------------------------------------
 *  Copyright (c) 2026 TouchLabs.  All rights reserved.
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
#define BUS_GAP_US  700           // 패킷 사이 간격 — 연속전송 깨짐 방지

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
  const int SDIR = +1;            // 왼손 (실측 확인). 브이가 오므라들면 부호 반대로
#else
  const int SDIR = -1;            // 오른손 (거울상)
#endif
const int BDIR = +1;              // 굽힘 방향 (양손 동일)

// ───────── 손가락 = 서보쌍 매핑 (물리 배선에 맞게 조정) ─────────
//  손가락 순서:  0=엄지  1=검지  2=중지약지  3=새끼
//  실측 매핑:  검지=서보1,2 / 중지약지=3,4 / 새끼=5,6 / 엄지=7,8
//  ★ 엉뚱한 손가락이 움직이면 아래 두 줄의 서보 ID 순서만 바꾸면 됨.
const uint8_t SA[4] = { 7, 1, 3, 5 };   // 엄지, 검지, 중지약지, 새끼 (a쪽 서보)
const uint8_t SB[4] = { 8, 2, 4, 6 };   //                          (b쪽 서보)
#define THUMB  0
#define INDEX  1
#define MIDDLE 2                          // 중지약지
#define PINKY  3

// ───────── 손 모델 (offsets.py 이식) ─────────
const int MID = 511;
const int OFFSET[9] = { 0, 0, +14, -16, -28, +10, -20, +8, +7 };  // [서보ID 1..8]
const int LIMIT = 307;
const int SPEED = 600;

const int FLEX = 300, EXT = 80, SWAY = 110, SPREAD = 65;
const int THUMB_FLEX = 180, THUMB_TUCK = 120;   // 주먹 시 엄지 안쪽으로 감기

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

// ───────── 포즈 (0~4) ─────────
void pOpen() { poseSet(-EXT, -EXT, -EXT, -EXT); }
void pFist() {   // 네 손가락 먼저 말고 → 엄지를 위로 (엄지·검지 간섭 방지)
  finger(INDEX, FLEX); finger(MIDDLE, FLEX); finger(PINKY, FLEX);
  delay(150);
  finger(THUMB, THUMB_FLEX, THUMB_TUCK);
}

// 숫자 세기: 검지 → 중지약지 → 새끼 → 엄지 순으로 편다
void pCount(int n) {
  const int order[4] = { INDEX, MIDDLE, PINKY, THUMB };
  bool up[4] = { false, false, false, false };
  for (int i = 0; i < n && i < 4; i++) up[order[i]] = true;
  for (int i = 0; i < 4; i++) finger(i, up[i] ? -EXT : FLEX);
}

bool doPose(int n) {
  switch (n) {
    case 0:  poseSet(0, 0, 0, 0); break;                                     // 중립
    case 1:  pCount(1); break;                                               // 하나 (검지)
    case 2:  pCount(2); break;                                               // 둘 (검지+중지약지)
    case 3:  pCount(3); break;                                               // 셋 (+새끼)
    case 4:  pCount(4); break;                                               // 넷 (다 폄)
    default: return false;
  }
  return true;
}

// ───────── 모션 (1~6) ─────────  poseSet 인자 순서 = [엄지, 검지, 중지약지, 새끼]
//  m1 노노 · m2 가위바위보 · m3 박수 · m4 따봉 · m5 브이 · m6 손흔들기
void mNo() {   // 검지 세우고 좌우로 "노노"
  finger(THUMB,FLEX); finger(INDEX,-EXT); finger(MIDDLE,FLEX); finger(PINKY,FLEX); delay(400);
  for (int r=0;r<4;r++){ finger(INDEX,-EXT,SWAY); delay(180); finger(INDEX,-EXT,-SWAY); delay(180);}
  finger(INDEX,-EXT,0); delay(200); pOpen();
}
void mRps() { pFist(); delay(700);          // 바위 → 가위 → 보
  finger(THUMB,FLEX); finger(INDEX,-EXT); finger(MIDDLE,-EXT); finger(PINKY,FLEX); delay(700); pOpen(); delay(700); }
void mClap() {   // 박수: 네 손가락 모아 접었다 폈다
  for (int r=0;r<3;r++){ poseSet(FLEX,FLEX,FLEX,FLEX); delay(160); pOpen(); delay(160);} }
void mThumbUp() {   // 따봉: 엄지만 펴고 나머지 접기
  finger(THUMB,-EXT); finger(INDEX,FLEX); finger(MIDDLE,FLEX); finger(PINKY,FLEX); delay(900); pOpen(); }
void mV() {   // 브이: 검지·중지약지 펴서 벌리기
  int v = SPREAD/2; finger(THUMB,FLEX); finger(INDEX,-EXT,-v); finger(MIDDLE,-EXT,+v); finger(PINKY,FLEX); delay(900); pOpen(); }
void mWave() { pOpen(); delay(400);         // 손흔들기: 엄지만 반대로 저어 자연스럽게
  for (int i=0;i<4;i++){ poseSet(-EXT,-EXT,-EXT,-EXT, -SWAY, SWAY, SWAY, SWAY); delay(280);
                         poseSet(-EXT,-EXT,-EXT,-EXT,  SWAY,-SWAY,-SWAY,-SWAY); delay(280);} pOpen(); }

bool doMotion(int n) {
  switch (n) {
    case 1: mNo(); break;      case 2: mRps(); break;   case 3: mClap(); break;
    case 4: mThumbUp(); break; case 5: mV(); break;     case 6: mWave(); break;
    default: return false;
  }
  return true;
}

// 자유 포즈: "F b0,b1,b2,b3,s0,s1,s2,s3"  (순서=[엄지,검지,중지약지,새끼])
bool doFree(char *args) {
  int v[8], i = 0;
  char *tok = strtok(args, ", \t");
  while (tok && i < 8) { v[i++] = atoi(tok); tok = strtok(NULL, ", \t"); }
  if (i != 8) return false;
  for (int k = 0; k < 4; k++) finger(k, v[k], v[4 + k]);   // clampv 가 안전장치
  return true;
}

// ───────── 명령 파서 (PC -> XIAO) ─────────
void handleCommand(char *s) {
  char c = toupper(s[0]);
  char *rest = s + 1;
  while (*rest == ' ' || *rest == '\t') rest++;
  bool ok = false;
  switch (c) {
    case 'P': ok = doPose(atoi(rest));   break;
    case 'M': ok = doMotion(atoi(rest)); break;
    case 'F': ok = doFree(rest);         break;
    case 'N': ok = doPose(0);            break;
    default:  ok = false;
  }
  Serial.println(ok ? "OK" : "ERR");
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, PIN_RX, PIN_TX);
  delay(300);
  for (int id = 1; id <= 8; id++) scsWriteByte(id, 40, 1);   // 토크 ON
  doPose(0);                                                 // 중립으로 시작
  Serial.println("READY");
}

void loop() {
  static char buf[80];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (len) { buf[len] = 0; handleCommand(buf); len = 0; }
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}
