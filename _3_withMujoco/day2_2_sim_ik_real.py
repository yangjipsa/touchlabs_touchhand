#!/usr/bin/env python3
# ============================================================
#  Amazing Hand - 빨간 점(IK 목표) 드래그 → 실물
#  3D 창의 빨간 구슬(손끝 목표)을 마우스로 옮기면,
#  역기구학(IK)이 손가락을 그쪽으로 움직이고, 진짜 손이 따라옵니다.
#
#  ▶ 조작 (3D 창):
#     · 빨간 구슬 더블클릭 → 선택
#     · Ctrl + 마우스 '오른쪽 버튼' 드래그 → 구슬을 옮김 → 손가락이 따라감
#       (맥: Ctrl+왼쪽은 회전. 이동은 반드시 '오른쪽 버튼')
#     · 그냥(왼쪽) 드래그/휠 = 시점 회전/줌
#  ▶ 터미널: q = 종료
#
#  준비 : pip install mink loop-rate-limiters quadprog feetech-servo-sdk
#         Waveshare 어댑터 = USB 모드로 컴퓨터에 직결 (XIAO 불필요)
#  실행(★ 맥):  mjpython day2_2_sim_ik_real.py
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

BACKEND   = "both"      # "both"(시뮬+실물) / "sim"(시뮬만)
STREAM_HZ = 12
SWAY_DIR  = +1          # 좌우가 실물에서 반대로 움직이면 -1 로

HAND = "AH_Left"
HERE = Path(__file__).resolve().parent
MODEL = HERE / "AHSimulation" / HAND / "mjcf" / "scene.xml"
model = mujoco.MjModel.from_xml_path(str(MODEL))

# ── mink IK 세팅 ──
cfg = mink.Configuration(model)
data = cfg.data
posture = mink.PostureTask(model, cost=1e-2)
tasks = [mink.EqualityConstraintTask(model, cost=1000.0), posture]
TIPS   = ["tip1", "tip2", "tip3", "tip4"]
TARGETS = ["finger1_target", "finger2_target", "finger3_target", "finger4_target"]
for tip in TIPS:
    tasks.append(mink.FrameTask(frame_name=tip, frame_type="site",
                                position_cost=1.0, orientation_cost=0.0, lm_damping=1.0))

# 모터 관절 qpos 주소 (finger1~4, motor1/2)  → 실물 변환용
def jadr(name):
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
            bend = [(data.qpos[a] - data.qpos[b]) / 2 for (a, b) in MADR]  # 굽힘 (모터 반대)
            sway = [(data.qpos[a] + data.qpos[b]) / 2 for (a, b) in MADR]  # 좌우 (모터 같은방향)
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

with mujoco.viewer.launch_passive(model, data) as viewer:
    cfg.update_from_keyframe("zero")
    posture.set_target_from_configuration(cfg)
    for tip, tgt in zip(TIPS, TARGETS):
        mink.move_mocap_to_frame(model, data, tgt, tip, "site")
    rate = RateLimiter(frequency=200.0)
    while viewer.is_running() and state["run"]:
        if state.get("reset"):                          # 원래대로
            state["reset"] = False
            cfg.update_from_keyframe("zero")
            posture.set_target_from_configuration(cfg)
            for tip, tgt in zip(TIPS, TARGETS):
                mink.move_mocap_to_frame(model, data, tgt, tip, "site")
        for k, tgt in enumerate(TARGETS):
            tasks[2 + k].set_target(mink.SE3.from_mocap_name(model, data, tgt))
        vel = mink.solve_ik(cfg, tasks, rate.dt, "quadprog", 1e-5)
        cfg.integrate_inplace(vel, rate.dt)
        viewer.sync()
        rate.sleep()

state["run"] = False
time.sleep(0.2)
if hand is not None:
    try:
        hand.close()      # 중립으로 + 포트 닫기
    except Exception:
        pass
print("\n종료!")
