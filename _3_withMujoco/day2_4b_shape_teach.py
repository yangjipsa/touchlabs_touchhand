#!/usr/bin/env python3
# ============================================================
#  모양 인식 - "내가 직접 가르치기" (인터랙티브 학습, 하드웨어 없이)
#   학생이 도형을 3D로 굴려가며 직접 잡아서 데이터를 모으고 → 학습 → 테스트.
#   = 머신러닝 전체 루프를 손으로 체험 (수집→학습→추론).
#   판정은 MuJoCo가 실제로 잡을 때의 '손가락 깊이'(물리)로.
#
#  ▶ 터미널 창을 클릭해 두고 키:
#     Z : 가르칠 도형 바꾸기 (구/타원/정육면체)
#     A/D : 좌우돌리기   W/S : 앞뒤굴리기   E/R : 옆으로굴리기   (3축!)
#     G : 잡아서 수집(4번)   T : 학습   B : 맞혀보기   N : 블라인드   X : 종료
#   ※ 숫자키/Space 등은 MuJoCo 뷰어 자체 기능이라 피했음
#
#  준비 : pip install mujoco scikit-learn numpy
#  실행(★맥):  mjpython day2_4b_shape_teach.py      (윈도우: python day2_4b_shape_teach.py)
#  v2: 빈손 기준(막힌 비율) 특징 · Pacer(저사양/윈도우) · 카메라 자동 프레이밍
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
# 위치 이동 키 (물체를 손바닥 기준으로 옮기기) — y=좌우, x=앞뒤, z=상하
MOVE = {"j": ("y", +1), "l": ("y", -1), "i": ("x", +1), "k": ("x", -1), "u": ("z", +1), "m": ("z", -1)}
AXI = {"x": 0, "y": 1, "z": 2}
POS_STEP = 0.004

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
    elif ch in MOVE: st["cmd"] = ("move", ch)          # j/l i/k u/m = 위치 이동
    elif ch == "g": st["cmd"] = ("collect", None)      # 잡아서 수집
    elif ch == "t": st["cmd"] = ("train", None)        # 학습
    elif ch == "b": st["cmd"] = ("test", None)         # 맞혀보기
    elif ch == "n": st["cmd"] = ("hidden", None)       # 블라인드

def banner():
    sel = " / ".join(f"{EMOJI[s]}{s}" for s in SHAPES)
    print("="*62)
    print("  내가 직접 가르치기   ▶ 키는 '터미널 창'에서 (3D창은 마우스 시점만)")
    print("  Z = 가르칠 도형 바꾸기  (" + sel + ")")
    print("  회전(3축):  A/D=좌우돌리기   W/S=앞뒤굴리기   E/R=옆으로굴리기")
    print("  이동:  J/L=좌우   I/K=앞뒤   U/M=위아래   (물체 위치 옮기기)")
    print("  G=잡아서수집   T=학습   B=맞혀보기   N=블라인드   X=종료")
    print("="*62)
    print(f"  지금 도형: {EMOJI[SHAPES[0]]} {SHAPES[0]}  · 굴리고 G로 잡아 모으세요")

def run():
    import mujoco.viewer
    rng = np.random.default_rng()
    model = G.build_model(); d = mujoco.MjData(model); FQ = G.finger_q(model)
    BID  = {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY, f"OBJ_{s}") for s in SHAPES}
    OGEOM= {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,f"OBJ_{s}") for s in SHAPES}
    REF = G.measure_ref(model, d, FQ, close=G.CLOSE_DEMO)    # ★ 빈손·펼침 기준(막힌 비율용)

    def show(idx, pos):
        for s in SHAPES:
            model.body_pos[BID[s]] = pos if s == SHAPES[idx] else G.AWAY_POS
            model.geom_rgba[OGEOM[s]] = G.COLOR[s]

    cur_pos = G.jitter_pos(rng)                     # 물체 위치(학생이 J/L·I/K·U/M로 옮김)
    banner(); show(0, cur_pos); mujoco.mj_resetData(model, d)
    quat = IDENT.copy(); cur_v = -0.8
    phase = "idle"; frames = 0; buf = []; buf_mode = None
    CLOSE_F, HOLD_F, OPEN_F = G.CLOSE_STEPS, 40, 90
    pacer = Pacer(model.opt.timestep)               # ★ 렌더 속도와 무관하게 실시간 물리

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
    with mujoco.viewer.launch_passive(model, d) as viewer:   # 키는 터미널에서만(key_thread)
        frame_camera(viewer)                                 # ★ 손+물체가 한눈에
        while viewer.is_running() and st["run"]:
            cs = SHAPES[st["sel"]]
            model.body_quat[BID[cs]] = quat        # 정적 body 방향 = 학생이 돌린 자세
            model.body_pos[BID[cs]]  = cur_pos     # 정적 body 위치 = 학생이 옮긴 위치

            cmd = st["cmd"]; st["cmd"] = None
            if cmd and phase == "idle":
                kind, val = cmd
                if kind == "cycle":                       # 가르칠 도형 순환
                    st["sel"] = (st["sel"] + 1) % len(SHAPES); D["hidden"] = False
                    cur_pos = G.jitter_pos(rng); show(st["sel"], cur_pos)
                    quat = IDENT.copy(); buf = []; buf_mode = None
                    print(f"  지금 도형: {EMOJI[SHAPES[st['sel']]]} {SHAPES[st['sel']]}")
                elif kind == "hidden":
                    st["sel"] = int(rng.integers(len(SHAPES))); D["hidden"] = True
                    cur_pos = G.jitter_pos(rng); show(st["sel"], cur_pos)
                    quat = G.rand_quat(rng); buf = []; buf_mode = None
                    print("  🙈 숨김 도형 — 굴리며 B 3번 = 맞혀보기")
                elif kind == "rot":
                    ax, sgn = ROT[val]; quat = G.qmul(G.axis_quat(AXIS[ax], sgn*np.deg2rad(20)), quat)
                    quat = quat/np.linalg.norm(quat); print(f"  ↻ 굴림 ({val.upper()})")
                elif kind == "move":
                    ax, sgn = MOVE[val]; cur_pos = cur_pos.copy(); cur_pos[AXI[ax]] += sgn * POS_STEP
                    print(f"  ⇄ 이동 ({val.upper()})  pos={np.round(cur_pos, 3)}")
                elif kind == "train":
                    train()
                elif kind in ("collect", "test"):
                    if buf_mode is None: buf = []; buf_mode = kind
                    mujoco.mj_resetData(model, d); cur_v = -0.8   # 학습(4a)과 같은 초기상태에서 잡기
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
                            print("  → 위치(J/L·I/K·U/M)·자세(A/D·W/S·E/R)를 바꿔 다시 G")
                mujoco.mj_step(model, d)
            viewer.sync(); time.sleep(0.001)
    st["run"] = False

if __name__ == "__main__":
    try:
        import mujoco  # noqa
        run()
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n(MuJoCo 뷰어 실행 필요: 맥 mjpython / 윈도우 python  day2_4b_shape_teach.py )")
    print("\n종료!")
