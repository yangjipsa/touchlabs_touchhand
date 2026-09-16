# TouchHand PhysicalAI — SourceCode

**피지컬 AI 교육 키트** 실습 소스코드. 로봇 손(Amazing Hand, 4손가락·서보 8개)을 ESP32·파이썬·LLM으로 움직이고, MuJoCo 시뮬레이션에서 학습한 모양 인식을 실물 손으로 옮긴다. TouchLabs.

- 이 저장소에는 **실습 코드와 실행 안내**만 있다. 강의자료는 포함되지 않는다.
- 각 폴더의 `README.md`에 배선·업로드 옵션·파일별 역할이 더 자세히 있다.

---

## 구성 한눈에

| 폴더 | 트랙 | 내용 | 실행 도구 |
|---|---|---|---|
| `_0_setup/` | 준비 | 서보 ID·중립 세팅 도구 (조립·정비 시) | 터미널 파이썬 |
| `_1_withESP32/` | **Day 1** | ESP32 기초 → 아두이노 손 제어 → 파이썬 제어 → LLM 대화 제어 | Arduino IDE · Thonny/파이썬 |
| `_2_tinyML/` | TinyML | XIAO 카메라로 손동작 인식 → 로봇 손 따라하기 | Arduino IDE · Edge Impulse |
| `_3_withMujoco/` | **Day 2** | MuJoCo 시뮬 → IK → 잡기 감지 → 모양 학습 → 실물 테스트 (sim2real) | 파이썬(MuJoCo) |
| `Demo_dora/` | 참고 | 원본 Amazing Hand dora-rs 데모를 이 키트(왼손)로 돌리는 설정 | dora-rs |

```
Day 1  손 움직이기 (ESP · LLM)  →  Day 2  시뮬에서 배워 실물로 (MuJoCo · sim2real)  →  모양 인식 (구·타원·정육면체)
```

---

## 하드웨어 · 연결

| 구성 | 사양 |
|---|---|
| 로봇 손 | Amazing Hand — 손가락 4개, 손가락당 서보 2개 (Pollen Robotics 오픈소스 + TouchLabs 튜닝) |
| 서보 | Feetech **SCS0009** ×8, 5V, 1M baud |
| 보드 | XIAO ESP32S3 (Sense: 카메라 포함) |
| 어댑터 | Waveshare Bus Servo Adapter |

**연결 경로는 두 가지.** Waveshare 점퍼가 분기점이다.

| | 경로 | Waveshare 점퍼 | 포트 (Mac / Windows) | 쓰는 곳 |
|---|---|---|---|---|
| **A** | 컴퓨터 → USB → **ESP** → UART → Waveshare → 서보 | **A (UART)** | `cu.usbmodem…` / `COMx` | Day 1 · TinyML |
| **B** | 컴퓨터 → USB → Waveshare → 서보 (**ESP 없음**) | **B (USB 직결)** | `cu.wchusbserial…` / `COMx` | 서보 세팅 · Day 2 |

- 손가락 ↔ 서보 ID: **검지 1·2 / 중지약지 3·4 / 새끼 5·6 / 엄지 7·8**
- 이 키트는 **왼손** 기준. 아두이노 코드 상단 `#define HAND_LEFT`(기본) / `HAND_RIGHT`로 전환.
- ESP ↔ Waveshare 배선(경로 A): `D6(TX)→RX`, `D7(RX)→TX`, `GND→GND`.
- 한 포트에는 한 프로그램만. 파이썬 실행 전 아두이노 시리얼 모니터를 닫는다.

---

## 처음 한 번 — 환경 설치

### (1) Python **3.12**
- Windows: python.org 설치 시 **"Add python.exe to PATH" 체크**. 확인 `py --version`
- Mac: `python3 --version` (없으면 python.org 설치)
- 3.13 이상은 일부 패키지(mujoco 등)의 미리 빌드된 파일이 없어 설치가 실패할 수 있다. **3.12 권장**.

### (2) Arduino IDE 2.x (Day 1 · TinyML)
1. 환경설정 → 추가 보드 매니저 URL에 `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. 보드 매니저에서 **esp32 by Espressif** 설치
3. Tools → Board **`XIAO_ESP32S3`**, **USB CDC On Boot = Enabled** (꺼져 있으면 시리얼 무출력)
4. TinyML 추가: **PSRAM = OPI PSRAM**, Partition = **Maximum APP (7.9MB)**

### (3) USB 드라이버
| 연결 | Windows | Mac |
|---|---|---|
| XIAO 직결 (경로 A) | 기본 인식 → `COMx` | 기본 인식 → `cu.usbmodem…` |
| Waveshare 직결 (경로 B) | **WCH CH343SER** 설치 | **WCH CH34x VCP** 설치 → `cu.wchusbserial…` |

드라이버가 없으면 Waveshare 포트가 목록에 안 뜬다. 포트 확인: Mac `ls /dev/cu.*` · Windows 장치 관리자 → 포트(COM & LPT).

### (4) Thonny (선택 — 파이썬 편집기)
- Thonny는 **자기만의 파이썬을 내장**한다. 패키지는 **Tools → Manage packages**(또는 Tools → Open system shell → `pip install …`)로 설치해야 Thonny 안에서 잡힌다. 일반 cmd/PowerShell의 `pip install`은 다른 파이썬에 들어간다.
- Windows는 Day 1·Day 2 모두 Thonny로 실행 가능. **Mac은 Day 2의 3D 뷰어 스크립트를 터미널에서 `mjpython`으로** 실행한다.

---

## 폴더별 실행

### `_0_setup/` — 서보 세팅 (조립·정비 시)
경로 **B**. 학생 키트는 세팅 완료 상태로 배포되므로 보통 실행할 일이 없다.
```bash
pip install feetech-servo-sdk pyserial
python hand_setup.py          # Mac: python3
```
메뉴: `3` ID 순서대로(서보 1개씩 연결) → `1` 스캔 → `4` 전체 중립 → `6` 오프셋 튜닝.

### `_1_withESP32/` — Day 1
경로 **A**. 진행 순서대로 폴더가 나뉘어 있다.

| 순서 | 파일 | 역할 |
|---|---|---|
| 0 | `_0_ESP_Basic/Practice_1~4` | 확장보드 입출력 (네오픽셀·스위치·부저·합본) |
| 1 | `day1_1_finger/` | 손가락 하나 제어 (서보 2개 차동) |
| 2 | `day1_2_motion/` | 포즈·모션 라이브러리 + 시리얼 메뉴 |
| 3 | `day1_3_command/` | **최종 펌웨어** — USB 명령(P/M/F/N) 수신. 파이썬이 이걸 제어 |
| 4 | `day1_4_command.py` | 번호 입력 → 손 동작 |
| 5 | `day1_5_LLM_select.py` | LLM이 정해진 동작을 **선택** |
| 6 | `day1_6_LLM_create.py` | LLM이 각도(키프레임)를 **생성** |

```bash
# 아두이노: 각 폴더의 .ino를 Arduino IDE로 업로드 (Board XIAO_ESP32S3, USB CDC Enabled)
# 파이썬:
pip install pyserial requests
python day1_4_command.py        # 입력 > p3 / m1 / N / q
python day1_5_LLM_select.py     # API 키 필요 (아래 '시작 전 준비')
python day1_6_LLM_create.py
```
- 명령 프로토콜(PC → XIAO): `P<n>` 포즈 · `M<n>` 모션 · `F b0,b1,b2,b3,s0,s1,s2,s3` 자유 포즈 · `N` 중립 → 응답 `OK`/`ERR`
- 동작 번호는 펌웨어 `doPose()/doMotion()`과 파이썬 `POSES/MOTIONS`를 **양쪽 일치**시킨다.
- LLM 제공자 전환: `.py` 상단 `PROVIDER = "claude"` / `"gemini"`.
- 저장소 최상위의 `prompt_example`: 바이브 코딩(LLM으로 `day1_2_motion.ino`에 모션 추가) 때 쓰는 프롬프트 예시.

### `_2_tinyML/` — 카메라 손동작 인식
경로 **A**. 카메라 XIAO 한 보드가 추론과 서보 구동을 모두 한다.

```
1_데이터수집_웹캡처  →  Edge Impulse 학습(브라우저)  →  2_추론_테스트  →  3_손동작_연동
```
- Arduino 옵션: `XIAO_ESP32S3` · **PSRAM OPI** · Partition **Maximum APP** · USB CDC Enabled
- Edge Impulse에서 받은 `<프로젝트>_inferencing.zip`을 Arduino에 **Add .ZIP Library**. 라이브러리는 용량이 커서 저장소에 없다.
- 설치 후 **overflow 패치 필수**: `Arduino/libraries/<프로젝트>_inferencing/src/edge-impulse-sdk/porting/ei_classifier_porting.h`의 `EI_MAX_OVERFLOW_BUFFER_COUNT 30` → **`200`**. 안 하면 부팅 직후 재부팅 루프.
- `3_손동작_연동/XIAO_gesture_hand`에서 두 곳 교체: `#include <…_inferencing.h>`(내 프로젝트명) · `GES[]` 라벨(학습 클래스명과 일치).
- 5클래스: `rock`(주먹) · `paper`(펴기) · `scissors` · `thumbsup` · `v`

### `_3_withMujoco/` — Day 2
경로 **B** (ESP 제거). 실물 없이 시뮬만 돌리는 스크립트도 있다.

**패키지 (최초 1회)**
```bash
pip install mujoco feetech-servo-sdk scikit-learn numpy joblib matplotlib pyserial
pip install mink loop-rate-limiters daqp      # STEP 2(IK) 전용
```
- IK 솔버는 설치된 것(daqp/osqp/quadprog)을 자동 선택한다. `quadprog`은 C 컴파일러가 없는 PC에서 설치가 실패하므로 `daqp`를 쓴다.

**실행**

| STEP | 파일 | 역할 | 실물 손 |
|---|---|---|---|
| 준비 | `hand_driver.py` | 서보 직결 드라이버 (연결 확인 `python hand_driver.py`) | 필요 |
| 1 | `day2_1_sim_stream_real.py` | 시뮬 관절각 → 실물 스트리밍 | 필요 (`BACKEND="sim"`이면 시뮬만) |
| 2 | `day2_2_sim_ik_real.py` | 빨간 점(IK 목표) 드래그 | 선택 |
| 3 | `day2_3_grasp_sim.py` | 잡기 감지 · `k` 캘리브 | 필요 |
| 4a | `day2_4a_shape_learn.py` | 자동 대량 학습 → `shape_model.pkl` | 불필요 |
| 4b | `day2_4b_shape_teach.py` | 도형을 굴려·옮겨 직접 가르치기 (키보드) | 불필요 |
| 4c | `day2_4c_shape_teach_mouse.py` | 4b와 동일, 물체 이동을 마우스로 | 불필요 |
| 5 | `day2_5_shape_grasp_sim.py` | 학습 결과 시뮬 테스트 | 불필요 |
| 6 | `day2_6_shape_grasp.py` | 학습 결과 실물 테스트 (sim2real) | 필요 |

```bash
# 3D 뷰어가 뜨는 스크립트
python   day2_5_shape_grasp_sim.py     # Windows / Linux (Thonny 가능)
mjpython day2_5_shape_grasp_sim.py     # Mac 전용 런처
# 뷰어 없는 학습
python   day2_4a_shape_learn.py
```
- 조작 키(잡기 `G`, 회전 `A/D` 등)는 **터미널(또는 Thonny Shell) 창**에 입력한다. 3D 창은 마우스 시점용. Windows/Thonny는 키 뒤 **Enter**.
- 3D 창 마우스: 왼쪽 드래그 회전 · 오른쪽 드래그 이동 · 휠 줌 · 더블클릭 선택 · **Ctrl+오른쪽 드래그**로 선택 물체 이동.
- `shape_model.pkl`(시뮬 학습본)이 포함되어 있어 STEP 5·6은 학습 없이 바로 실행된다.
- 실물 잡기 판정 기준값은 `grip_config.py`의 `DEFAULT`. 손 개체별 빈손 기준은 `day2_3`에서 **`k`**를 누르면 `grip_cal.json`으로 자동 생성된다(저장소에 없음, 각자 생성).
- 시리얼 포트는 자동 탐지. 여러 개 잡혀 엉뚱한 포트를 열면 `HandDriver(port="COM4")`처럼 직접 지정한다.
- `dora_가이드.md`: 원본 dora-rs 데모의 개념·설치·실행 안내.

### `Demo_dora/` — 원본 dora-rs 데모 (참고)
원본 Amazing Hand `Demo/`(dora-rs 기반)를 이 키트(왼손, 모터 ID 1~8)로 돌리기 위한 파일 2개(`l_hand.toml`, `dataflow_tracking_real_left.yml`)와 넣을 위치 안내. 원본 Demo 폴더 자체는 Pollen Robotics 저장소에서 받는다. 상세는 폴더 `README.md`와 `_3_withMujoco/dora_가이드.md`.

---

## 시작 전 준비

- **API 키** (Day 1 STEP 5·6, `day1_5`·`day1_6`): 양식 `_1_withESP32/api_key.txt.example`을 같은 폴더에 `api_key.txt`로 복사한 뒤 키를 채운다.
  ```bash
  cd _1_withESP32 && cp api_key.txt.example api_key.txt     # Windows: copy
  ```
  `api_key.txt`는 `.gitignore`로 저장소에 올라가지 않는다. 발급: Claude `console.anthropic.com` · Gemini `aistudio.google.com/apikey`. **키를 다른 파일이나 코드에 적지 않는다.**
- **Edge Impulse 라이브러리** (`*_inferencing`): 미포함. 각자 학습 후 설치하고 overflow 패치(위 `_2_tinyML`).
- **실물 도형 3종** (구·타원·정육면체, Day 2 STEP 6): `_3_withMujoco/day2_부록_shape_print_stl.py`로 STL 생성 후 3D 프린트.

---

## 실행 환경 확인

코드가 아예 안 뜨거나 연결이 안 될 때 먼저 볼 것.

| 증상 | 확인 |
|---|---|
| Waveshare 포트(`COMx` / `cu.wchusbserial…`)가 안 보임 | CH343 드라이버 설치 · 점퍼 **B** |
| `Resource busy` / 포트 사용 중 | 아두이노 시리얼 모니터 등 다른 프로그램이 포트 점유 → 닫기 |
| 아두이노 시리얼 모니터 무출력 | Tools → **USB CDC On Boot = Enabled** 후 재업로드 |
| 업로드 실패 | XIAO의 BOOT 버튼을 누른 채 연결(다운로드 모드) 후 업로드 |
| Mac에서 3D 뷰어 안 뜸 | `python` 대신 **`mjpython`** |
| `No module named 'serial'` (Thonny) | Thonny 안에서 설치 (Manage packages / Open system shell). 설치명은 `pyserial` |
| `No module named 'scservo_sdk'` | `pip install feetech-servo-sdk` |
| Windows `python` 명령이 없음 | Python 재설치 시 Add to PATH, 또는 `py` 사용 |
| `import mujoco` DLL 오류 (Windows) | Python **3.12** 사용 · Microsoft Visual C++ Redistributable(x64) 설치 |
| TinyML 부팅 직후 재부팅 반복 | overflow 패치(30→200) · PSRAM = OPI PSRAM |

---

## 라이선스 · 출처

- 로봇 손: **Amazing Hand** — Pollen Robotics (SW **Apache 2.0** / HW **CC BY 4.0**)
- 시뮬레이션 모델(`_3_withMujoco/AHSimulation/`)·원본 `Demo/`: Pollen Robotics, Apache 2.0
- 교육용 확장·수업 코드: **TouchLabs**
