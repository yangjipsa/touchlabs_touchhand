/*
 * ============================================================
 *  XIAO ESP32S3 Sense - 기초실습 ④  통합 (셔터 흉내)
 * ============================================================
 *  Author  : yangjipsa  /  TouchLabs (touchlabs.kr)
 *  Board   : Seeed Studio XIAO ESP32S3 (Sense)
 *  확장보드 : 부저 GPIO4 · 스위치 GPIO1 · 네오픽셀 GPIO2
 *  목표    : 스위치 + 부저 + 네오픽셀을 한 번에 —
 *            버튼(셔터)을 누르면 "삑!" 소리 + LED 번쩍 (사진 찍는 느낌)
 *            평소에는 LED 가 은은하게 숨쉬듯 빛남
 *  준비    : "Adafruit NeoPixel" 라이브러리 설치
 *  Tools   : Board = XIAO_ESP32S3 / USB CDC On Boot = Enabled
 * ============================================================
 */

#include <Adafruit_NeoPixel.h>

#define PIN_BUZZER   4     // GPIO4 (D3)  액티브 부저
#define PIN_SWITCH   1     // GPIO1 (D0)  풀업 버튼
#define PIN_PIXEL    2     // GPIO2 (D1)  네오픽셀
#define NUM_PIXEL    1

Adafruit_NeoPixel pixels(NUM_PIXEL, PIN_PIXEL, NEO_GRB + NEO_KHZ800);

int  lastState = HIGH;
unsigned long lastChange = 0;
const unsigned long DEBOUNCE_MS = 30;

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NUM_PIXEL; i++) pixels.setPixelColor(i, pixels.Color(r, g, b));
  pixels.show();
}
void beep(int ms) {
  digitalWrite(PIN_BUZZER, HIGH); delay(ms); digitalWrite(PIN_BUZZER, LOW);
}

// 셔터: 삑! + 흰색 번쩍
void shutter() {
  setColor(255, 255, 255);   // 플래시
  beep(60);
  delay(120);
  setColor(0, 0, 0);
  delay(80);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  pinMode(PIN_SWITCH, INPUT_PULLUP);
  pixels.begin();
  pixels.setBrightness(60);
  pixels.clear(); pixels.show();
  Serial.println("셔터 실습 준비 완료 — 버튼을 눌러보세요");
}

void loop() {
  // ① 버튼 눌림 감지 (디바운스)
  int state = digitalRead(PIN_SWITCH);
  if (state != lastState && millis() - lastChange > DEBOUNCE_MS) {
    lastChange = millis();
    lastState = state;
    if (state == LOW) {              // 눌리는 순간
      Serial.println("📸 찰칵!");
      shutter();
    }
  }

  // ② 평소에는 파란빛이 은은하게 숨쉬기 (밝기 오르내림)
  //    millis 기반 사인파로 부드럽게
  float t = millis() / 1000.0;
  int brightness = (int)((sin(t * 2.0) * 0.5 + 0.5) * 60);   // 0~60
  setColor(0, 0, brightness);
}
