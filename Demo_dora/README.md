# Demo_dora — 원본 dora 데모용 왼손 파일

이 폴더는 **원본 AmazingHand `Demo/`(dora-rs 기반)를 이 수업 키트(왼손)로 돌리기 위한 추가 파일**만 담는다. 원본 Demo 폴더 자체는 여기 없다 — 아래 절차대로 원본을 받아 이 두 파일을 넣는다.

전체 개념·설치·트러블슈팅은 **강의자료 `dora_가이드`** 참고.

---

## 들어있는 파일 2개

| 파일 | 원본 Demo 안 넣을 위치 |
|---|---|
| `l_hand.toml` | `Demo/AHControl/config/l_hand.toml` |
| `dataflow_tracking_real_left.yml` | `Demo/dataflow_tracking_real_left.yml` (Demo 최상위) |

---

## 절차

### 1. 원본 Demo 받기
Pollen Robotics AmazingHand 저장소에서 `Demo/` 폴더를 받는다. (원본은 오른손 기준.)

### 2. 사전 설치 (한 번만)
- **Rust**: https://www.rust-lang.org/tools/install
- **uv**: `pip install uv` (설치 후 터미널 새로 열기)
- **dora CLI**: `pip install dora-rs-cli==0.3.13`
  - ⚠️ 최신(1.0.x) 설치 금지. 노드가 dora-rs 0.3.11~0.3.13 을 요구 → 버전 안 맞으면 실행 실패.
  - 확인: `dora --version` → 0.3.x

### 3. 이 폴더의 파일 2개를 원본 Demo에 복사
- `l_hand.toml` → `Demo/AHControl/config/`
- `dataflow_tracking_real_left.yml` → `Demo/` (최상위)

### 4. 자기 환경에 맞게 손볼 곳 ★
`dataflow_tracking_real_left.yml` 안:
- `--serialport COM4` → **이 PC의 실제 시리얼 포트**. Windows 는 `/dev/` 없이 `COMx`(장치 관리자 > 포트에서 번호 확인). 맥/리눅스는 `/dev/ttyACM0` 등.

`l_hand.toml` 안:
- `motor1.id`~`motor2.id` → **이 키트의 실제 모터 ID**. 기본값은 1~8, 매핑 f1=1·2 / f2=3·4 / f3=5·6 / f4=7·8.
- `invert` → 왼손 기본 `true`. 굽힘·폄이 반대로 나오면 여기를 뒤집는다.
- `offset` → 자세가 어긋나면 AHControl `get_zeros`로 이 손의 영점을 추출해 반영.

### 5. 실행 (Demo 폴더에서)
```
uv venv --python 3.12                              # 최초 1회
dora build dataflow_tracking_real_left.yml --uv    # 최초 1회
dora run   dataflow_tracking_real_left.yml --uv
```
- 웹캠에 왼손을 비추면 실물 왼손이 따라 움직인다.
- 웹캠 영상 창 제목: `MediaPipe Hands` (3D 창 뒤에 가려지면 Alt+Tab).
- 종료: `Ctrl + C`.

---

## 모터가 안 움직이거나 divide by zero 나면
`Demo/AHControl` 에서 모터를 하나씩 진단:
```
cargo run --bin=goto -- --serialport COM4 --id 1 --pos 0.2
```
id 1~8 을 바꿔가며 어느 모터가 응답하는지 확인. 자세한 증상별 대응은 `dora_가이드` 4절.

---

## 오른손 키트라면
이 폴더 대신 원본 기본 파일을 쓴다. `dataflow_tracking_real.yml` + `AHControl/config/r_hand.toml`, `invert=false`. 왼/오 차이는 ① config 파일 ② finger_name(l_/r_) ③ invert(true/false) ④ dataflow 노드·경로(l/r) 네 가지.

---

## 출처
원본 `Demo/`: Pollen Robotics — AmazingHand (Apache License 2.0). 이 폴더의 두 파일은 원본을 왼손용으로 파생한 설정.
