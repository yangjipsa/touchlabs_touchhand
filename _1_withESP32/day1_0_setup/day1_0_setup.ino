/*
 * ============================================================
 *  Amazing Hand  -  [0] Servo Setup  (ID 설정 · 중립 설정)
 * ============================================================
 *  Author   : yangjipsa
 *  Company  : TouchLabs (touchlabs.kr)
 *  Version  : 1.0
 *  Date     : 2026-08-25
 *  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
 *  Purpose  : 조립 전 서보 세팅을 XIAO ESP32S3 에서 한다.
 *              1) ID 설정  (서보마다 번호 1~8 부여)
 *              2) 중립 설정 (혼/손가락을 중앙에 맞춰 조립)
 *             읽기(ping) 없이 '쓰기'만으로 동작 → 반이중 이슈 없음.
 *  Board    : Seeed Studio XIAO ESP32S3
 *  Wiring   : XIAO D6(GPIO43,TX) -> Waveshare 어댑터 RX
 *             XIAO D7(GPIO44,RX) -> Waveshare 어댑터 TX
 *             GND 공통 / 서보 전원 5V (어댑터 UART 모드)
 *  Upload   : Board = "XIAO_ESP32S3" / USB CDC On Boot = "Enabled"
 *  Serial   : 115200 baud, 줄끝 개행(LF)
 *     id <n>          연결된 서보 1개의 ID를 n(1~8)으로  (⚠️ 1개만 연결!)
 *     mid <id>        서보 하나를 중립(511)으로
 *     mid all         ID 1~8 전부 중립으로 (조립/정렬용)
 *     pos <id> <p>    서보를 특정 위치로 (0~1023)
 *     t <id>          튜닝모드: +5 / -5 / 숫자 / q  (중심 미세조정)
 *     ?               도움말
 *  Note     : ID 변경은 EEPROM 이라 전원 꺼도 유지됨.
 *             SCS0009 중립 = 511.  튜닝 offset 은 손 제어코드에 반영.
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
#define BUS_GAP_US  700
#define BROADCAST   0xFE       // 브로드캐스트 ID (연결된 모든 서보)

// SCS 레지스터
#define REG_ID      5
#define REG_LOCK    48         // 0=EEPROM 잠금해제, 1=잠금
#define REG_TORQUE  40         // 1=토크 ON
#define REG_GOAL    42         // 목표 위치
#define MID         511        // SCS0009 중립

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
  pos = constrain(pos, 0, 1023);
  uint8_t p[6] = {
    (uint8_t)((pos >> 8) & 0xFF), (uint8_t)(pos & 0xFF),
    (uint8_t)((moveTime >> 8) & 0xFF), (uint8_t)(moveTime & 0xFF),
    (uint8_t)((speed >> 8) & 0xFF), (uint8_t)(speed & 0xFF)
  };
  scsWrite(id, REG_GOAL, p, 6);
}

// ───────── 기능 ─────────
// ID 설정: 연결된 서보 1개에 브로드캐스트로 ID 부여 (스캔 불필요)
void setServoID(int newid) {
  scsWriteByte(BROADCAST, REG_LOCK, 0);   delay(20);   // EEPROM 잠금해제
  scsWriteByte(BROADCAST, REG_ID, newid); delay(20);   // ID 쓰기
  scsWriteByte(BROADCAST, REG_LOCK, 1);   delay(50);   // 재잠금
  // 새 ID로 살짝 흔들어 확인
  scsWriteByte(newid, REG_TORQUE, 1);
  scsWritePos(newid, MID - 40, 0, 150); delay(400);
  scsWritePos(newid, MID + 40, 0, 150); delay(400);
  scsWritePos(newid, MID,      0, 150);
  Serial.printf("→ ID를 %d 로 설정. 서보가 좌우로 살짝 흔들렸으면 성공! (전원 꺼도 유지)\n", newid);
}

void midOne(int id) {
  scsWriteByte(id, REG_TORQUE, 1);
  scsWritePos(id, MID, 0, 150);
  Serial.printf("→ ID %d 중립(%d). 이 위치에서 혼/손가락 정렬하세요.\n", id, MID);
}
void midAll() {
  for (int id = 1; id <= 8; id++) { scsWriteByte(id, REG_TORQUE, 1); scsWritePos(id, MID, 0, 150); }
  Serial.println("→ ID 1~8 전부 중립(511)으로. 조립/정렬하세요. (없는 ID는 무시됨)");
}

// 튜닝 모드 상태
int tuneID  = 0;               // 0 = 튜닝모드 아님
int tunePos = MID;

void enterTune(int id) {
  tuneID = id; tunePos = MID;
  scsWriteByte(id, REG_TORQUE, 1);
  scsWritePos(id, tunePos, 0, 100);
  Serial.printf("\n[튜닝 ID %d] +5 / -5 / 숫자(0~1023) / q(종료)\n", id);
  Serial.printf("[ID %d] 목표 %d (offset %+d) > ", tuneID, tunePos, tunePos - MID);
}
void tuneLine(char *s) {
  if (s[0] == 'q') {
    Serial.printf("\n>>> ID %d :  중립값 = %d,  offset = %+d\n", tuneID, tunePos, tunePos - MID);
    Serial.println("    → 손 제어코드의 OFFSET 에 이 값을 넣으세요.");
    tuneID = 0;
    return;
  }
  if (s[0] == '+' || s[0] == '-') tunePos += atoi(s);   // 상대 이동
  else                            tunePos  = atoi(s);   // 절대 위치
  tunePos = constrain(tunePos, 0, 1023);
  scsWritePos(tuneID, tunePos, 0, 100);
  Serial.printf("[ID %d] 목표 %d (offset %+d) > ", tuneID, tunePos, tunePos - MID);
}

// ───────── ID 일괄 설정 마법사 (여러 대 만들 때 빠르게) ─────────
#define SERVO_COUNT 8
bool autoMode = false;
int  autoID   = 1;

void autoPrompt() {
  Serial.printf("\n[일괄] %d번 서보만 꽂고 Enter   (s=건너뛰기, q=중단)\n> ", autoID);
}
void startAuto() {
  autoMode = true; autoID = 1;
  Serial.println(F("\n=== ID 일괄 설정 (한 대분 1~8) ==="));
  Serial.println(F("서보를 '1개씩' 꽂고 Enter 만 누르면 번호가 자동으로 올라갑니다."));
  autoPrompt();
}
void handleAuto(char *s) {
  if (s[0] == 'q') { autoMode = false; Serial.println(F("(일괄모드 중단)")); return; }
  if (s[0] == 's') { Serial.printf("(ID %d 건너뜀)\n", autoID); autoID++; }
  else             { setServoID(autoID); autoID++; }
  if (autoID > SERVO_COUNT) {
    autoMode = false;
    Serial.println(F("\n✅ 한 대 완료! (1~8)  다음 손이면 'auto' 다시 실행."));
    return;
  }
  autoPrompt();
}

void help() {
  Serial.println(F("── 서보 세팅 명령 ──"));
  Serial.println(F("  auto          ID 일괄설정 (Enter로 1~8 쭉쭉 — 여러 대용) ⭐"));
  Serial.println(F("  id <n>        연결된 서보 1개 ID 설정 (⚠️ 1개만 연결!)"));
  Serial.println(F("  mid <id>      서보 하나 중립(511)"));
  Serial.println(F("  mid all       ID 1~8 전부 중립"));
  Serial.println(F("  pos <id> <p>  특정 위치 (0~1023)"));
  Serial.println(F("  t <id>        튜닝모드 (+5/-5/숫자/q)"));
  Serial.println(F("  ?             도움말"));
}

void handleLine(char *s) {
  if (tuneID != 0) { tuneLine(s); return; }     // 튜닝모드면 그쪽으로

  char *cmd = strtok(s, " \t");
  if (!cmd) return;

  if (!strcmp(cmd, "id")) {
    char *a = strtok(NULL, " \t");
    if (!a) { Serial.println(F("! 사용법: id <번호>  (예: id 1)")); return; }
    int n = atoi(a);
    if (n < 1 || n > 30) { Serial.println(F("! ID는 1~30")); return; }
    setServoID(n);
  }
  else if (!strcmp(cmd, "mid")) {
    char *a = strtok(NULL, " \t");
    if (!a) { Serial.println(F("! 사용법: mid <id> 또는 mid all")); return; }
    if (!strcmp(a, "all")) midAll();
    else midOne(atoi(a));
  }
  else if (!strcmp(cmd, "pos")) {
    char *a = strtok(NULL, " \t"); char *b = strtok(NULL, " \t");
    if (!a || !b) { Serial.println(F("! 사용법: pos <id> <위치>")); return; }
    int id = atoi(a), p = atoi(b);
    scsWriteByte(id, REG_TORQUE, 1);
    scsWritePos(id, p, 0, 150);
    Serial.printf("→ ID %d → %d\n", id, constrain(p, 0, 1023));
  }
  else if (!strcmp(cmd, "t")) {
    char *a = strtok(NULL, " \t");
    if (!a) { Serial.println(F("! 사용법: t <id>")); return; }
    enterTune(atoi(a));
  }
  else if (!strcmp(cmd, "auto")) startAuto();
  else if (!strcmp(cmd, "?")) help();
  else Serial.println(F("? 알 수 없는 명령 ('?' 도움말)"));
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, PIN_RX, PIN_TX);
  delay(300);
  Serial.println(F("\n[0] Amazing Hand 서보 세팅 — 준비 완료"));
  Serial.println(F("  ※ ID 설정할 땐 서보를 반드시 '1개만' 연결하세요!"));
  help();
}

void loop() {
  static char buf[48];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;                 // CR 무시 (CRLF 대응)
    if (c == '\n') {
      buf[len] = 0;
      if (autoMode)   { Serial.println(buf); handleAuto(buf); }   // 빈 Enter도 처리
      else if (len)   { Serial.print(F("> ")); Serial.println(buf); handleLine(buf); }
      len = 0;
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}
