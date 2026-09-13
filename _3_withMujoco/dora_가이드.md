# dora-rs 가이드 — 원본 AmazingHand 데모 이해와 실행

원본 AmazingHand(`Demo/`)는 **dora-rs** 위에서 동작한다. 이 문서는 dora의 개념, 설치, 데모 실행, 문제 해결을 다룬다.

> 이 수업의 Day2는 원본 dora 구조를 STEP별로 분해해 파이썬만으로 재구성한 것이다. dora 자체는 수업 필수가 아니며, "원본은 어떻게 돌아가는가"를 이해하기 위한 보조 자료다.

---

## 1. dora란

- **dora-rs = 로봇·AI용 데이터플로우 런타임.** 작은 프로그램(노드)들을 메시지로 연결해 실행한다.
- Rust로 작성되어 가볍고 지연이 짧다. ROS의 대안으로 개발됨.
- 노드는 독립 프로세스로 실행되고, 언어를 섞을 수 있다(이 프로젝트는 Python + Rust).
- 노드 간 연결은 **YAML 파일(dataflow)** 로 선언한다.

### 1.1 ROS와의 비교

| 개념 | ROS / ROS2 | dora-rs |
|---|---|---|
| 프로그램 단위 | 노드(node) | 노드(node) |
| 노드 간 통신 | 토픽 발행/구독 | 입력/출력 스트림 |
| 실행 묶음 | launch 파일 | dataflow YAML |
| 언어 | C++ / Python | Python / Rust |
| 등장 | 2007~ | 2022~ |
| 특성 | 표준·방대한 생태계 | 신생·빠름·경량 |

- 두 프레임워크 모두 "지각 → 판단 → 구동"을 노드로 분리하는 사고방식을 공유한다.
- dora는 카메라·AI 추론처럼 데이터가 빠르게 흐르는 작업에 유리하다.
- ROS는 생태계(드라이버·툴)가 크고, dora는 아직 작다.

### 1.2 AmazingHand의 노드 3개

| 노드 | 언어 | 역할 | 입력 → 출력 |
|---|---|---|---|
| **HandTracking** | Python | 지각 | 웹캠 → 손끝 목표 위치 |
| **AHSimulation** | Python | 판단 | 손끝 목표 → 관절각 8개 (MuJoCo + mink IK) |
| **AHControl** | Rust | 구동 | 관절각 → 모터 (Feetech 시리얼) |

- HandTracking: Mediapipe로 웹캠에서 손 keypoint 21개 추출 → 손목 기준 좌표로 손끝 4개 목표 계산. 출력 `r_hand_pos` / `l_hand_pos`.
- AHSimulation: MJCF `scene.xml` 로드, mink IK로 관절각 계산, `mujoco.viewer`로 3D 창. Day2의 `day2_2_sim_ik_real.py`가 이 노드에 대응.
- AHControl: TOML 설정(모터 ID·영점·방향)으로 SCS0009 서보 구동. Day2에선 파이썬 시리얼 스크립트로 대체.

### 1.3 노드 3개 × 조합 = 데모 4개

노드는 재사용하고, 연결(dataflow YAML)만 바꿔 여러 데모를 만든다.

| dataflow 파일 | 연결 | 결과 |
|---|---|---|
| `dataflow_tracking_simu.yml` | 웹캠 → 추적 → 시뮬 | 3D 화면만 (하드웨어 불필요) |
| `dataflow_tracking_real.yml` | + 제어 → 손 | 실물 손이 웹캠 손을 따라함 |
| `dataflow_tracking_real_2hands.yml` | 시뮬·제어 ×2 | 양손 |
| `dataflow_angle_simu.yml` | 각도 → 시뮬 | 웹캠 없이 각도 직접 입력 |

### 1.4 dataflow YAML 읽는 법

`dataflow_tracking_simu.yml`의 연결 구조:

```yaml
nodes:
  - id: hand_tracker              # 웹캠 노드
    outputs: [r_hand_pos]          #   → 손끝 위치 출력

  - id: r_hand_simulation          # 시뮬 노드
    inputs:
      r_hand_pos: hand_tracker/r_hand_pos   # 위 노드의 출력을 입력으로
    outputs: [mj_r_joints_pos]     #   → 관절각 출력
```

- `A/B` 표기 = "A 노드의 B 출력". 예: `hand_tracker/r_hand_pos`.
- `tick: dora/timer/millis/50` = 50ms 주기 실행(20Hz). 시뮬 노드는 `millis/2`(500Hz).

---

## 2. 설치

순서: Rust → uv → dora CLI. 3개 모두 필요.

### 2.1 Rust

모터 제어 노드(AHControl)와 dora 일부가 Rust다.

- 설치: https://www.rust-lang.org/tools/install
- 확인: `cargo --version`

### 2.2 uv

파이썬 노드의 패키지·가상환경 관리 도구.

- Windows(cmd/PowerShell 공통, 파이썬 있을 때): `pip install uv`
- 또는 PowerShell 스크립트: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **설치 후 터미널을 새로 연다**(PATH 갱신). 기존 창은 uv를 인식하지 못함.
- 확인: `uv --version`

### 2.3 dora CLI — 버전 주의 ★

이 프로젝트의 노드는 `pyproject.toml`에서 **`dora-rs >=0.3.11, <=0.3.13`** 을 요구한다. CLI 버전이 이와 다르면 통신 규격이 어긋나 실행이 실패한다(§4.1).

- **최신(1.0.x)을 설치하면 안 됨.** 노드에 맞춰 **0.3.13**을 설치한다.
- **권장(빠름) — pip:** `pip install dora-rs-cli==0.3.13`  ← 미리 빌드된 파일, 1~2분
- 대안 — cargo(소스 컴파일, 5~20분): `cargo install dora-cli --version 0.3.13 --locked`
- 확인: `dora --version` → `0.3.x` 표시
- 이미 최신을 깔았다면 먼저 제거: `cargo uninstall dora-cli`

> 패키지 이름 구분: `dora-rs-cli` = `dora` 명령어(CLI). `dora-rs` = 파이썬 API(노드 코드 import용). 둘은 별개이며 버전을 맞춘다.

### 2.4 CLI와 노드 라이브러리 버전 일치 원칙

- dora CLI(데몬)와 파이썬 `dora-rs`는 **같은 계열 버전**이어야 한다.
- CLI 0.3.13 ↔ 노드 dora-rs 0.3.x = 일치.
- CLI 1.0.1 ↔ 노드 dora-rs 0.3.x = 불일치 → 등록 메시지 역직렬화 실패.

---

## 3. 데모 실행

Demo 폴더에서 진행. 각 데모는 build(1회) → run 순서.

### 3.1 가상환경 준비

```bash
cd .../AmazingHand-main/Demo
uv venv --python 3.12
```

- 파이썬 **3.12** 사용(3.14 등 최신은 패키지 wheel 문제 소지).

### 3.2 시뮬 데모 (하드웨어 불필요, 웹캠만)

```bash
dora build dataflow_tracking_simu.yml --uv    # 최초 1회
dora run   dataflow_tracking_simu.yml --uv
```

- 웹캠에 손을 비추면 3D 시뮬 손(좌·우)이 따라 움직인다.
- **웹캠 영상 창**: 제목 `MediaPipe Hands`. MuJoCo 3D 창 뒤에 가려질 수 있으므로 작업표시줄이나 Alt+Tab으로 전환해 확인한다.
- 종료: 터미널에서 `Ctrl + C`.

### 3.3 각도 데모 (웹캠 없이)

```bash
dora build dataflow_angle_simu.yml --uv
dora run   dataflow_angle_simu.yml --uv
```

- 카메라 없이 관절각을 직접 넣어 시뮬만 확인. dora 구조 점검용.

### 3.4 실물 데모 — 왼손 (이 수업 키트 기준) ★

이 수업 키트는 **왼손**이므로 왼손용 dataflow·config를 쓴다. 원본은 오른손 기준이라 그대로 실행하면 동작하지 않는다.

**① 왼손 config 만들기** — `AHControl/config/l_hand.toml` 신규 생성

- `finger_name`은 **`l_finger1`~`l_finger4`** 여야 한다. 왼손 시뮬 노드(`mj_mink_left.py`)가 이 이름으로 관절 데이터를 보내고, AHControl은 config의 `finger_name`으로 그 데이터를 찾기 때문. 이름이 `r_finger`면 매핑을 못 찾아 손가락이 안 움직인다.
- `motor1/2.id`는 **이 키트의 실제 모터 ID(1~8)**. 매핑: finger1=1·2, finger2=3·4, finger3=5·6, finger4=7·8.
- `invert`는 **8개 모두 `true`**. 왼손은 오른손의 거울상이라 회전 방향이 반대 → false로 두면 굽힘·폄이 뒤바뀐다.

```toml
# Config for the left hand — 실제 모터 ID 1~8, 왼손이라 invert=true
[Fingers]
[[motors]]
finger_name="l_finger1"
motor1.id = 1
motor1.offset = 0.12217304763960307
motor1.invert = true
motor1.model = "SCS0009"
motor2.id = 2
motor2.offset = 0.08726646259971647
motor2.invert = true
motor2.model = "SCS0009"
[[motors]]
finger_name="l_finger2"
motor1.id = 3
motor1.offset = 0.0
motor1.invert = true
motor1.model = "SCS0009"
motor2.id = 4
motor2.offset = 0.12217304763960307
motor2.invert = true
motor2.model = "SCS0009"
[[motors]]
finger_name="l_finger3"
motor1.id = 5
motor1.offset = 0.08726646259971647
motor1.invert = true
motor1.model = "SCS0009"
motor2.id = 6
motor2.offset = 0.12217304763960307
motor2.invert = true
motor2.model = "SCS0009"
[[motors]]
finger_name="l_finger4"
motor1.id = 7
motor1.offset = 0.0
motor1.invert = true
motor1.model = "SCS0009"
motor2.id = 8
motor2.offset = 0.12217304763960307
motor2.invert = true
motor2.model = "SCS0009"
```

**② 왼손 dataflow 만들기** — `dataflow_tracking_real_left.yml` 신규 생성

오른손 데모에서 `r`→`l`로 바꾼 것. 노드 이름·출력·config가 전부 왼손.

```yaml
nodes:
  - id: hand_tracker
    build: pip install -e HandTracking
    path: HandTracking/HandTracking/main.py
    inputs:
      tick: dora/timer/millis/50
    outputs:
      - l_hand_pos

  - id: l_hand_simulation
    build: pip install -e AHSimulation
    path: AHSimulation/AHSimulation/mj_mink_left.py
    inputs:
      l_hand_pos: hand_tracker/l_hand_pos
      tick: dora/timer/millis/2
      tick_ctrl: dora/timer/millis/10
    outputs:
      - mj_l_joints_pos

  - id: hand_controller
    build: cargo build -p AHControl
    path: target/debug/AHControl
    args: --serialport COM4 --config AHControl/config/l_hand.toml
    inputs:
      mj_l_joints_pos: l_hand_simulation/mj_l_joints_pos
```

- **시리얼 포트**: `--serialport COM4`. Windows는 `/dev/` 없이 `COMx`(장치 관리자에서 번호 확인). 원본 주석의 `/dev/ttyACM0`는 맥/리눅스 표기.

**③ 실행**

```powershell
dora destroy
dora build dataflow_tracking_real_left.yml --uv
dora run   dataflow_tracking_real_left.yml --uv
```

**④ 실행 전 안전**

- 손 주변을 치운다(시작 시 손가락이 갑자기 움직일 수 있음).
- offset이 원본 값이라 자세가 약간 어긋날 수 있다. 하드웨어에 무리가 갈 정도로 밀면 즉시 `Ctrl + C`.

### 3.5 실물 데모 — 오른손 (참고)

원본 기본값이 오른손이다. 오른손 키트라면 원본 `dataflow_tracking_real.yml`을 거의 그대로 쓴다.

- config: `AHControl/config/r_hand.toml`(원본 제공, `r_finger1~4`).
- `invert`: 오른손은 원본 그대로 **`false`**.
- id: 이 키트 기준 1~8로 맞춘다(원본 파일도 1~8).
- 포트만 Windows `COMx`로 수정.

왼손과의 차이는 **① config 파일(l_/r_) ② finger_name(l_/r_) ③ invert(true/false) ④ dataflow의 노드·경로(l/r)** 네 가지뿐이다.

### 3.6 AHControl 도구 (모터 진단·설정)

`Demo/AHControl`에서 `cargo run --bin=<도구> -- <인자>`.

| 도구 | 역할 | 예 |
|---|---|---|
| `goto` | 단일 모터를 지정 위치로 이동 | `cargo run --bin=goto -- --serialport COM4 --id 1 --pos 0.2` |
| `get_zeros` | 힘 풀린 상태의 영점 추출 → TOML offset 값 | 손을 중립 자세로 잡고 실행 |
| `set_zeros` | 설정 영점 자세로 이동 | config 검증용 |
| `change_id` | 모터 ID 변경 | 중복 ID 정리 시 |

- baudrate 기본값 1,000,000. 포트만 맞으면 생략 가능.
- **모터 개별 진단**: `goto`로 id 1~8을 하나씩 움직여 어느 모터가 응답하는지 확인. 실물 데모가 `divide by zero`로 죽으면 이걸로 원인 모터를 좁힌다(§4.7).

### 3.7 실행 흐름 요약

```
dora build <데모>.yml --uv    (데모당 최초 1회)
dora run   <데모>.yml --uv    (실행)
Ctrl + C                      (종료)
```

- `dora run`은 임시 데몬을 자체적으로 띄우고 종료 시 정리한다. `dora up`을 따로 실행하면 데몬이 중복되어 충돌할 수 있으므로, `dora run` 단독 사용을 기본으로 한다.

---

## 4. 문제 해결

### 4.1 노드가 `server disconnected` / `failed to send register request`

증상 로그:
```
dora_daemon::node_communication: failed to receive register message
  1: Serde Deserialization Error   (dora-message-1.0.1)
RuntimeError: Could not initiate node from environment variable
  2: server disconnected unexpectedly
```

- 원인: **CLI 버전 ≠ 노드 dora-rs 버전.** 노드가 보낸 등록 메시지를 데몬이 해독하지 못함.
- 해결: CLI를 노드에 맞춘다.
  ```
  cargo uninstall dora-cli          (최신 1.0.x 제거)
  pip install dora-rs-cli==0.3.13   (노드 요구 범위 0.3.11~0.3.13)
  dora --version                    (0.3.x 확인)
  dora destroy                      (이전 실패 상태 정리)
  ```
  이후 §3의 build/run 재실행.

### 4.2 `'uv'은(는) ... 명령이 아닙니다`

- 원인: uv 미설치, 또는 설치 후 기존 터미널이 PATH를 반영 못 함.
- 해결: `pip install uv` 후 **터미널을 새로 연다**. `uv --version`으로 확인.

### 4.3 cargo install이 오래 걸림

- 정상. 소스 컴파일이라 5~20분 소요. `Compiling ...`이 계속 바뀌면 진행 중.
- 회피: 가능하면 `pip install dora-rs-cli==<버전>`을 사용(미리 빌드, 1~2분).

### 4.4 웹캠 창이 안 보임

- `MediaPipe Hands` 창이 다른 창 뒤에 있음 → Alt+Tab / 작업표시줄로 전환.
- 웹캠을 다른 앱(화상회의·카메라 앱)이 점유 중이면 dora가 못 씀 → 해당 앱 종료 후 재실행.
- 카메라 권한(윈도우 설정 > 개인정보 > 카메라) 허용.
- 외장 웹캠이 여러 개면 `cv2.VideoCapture(0)`의 인덱스를 조정.

### 4.5 손가락 방향이 반대(굽힘↔폄) / 자세 어긋남

- **굽힘·폄이 통째로 반대**: 왼손을 오른손 설정(invert=false)으로 돌린 경우. 해당 손가락 motor1·2를 **둘 다 `invert = true`**. 왼손 전체가 반대면 8개 모두 true.
- **좌우 벌림만 반대**: 그 손가락의 motor1·2 중 **하나만** invert. (Amazing Hand는 손가락당 모터 2개가 협조 — 굽힘=같은 방향, 벌림=반대 방향.)
- **자세가 살짝 어긋남(움직이긴 함)**: offset이 다른 손 기준값이라 그렇다 → AHControl `get_zeros`로 이 손의 영점을 추출해 TOML offset에 반영.

### 4.6 손가락이 안 움직임(에러는 없음)

- config `finger_name`이 노드가 보내는 이름과 불일치. **왼손 데모엔 `l_finger1~4`, 오른손엔 `r_finger1~4`**. 이름이 틀리면 AHControl이 관절 데이터를 못 찾아 조용히 안 움직인다.
- dataflow의 `--config` 경로가 엉뚱한 파일(예: 왼손 데모인데 `r_hand.toml`)을 가리킴.

### 4.7 `attempt to divide by zero` (rustypot) — 실물 데모 크래시

증상: 노드는 `ready`가 되고 dataflow 시작 직후 `hand_controller`가 패닉.
```
thread 'main' panicked at rustypot-.../dynamixel_protocol/v1.rs
attempt to divide by zero
```

- 원인: AHControl이 config에 적힌 ID의 모터에게 말을 걸었으나 **응답이 없음**(응답 0으로 나눔). 대개 config의 ID가 실제 모터와 불일치, 또는 특정 모터의 전원·배선 문제.
- 진단: `goto`로 id 1~8을 하나씩 움직여 어느 모터가 응답하는지 확인.
  ```
  cargo run --bin=goto -- --serialport COM4 --id 1 --pos 0.2
  ```
  - 전부 움직임 → 모터 정상. config의 ID 매핑·`finger_name`을 점검(§4.6).
  - 특정 id에서 멈춤/에러 → 그 모터의 ID·전원·배선 문제.
- 확인: baudrate(기본 1,000,000)와 COM 포트가 맞는지.

### 4.8 데몬 상태가 꼬임

- `dora destroy`로 데몬·상태를 정리한 뒤 재실행.
- `.dora/` 캐시 폴더가 이전 빌드를 담고 있으므로, 문제 지속 시 이 폴더 삭제 후 `dora build`부터.

---

## 5. 이 수업과의 관계

| 원본 (dora) | 이 수업 (Day2) |
|---|---|
| 노드 3개가 동시에 실행 | STEP별로 하나씩 학습 |
| AHSimulation 노드 | `day2_2`(IK), `day2_5`(엔진) |
| AHControl 노드 (Rust) | `day2_1`·`day2_3`·`day2_6` (파이썬 시리얼) |
| dora가 노드 간 메시지 전달 | 한 스크립트 안에서 순차 실행 |

- 원본은 완성된 실행 형태이지만 한 덩어리라 내부를 뜯어보기 어렵고, dora·Rust·uv 설치가 필요하다.
- 이 수업은 같은 기능을 부품별로 분해해 파이썬만으로 하나씩 익히도록 재구성했다.
- 수업에서 배운 STEP(추적·IK·제어)이 원본에선 dora 노드로 나뉘어 동시에 도는 것 = 로봇 미들웨어(ROS 계열)의 사고방식.

---

## 6. 준비물 · 요건 요약

| 항목 | 값 |
|---|---|
| dora CLI | `dora-rs-cli` 0.3.13 (노드 dora-rs 0.3.11~0.3.13에 일치) |
| 파이썬 | 3.12 |
| Rust | AHControl 빌드·dora용 |
| uv | 노드 가상환경·패키지 |
| 웹캠 | tracking 계열 데모 |
| 하드웨어 | 실물 데모만 (손 + Feetech 시리얼 + COM 포트) |
| Mediapipe | PC급 연산 — PC에서 실행 |
