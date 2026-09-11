/*
 * ============================================================
 *  XIAO ESP32S3 - 제스처 인식 → 손 + WiFi 화면 (실험, v2 구조)
 * ============================================================
 *  · 웹: 카메라 실시간 화면 + 예측  (http://192.168.4.1)
 *  · 손: 인식된 제스처대로 로봇 손이 따라 함
 *  · 추론은 별도 태스크(큰 스택), 웹은 저장 프레임만 서빙 (메모리 안정화)
 *
 *  ⚠️ WiFi + 모델을 함께 돌려 메모리가 빠듯 → 혹시 부팅 크래시(리부트)나면
 *     BOOT+RESET 로 내려받기모드 후 다른 스케치 업로드. 그땐 WiFi 없는
 *     XIAO_gesture_hand(손+시리얼)로 쓰세요.
 *
 *  [Tools]  Board: XIAO_ESP32S3 / PSRAM: OPI PSRAM /
 *           Partition: Maximum APP (7.9MB) / USB CDC On Boot: Enabled
 *  [배선]   XIAO D6(43)→Waveshare RX · D7(44)→Waveshare TX · GND 공통
 *           서보 5V · Waveshare 점퍼 A(UART)
 * ============================================================
 */

#include <rsp_test_inferencing.h>          // ★ 내 EI 라이브러리 이름
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include <WiFi.h>
#include <WebServer.h>
#include <cstring>

void *ei_malloc(size_t size)           { return heap_caps_aligned_alloc(16, size, MALLOC_CAP_SPIRAM); }
void *ei_calloc(size_t n, size_t size) { void *p = heap_caps_aligned_alloc(16, n*size, MALLOC_CAP_SPIRAM); if (p) memset(p,0,n*size); return p; }
void  ei_free(void *ptr)               { heap_caps_free(ptr); }

// ===== 손 구동 (Day1 서보 라이브러리) =====
#define SERVO_BAUD 1000000
#define PIN_TX 44
#define PIN_RX 43
#define BUS_GAP_US 700
void scsWrite(uint8_t id, uint8_t addr, const uint8_t *data, uint8_t n) {
  while (Serial1.available()) Serial1.read();
  uint8_t len=n+3, chk=id+len+0x03+addr;
  Serial1.write(0xFF); Serial1.write(0xFF); Serial1.write(id); Serial1.write(len);
  Serial1.write(0x03); Serial1.write(addr);
  for (uint8_t i=0;i<n;i++){ Serial1.write(data[i]); chk+=data[i]; }
  Serial1.write((uint8_t)(~chk)); Serial1.flush(); delayMicroseconds(BUS_GAP_US);
}
void scsWriteByte(uint8_t id, uint8_t addr, uint8_t v){ scsWrite(id,addr,&v,1); }
void scsWritePos(uint8_t id,int pos,uint16_t t,uint16_t s){ uint8_t p[6]={(uint8_t)((pos>>8)&0xFF),(uint8_t)(pos&0xFF),(uint8_t)((t>>8)&0xFF),(uint8_t)(t&0xFF),(uint8_t)((s>>8)&0xFF),(uint8_t)(s&0xFF)}; scsWrite(id,42,p,6); }
#define HAND_LEFT
const int SDIR=+1, BDIR=+1;
const uint8_t SA[4]={7,1,3,5}, SB[4]={8,2,4,6};
#define THUMB 0
#define INDEX 1
#define MIDDLE 2
#define PINKY 3
const int MID=511; const int OFFSET[9]={0,0,+14,-16,-28,+10,-20,+8,+7};
const int LIMIT=307, SPEED=600, FLEX=300, EXT=80, SWAY=110, SPREAD=65, THUMB_FLEX=180, THUMB_TUCK=120;
int  midv(int id){ return constrain(MID+OFFSET[id],0,1023); }
int  clampv(int id,int p){ int m=midv(id); return constrain(constrain(p,m-LIMIT,m+LIMIT),0,1023); }
void w(int id,int p){ scsWritePos(id,clampv(id,p),0,SPEED); }
void finger(int idx,int flex,int sway=0){ flex*=BDIR; sway*=SDIR; w(SA[idx],midv(SA[idx])-flex+sway); w(SB[idx],midv(SB[idx])+flex+sway); }
void handOpen(){ finger(THUMB,-EXT); finger(INDEX,-EXT); finger(MIDDLE,-EXT); finger(PINKY,-EXT); }
void poseRock(){ finger(INDEX,FLEX); finger(MIDDLE,FLEX); finger(PINKY,FLEX); delay(150); finger(THUMB,THUMB_FLEX,THUMB_TUCK); }
void posePaper(){ handOpen(); }
void poseScissors(){ finger(THUMB,FLEX); finger(INDEX,-EXT); finger(MIDDLE,-EXT); finger(PINKY,FLEX); }
void poseThumbsUp(){ finger(THUMB,-EXT); finger(INDEX,FLEX); finger(MIDDLE,FLEX); finger(PINKY,FLEX); }
void poseV(){ int v=SPREAD/2; finger(THUMB,FLEX); finger(INDEX,-EXT,-v); finger(MIDDLE,-EXT,+v); finger(PINKY,FLEX); }
struct Gesture{ const char* label; void(*pose)(); };
Gesture GES[]={{"rock",poseRock},{"paper",posePaper},{"scissors",poseScissors},{"thumbsup",poseThumbsUp},{"v",poseV}};
const int N_GES=sizeof(GES)/sizeof(GES[0]);
void applyGesture(const char* label){ for(int i=0;i<N_GES;i++) if(strcmp(label,GES[i].label)==0){ GES[i].pose(); return; } }

// ===== 카메라 핀 =====
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 10
#define SIOD_GPIO_NUM 40
#define SIOC_GPIO_NUM 39
#define Y9_GPIO_NUM 48
#define Y8_GPIO_NUM 11
#define Y7_GPIO_NUM 12
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 16
#define Y4_GPIO_NUM 18
#define Y3_GPIO_NUM 17
#define Y2_GPIO_NUM 15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM 47
#define PCLK_GPIO_NUM 13
#define RAW_W 320
#define RAW_H 240

// 인식 안정화
#define CONF_TH        0.60f
#define STABLE_NEEDED  3
#define HOLD_MS 1200

const char* AP_SSID="TouchLabs-Cam";
const char* AP_PASS="12345678";
WebServer server(80);
uint8_t *rgb_buf=nullptr, *jpg_buf=nullptr;
volatile size_t jpg_len=0;
char pred_str[64]="준비 중...";

static camera_config_t camera_config = {
  .pin_pwdn=PWDN_GPIO_NUM,.pin_reset=RESET_GPIO_NUM,.pin_xclk=XCLK_GPIO_NUM,.pin_sscb_sda=SIOD_GPIO_NUM,.pin_sscb_scl=SIOC_GPIO_NUM,
  .pin_d7=Y9_GPIO_NUM,.pin_d6=Y8_GPIO_NUM,.pin_d5=Y7_GPIO_NUM,.pin_d4=Y6_GPIO_NUM,.pin_d3=Y5_GPIO_NUM,.pin_d2=Y4_GPIO_NUM,.pin_d1=Y3_GPIO_NUM,.pin_d0=Y2_GPIO_NUM,
  .pin_vsync=VSYNC_GPIO_NUM,.pin_href=HREF_GPIO_NUM,.pin_pclk=PCLK_GPIO_NUM,
  .xclk_freq_hz=20000000,.ledc_timer=LEDC_TIMER_0,.ledc_channel=LEDC_CHANNEL_0,
  .pixel_format=PIXFORMAT_JPEG,.frame_size=FRAMESIZE_QVGA,.jpeg_quality=12,.fb_count=1,.fb_location=CAMERA_FB_IN_PSRAM,.grab_mode=CAMERA_GRAB_WHEN_EMPTY,
};

static int get_data(size_t offset,size_t length,float *out){ size_t px=offset*3,o=0,left=length; while(left){ out[o++]=(rgb_buf[px+2]<<16)+(rgb_buf[px+1]<<8)+rgb_buf[px]; px+=3; left--; } return 0; }

const char* PAGE =
"<!doctype html><meta charset='utf-8'><meta name=viewport content='width=device-width,initial-scale=1'>"
"<body style='margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center'>"
"<h3 style='margin:8px'>TouchLabs Gesture Hand</h3>"
"<img id=v style='width:100%;max-width:480px;border-radius:8px'>"
"<div id=p style='font-size:22px;font-weight:700;padding:10px'>...</div>"
"<div style='padding:6px'>"
"<button onclick='fy()' style='font-size:16px;padding:8px 14px;margin:4px;border-radius:8px'>↕ 상하</button>"
"<button onclick='fx()' style='font-size:16px;padding:8px 14px;margin:4px;border-radius:8px'>↔ 좌우</button>"
"</div>"
"<script>"
"var sx=1,sy=1;try{sx=+localStorage.gx||1;sy=+localStorage.gy||1;}catch(e){}"
"function ap(){document.getElementById('v').style.transform='scaleX('+sx+') scaleY('+sy+')';try{localStorage.gx=sx;localStorage.gy=sy;}catch(e){}}"
"function fx(){sx=-sx;ap();}function fy(){sy=-sy;ap();}ap();"
"setInterval(()=>{document.getElementById('v').src='/frame?'+Date.now();"
"fetch('/pred').then(r=>r.text()).then(t=>document.getElementById('p').innerText=t);},1500);</script>";
void handleRoot(){ server.send(200,"text/html",PAGE); }
void handlePred(){ server.send(200,"text/plain",pred_str); }
void handleFrame(){ size_t n=jpg_len; if(!jpg_buf||!n){ server.send(503,"text/plain","no frame"); return; }
  WiFiClient c=server.client(); c.print("HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: "); c.print(n); c.print("\r\nConnection: close\r\n\r\n"); c.write(jpg_buf,n); }

void inferenceTask(void *pv){
  char lastLabel[32]="", applied[32]=""; int stable=0; uint32_t holdUntil=0;
  for(;;){
    camera_fb_t *fb=esp_camera_fb_get();
    if(!fb){ vTaskDelay(pdMS_TO_TICKS(30)); continue; }
    if(jpg_buf && fb->len<=45000){ memcpy(jpg_buf,fb->buf,fb->len); jpg_len=fb->len; }
    bool ok=fmt2rgb888(fb->buf,fb->len,PIXFORMAT_JPEG,rgb_buf);
    esp_camera_fb_return(fb);
    if(ok){
      if((uint32_t)EI_CLASSIFIER_INPUT_WIDTH!=RAW_W||(uint32_t)EI_CLASSIFIER_INPUT_HEIGHT!=RAW_H)
        ei::image::processing::crop_and_interpolate_rgb888(rgb_buf,RAW_W,RAW_H,rgb_buf,EI_CLASSIFIER_INPUT_WIDTH,EI_CLASSIFIER_INPUT_HEIGHT);
      ei::signal_t signal; signal.total_length=EI_CLASSIFIER_INPUT_WIDTH*EI_CLASSIFIER_INPUT_HEIGHT; signal.get_data=&get_data;
      ei_impulse_result_t result={0};
      if(run_classifier(&signal,&result,false)==EI_IMPULSE_OK){
        int best=0; for(uint16_t i=1;i<EI_CLASSIFIER_LABEL_COUNT;i++) if(result.classification[i].value>result.classification[best].value) best=i;
        const char* label=ei_classifier_inferencing_categories[best];
        float conf=result.classification[best].value;
        snprintf(pred_str,sizeof(pred_str),"%s  %.0f%%",label,conf*100.0f);
        Serial.printf(">>> %s\n",pred_str);
        // 안정화 후 손동작
        if(conf>=CONF_TH && strcmp(label,lastLabel)==0) stable++; else stable=(conf>=CONF_TH)?1:0;
        strncpy(lastLabel,label,sizeof(lastLabel)-1);
        if(stable>=STABLE_NEEDED && millis()>holdUntil && strcmp(label,applied)!=0){
          applyGesture(label); strncpy(applied,label,sizeof(applied)-1); holdUntil=millis()+HOLD_MS;
          Serial.printf("✋ 손동작: %s\n",label);
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(30));
  }
}

bool ei_camera_init(){ if(esp_camera_init(&camera_config)!=ESP_OK) return false;
  sensor_t *s=esp_camera_sensor_get(); if(s->id.PID==OV3660_PID){ s->set_vflip(s,1); s->set_brightness(s,1); s->set_saturation(s,0);}
  s->set_hmirror(s, 1);   // ★ 캡처(_HW)와 좌우반전 일치 = 학습 데이터와 방향 맞춤(OV2640)
  return true; }

void setup(){
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD,SERIAL_8N1,PIN_RX,PIN_TX); delay(300);
  for(int id=1;id<=8;id++) scsWriteByte(id,40,1);   // 토크 ON
  handOpen();
  if(!ei_camera_init()) Serial.println("❌ 카메라 초기화 실패"); else Serial.println("✅ 카메라 준비");
  rgb_buf=(uint8_t*)ps_malloc(RAW_W*RAW_H*3); jpg_buf=(uint8_t*)ps_malloc(45000);
  WiFi.softAP(AP_SSID,AP_PASS);
  Serial.printf("핫스팟: '%s' (비번 %s)\n",AP_SSID,AP_PASS);
  Serial.print("👉 브라우저: http://"); Serial.println(WiFi.softAPIP());
  server.on("/",handleRoot); server.on("/pred",handlePred); server.on("/frame",handleFrame); server.begin();
  xTaskCreatePinnedToCore(inferenceTask,"infer",16384,nullptr,2,nullptr,1);   // 우선순위 2 = 웹(loop,1)보다 추론/서보 우선
}
void loop(){ server.handleClient(); delay(1); }

#if !defined(EI_CLASSIFIER_SENSOR) || EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_CAMERA
#error "Invalid model for current sensor"
#endif
