# Amazing Hand — Command / LLM 제어 (TouchLabs)

로봇 손(SCS0009)을 **USB 시리얼**로 제어한다. 두 갈래:
- **직접 제어** — 번호 입력 → 동작
- **LLM 제어** — Claude/Gemini 와 대화 → 동작

```
[노트북] Python ──USB 시리얼──▶ [XIAO ESP32S3] ──UART(1M)──▶ Waveshare 어댑터 ─▶ SCS0009 8서보
```

---

## 파일 구성 (진행 순서)

### 0-A. ESP32 기초 — `_0_ESP_Basic/`
확장보드 입출력을 먼저 손에 익힌다. (아두이노에서 각 폴더 열어 업로드)
| 폴더 | 역할 |
|---|---|
| `Practice_1_NeoPixel/` | 네오픽셀 RGB LED 색 제어 (`Adafruit NeoPixel`) |
| `Practice_2_Switch/` | 버튼 입력 감지 (내부 풀업·디바운스) |
| `Practice_3_Buzzer/` | 액티브 부저로 소리내기 |
| `Practice_4_All/` | 합본 — 버튼 누르면 소리+색 변화 |

### 0-B. 서보 세팅 — `day1_0_setup/`
| 파일 | 역할 |
|---|---|
| `day1_0_setup.ino` | 서보 **ID(1~8)·중립** 설정 (조립 전). XIAO에서 **쓰기전용** 제어 → 반이중 이슈 없음 |

### 1~3. 아두이노 손제어 (XIAO ESP32S3)
| 폴더 | 역할 |
|---|---|
| `day1_1_finger/` | ① 서보·손가락 시리얼 제어 (프로토콜·방향·중립 검증) |
| `day1_2_motion/` | ② 포즈/모션 라이브러리 + 시리얼 메뉴 (동작 확인·튜닝) |
| `day1_3_command/` | ③ **최종본** — USB 명령(P/M/F/N) 받아 동작. 파이썬이 이걸 제어 |

### 4~6. 파이썬 (노트북)
| 파일 | 역할 |
|---|---|
| `day1_4_command.py` | 번호 입력 → 손 동작 (LLM 없음) |
| `day1_5_LLM_select.py` | LLM이 **정해진 동작을 선택** (P/M) — 안정적 |
| `day1_6_LLM_create.py` | LLM이 **각도를 직접 생성**(키프레임 F) — 창의적 |

> LLM 두 버전은 개념이 다름: **select** = 목록에서 고르기(분류), **create** = 각도를 만들어내기(생성).

> ①②는 학습·검증 단계, 실제 배포 펌웨어는 **③ command** 하나.

---

## 하드웨어 배선
| XIAO ESP32S3 | → | Waveshare Bus Servo Adapter |
|---|---|---|
| D6 (GPIO43, TX) | → | RX |
| D7 (GPIO44, RX) | → | TX |
| GND | → | GND |

어댑터 **UART 모드**, 서보 전원 **5V**. 서보 ID 1~8, 중립·오프셋 세팅 완료 상태.

## 업로드 옵션 (Arduino IDE → Tools)
- Board : **XIAO_ESP32S3**
- USB CDC On Boot : **Enabled**
- 그 외 기본값 (PSRAM 불필요)

## 왼손 / 오른손
`③ command`(및 ②) 코드 상단 **한 줄**로 선택:
```cpp
#define HAND_LEFT       // 기본 (이 수업은 왼손)
// #define HAND_RIGHT   // 오른손이면 이 줄로
```
굽힘은 양손 동일, **좌우(sway)만** 거울상이라 자동 반전(`SDIR`). 좌우가 반대로 보이면 반대쪽으로.

---

## 실행

### ① 직접 제어
```bash
pip install pyserial
python day1_4_command.py
```
```
입력 > p3      → 셋
입력 > m1      → 노노
입력 > N       → 중립
입력 > q       → 종료
```

### ② LLM 제어 — 두 가지 방식
```bash
pip install pyserial requests
```
- **API 키**: `api_key.txt` 파일에 넣거나(추천), 코드 상단 변수, 또는 환경변수
- Gemini 로 바꾸려면 `.py` 상단 `PROVIDER = "gemini"`

**A. 선택(select)** — LLM이 정해진 목록에서 고름 (안정적)
```bash
python day1_5_LLM_select.py
```
```
나 > 안녕            로봇 > 반가워요! 👋   [손흔들기]
나 > 가위바위보 하자  로봇 > 가위바위보! ✌️   [가위바위보]
```

**B. 생성(create)** — LLM이 손 구조를 이해해 각도(키프레임)를 직접 만듦 (창의적)
```bash
python day1_6_LLM_create.py
```
```
나 > 브이 해봐        로봇 > 브이! ✌️ (1프레임)
나 > 손 흔들어봐      로봇 > 안녕! 👋 (4프레임)   ← LLM 이 흔드는 키프레임 생성
```
> create 출력 형식: `{"say":"...🤖", "frames":[{"b":[검지,중지,약지,엄지쪽],"s":[..],"t":ms}, ...]}`
> b=굽힘(-80폄~+300주먹), s=좌우(-110~110). 하드웨어가 안전 클램프.

---

## 동작 번호 (펌웨어 ↔ 파이썬 일치 필수)
**포즈 0~4** : 0중립 1하나 2둘 3셋 4넷  (주먹·가위·보·브이는 모션 m2·m5 등으로)
**모션 1~6** : 1노노 2가위바위보 3박수 4따봉 5브이 6손흔들기  (m2~6은 STEP3 바이브 코딩 결과)

## 명령 프로토콜 (PC → XIAO)
| 명령 | 뜻 |
|---|---|
| `P<n>` | 포즈 |
| `M<n>` | 모션 |
| `F b0,b1,b2,b3,s0,s1,s2,s3` | 자유 포즈 (굽힘4+좌우4) |
| `N` | 중립 |

→ XIAO 가 `OK` / `ERR` 응답 (모션은 끝나야 응답)

## 동작 추가
1. `③ day1_3_command.ino` 의 `doPose()`/`doMotion()` 에 `case` 추가
2. 두 파이썬의 `POSES`/`MOTIONS` 딕셔너리에 같은 번호로 추가
3. 번호·이름을 **양쪽 일치**시킬 것
