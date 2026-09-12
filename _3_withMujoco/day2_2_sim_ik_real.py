#!/usr/bin/env python3
# ============================================================
#  Amazing Hand - 빨간 점(IK 목표) 드래그 → 실물   [STEP 2]
#  3D 창의 빨간 구슬(손끝 목표)을 마우스로 옮기면,
#  역기구학(IK)이 손가락을 그쪽으로 움직이고, 진짜 손이 따라옵니다.
#
#  ▷ 강의자료 연결(MuJoCo_자료.md):
#     · 12절 STEP2 = "역기구학(IK)으로 손끝 목표 추종" (이 파일, mink 라이브러리)
#     · IK(역기구학) = 손끝 목표 좌표 → 필요한 관절각을 역산 (→ 14절 용어)
#     · 빨간 구슬 = mocap body: 물리 무시, 좌표로만 조종하는 IK 목표점 (→ 4·9절)
#     · 5절 = qpos(관절각)를 읽어 실물 굽힘/좌우로 변환 · 11절 = 뷰어 조작
#  ▷ 흐름: 마우스로 mocap(목표구슬) 이동 → mink 가 관절각(qpos) 계산 →
#          그 qpos 를 읽어 실물 서보로 스트리밍.
#
#  ▶ 조작 (3D 창):
#     · 빨간 구슬 더블클릭 → 선택
#     · Ctrl + 마우스 '오른쪽 버튼' 드래그 → 구슬을 옮김 → 손가락이 따라감
#       (맥: Ctrl+왼쪽은 회전. 이동은 반드시 '오른쪽 버튼')  → 11.1절 마우스 조작
#     · 그냥(왼쪽) 드래그/휠 = 시점 회전/줌
#  ▶ 터미널: r = 원래대로(리셋)   q = 종료
#
#  준비 : pip install mink loop-rate-limiters daqp feetech-servo-sdk
#         (quadprog 은 C 컴파일러 필요 → 윈도우에서 설치 실패. daqp 로 대체)
#         Waveshare 어댑터 = USB 모드로 컴퓨터에 직결 (XIAO 불필요)
#  실행(★ 맥):  mjpython day2_2_sim_ik_real.py   (윈도우/리눅스: python day2_2_sim_ik_real.py)
# ============================================================
import time
import glob
import threading
from pathlib import Path
import numpy as np
import mujoco
import mujoco.viewer
import mink
from loop_rate_limiters import RateLimiter

# QP 솔버 자동 선택: 설치된 것 중 하나를 씀
#  quadprog 은 C 컴파일러가 없는 PC(대부분의 윈도우)에서 설치가 안 됨.
#  daqp / osqp 는 미리 빌드된 wheel 이 제공돼 컴파일 없이 설치됨 → 우선 사용.
import qpsolvers
for _s in ("daqp", "osqp", "quadprog", "proxqp", "scs"):
    if _s in qpsolvers.available_solvers:
        QP_SOLVER = _s
        break
else:
    raise SystemExit(
        "QP 솔버가 하나도 없습니다. Thonny 패키지 관리에서 'daqp' 를 설치하세요."
    )
print(f"⚙  IK QP 솔버: {QP_SOLVER}")

BACKEND   = "both"      # "both"(시뮬+실물) / "sim"(시뮬만)
STREAM_HZ = 12
SWAY_DIR  = +1          # 좌우가 실물에서 반대로 움직이면 -1 로

HAND = "AH_Left"
HERE = Path(__file__).resolve().parent
MODEL = HERE / "AHSimulation" / HAND / "mjcf" / "scene.xml"
model = mujoco.MjModel.from_xml_path(str(MODEL))   # 설계도(mjModel) 로드 → 3절

# ── mink IK 세팅 ── (IK = 손끝 목표 → 관절각 역산)
cfg = mink.Configuration(model)
data = cfg.data                                    # mink 가 관리하는 상태(mjData) → 3·5절
posture = mink.PostureTask(model, cost=1e-2)       # 기본자세 유지 태스크(자연스러운 손 모양 유도)
# EqualityConstraintTask: 손가락당 두 모터의 차동 커플링(cost 1000 = 거의 강제) → 우리 손 8모터 구조
tasks = [mink.EqualityConstraintTask(model, cost=1000.0), posture]
TIPS   = ["tip1", "tip2", "tip3", "tip4"]                                          # 손끝 site 4개 → 4·9절
TARGETS = ["finger1_target", "finger2_target", "finger3_target", "finger4_target"] # 빨간 구슬 mocap 4개
for tip in TIPS:                                    # 각 손끝 site 를 자기 목표구슬 쪽으로 끌어당기는 태스크
    tasks.append(mink.FrameTask(frame_name=tip, frame_type="site",
                                position_cost=1.0, orientation_cost=0.0, lm_damping=1.0))

# 모터 관절 qpos 주소 (finger1~4, motor1/2)  → 실물 변환용 (→ 5절 qpos)
def jadr(name):                                    # 관절 이름 → qpos 배열에서의 위치(주소)
    return model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]
MADR = [(jadr(f"finger{f+1}_motor1"), jadr(f"finger{f+1}_motor2")) for f in range(4)]
# 시뮬 finger1~4 = [검지, 중지약지, 새끼, 엄지]  (실측 매핑)

def flex_to_bend(v):                 # 시뮬 라디안 → 실물 bend(-80~300)
    return max(-80, min(300, int(v * 250)))
def sway_to_real(v):                 # 시뮬 라디안 → 실물 좌우(-110~110)
    return max(-110, min(110, int(v * 250 * SWAY_DIR)))

# ── 실물 (Waveshare 직결, hand_driver) ──
hand = None
def open_real():
    global hand
    if BACKEND == "sim":
        return
    try:
        from hand_driver import HandDriver
        hand = HandDriver()          # Waveshare USB 자동 탐지 + 토크ON + 중립
    except Exception as e:
        print("⚠️  실물 연결 실패 → 시뮬만:", e); hand = None

state = {"run": True}
def stream_loop():
    period = 1.0 / STREAM_HZ
    while state["run"]:
        if hand is not None:
            # IK 결과 관절각(qpos)을 읽어 실물 굽힘/좌우로 변환 (→ 5·9절: 두 모터의 차동)
            bend = [(data.qpos[a] - data.qpos[b]) / 2 for (a, b) in MADR]  # 굽힘 (모터 반대 = 차)
            sway = [(data.qpos[a] + data.qpos[b]) / 2 for (a, b) in MADR]  # 좌우 (모터 같은방향 = 합)
            order = [3, 0, 1, 2]        # 실물 순서 [엄지,검지,중지약지,새끼] = finger[4,1,2,3]
            bends = [flex_to_bend(bend[i]) for i in order]
            sways = [sway_to_real(sway[i]) for i in order]
            try:
                hand.set_free(bends, sways)     # [엄지,검지,중지약지,새끼] 직접 지정
            except Exception:
                pass
        time.sleep(period)

def reader():
    print("=" * 52)
    print("  빨간 점(손끝 목표)을 드래그하면 손가락이 따라가고 실물도 따라옵니다")
    print("  · 빨간 구슬 더블클릭 → Ctrl + 마우스 '오른쪽 버튼' 드래그 로 이동")
    print("  · r = 원래대로(손 펴고 점 제자리)   · q = 종료")
    print("=" * 52)
    while state["run"]:
        try:
            s = input("> ").strip().lower()
        except EOFError:
            break
        if s in ("q", "quit"):
            state["run"] = False; break
        elif s == "r":
            state["reset"] = True
            print("  → 원래대로 리셋")

open_real()
threading.Thread(target=reader, daemon=True).start()
if BACKEND != "sim":
    threading.Thread(target=stream_loop, daemon=True).start()

with mujoco.viewer.launch_passive(model, data) as viewer:   # 대화형 3D 창(마우스로 구슬 드래그) → 11절
    cfg.update_from_keyframe("zero")                # 초기 자세 = scene 의 'zero' 키프레임
    posture.set_target_from_configuration(cfg)      # 현재 자세를 기본자세 목표로 설정
    for tip, tgt in zip(TIPS, TARGETS):
        mink.move_mocap_to_frame(model, data, tgt, tip, "site")  # 목표구슬을 각 손끝 위치로 붙여둠(시작점)
    rate = RateLimiter(frequency=200.0)             # IK 를 초당 200회로 일정하게 돌림
    while viewer.is_running() and state["run"]:
        if state.get("reset"):                          # 원래대로(터미널 r): 초기 자세·구슬 재배치
            state["reset"] = False
            cfg.update_from_keyframe("zero")
            posture.set_target_from_configuration(cfg)
            for tip, tgt in zip(TIPS, TARGETS):
                mink.move_mocap_to_frame(model, data, tgt, tip, "site")
        for k, tgt in enumerate(TARGETS):
            # 마우스로 옮긴 목표구슬(mocap)의 현재 위치를 IK 태스크 목표로 갱신 (→ 5절 mocap_pos)
            tasks[2 + k].set_target(mink.SE3.from_mocap_name(model, data, tgt))
        vel = mink.solve_ik(cfg, tasks, rate.dt, QP_SOLVER, 1e-5)  # 목표에 다가갈 관절 속도 계산(IK 풀기)
        cfg.integrate_inplace(vel, rate.dt)         # 그 속도로 qpos 를 한 스텝 적분 → 손이 목표로 이동
        viewer.sync()                               # 결과를 3D 창에 그림
        rate.sleep()

state["run"] = False
time.sleep(0.2)
if hand is not None:
    try:
        hand.close()      # 중립으로 + 포트 닫기
    except Exception:
        pass
print("\n종료!")
