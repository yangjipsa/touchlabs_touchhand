/*
 * ============================================================
 *  XIAO ESP32S3 Sense - 기초실습 ③  부저 (Buzzer)
 * ============================================================
 *  Author  : yangjipsa  /  TouchLabs (touchlabs.kr)
 *  Board   : Seeed Studio XIAO ESP32S3 (Sense)
 *  확장보드 : 부저 GPIO4 · 스위치 GPIO1 · 네오픽셀 GPIO2
 *  목표    : 부저로 소리내기 (액티브 부저 = HIGH면 소리)
 *  Tools   : Board = XIAO_ESP32S3
 *  ※ 이 보드는 '액티브 부저'라 digitalWrite HIGH/LOW 로 켜고 끔.
 *    (음정을 내는 '패시브 부저'라면 tone(핀, 주파수) 사용)
 * ============================================================
 */

#define PIN_BUZZER   4     // 부저 핀 (GPIO4 = D3)

// ms 동안 삐- 소리 한 번
void beep(int ms) {
  digitalWrite(PIN_BUZZER, HIGH);
  delay(ms);
  digitalWrite(PIN_BUZZER, LOW);
}

// n번 짧게 삐삐삐
void beepN(int n, int onMs, int gapMs) {
  for (int i = 0; i < n; i++) {
    beep(onMs);
    delay(gapMs);
  }
}

void setup() {
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // 시작 신호음 (삐- 삐-)
  beepN(2, 80, 120);
}

void loop() {
  beep(100);          // 짧게 한 번
  delay(1000);

  beepN(3, 60, 80);   // 짧게 세 번
  delay(1500);

  beep(500);          // 길게 한 번
  delay(2000);
}
