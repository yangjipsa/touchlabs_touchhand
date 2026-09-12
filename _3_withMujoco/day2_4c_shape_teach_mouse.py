#!/usr/bin/env python3
# ============================================================
#  모양 인식 - "내가 직접 가르치기" (마우스 이동판, 하드웨어 없이)
#   day2_4b 와 동일한 머신러닝 루프(수집→학습→추론)를 그대로 쓰되,
#   물체 '위치 이동'을 키보드 대신 3D 창에서 마우스 드래그로 한다.
#   (회전은 재현성을 위해 기존과 같은 키보드 20도 단위 그대로 유지)
#
#  ▶ 이동(마우스):  3D 창에서 물체 위에 뜬 '반투명 초록 핸들'을
#       더블클릭해 선택 → Ctrl 누른 채 드래그하면 물체가 따라온다.
#     (핸들 = mocap body. MuJoCo 뷰어는 mocap/free body 만 마우스로 잡힌다)
#  ▶ 나머지 키는 '터미널 창'에서:
#     Z : 가르칠 도형 바꾸기 (구/타원/정육면체)
#     A/D : 좌우돌리기   W/S : 앞뒤굴리기   E/R : 옆으로굴리기   (3축!)
#     J/L·I/K·U/M : 위치 이동(마우스 대신 키보드로도 가능, 병행)
#     G : 잡아서 수집(4번)   T : 학습   B : 맞혀보기   N : 블라인드   X : 종료
#   ※ 숫자키/Space 등은 MuJoCo 뷰어 자체 기능이라 피했음
#
#  준비 : pip install mujoco scikit-learn numpy
#  실행(★맥):  mjpython day2_4c_shape_teach_mouse.py   (윈도우: python day2_4c_shape_teach_mouse.py)
#  구현: 물체는 기존처럼 조인트 없는 정적 body(마우스로 안 잡힘)라서,
#        별도의 mocap '드래그 핸들' body 를 MjSpec 에 추가하고
#        매 프레임 data.mocap_pos 를 읽어 물체 위치에 반영한다(접근 A).
#        데이터 수집/학습/추론·물리 판정 로직은 day2_4b 와 동일.
# ============================================================
import time, threading
import numpy as np
import mujoco
from sklearn.ensemble import RandomForestClassifier
from shape_common import SHAPES, EMOJI, N_GRASP, extract_features, Pacer, frame_camera
import day2_5_shape_grasp_sim as G

st = {"cmd": None, "run": True, "sel": 0}
D = {"X": [], "y": [], "clf": None, "hidden": False}

# 안전한 문자키만 (MuJoCo 네이티브 숫자/Space/Esc 등과 안 겹침)
ROT = {"a": ("z", +1), "d": ("z", -1), "w": ("y", +1), "s": ("y", -1), "e": ("x", +1), "r": ("x", -1)}
AXIS = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
IDENT = np.array([1.0, 0, 0, 0])
# 위치 이동 키(마우스와 병행) — y=좌우, x=앞뒤, z=상하
MOVE = {"j": ("y", +1), "l": ("y", -1), "i": ("x", +1), "k": ("x", -1), "u": ("z", +1), "m": ("z", -1)}
AXI = {"x": 0, "y": 1, "z": 2}
POS_STEP = 0.004

# ── 마우스 드래그용 mocap 핸들 ──
HANDLE_NAME  = "DRAG_HANDLE"
HANDLE_OFFSET = np.array([0.0, 0.0, 0.09])     # 물체 위로 9cm 띄움(물체를 덜 가림)
HANDLE_R     = 0.01                              # 작게(물체 가림 최소) — 더블클릭엔 충분
HANDLE_RGBA  = [0.15, 0.9, 0.5, 0.28]           # 반투명 초록(덜 도드라지게)

def counts():
    c = [0]*len(SHAPES)
    for yy in D["y"]: c[yy] += 1
    return c

def train():
    X, y = np.array(D["X"]), np.array(D["y"]); cc = counts()
    if len(set(y)) < 2 or min(cc[i] for i in set(y)) < 2:
        print("  ⚠️  최소 2종류, 종류당 2개 이상 필요. 지금:",
              {SHAPES[i]: cc[i] for i in range(len(SHAPES)) if cc[i]}); return
    clf = RandomForestClassifier(n_estimators=200, random_state=0).fit(X, y)
    D["clf"] = clf
    print(f"  ✅ 학습 완료! 데이터 {len(y)}개 → 학습셋 정확도 {(clf.predict(X)==y).mean()*100:.0f}%  (B 로 테스트)")

def handle(ch):
    if ch == "x": st["run"] = False                   # 종료
    elif ch == "z": st["cmd"] = ("cycle", None)        # 가르칠 도형 바꾸기
    elif ch in ROT: st["cmd"] = ("rot", ch)            # a/d w/s e/r = 3축 회전
    elif ch in MOVE: st["cmd"] = ("move", ch)          # j/l i/k u/m = 위치 이동(마우스 대신)
    elif ch == "g": st["cmd"] = ("collect", None)      # 잡아서 수집
    elif ch == "t": st["cmd"] = ("train", None)        # 학습
    elif ch == "b": st["cmd"] = ("test", None)         # 맞혀보기
    elif ch == "n": st["cmd"] = ("hidden", None)       # 블라인드

def banner():
    sel = " / ".join(f"{EMOJI[s]}{s}" for s in SHAPES)
    print("="*62)
    print("  내가 직접 가르치기 (마우스 이동판)")
    print("  이동:  3D창에서 물체 위 '반투명 초록 핸들' 더블클릭→Ctrl+드래그")
    print("        (키보드 J/L·I/K·U/M 도 병행 가능)")
    print("  ─ 아래 키는 '터미널 창'에서 ─")
    print("  Z = 가르칠 도형 바꾸기  (" + sel + ")")
    print("  회전(3축):  A/D=좌우돌리기   W/S=앞뒤굴리기   E/R=옆으로굴리기")
    print("  G=잡아서수집   T=학습   B=맞혀보기   N=블라인드   X=종료")
    print("="*62)
    print(f"  지금 도형: {EMOJI[SHAPES[0]]} {SHAPES[0]}  · 굴리고/옮기고 G로 잡아 모으세요")

def build_model_with_handle():
    """day2_5.build_model() 을 복제하되, 마우스 드래그용 mocap 핸들 body 를 추가.
    (기존 파일 불변 — day2_5 의 상수/함수는 읽기만 재사용). 물체는 그대로 정적 body."""
    spec = mujoco.MjSpec.from_file(str(G.HERE/"AHSimulation"/"AH_Left"/"mjcf"/"scene.xml"))
    for bn in G.TIPB:                                       # 손끝 충돌 캡슐(투명)
        b = spec.body(bn); g = b.add_geom(); g.type = mujoco.mjtGeom.mjGEOM_CAPSULE
        g.fromto = G.CAP_FROMTO; g.size[0] = G.CAP_R
        g.contype = 1; g.conaffinity = 2; g.group = 3; g.rgba[:] = [1, .6, 0, 0.0]
    for bn in G.DISTB:                                      # 원위 마디 충돌 캡슐(투명)
        b = spec.body(bn); g = b.add_geom(); g.type = mujoco.mjtGeom.mjGEOM_CAPSULE
        g.fromto = G.CAP2_FROMTO; g.size[0] = G.CAP2_R
        g.contype = 1; g.conaffinity = 2; g.group = 3; g.rgba[:] = [1, .6, 0, 0.0]
    for s in SHAPES:
        G._add_object(spec, mujoco, s)                     # 정육면체/구/타원 = 조인트 없는 정적 body
    # ★ mocap 드래그 핸들: 마우스로 잡히는 유일한 body. 충돌 없음(contype/conaffinity=0).
    h = spec.worldbody.add_body(); h.name = HANDLE_NAME
    h.mocap = True
    h.pos[:] = G.GRASP_POS + HANDLE_OFFSET
    hg = h.add_geom(); hg.type = mujoco.mjtGeom.mjGEOM_SPHERE
    hg.size[:] = [HANDLE_R, 0, 0]
    hg.contype = 0; hg.conaffinity = 0; hg.group = 2; hg.rgba[:] = HANDLE_RGBA
    m = spec.compile()
    m.actuator_forcelimited[:] = 1; m.actuator_forcerange[:] = np.array([-G.TORQUE, G.TORQUE])
    for i in range(1, 5):                                   # 원본의 빨간 목표구슬 숨김
        bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"finger{i}_target")
        if bid >= 0:
            for g in range(m.ngeom):
                if m.geom_bodyid[g] == bid: m.geom_rgba[g] = [0, 0, 0, 0]
    return m

def run():
    import mujoco.viewer
    rng = np.random.default_rng()
    model = build_model_with_handle(); d = mujoco.MjData(model); FQ = G.finger_q(model)
    BID  = {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY, f"OBJ_{s}") for s in SHAPES}
    OGEOM= {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,f"OBJ_{s}") for s in SHAPES}
    HBID = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, HANDLE_NAME)
    MOCAP = int(model.body_mocapid[HBID])                  # 핸들의 mocap 인덱스
    REF = G.measure_ref(model, d, FQ, close=G.CLOSE_DEMO)  # ★ 빈손·펼침 기준(막힌 비율용)

    def show(idx, pos):
        for s in SHAPES:
            model.body_pos[BID[s]] = pos if s == SHAPES[idx] else G.AWAY_POS
            model.geom_rgba[OGEOM[s]] = G.COLOR[s]

    def push_handle(pos):
        d.mocap_pos[MOCAP] = np.asarray(pos, float) + HANDLE_OFFSET   # 핸들을 물체 위로 따라오게

    def reset_sim():
        mujoco.mj_resetData(model, d)                     # ★ mj_resetData 는 mocap_pos 도 초기화 →
        push_handle(cur_pos)                              #    현재 물체 위치로 핸들 재동기화

    cur_pos = G.jitter_pos(rng)                            # 물체 위치(마우스 드래그/키보드로 이동)
    banner(); show(0, cur_pos); reset_sim()
    quat = IDENT.copy(); cur_v = -0.8
    phase = "idle"; frames = 0; buf = []; buf_mode = None
    CLOSE_F, HOLD_F, OPEN_F = G.CLOSE_STEPS, 40, 90
    pacer = Pacer(model.opt.timestep)                      # ★ 렌더 속도와 무관하게 실시간 물리

    def finish():
        cs = SHAPES[st["sel"]]; feat = extract_features(buf, ref=REF)
        if buf_mode == "collect":
            D["X"].append(feat); D["y"].append(st["sel"]); cc = counts()
            print(f"  ➕ 데이터 1개! [{EMOJI[cs]}{cs}] 총 {len(D['y'])}개  "
                  + " ".join(f"{EMOJI[SHAPES[i]]}{cc[i]}" for i in range(len(SHAPES))) + "   (T=학습)")
        else:
            if D["clf"] is None: print("  ⚠️  먼저 모으고 T 로 학습하세요.")
            else:
                p = D["clf"].predict_proba(feat.reshape(1,-1))[0]; pi = int(p.argmax()); ok = (pi == st["sel"])
                model.geom_rgba[OGEOM[cs]] = [.2,.85,.3,1] if ok else [.9,.2,.2,1]
                print(f"  🤖 판정: {EMOJI[SHAPES[pi]]}{SHAPES[pi]} ({p.max()*100:.0f}%)  {'✅정답' if ok else '❌땡'}  (정답 {EMOJI[cs]}{cs})")

    threading.Thread(target=G.key_thread, args=(handle, lambda: st["run"]), daemon=True).start()
    with mujoco.viewer.launch_passive(model, d) as viewer:   # 회전/명령 키는 터미널, 이동은 마우스
        frame_camera(viewer)                                 # ★ 손+물체가 한눈에
        while viewer.is_running() and st["run"]:
            cs = SHAPES[st["sel"]]
            if phase == "idle":                              # ★ 마우스로 끈 핸들 위치를 물체에 반영
                cur_pos = (d.mocap_pos[MOCAP] - HANDLE_OFFSET).copy()
            model.body_quat[BID[cs]] = quat        # 정적 body 방향 = 학생이 돌린 자세
            model.body_pos[BID[cs]]  = cur_pos     # 정적 body 위치 = 마우스/키보드로 옮긴 위치

            cmd = st["cmd"]; st["cmd"] = None
            if cmd and phase == "idle":
                kind, val = cmd
                if kind == "cycle":                       # 가르칠 도형 순환
                    st["sel"] = (st["sel"] + 1) % len(SHAPES); D["hidden"] = False
                    cur_pos = G.jitter_pos(rng); show(st["sel"], cur_pos); push_handle(cur_pos)
                    quat = IDENT.copy(); buf = []; buf_mode = None
                    print(f"  지금 도형: {EMOJI[SHAPES[st['sel']]]} {SHAPES[st['sel']]}")
                elif kind == "hidden":
                    st["sel"] = int(rng.integers(len(SHAPES))); D["hidden"] = True
                    cur_pos = G.jitter_pos(rng); show(st["sel"], cur_pos); push_handle(cur_pos)
                    quat = G.rand_quat(rng); buf = []; buf_mode = None
                    print("  🙈 숨김 도형 — 굴리며 B 3번 = 맞혀보기")
                elif kind == "rot":
                    ax, sgn = ROT[val]; quat = G.qmul(G.axis_quat(AXIS[ax], sgn*np.deg2rad(20)), quat)
                    quat = quat/np.linalg.norm(quat); print(f"  ↻ 굴림 ({val.upper()})")
                elif kind == "move":                      # 키보드 이동(마우스와 병행)
                    ax, sgn = MOVE[val]; cur_pos = cur_pos.copy(); cur_pos[AXI[ax]] += sgn * POS_STEP
                    push_handle(cur_pos); print(f"  ⇄ 이동 ({val.upper()})  pos={np.round(cur_pos, 3)}")
                elif kind == "train":
                    train()
                elif kind in ("collect", "test"):
                    if buf_mode is None: buf = []; buf_mode = kind
                    reset_sim(); cur_v = -0.8            # 학습(4a)과 같은 초기상태에서 잡기(핸들도 재동기)
                    phase = "close"; frames = 0

            for _ in range(pacer.substeps()):            # ★ 물리 스텝 단위로 램프/카운트 (학습과 동일)
                tgt = G.CLOSE_DEMO if phase == "close" else (-0.8 if phase == "open" else cur_v)
                cur_v += np.clip(tgt - cur_v, -0.03, 0.03); d.ctrl[:] = G.ctrl_v(cur_v)
                if phase in ("close","open","hold"):
                    frames += 1
                    if phase == "close" and frames >= CLOSE_F:
                        buf.append(G.read_flex(d, FQ)); phase, frames = "hold", 0   # 다 잡은 뒤 읽기
                    elif phase == "hold" and frames >= HOLD_F: phase, frames = "open", 0
                    elif phase == "open" and frames >= OPEN_F:
                        phase = "idle"
                        if len(buf) < N_GRASP:
                            nk = "G" if buf_mode == "collect" else "B"
                            print(f"  ✊ 잡기 {len(buf)}/{N_GRASP} — 굴리고 다시 {nk} (다른 자세로!)")
                        else:
                            finish(); buf = []; buf_mode = None
                            print("  → 위치(마우스 드래그·J/L·I/K·U/M)·자세(A/D·W/S·E/R)를 바꿔 다시 G")
                mujoco.mj_step(model, d)
            viewer.sync(); time.sleep(0.001)
    st["run"] = False

if __name__ == "__main__":
    try:
        import mujoco  # noqa
        run()
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n(MuJoCo 뷰어 실행 필요: 맥 mjpython / 윈도우 python  day2_4c_shape_teach_mouse.py )")
    print("\n종료!")
