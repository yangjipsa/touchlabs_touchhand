#!/usr/bin/env python3
# ============================================================
#  모양 인식 ② 실제로 잡아서 맞히기  (sim2real 완성)
#
#  시뮬로 배운 분류기(shape_model.pkl)를 실제 손에 적용.
#  물체를 4번(조금씩 돌려가며) 잡으면 → 4손가락 깊이 16개 → 모양 판정.
#  = '능동 지각': 한 번 봐선 모른다. 만지고 돌려봐야 안다.
#
#  준비 : pip install feetech-servo-sdk mujoco joblib
#         먼저  python3 day2_4a_shape_learn.py  로 shape_model.pkl 생성
#         Waveshare USB 모드 연결 (없으면 시뮬 데모 모드)
#  실행(★맥, 3D뷰):  mjpython day2_6_shape_grasp.py
#        (뷰 없이):    python3 day2_6_shape_grasp.py
#
#  키 : c = 잡기(돌려가며 4번)   o = 리셋   q = 종료
# ============================================================
import time, threading
from pathlib import Path
import numpy as np
import joblib
from shape_common import SHAPES, EMOJI, N_GRASP, extract_features, simulate_readings
import sys
try:                                   # 단일 키 입력(엔터 없이 c/o/q)
    import termios, tty
    def _getch():
        fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
        try: tty.setcbreak(fd); return sys.stdin.read(1)
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
except Exception:                      # 윈도우 등: 줄 입력 대체
    def _getch():
        return (sys.stdin.readline().strip()[:1] or " ")

import grip_config as GC              # ★ STEP 3(day2_3_grasp_sim)에서 세팅/캘리브한 값을 이어받음
_cfg         = GC.load()
OPEN_BEND    = _cfg["OPEN_BEND"]
CLOSE_TARGET = _cfg["CLOSE_TARGET"]   # 쥐는 힘/깊이 (STEP 3에서 조절한 값 공유)
GAP          = _cfg["GAP"]            # 감지 예민도(캘리브 없을 때 폴백)
MARGIN       = _cfg["MARGIN"]         # 캘리브 기준보다 이만큼 덜 닫히면 '잡음'
SETTLE       = _cfg["SETTLE"]
FREECLOSE    = _cfg["FREECLOSE"]      # STEP 3의 k 캘리브 결과 [엄지,검지,중지약지,새끼] (없으면 None)

# ── 분류기 ──
M = joblib.load(Path(__file__).resolve().parent / "shape_model.pkl")
clf = M["clf"]

# ── 실제 손 (없으면 데모) ──
hand = None
try:
    from hand_driver import HandDriver
    hand = HandDriver(); hand.speed = 200
except Exception as e:
    print("⚠️  실물 없음 → 데모 모드(가상 물체로 흐름 시연):", e)
    _demo_shape = np.random.choice(SHAPES)
    _demo_gain  = np.random.uniform(0.6, 1.4)
    _demo_off   = np.random.uniform(-0.4, 0.4)
    _demo_yaw   = np.random.uniform(0, 2*np.pi)

def do_one_grasp(k):
    """한 번 잡고 4손가락 깊이 [검지,중지약지,새끼,엄지] 반환 (막힌 손가락은 접촉점 고정)."""
    global _demo_yaw
    if hand is not None:
        hand.set_free([CLOSE_TARGET]*4, [0]*4)          # 닫기 한 번
        # SETTLE 동안 '계속' 읽어 뷰어(손+구슬)가 실시간으로 따라오게 함
        t0 = time.time(); rd = hand.read()
        while time.time() - t0 < SETTLE:
            rd = hand.read()                             # [엄지,검지,중지약지,새끼] (bend,sway)
            state["depth"] = [rd[i][0] if rd[i][0] is not None else state["depth"][i] for i in range(4)]
            time.sleep(0.05)
        depth_anat = [rd[i][0] if rd[i][0] is not None else CLOSE_TARGET for i in range(4)]
        if FREECLOSE:                                     # STEP 3 캘리브 있으면: 기준보다 덜 닫힘 = 잡음
            gripped = [(FREECLOSE[i] - depth_anat[i]) > MARGIN for i in range(4)]
        else:                                             # 없으면: 고정 목표 폴백
            gripped = [depth_anat[i] < CLOSE_TARGET - GAP for i in range(4)]
        # 읽고 바로 반환 → 호출부(session)가 매 잡기 후 손을 편다(다음 자세로 굴리게)
        # 특징용 순서 [검지,중지약지,새끼,엄지] = anat[1,2,3,0]
        return np.array([depth_anat[1], depth_anat[2], depth_anat[3], depth_anat[0]]), gripped
    else:                                                 # 데모: 가상 물체 잡기
        r = simulate_readings(_demo_shape, _demo_yaw, 1.0, _demo_gain, _demo_off, 0.02)
        _demo_yaw += np.deg2rad(np.random.uniform(20, 50))
        return r, [True, True, True, True]

def classify(grasps):
    x = extract_features(grasps).reshape(1, -1)
    proba = clf.predict_proba(x)[0]
    i = int(np.argmax(proba))
    return SHAPES[i], proba[i], proba

def open_hand():
    if hand is not None: hand.set_free([OPEN_BEND]*4, [0]*4)

# ── 진행 상태(뷰어가 읽음) ──
state = {"grasps": [], "result": None, "busy": False, "run": True,
         "depth": [OPEN_BEND]*4, "grip": [False]*4}   # grip = 잡힌 손가락 [엄지,검지,중지약지,새끼]

def session():
    print("=" * 52)
    print(f"  실제로 잡아 맞히기   c=잡기(총 {N_GRASP}번)  o=리셋  q=종료")
    if FREECLOSE:
        print(f"  ✅ STEP3 캘리브 이어받음 (기준 {[int(v) for v in FREECLOSE]}, 힘 CLOSE_TARGET={CLOSE_TARGET})")
    else:
        print(f"  ℹ️  STEP3에서 k로 캘리브하면 더 정확 (지금은 기본값, 힘 CLOSE_TARGET={CLOSE_TARGET})")
    if hand is None: print(f"  [데모] 숨긴 정답 = '{_demo_shape}' (흐름만 시연)")
    print("=" * 52)
    open_hand()
    while state["run"]:
        s = _getch().lower()
        if s in ("q", "\x03"): state["run"] = False; break
        if s == "o":
            state["grasps"] = []; state["result"] = None; state["grip"] = [False]*4; open_hand()
            print("  → 리셋. 물체 놓고 c 로 잡기 시작."); continue
        if s == "c":
            if state["busy"]: continue
            state["busy"] = True
            k = len(state["grasps"]) + 1
            print(f"  ✊ {k}/{N_GRASP} 번째 잡는 중...")
            depth, gripped = do_one_grasp(k)
            state["depth"] = [depth[3], depth[0], depth[1], depth[2]]  # 뷰어용 anat순
            state["grip"] = gripped                                    # 빨간 구슬 표시용
            state["grasps"].append(depth)
            names = ["검지", "중지약지", "새끼", "엄지"]
            grabbed = ", ".join(names[i] for i in range(4) if gripped[i]) or "(막힌 손가락 없음)"
            print(f"     깊이[검지 중지약지 새끼 엄지] = {np.round(depth,0).astype(int)}  막힘: {grabbed}")
            if len(state["grasps"]) >= N_GRASP:
                name, conf, proba = classify(state["grasps"])
                state["result"] = name
                print("\n" + "─" * 40)
                print(f"    🤖 이건  {EMOJI[name]}  '{name}'  이에요!   (확신 {conf*100:.0f}%)")
                order = np.argsort(proba)[::-1]
                print("    " + "   ".join(f"{SHAPES[j]} {proba[j]*100:.0f}%" for j in order))
                if hand is None: print(f"    (정답: '{_demo_shape}')")
                print("─" * 40 + "\n  → o 로 리셋 후 다른 물체.")
                state["grasps"] = []
            else:
                print(f"  → 물체를 살짝(약 30°) 돌리고 다시 c  [{len(state['grasps'])}/{N_GRASP}]")
            time.sleep(0.7)                                # 잡힌 손가락(빨강) 잠깐 보여주고
            open_hand()                                    # 편다(다음 자세로 굴리게)
            state["depth"] = [OPEN_BEND]*4
            state["grip"] = [False]*4                      # 펴지면 구슬 색 복귀(빨강 → 기본)
            state["busy"] = False

# ── 3D 뷰어(있으면) : 실제 손 모습을 비춤 ──
def run_with_viewer():
    import mujoco, mujoco.viewer
    HERE = Path(__file__).resolve().parent
    model = mujoco.MjModel.from_xml_path(str(HERE/"AHSimulation"/"AH_Left"/"mjcf"/"scene.xml"))
    data = mujoco.MjData(model)
    SIM = {"thumb": 3, "index": 0, "mid": 1, "pinky": 2}
    def pose_to_ctrl(flex4):
        c = [0.0]*8; vals = {"thumb":flex4[0],"index":flex4[1],"mid":flex4[2],"pinky":flex4[3]}
        for nm, f in SIM.items(): c[f*2] = +vals[nm]; c[f*2+1] = -vals[nm]
        return c
    # 손끝 목표 구슬(빨간 점)을 손끝을 따라오게 + 잡힌 손가락은 빨강으로 표시
    def _bid(nm): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, nm)
    GEOM = []
    for i in range(4):
        b = _bid(f"finger{i+1}_target")
        GEOM.append(next((g for g in range(model.ngeom) if model.geom_bodyid[g] == b), -1))
    TIPSITE = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"tip{i+1}") for i in range(4)]
    MOCAPID = [model.body_mocapid[_bid(f"finger{i+1}_target")] for i in range(4)]
    SIMFINGER_TO_ANAT = [1, 2, 3, 0]        # 시뮬 finger1~4 = [검지,중지약지,새끼,엄지]
    GREEN = [0.2, 0.8, 0.3, 0.55]; RED = [1.0, 0.15, 0.1, 0.95]

    cur = [0.0]*8
    threading.Thread(target=session, daemon=True).start()
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running() and state["run"]:
            flex4 = [state["depth"][a]/250.0 for a in range(4)]
            tgt = pose_to_ctrl(flex4)
            for k in range(8):
                d = tgt[k]-cur[k]; cur[k] += 0.06 if d>0.06 else (-0.06 if d<-0.06 else d)
                data.ctrl[k] = cur[k]
            mujoco.mj_step(model, data)
            for sf in range(4):                                  # 잡힌 손가락 구슬 빨강
                if GEOM[sf] >= 0:
                    model.geom_rgba[GEOM[sf]] = RED if state["grip"][SIMFINGER_TO_ANAT[sf]] else GREEN
            for i in range(4):                                   # 구슬을 손끝 위치로(따라다니게)
                if MOCAPID[i] >= 0 and TIPSITE[i] >= 0:
                    data.mocap_pos[MOCAPID[i]] = data.site_xpos[TIPSITE[i]]
            viewer.sync(); time.sleep(0.004)
    state["run"] = False

if __name__ == "__main__":
    try:
        import mujoco  # noqa
        run_with_viewer()
    except Exception as e:
        print("(3D 뷰 없이 진행:", e, ")")
        session()
    if hand is not None: hand.close()
    print("\n종료!")
