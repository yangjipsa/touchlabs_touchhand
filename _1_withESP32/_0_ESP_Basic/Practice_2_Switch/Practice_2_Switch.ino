/*
 * ============================================================
 *  XIAO ESP32S3 Sense - 기초실습 ②  스위치 (셔터 버튼)
 * ============================================================
 *  Author  : yangjipsa  /  TouchLabs (touchlabs.kr)
 *  Board   : Seeed Studio XIAO ESP32S3 (Sense)
 *  확장보드 : 부저 GPIO4 · 스위치 GPIO1 · 네오픽셀 GPIO2
 *  목표    : 버튼 눌림을 감지하는 법 (풀업 + 디바운스)
 *  배선    : 버튼 한쪽 = GPIO1, 다른쪽 = GND
 *            내부 풀업 사용 -> 평소 HIGH, 누르면 LOW
 *  Tools   : Board = XIAO_ESP32S3 / USB CDC On Boot = Enabled
 *  확인    : 시리얼 모니터 115200
 * ============================================================
 */

#define PIN_SWITCH   1     // 스위치 핀 (GPIO1 = D0)

int  lastState = HIGH;     // 직전 버튼 상태
int  pressCount = 0;       // 누른 횟수
unsigned long lastChange = 0;
const unsigned long DEBOUNCE_MS = 30;   // 채터링 방지 시간

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SWITCH, INPUT_PULLUP);    // 내부 풀업: 평소 HIGH, 누르면 LOW
  Serial.println("스위치 실습 준비 완료 — 버튼을 눌러보세요");
}

void loop() {
  int state = digitalRead(PIN_SWITCH);

  // 상태가 바뀌었고, 디바운스 시간이 지났을 때만 처리
  if (state != lastState && millis() - lastChange > DEBOUNCE_MS) {
    lastChange = millis();
    lastState = state;

    if (state == LOW) {                 // 눌림 (HIGH -> LOW)
      pressCount++;
      Serial.printf("● 눌림!  (총 %d번)\n", pressCount);
    } else {                            // 뗌 (LOW -> HIGH)
      Serial.println("○ 뗌");
    }
  }
}
