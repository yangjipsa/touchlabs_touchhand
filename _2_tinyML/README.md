# TinyML — 카메라 손동작 인식 → 로봇 손 따라하기

XIAO ESP32S3 Sense **카메라**로 사람 제스처(바위·보·가위·따봉·브이)를 인식하고,
**Amazing Hand**가 그대로 따라 하는 TinyML 트랙. (피지컬 AI 심화/확장 — 배포 키트와 별개)

## 폴더 구성 (진행 순서)

| 폴더 | 내용 |
|---|---|
| `1_데이터수집_웹캡처/` | `XIAO_WebCapture` — 브라우저로 클래스별 사진 수집 (`_HW`=버튼 촬영판) |
| `2_추론_테스트/` | `XIAO_gesture_inference`(인식만·시리얼) · `XIAO_camera_preview`·`XIAO_gesture_preview`(카메라 화면 확인) |
| `3_손동작_연동/` | `XIAO_gesture_hand`(권장·통합 최종) · `XIAO_gesture_hand_wifi`(화면+손 동시, 무거움) |

> **선행**: ESP 확장보드 기초(네오픽셀·스위치·부저)는 `_1_withESP32/_0_ESP_Basic/`에서 먼저 익힌다.
> 강의자료(`TinyML_자료`)·설치·회로 상세 가이드는 **강사가 별도 제공**(실습 배포엔 미포함).

## 진행 흐름

```
(ESP 기초=_1) → 웹캡처로 수집 → Edge Impulse 학습(.zip) → 라이브러리 추론 → 손동작 연동
```

## 실행 환경 (Arduino IDE)

- Board **`XIAO_ESP32S3`** · **PSRAM `OPI PSRAM`(필수)** · Partition **`Maximum APP (7.9MB)`** · USB CDC On Boot **Enabled**
- 라이브러리: Edge Impulse에서 받은 `프로젝트명_inferencing`(추론). (`Adafruit NeoPixel`은 ESP 기초=`_1_withESP32/_0_ESP_Basic`)
- 확장보드 핀: 부저 GPIO4 · 스위치 GPIO1 · 네오픽셀 GPIO2 · 서보버스 TX GPIO43/RX GPIO44

## ★ EI 라이브러리 패치 (필수 — 안 하면 재부팅 크래시)

Edge Impulse에서 카메라 모델 라이브러리(`*_inferencing.zip`)를 받아 설치하면, 기본값이 작아 업로드 후 **`reached EI_MAX_OVERFLOW_BUFFER_COUNT`** 를 뿜으며 **재부팅 루프**에 빠질 수 있음. **라이브러리를 새로 받을 때마다** 아래 한 줄을 고친다:

- 파일: `Arduino/libraries/<프로젝트>_inferencing/src/edge-impulse-sdk/porting/ei_classifier_porting.h`
- **약 374번째 줄** `#define EI_MAX_OVERFLOW_BUFFER_COUNT 30` → **`200`** (369번째 줄의 `50`은 그대로 둠)

> 자동 패치 스크립트(`EI_라이브러리_패치.command`)는 강사가 별도 보관 — 위 한 줄만 **수동으로 고쳐도** 동일함.
> 추론 스케치는 라이브러리 본체를 수정하지 않고 **PSRAM 오버라이드를 스케치 안에** 두어, 라이브러리를 다시 받아도 그대로 동작.

## 5클래스 ↔ 손동작

| 제스처 | EI 라벨(권장) | 로봇 손 |
|---|---|---|
| 바위 | `rock` | 주먹 |
| 보 | `paper` | 펴기 |
| 가위 | `scissors` | 검지·중지약지 펴기 |
| 따봉 | `thumbsup` | 엄지만 펴기 |
| 브이 | `v` | 검지·중지약지 벌려 펴기 |

## 쓰기 전 2가지 교체 (`3_손동작_연동/XIAO_gesture_hand`)

1. `#include <…_inferencing.h>` → **내 EI 프로젝트** 라이브러리 이름
2. `GES[]`의 라벨 문자열 → **학습 때 쓴 클래스 이름**과 정확히 일치

> 손 배선·점퍼는 **Day1과 동일**(ESP → Waveshare 점퍼 A). 카메라 XIAO 한 보드가 추론과 서보 구동을 모두 함.

## 비고

- 원본 코드는 저장소(`AmazingHand-main/`)에도 그대로 있으며, 이 폴더는 **수업용으로 정리한 사본**입니다.
- Edge Impulse에서 받은 `*_inferencing.zip` 라이브러리는 용량이 커서 여기 넣지 않음 — 학습 후 각자 생성·설치.
</content>
