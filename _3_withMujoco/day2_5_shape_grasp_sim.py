#!/usr/bin/env python3
# ============================================================
#  모양 인식 - 하이브리드 데모 (하드웨어 없이)  ※ 3축 회전판
#   · MuJoCo 가 물체를 '실제 물리로' 꽉 쥔다 (충돌+토크한계 → 손가락이 막혀 멈춤)
#   · 물체를 4번(3D로 굴려가며) 잡아 = 능동 지각
#   · 판정 = 잡을 때 손가락 깊이(물리)로 학습한 분류기 → "이건 정육면체예요!"
#     (시뮬·실물이 똑같이 '손가락 깊이'를 쓰므로 일관됨)
#
#  도형: 구(공) · 타원(럭비공) · 정육면체   ★ 실물과 동일 치수 (85 / 120×70 / 75 mm)
#  준비 : pip install mujoco scikit-learn joblib numpy
#         먼저  python3 day2_4a_shape_learn.py  (shape_model.pkl 생성)
#  실행(★맥):  mjpython day2_5_shape_grasp_sim.py      (윈도우: python day2_5_shape_grasp_sim.py)
#  ▶ 키(터미널 창 클릭 후):  G = 잡아서 맞히기(4번)   N = 다른 물체   X = 종료
#
#  v2: · '막힌 비율' 특징(빈손 기준 대비) → 크기까지 반영   · 실물 치수로 교정
#      · 물리를 렌더와 분리(Pacer) → 저사양/윈도우에서도 손이 느리거나 힘없어 보이지 않음
#      · 카메라 자동 프레이밍(frame_camera) → 창이 좁아도 양옆 안 잘림
# ============================================================
import sys, time, threading   # termios/tty/select 는 key_thread 안에서 (Windows 호환)
from pathlib import Path
import numpy as np
import joblib
from shape_common import SHAPES, EMOJI, N_GRASP, FEAT_VERSION, extract_features, Pacer, frame_camera

HERE = Path(__file__).resolve().parent
OBJDIR = HERE / "objmesh"

def load_model_file():
    """shape_model.pkl 읽기 (특징 버전 검사). 학습 스크립트가 import 할 땐 호출되지 않음."""
    M = joblib.load(HERE / "shape_model.pkl")
    if M.get("feat_version") != FEAT_VERSION:
        print(f"⚠️  shape_model.pkl 이 옛 형식입니다(특징 v{M.get('feat_version', 1)} ≠ v{FEAT_VERSION}).")
        print("    →  python day2_4a_shape_learn.py  로 다시 학습한 뒤 실행하세요.")
        sys.exit(1)
    return M

TIPB = ['parallel_pin_2_x_10__fee063fca0c8b40e46bbc4ffff61d999'+s for s in ['', '_2', '_3', '_4']]
# 손끝 패드를 따라 이어진 충돌 캡슐(막대) → 뾰족한 모서리도 틈으로 안 파고듦
# 반지름을 보이는 손가락 굵기(~13mm)에 맞춰 면에 안 박히게
CAP_FROMTO = [0.028, -0.029, 0.0022, 0.012, -0.009, 0.0022]
CAP_R = 0.013
# 원위(끝) 마디 x_16 — 손끝뿐 아니라 손가락 마디 전체가 물체에 막히도록(관통·발산 완화)
DISTB = ['parallel_pin_2_x_16__da4b7ddbe9d803fe3fbc70f2e822b99b'+s for s in ['', '_2', '_3', '_4']]
CAP2_FROMTO = [-0.004, -0.010, 0.005, -0.042, -0.010, 0.005]
CAP2_R = 0.012
GRASP_POS = np.array([0.032, 0.014, 0.10])     # 손바닥에 붙인 위치(실제 잡는 방식)
AWAY_POS  = np.array([0.05, 0.014, -1.0])
POS_JITTER = np.array([0.004, 0.008, 0.005])   # 랜덤범위 (x앞뒤 작게=손바닥밀착, y좌우 위주, z상하)
def jitter_pos(rng):
    return GRASP_POS + rng.uniform(-POS_JITTER, POS_JITTER)
TORQUE = 0.5
SIM = {"thumb": 3, "index": 0, "mid": 1, "pinky": 2}
COLOR = {"구":[.3,.6,.9,1], "타원":[.9,.55,.3,1], "정육면체":[.85,.35,.35,1]}
# 물체 치수 — ★ 실물과 동일 (sim2real 성립 조건). 반지름/반축 단위 m
SIZE = {"구":    ("sphere", [0.0425, 0, 0]),             # 지름 85mm 공
        "타원":   ("ell",    [0.0600, 0.0350, 0.0350]),  # 럭비공 120 x 70 mm
        "정육면체": ("box",    [0.0375, 0.0375, 0.0375])}  # 75mm 정육면체
CLOSE_STEPS = 300      # 이만큼 닫고(거의 다 잡힘) 손가락 깊이를 읽음. 학습·데모 동일
CLOSE_DEMO  = 1.4      # 데모/가르치기에서 쥐는 정도 (학습은 1.2~1.6 랜덤)

def _add_object(spec, mujoco, shape):
    # 조인트 없는 정적 body — 방향은 model.body_quat 로 직접 제어(솔버 충돌 없음, 3축 자유)
    ob = spec.worldbody.add_body(); ob.name = f"OBJ_{shape}"; ob.pos[:] = AWAY_POS
    g = ob.add_geom(); g.contype = 2; g.conaffinity = 1; g.rgba[:] = COLOR[shape]
    kind, sz = SIZE[shape]
    if kind == "sphere": g.type = mujoco.mjtGeom.mjGEOM_SPHERE;   g.size[:] = sz
    elif kind == "ell":  g.type = mujoco.mjtGeom.mjGEOM_ELLIPSOID; g.size[:] = sz
    elif kind == "box":  g.type = mujoco.mjtGeom.mjGEOM_BOX;       g.size[:] = sz

def build_model():
    """3개 도형을 한 모델에(활성만 잡는 자리, 나머지는 멀리). 각 물체 = 정적 body(3축 회전은 quat)."""
    import mujoco
    spec = mujoco.MjSpec.from_file(str(HERE/"AHSimulation"/"AH_Left"/"mjcf"/"scene.xml"))
    for bn in TIPB:                                         # 손끝 충돌 캡슐(투명, 패드 덮음)
        b = spec.body(bn); g = b.add_geom(); g.type = mujoco.mjtGeom.mjGEOM_CAPSULE
        g.fromto = CAP_FROMTO; g.size[0] = CAP_R
        g.contype = 1; g.conaffinity = 2; g.group = 3; g.rgba[:] = [1, .6, 0, 0.0]
    for bn in DISTB:                                        # 원위 마디 충돌 캡슐(투명, 마디 전체 덮음)
        b = spec.body(bn); g = b.add_geom(); g.type = mujoco.mjtGeom.mjGEOM_CAPSULE
        g.fromto = CAP2_FROMTO; g.size[0] = CAP2_R
        g.contype = 1; g.conaffinity = 2; g.group = 3; g.rgba[:] = [1, .6, 0, 0.0]
    for s in SHAPES:
        _add_object(spec, mujoco, s)
    m = spec.compile()
    m.actuator_forcelimited[:] = 1; m.actuator_forcerange[:] = np.array([-TORQUE, TORQUE])
    for i in range(1, 5):                                   # 원본의 빨간 목표구슬 숨김
        bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"finger{i}_target")
        if bid >= 0:
            for g in range(m.ngeom):
                if m.geom_bodyid[g] == bid: m.geom_rgba[g] = [0, 0, 0, 0]
    return m

def ctrl_v(v):
    c = [0.0]*8
    for nm, f in SIM.items(): c[f*2] = +v; c[f*2+1] = -v
    return c

def finger_q(model):
    import mujoco
    return {f: (model.jnt_qposadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,f'finger{f}_motor1')],
                model.jnt_qposadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,f'finger{f}_motor2')]) for f in range(1,5)}

def read_flex(data, FQ):
    """손가락별 실제 닫힘량 [검지,중지약지,새끼,엄지] (물리 접촉으로 막힌 만큼)."""
    return np.array([(data.qpos[FQ[f][0]] - data.qpos[FQ[f][1]])/2 for f in range(1, 5)])

def settle(model, data, close):
    """리셋 후 손을 close 까지 닫으며(학습·데모 공통 램프) CLOSE_STEPS 만큼 물리 진행."""
    import mujoco
    mujoco.mj_resetData(model, data); cur = -0.8
    for _ in range(CLOSE_STEPS):
        cur += np.clip(close - cur, -0.03, 0.03); data.ctrl[:] = ctrl_v(cur)
        mujoco.mj_step(model, data)

def measure_ref(model, data, FQ, close=CLOSE_DEMO, open_ref=None):
    """★ 빈손 기준(free)·펼침 기준(open) 측정 = 실물의 STEP3 'k' 캘리브(FREECLOSE)와 같은 정의.
    모든 물체를 멀리 치우고 잡아 본다. open_ref 를 주면 open 측정은 생략(학습에서 재사용).
    ※ 호출 후 물체는 모두 AWAY 상태 → 필요하면 다시 놓을 것."""
    import mujoco
    for s in SHAPES:
        model.body_pos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"OBJ_{s}")] = AWAY_POS
    settle(model, data, close);  free = read_flex(data, FQ)
    if open_ref is None:
        settle(model, data, -0.8); open_ref = read_flex(data, FQ)
    return free, np.asarray(open_ref, float)

# ── 3D 회전 유틸 (쿼터니언 [w,x,y,z]) ──
def rand_quat(rng):
    u1, u2, u3 = rng.random(3)
    return np.array([np.sqrt(u1)*np.cos(2*np.pi*u3), np.sqrt(1-u1)*np.sin(2*np.pi*u2),
                     np.sqrt(1-u1)*np.cos(2*np.pi*u2), np.sqrt(u1)*np.sin(2*np.pi*u3)])

def axis_quat(axis, ang):
    s = np.sin(ang/2); a = np.asarray(axis, float)
    return np.array([np.cos(ang/2), a[0]*s, a[1]*s, a[2]*s])

def qmul(a, b):
    w1,x1,y1,z1 = a; w2,x2,y2,z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2,
                     w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])

def classify(clf, flex_list, ref):
    p = clf.predict_proba(extract_features(flex_list, ref=ref).reshape(1, -1))[0]
    return SHAPES[int(p.argmax())], p

# ── 터미널 단일키 입력 (뷰어 단축키와 충돌 없음) ──
def key_thread(handle, run_flag):
    # 키를 '엔터 없이 한 글자씩' 받는다. OS마다 단일키 입력 방식이 달라 분기.
    try:
        import msvcrt                          # Windows: 단일키 입력 모듈(표준)
        while run_flag():
            if msvcrt.kbhit():                 # 눌린 키가 있으면
                ch = msvcrt.getch()            # 한 글자 읽기(엔터 불필요)
                try: handle(ch.decode(errors="ignore").lower())
                except Exception: pass
            else:
                time.sleep(0.03)               # 없으면 잠깐 쉬어 CPU 절약
        return
    except ImportError:
        pass                                   # msvcrt 없음 = Mac/Linux → 아래로

    try:
        import termios, tty, select            # Mac/Linux: 단일키(termios raw 모드)
    except ImportError:
        termios = tty = select = None          # 둘 다 없으면: 줄입력(Enter) 폴백
    fd = sys.stdin.fileno()
    try: old = termios.tcgetattr(fd)
    except Exception: old = None
    try:
        if old is not None: tty.setcbreak(fd)  # raw 모드: 엔터 없이 즉시 읽기
        while run_flag():
            if old is not None:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if r: handle(sys.stdin.read(1).lower())
            else:
                handle((sys.stdin.readline().strip()[:1] or " ").lower())
    finally:
        if old is not None: termios.tcsetattr(fd, termios.TCSADRAIN, old)

state = {"cmd": None, "run": True}
def handle(ch):
    # 안전한 문자키만 (MuJoCo 네이티브 숫자/Space/Esc 등과 안 겹침)
    if ch == "x": state["run"] = False               # 종료
    elif ch in ("g", "n"): state["cmd"] = ch          # g=잡기, n=다른물체

def run():
    import mujoco, mujoco.viewer
    clf = load_model_file()["clf"]
    rng = np.random.default_rng()
    model = build_model(); data = mujoco.MjData(model)
    FQ = finger_q(model)
    BID  = {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY, f"OBJ_{s}") for s in SHAPES}
    OGEOM= {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,f"OBJ_{s}") for s in SHAPES}
    REF = measure_ref(model, data, FQ, close=CLOSE_DEMO)    # ★ 빈손·펼침 기준(시뮬) — 학습과 같은 정의

    def place(active, pos):
        for s in SHAPES:
            model.body_pos[BID[s]] = pos if s == active else AWAY_POS
            model.geom_rgba[OGEOM[s]] = COLOR[s]
    def set_quat(shape, q):
        model.body_quat[BID[shape]] = q       # 정적 body 방향 = 물체 회전

    print("="*52)
    print("  하이브리드: MuJoCo가 실제로 쥐고, AI가 맞힘 (3축 회전)")
    print("  ▶ 키는 '터미널 창'에서:  G=잡아서 맞히기  N=다른 물체  X=종료")
    print("    (3D창은 마우스로 시점만. 창에서 키 누르지 마세요)")
    print("="*52)
    truth = str(rng.choice(SHAPES)); obj_pos = jitter_pos(rng); place(truth, obj_pos)
    quat = rand_quat(rng); set_quat(truth, quat)
    mujoco.mj_resetData(model, data)
    threading.Thread(target=key_thread, args=(handle, lambda: state["run"]), daemon=True).start()
    print("\n  [새 물체 등장]  무엇일까요?  (G 로 잡아보기)")

    cur_v = -0.8
    phase = "idle"; rep = 0; frames = 0; flexes = []; quats = []
    CLOSE_F, HOLD_F, OPEN_F = CLOSE_STEPS, 40, 110
    pacer = Pacer(model.opt.timestep)                        # ★ 렌더 속도와 무관하게 실시간 물리

    with mujoco.viewer.launch_passive(model, data) as viewer:   # 키는 터미널에서만(key_thread)
        frame_camera(viewer)                                  # ★ 손+물체가 한눈에
        while viewer.is_running() and state["run"]:
            if state["cmd"] == "n" and phase == "idle":
                state["cmd"] = None
                truth = str(rng.choice(SHAPES)); obj_pos = jitter_pos(rng); place(truth, obj_pos)
                quat = rand_quat(rng); set_quat(truth, quat); cur_v = -0.8
                print("\n  [새 물체 등장]  무엇일까요?  (G 로 잡아보기)")
            elif state["cmd"] == "g" and phase == "idle":
                state["cmd"] = None; phase = "close"; rep = 0; frames = 0; flexes = []
                quats = [rand_quat(rng) for _ in range(N_GRASP)]; quat = quats[0]; set_quat(truth, quat)
                mujoco.mj_resetData(model, data); cur_v = -0.8   # ★ 학습과 동일하게 매 잡기 초기화(sim2real 일치)
                print(f"  ✊ 1/{N_GRASP} 잡는 중 (물체 3D 자세)...")

            for _ in range(pacer.substeps()):                # ★ 물리 스텝 단위로 램프/카운트 (학습과 동일)
                tgt = CLOSE_DEMO if phase == "close" else (-0.8 if phase == "open" else cur_v)
                cur_v += np.clip(tgt - cur_v, -0.03, 0.03); data.ctrl[:] = ctrl_v(cur_v)
                if phase in ("close","open","hold"):
                    frames += 1
                    if phase == "close" and frames >= CLOSE_F:
                        flexes.append(read_flex(data, FQ)); phase, frames = "hold", 0   # 다 잡은 뒤 읽기
                    elif phase == "hold" and frames >= HOLD_F: phase, frames = "open", 0
                    elif phase == "open" and frames >= OPEN_F:
                        rep += 1
                        if rep < N_GRASP:
                            quat = quats[rep]; set_quat(truth, quat)
                            mujoco.mj_resetData(model, data); cur_v = -0.8   # ★ 매 잡기 초기화
                            phase, frames = "close", 0
                            print(f"  ✊ {rep+1}/{N_GRASP} 잡는 중 (다른 자세로 굴림)...")
                        else:
                            name, p = classify(clf, flexes, REF); ok = (name == truth)
                            model.geom_rgba[OGEOM[truth]] = [0.2,0.85,0.3,1] if ok else [0.9,0.2,0.2,1]
                            print("\n"+"─"*40)
                            print(f"    🤖 이건  {EMOJI[name]} '{name}' 이에요!  (확신 {p.max()*100:.0f}%)")
                            print(f"    정답: {EMOJI[truth]} '{truth}'   {'✅ 맞음!' if ok else '❌ 틀림'}")
                            print("─"*40+"\n  → N 다른 물체 / X 종료")
                            phase = "idle"
                mujoco.mj_step(model, data)
            viewer.sync(); time.sleep(0.001)
    state["run"] = False

if __name__ == "__main__":
    try:
        import mujoco  # noqa
        run()
    except SystemExit:
        pass
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n(MuJoCo 뷰어 실행 필요: 맥 mjpython / 윈도우 python  day2_5_shape_grasp_sim.py )")
    print("\n종료!")
