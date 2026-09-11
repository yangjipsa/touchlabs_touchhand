/*
 * XIAO ESP32S3 Sense - 웹 캡처 앱 (수업용 데이터 수집 도구)
 * ---------------------------------------------------------------
 * 브라우저에서 [라벨 입력] + [촬영 버튼] → XIAO 카메라 사진이
 * 노트북에 자동 저장됩니다. SD카드 / 리더기 / MSC 전부 불필요!
 *
 * [Tools 설정]
 *   - Board        : XIAO_ESP32S3
 *   - PSRAM        : OPI PSRAM          (필수)
 *   - USB Mode     : Hardware CDC and JTAG   (일반 업로드용)
 *   - Partition    : Default with spiffs
 *
 * [사용법]
 *   1) 아래 WiFi 정보 입력 (또는 USE_AP_MODE=true 로 XIAO 자체 핫스팟)
 *   2) 업로드 → Serial Monitor(115200)에 뜨는 http://주소 확인
 *   3) 같은 WiFi의 노트북 크롬에서 그 주소 열기
 *   4) 라벨 입력 후 [촬영](또는 Space) → 사진이 노트북에 저장됨
 *   5) 클래스마다 라벨 바꿔 반복 → Edge Impulse에 업로드
 *
 * 파일명은  라벨.시간.jpg  형식이라, Edge Impulse 업로드 시
 * "Infer from filename"으로 라벨이 자동 인식됩니다.
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// ===== 네트워크 설정 =====================================
#define USE_AP_MODE  false          // true=XIAO가 자체 WiFi 핫스팟 생성, false=기존 WiFi 접속

// (USE_AP_MODE=false 일 때) 접속할 WiFi
const char* ssid     = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";

// (USE_AP_MODE=true 일 때) XIAO가 만들 핫스팟  → 노트북을 이 WiFi에 연결 후 http://192.168.4.1
const char* ap_ssid  = "TouchLabs-Cam-01";   // ★ 여러 명 동시 사용 시 이름 충돌! 학생마다 다르게 (TouchLabs-Cam-01, -02 … 또는 각자 이름)
const char* ap_pass  = "12345678";  // 8자 이상

// ===== XIAO ESP32S3 Sense 카메라 핀 ======================
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   10
#define SIOD_GPIO_NUM   40
#define SIOC_GPIO_NUM   39
#define Y9_GPIO_NUM     48
#define Y8_GPIO_NUM     11
#define Y7_GPIO_NUM     12
#define Y6_GPIO_NUM     14
#define Y5_GPIO_NUM     16
#define Y4_GPIO_NUM     18
#define Y3_GPIO_NUM     17
#define Y2_GPIO_NUM     15
#define VSYNC_GPIO_NUM  38
#define HREF_GPIO_NUM   47
#define PCLK_GPIO_NUM   13

WebServer server(80);

// ===== 웹페이지 (브라우저 UI) ============================
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
 <button id="shoot">촬영 (Space)</button>
 <div class="count">저장한 사진: <span id="c">0</span></div>
 <div class="hint">크롬 권장 · 처음 "여러 파일 다운로드 허용"을 눌러주세요<br>
 클래스가 바뀌면 라벨을 바꾸세요 (파일명에 라벨이 들어갑니다)</div>
<script>
 let c=0, last=null;
 const pv=document.getElementById('pv');
 async function preview(){
   try{const r=await fetch('/capture');const b=await r.blob();
       if(last)URL.revokeObjectURL(last);last=URL.createObjectURL(b);pv.src=last;}catch(e){}
   setTimeout(preview,200);
 }
 preview();
 async function shoot(){
   const r=await fetch('/capture');const b=await r.blob();
   const url=URL.createObjectURL(b);
   const label=(document.getElementById('label').value||'class1').trim();
   const a=document.createElement('a');
   a.href=url;a.download=label+'.'+Date.now()+'.jpg';
   document.body.appendChild(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),1000);
   c++;document.getElementById('c').textContent=c;
 }
 document.getElementById('shoot').onclick=shoot;
 addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();shoot();}});
</script></body></html>
)HTML";

void handleRoot(){ server.send_P(200, "text/html", PAGE); }

// 카메라 한 장을 JPEG로 응답 (raw write 방식 = 바이너리 안전)
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
}

void setup(){
  Serial.begin(115200);
  delay(500);

  // --- 카메라 초기화 ---
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM; config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size   = FRAMESIZE_QVGA;     // 320x240 (수집엔 충분, 파일 작음)
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count     = 2;

  if(esp_camera_init(&config) != ESP_OK){
    Serial.println("카메라 초기화 실패! (PSRAM=OPI PSRAM 확인, 카메라 재장착)");
    return;
  }

  { sensor_t *s = esp_camera_sensor_get(); if (s) s->set_hmirror(s, 1); }  // ★ _HW·추론과 좌우반전 일치(OV2640)

  // --- 네트워크 ---
  IPAddress ip;
  if(USE_AP_MODE){
    WiFi.softAP(ap_ssid, ap_pass);
    ip = WiFi.softAPIP();
    Serial.printf("핫스팟 생성: '%s' (비번 %s)\n", ap_ssid, ap_pass);
    Serial.println("→ 노트북을 이 WiFi에 연결하세요");
  } else {
    WiFi.begin(ssid, password);
    Serial.print("WiFi 연결중");
    while(WiFi.status() != WL_CONNECTED){ delay(400); Serial.print("."); }
    Serial.println();
    ip = WiFi.localIP();
  }
  Serial.print("👉 크롬에서 열기:  http://");
  Serial.println(ip);

  server.on("/", handleRoot);
  server.on("/capture", handleCapture);
  server.begin();
}

void loop(){ server.handleClient(); }
