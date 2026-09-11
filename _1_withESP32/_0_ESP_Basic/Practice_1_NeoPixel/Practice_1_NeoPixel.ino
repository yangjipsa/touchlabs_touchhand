/*
 * ============================================================
 *  XIAO ESP32S3 Sense - 기초실습 ①  네오픽셀 (NeoPixel)
 * ============================================================
 *  Author  : yangjipsa  /  TouchLabs (touchlabs.kr)
 *  Board   : Seeed Studio XIAO ESP32S3 (Sense)
 *  확장보드 : 부저 GPIO4 · 스위치 GPIO1 · 네오픽셀 GPIO2
 *  목표    : RGB LED(네오픽셀)로 색을 켜고 바꾸는 법 익히기
 *  준비    : 라이브러리 매니저에서 "Adafruit NeoPixel" 설치
 *  Tools   : Board = XIAO_ESP32S3
 * ============================================================
 */

#include <Adafruit_NeoPixel.h>

#define PIN_PIXEL   2      // 네오픽셀 신호핀 (GPIO2 = D1)
#define NUM_PIXEL   1      // 네오픽셀 개수 (보드에 맞게 수정)

Adafruit_NeoPixel pixels(NUM_PIXEL, PIN_PIXEL, NEO_GRB + NEO_KHZ800);

// 색 하나로 전체 채우기 (r,g,b 는 0~255)
void setColor(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NUM_PIXEL; i++) pixels.setPixelColor(i, pixels.Color(r, g, b));
  pixels.show();
}

void setup() {
  pixels.begin();
  pixels.setBrightness(50);   // 밝기 0~255 (너무 밝으면 눈부심)
  pixels.clear();
  pixels.show();
}

void loop() {
  // 기본 색들을 하나씩
  setColor(255,   0,   0);  delay(600);   // 빨강
  setColor(  0, 255,   0);  delay(600);   // 초록
  setColor(  0,   0, 255);  delay(600);   // 파랑
  setColor(255, 255,   0);  delay(600);   // 노랑
  setColor(255, 255, 255);  delay(600);   // 흰색
  setColor(  0,   0,   0);  delay(600);   // 끄기

  // 무지개 (색상환을 한 바퀴 도는 응용)
  for (int hue = 0; hue < 65536; hue += 512) {
    uint32_t c = pixels.gamma32(pixels.ColorHSV(hue));
    for (int i = 0; i < NUM_PIXEL; i++) pixels.setPixelColor(i, c);
    pixels.show();
    delay(10);
  }
}
