#!/usr/bin/env python3
# ============================================================
#  Amazing Hand - "잡으면 손이 안다" (실물 잡기 감지 + 시뮬 표시)   [STEP 3]
#  손을 닫으면, 물체에 막혀 멈춘 손가락을 read()로 감지하고
#  시뮬에 실제 모습을 그대로 비추며 잡은 손가락을 빨갛게 표시.
#
#  ▷ 강의자료 연결(MuJoCo_자료.md):
#     · 12절 STEP3 = "물리로 물체를 쥐고 막힌 손가락 감지" (이 파일)
#     · 8절 = 충돌(접촉): 물체를 잡는다 = 손가락이 물체에 막혀 멈춘다.
#             '멈춘 깊이'가 학습·판정 신호.
#     · 이 파일은 실물 서보 피드백(read)으로 판정하고 그 모습을 시뮬에 '비추는' 구조.
#     · 여기서 k(빈손 기준 FREECLOSE) 캘리브 → grip_config 로 STEP6(day2_6)과 공유.
#     · 3·5절 = 모델/상태·ctrl · 6절 = mj_step 루프 · 11절 = 뷰어
#  ▷ '막힘' 판정: 빈손으로 끝까지 닫은 깊이(FREECLOSE)보다 MARGIN 이상 덜 닫히면
#     = 물체에 막힌 것 = 잡음. (개체차·작은 물체에 강함)
#
#  준비 : pip install feetech-servo-sdk mujoco
#         Waveshare USB 모드 연결 (없으면 시뮬만 도는 데모 모드)
#  실행(★ 맥):  mjpython day2_3_grasp_sim.py   (윈도우/리눅스: python day2_3_grasp_sim.py)
#
#  키(터미널 창) : k = 빈손 기준 측정(캘리브)  c = 손 닫기(잡기)  o = 펴기
#                  +/- = 쥐는 힘 조절   q = 종료
# ============================================================
import time
import threading
from collections import deque
from pathlib import Path
import mujoco
import mujoco.viewer

# ── 파라미터 ──
import grip_config as GC          # ★ STEP 3에서 세팅/캘리브 → STEP 6과 공유
_cfg         = GC.load()
OPEN_BEND    = _cfg["OPEN_BEND"]     # 펴기
CLOSE_TARGET = _cfg["CLOSE_TARGET"]  # 쥐는 힘/깊이 (낮출수록 약하게)
GAP          = _cfg["GAP"]           # (캘리브 안 했을 때 폴백) 감지 예민도
SETTLE       = _cfg["SETTLE"]        # 명령 후 판정까지 대기(초)
SPEED_STEP   = 0.06
# ── 캘리브레이션(권장): 빈손 닫힘 깊이를 손가락마다 기준으로 잡고,
#    그보다 MARGIN 이상 덜 닫히면 = 물체에 막힘(잡음). 개체차·작은 물체에 강함.
MARGIN       = _cfg["MARGIN"]        # 빈손 기준보다 이만큼 덜 닫히면 '잡음'
FREECLOSE    = list(_cfg["FREECLOSE"]) if _cfg["FREECLOSE"] else [None, None, None, None]

# ── 시뮬 ──
HAND = "AH_Left"
HERE = Path(__file__).resolve().parent
MODEL = HERE / "AHSimulation" / HAND / "mjcf" / "scene.xml"
model = mujoco.MjModel.from_xml_path(str(MODEL))
data  = mujoco.MjData(model)
SIM = {"thumb": 3, "index": 0, "mid": 1, "pinky": 2}   # 시뮬 finger 매핑
def pose_to_ctrl(flex4):                               # flex4=[엄지,검지,중지약지,새끼] 라디안
    c = [0.0] * 8
    vals = {"thumb": flex4[0], "index": flex4[1], "mid": flex4[2], "pinky": flex4[3]}
    for name, fsim in SIM.items():
        v = vals[name]; c[fsim*2] = +v; c[fsim*2+1] = -v
    return c

# 손끝 목표 구슬(mocap) geom 찾기 → 잡으면 색칠 (mj_name2id: 이름→id, → 10절 API)
def target_geom(i):
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"finger{i+1}_target")
    for g in range(model.ngeom):
        if model.geom_bodyid[g] == bid:
            return g
    return -1
# 시뮬 finger1~4 = [검지, 중지약지, 새끼, 엄지] = anatomical [1,2,3,0]
GEOM = [target_geom(i) for i in range(4)]
SIMFINGER_TO_ANAT = [1, 2, 3, 0]
# 구슬(mocap)이 손끝(tip site)을 따라다니게 하려고
TIPSITE = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"tip{i+1}") for i in range(4)]
MOCAPID = [model.body_mocapid[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"finger{i+1}_target")] for i in range(4)]

# ── 실물 (없으면 데모 모드) ──
hand = None
try:
    from hand_driver import HandDriver
    hand = HandDriver()
    hand.speed = 200          # 한 번만 명령하니 이 속도로도 부드러움
except Exception as e:
    print("⚠️  실물 없음 → 시뮬만 (데모 모드):", e)

state = {"cmd": "open", "actual": [0, 0, 0, 0], "grip": [False]*4, "run": True}

def worker():
    """한 번 명령 → 다 움직일 때까지 기다림(SETTLE) → 목표에 못 간 손가락 = 잡음"""
    gripped = [False]*4
    last_cmd = "open"
    judged = False
    close_t = 0.0
    tick = 0
    while state["run"]:
        if state["cmd"] != last_cmd:                  # 명령 바뀔 때 '한 번만' 전송
            last_cmd = state["cmd"]; judged = False
            if state["cmd"] == "open":
                gripped = [False]*4
                if hand is not None: hand.set_free([OPEN_BEND]*4, [0]*4)
            else:                                     # 닫기: 목표 한 번만 → 서보가 부드럽게 이동
                if hand is not None: hand.set_free([CLOSE_TARGET]*4, [0]*4)
                close_t = time.time()

        if hand is not None:
            act = hand.read()
            for i in range(4):
                if act[i][0] is not None: state["actual"][i] = act[i][0]
            # 다 움직인 뒤(SETTLE) 딱 한 번 판정
            if state["cmd"] in ("close", "calib") and not judged and time.time() - close_t > SETTLE:
                judged = True
                if state["cmd"] == "calib":                # 빈손 기준 측정
                    for i in range(4): FREECLOSE[i] = state["actual"][i]
                    GC.save(FREECLOSE=[float(v) for v in FREECLOSE],   # ★ STEP 6이 이어받음
                            CLOSE_TARGET=CLOSE_TARGET, GAP=GAP, MARGIN=MARGIN)
                    print("  ✅ 빈손 기준 측정 완료:",
                          " ".join(f"{int(v)}" for v in FREECLOSE),
                          "→ 저장됨(STEP6 자동 사용). 이제 c 로 잡기")
                    hand.set_free([OPEN_BEND]*4, [0]*4)     # 펴기
                    state["cmd"] = "open"
                else:                                       # 잡기 판정 (→ 8절: 막힌 깊이 = 신호)
                    for i in range(4):
                        if FREECLOSE[i] is not None:        # 캘리브: 빈손 기준보다 MARGIN 이상 덜 닫힘 = 막힘
                            gripped[i] = (FREECLOSE[i] - state["actual"][i]) > MARGIN
                        else:                               # 폴백(캘리브 없음): 목표 못 미침 = 막힘
                            gripped[i] = state["actual"][i] < CLOSE_TARGET - GAP
                    # 잡은 손가락은 접촉 지점에 고정 (그만 밀어서 부드럽게)
                    nt = [int(state["actual"][i]) if gripped[i] else CLOSE_TARGET for i in range(4)]
                    hand.set_free(nt, [0]*4)
            time.sleep(0.1)
        else:
            tgt = CLOSE_TARGET if state["cmd"] == "close" else OPEN_BEND
            for i in range(4): state["actual"][i] += (tgt - state["actual"][i]) * 0.12
            time.sleep(0.06)
        state["grip"] = gripped
        tick += 1
        if state["cmd"] == "close" and tick % 4 == 0:
            names = ["엄지", "검지", "중지약지", "새끼"]
            grabbed = [names[i] for i in range(4) if gripped[i]]
            act_str = " ".join(f"{int(state['actual'][i]):4d}" for i in range(4))
            status = (", ".join(grabbed) if grabbed else "(안 잡음)") if judged else "판정중..."
            print(f"   실제[엄검중약새끼]:[{act_str}]  ✊{status}", flush=True)

def reader():
    global CLOSE_TARGET
    print("=" * 56)
    print("  잡기 감지 + 시뮬   k=빈손기준측정  c=닫기(잡기)  o=펴기  q=종료")
    print(f"  +/- = 쥐는 힘 조절(저장→STEP6 공유)   현재 CLOSE_TARGET={CLOSE_TARGET}")
    print("  ※ 물체 없이 k 한 번 → 기준 측정 → c 로 잡기.  (엔터 없이 키 하나만)")
    print("=" * 56)
    import sys, select
    try:
        import termios, tty
        fd = sys.stdin.fileno(); _old = termios.tcgetattr(fd); tty.setcbreak(fd)
    except Exception:
        fd = None; _old = None
    try:
        while state["run"]:
            if fd is not None:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r:
                    continue
                s = sys.stdin.read(1).lower()
            else:
                s = (sys.stdin.readline().strip()[:1] or " ").lower()
            if s in ("q", "\x03"): state["run"] = False; break
            elif s == "k": state["cmd"] = "calib"; print("  → 빈손 기준 측정 (물체 치우고 잠시)")
            elif s == "c": state["cmd"] = "close"; print("  → 닫기(잡기)")
            elif s == "o": state["cmd"] = "open";  print("  → 펴기")
            elif s in ("+", "="):
                CLOSE_TARGET = min(300, CLOSE_TARGET + 10); GC.save(CLOSE_TARGET=CLOSE_TARGET)
                print(f"  ⬆ 쥐는 힘 CLOSE_TARGET={CLOSE_TARGET} (저장·STEP6 공유)")
            elif s == "-":
                CLOSE_TARGET = max(0, CLOSE_TARGET - 10); GC.save(CLOSE_TARGET=CLOSE_TARGET)
                print(f"  ⬇ 쥐는 힘 CLOSE_TARGET={CLOSE_TARGET} (저장·STEP6 공유)")
    finally:
        if fd is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, _old)

threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=reader, daemon=True).start()

cur = [0.0] * 8
GREEN = [0.2, 0.8, 0.3, 0.35]
RED   = [1.0, 0.15, 0.1, 0.9]
from shape_common import Pacer, frame_camera      # ★ 저사양/윈도우: 렌더와 물리 분리 + 카메라 프레이밍
pacer = Pacer(model.opt.timestep)                 # model.opt.timestep = 한 스텝 시간(기본 2ms) → 6절
with mujoco.viewer.launch_passive(model, data) as viewer:   # 대화형 3D 창 → 11절
    frame_camera(viewer)                          # 손+물체가 한눈에 보이게 카메라 고정
    while viewer.is_running() and state["run"]:
        # 시뮬을 '실제(read) 위치'로  (실물의 지금 모습을 비춤)
        flex4 = [state["actual"][a] / 250.0 for a in [0, 1, 2, 3]]  # 실물bend → 시뮬라디안(환산)
        tgt = pose_to_ctrl(flex4)
        for _ in range(pacer.substeps()):         # 렌더가 느려도 물리는 실시간에 맞춰 여러 스텝(→ 6절)
            for k in range(8):
                diff = tgt[k] - cur[k]
                cur[k] += SPEED_STEP if diff > SPEED_STEP else (-SPEED_STEP if diff < -SPEED_STEP else diff)
                data.ctrl[k] = cur[k]             # 8개 모터 명령 세팅 → 5절 ctrl
            mujoco.mj_step(model, data)           # 물리 한 스텝(힘·접촉 계산 + 적분) → 6절
        # 잡은 손가락 구슬 빨갛게 (geom_rgba 직접 수정 = 시각 표시)
        for sf in range(4):
            g = GEOM[sf]
            if g >= 0:
                anat = SIMFINGER_TO_ANAT[sf]
                model.geom_rgba[g] = RED if state["grip"][anat] else GREEN
        for i in range(4):                       # 구슬(mocap)을 손끝 site 위치로 (따라다니게) → 5절
            data.mocap_pos[MOCAPID[i]] = data.site_xpos[TIPSITE[i]]
        viewer.sync()
        time.sleep(0.002)

state["run"] = False
time.sleep(0.2)
if hand is not None:
    hand.close()
print("\n종료!")
