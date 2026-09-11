/*
 * XIAO ESP32S3 Sense - 웹 캡처 앱 (물리 버튼 + 네오픽셀 상태LED 버전)
 * ---------------------------------------------------------------
 * - 물리 스위치(D0)를 누르면 촬영 (브라우저 페이지가 열려 있을 때)
 * - 네오픽셀(D1)로 상태 표시:  빨강=초기화/에러, 초록=준비됨, 흰색깜빡=촬영
 * - 사진은 노트북 브라우저에 자동 저장 (SD/리더기 불필요)
 * - 서보(SCS0009)용 UART는 D6/D7 예약 (이 스케치에선 미사용)
 *
 * [필요 라이브러리]  Adafruit NeoPixel  (라이브러리 매니저에서 설치)
 *
 * [Tools 설정]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *              USB Mode: Hardware CDC and JTAG / Partition: Default with spiffs
 *
 * [배선]
 *   버튼:     D0 ── 버튼 ── GND
 *   네오픽셀: D1→DIN,  3V3→VCC,  GND→GND
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Adafruit_NeoPixel.h>

// ===== 네트워크 =====
#define USE_AP_MODE  true            // true=XIAO 자체 핫스팟(수업 권장), false=기존 WiFi
const char* ssid     = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";
const char* ap_ssid  = "TouchLabs-Cam-01";   // ★ 여러 명 동시 사용 시 이름 충돌! 학생마다 다르게 (TouchLabs-Cam-01, -02 … 또는 각자 이름)
const char* ap_pass  = "12345678";

// ===== 하드웨어 핀 =====
#define BTN_PIN  1     // D0 : 셔터 버튼 (버튼→GND, INPUT_PULLUP)
#define PIX_PIN  2     // D1 : 네오픽셀 DIN
#define PIX_N    1     // 네오픽셀 개수
#define BUZ_PIN  4     // D3(GPIO4) : 부저 (촬영 소리)
// 서보용 예약:  D6=GPIO43(TX), D7=GPIO44(RX)

Adafruit_NeoPixel pix(PIX_N, PIX_PIN, NEO_GRB + NEO_KHZ800);

// ===== 카메라 핀 (XIAO ESP32S3 Sense) =====
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

WebServer server(80);

// ===== 상태 =====
volatile bool shotFlag = false;      // 물리 버튼이 눌렸음 → 브라우저가 가져감
bool  camOK    = false;
bool  lastBtn  = HIGH;
unsigned long lastBtnMs = 0;
unsigned long flashUntil = 0;
int   ledShown = -1;                 // 0=red 1=green 2=white

void setPix(int s){
  if(s==ledShown) return;
  ledShown = s;
  if(s==0) pix.setPixelColor(0, pix.Color(60,0,0));      // 빨강
  else if(s==1) pix.setPixelColor(0, pix.Color(0,60,0)); // 초록
  else pix.setPixelColor(0, pix.Color(80,80,80));        // 흰색
  pix.show();
}

// 능동형(액티브) 부저 — HIGH=소리 (음높이는 부저 내부 고정). 짧게 켰다 끔.
void beepOn(int ms){
  digitalWrite(BUZ_PIN, HIGH); delay(ms);
  digitalWrite(BUZ_PIN, LOW);
}
void shutterBeep(){ beepOn(15); delay(35); beepOn(15); }   // 살짝 "삑삑" (셔터 느낌)

// ===== 웹페이지 =====
const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TouchLabs 데이터 수집</title>
<style>
 body{font-family:-apple-system,sans-serif;text-align:center;margin:0;padding:16px;background:#111;color:#eee}
 img{width:100%;max-width:360px;border-radius:12px;background:#000;aspect-ratio:4/3;object-fit:cover}
 input{font-size:20px;padding:8px;width:55%;border-radius:8px;border:1px solid #555;background:#222;color:#fff}
 button{font-size:22px;padding:16px;margin-top:12px;width:82%;max-width:360px;border:0;border-radius:12px;background:#3d8;color:#000;font-weight:700}
 .count{font-size:18px;margin-top:10px;color:#9cf}
 .hint{font-size:12px;color:#888;margin-top:12px;line-height:1.5}
</style></head><body>
 <h3>📷 TouchLabs 데이터 수집</h3>
 <img id="pv" style="transform:scaleY(-1)"><br>
 <div style="margin-top:10px">라벨: <input id="label" value="class1"></div>
 <button id="shoot">촬영 (버튼/Space)</button>
 <div class="count">저장한 사진: <span id="c">0</span></div>
 <div class="hint">크롬 권장 · 처음 "여러 파일 다운로드 허용"을 눌러주세요<br>
 물리 버튼은 이 페이지가 열려 있을 때 작동합니다</div>
<script>
 let c=0, last=null, busy=false;
 const pv=document.getElementById('pv');
 async function preview(){
   try{const r=await fetch('/capture');const b=await r.blob();
       if(last)URL.revokeObjectURL(last);last=URL.createObjectURL(b);pv.src=last;}catch(e){}
   setTimeout(preview,200);
 }
 preview();
 async function shoot(){
   if(busy) return; busy=true;
   try{
     const r=await fetch('/capture?dl=1');const b=await r.blob();
     const url=URL.createObjectURL(b);
     const label=(document.getElementById('label').value||'class1').trim();
     const a=document.createElement('a');
     a.href=url;a.download=label+'.'+Date.now()+'.jpg';
     document.body.appendChild(a);a.click();a.remove();
     setTimeout(()=>URL.revokeObjectURL(url),1000);
     c++;document.getElementById('c').textContent=c;
   }catch(e){}
   busy=false;
 }
 document.getElementById('shoot').onclick=shoot;
 addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();shoot();}});
 // 물리 버튼 폴링
 async function pollBtn(){
   try{const r=await fetch('/button');const t=await r.text();
       if(t.trim()==='1') await shoot();}catch(e){}
   setTimeout(pollBtn,120);
 }
 pollBtn();
</script></body></html>
)HTML";

void handleRoot(){ server.send_P(200, "text/html", PAGE); }

void handleButton(){
  bool s = shotFlag; shotFlag = false;
  server.send(200, "text/plain", s ? "1" : "0");
}

void handleCapture(){
  camera_fb_t* fb = esp_camera_fb_get();
  if(!fb){ server.send(500, "text/plain", "capture failed"); return; }
  WiFiClient client = server.client();
  client.print("HTTP/1.1 200 OK\r\n");
  client.print("Content-Type: image/jpeg\r\n");
  client.printf("Content-Length: %u\r\n", fb->len);
  client.print("Access-Control-Allow-Origin: *\r\n");
  client.print("Connection: close\r\n\r\n");
  client.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
  if(server.hasArg("dl")) shutterBeep();   // 실제 촬영(?dl=1)일 때만 소리
}

void setup(){
  Serial.begin(115200);
  delay(300);
  pix.begin(); pix.setBrightness(80); setPix(0);   // 초기화 = 빨강
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(BUZ_PIN, OUTPUT); digitalWrite(BUZ_PIN, LOW);

  // --- 카메라 ---
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0; config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0=Y2_GPIO_NUM; config.pin_d1=Y3_GPIO_NUM; config.pin_d2=Y4_GPIO_NUM; config.pin_d3=Y5_GPIO_NUM;
  config.pin_d4=Y6_GPIO_NUM; config.pin_d5=Y7_GPIO_NUM; config.pin_d6=Y8_GPIO_NUM; config.pin_d7=Y9_GPIO_NUM;
  config.pin_xclk=XCLK_GPIO_NUM; config.pin_pclk=PCLK_GPIO_NUM;
  config.pin_vsync=VSYNC_GPIO_NUM; config.pin_href=HREF_GPIO_NUM;
  config.pin_sccb_sda=SIOD_GPIO_NUM; config.pin_sccb_scl=SIOC_GPIO_NUM;
  config.pin_pwdn=PWDN_GPIO_NUM; config.pin_reset=RESET_GPIO_NUM;
  config.xclk_freq_hz=10000000;   // VGA에서 FB-OVF 방지 위해 20M→10M
  config.frame_size=FRAMESIZE_VGA;   // 640×480
  config.pixel_format=PIXFORMAT_JPEG;
  config.grab_mode=CAMERA_GRAB_LATEST;
  config.fb_location=CAMERA_FB_IN_PSRAM;
  config.jpeg_quality=12;
  config.fb_count=2;

  if(esp_camera_init(&config)!=ESP_OK){
    Serial.println("카메라 초기화 실패 (PSRAM=OPI PSRAM 확인)");
    setPix(0); return;                              // 빨강 유지
  }
  camOK = true;

  // --- 센서 보정 ---
  sensor_t *s = esp_camera_sensor_get();
  s->set_hmirror(s, 1);      // 좌우 반전 보정 (여전히 반대면 0 으로)
  // s->set_vflip(s, 1);     // 상하도 뒤집으려면 주석 해제

  // --- 네트워크 ---
  IPAddress ip;
  if(USE_AP_MODE){
    WiFi.softAP(ap_ssid, ap_pass); ip = WiFi.softAPIP();
    Serial.printf("핫스팟: '%s' (비번 %s)\n", ap_ssid, ap_pass);
  } else {
    WiFi.begin(ssid, password);
    Serial.print("WiFi 연결중");
    while(WiFi.status()!=WL_CONNECTED){ delay(400); Serial.print("."); }
    Serial.println(); ip = WiFi.localIP();
  }
  Serial.print("👉 크롬에서 열기:  http://"); Serial.println(ip);

  server.on("/", handleRoot);
  server.on("/capture", handleCapture);
  server.on("/button", handleButton);
  server.begin();

  setPix(1);   // 준비 완료 = 초록
}

void loop(){
  server.handleClient();

  // 버튼 읽기 (디바운스)
  bool b = digitalRead(BTN_PIN);
  unsigned long now = millis();
  if(b != lastBtn && now - lastBtnMs > 30){
    lastBtnMs = now;
    if(lastBtn==HIGH && b==LOW){ shotFlag = true; flashUntil = now + 150; }
    lastBtn = b;
  }

  // LED 상태
  if(!camOK) setPix(0);
  else if(now < flashUntil) setPix(2);   // 촬영 = 흰색
  else setPix(1);                        // 준비 = 초록
}
