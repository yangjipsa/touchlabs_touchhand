#!/usr/bin/env python3
# ============================================================
#  Amazing Hand - 시뮬 → 실물 스트리밍 (시뮬이 주인)   [STEP 1]
#  시뮬의 '실제 관절각'을 매 순간 읽어서 실물 서보로 흘려보냅니다.
#  → 시뮬이 움직이면(명령이든 뭐든) 실물이 실시간으로 따라옵니다.
#
#  ▷ 강의자료 연결(MuJoCo_자료.md):
#     · 12절 STEP1 = "시뮬의 관절각을 읽어 실물로 스트리밍" (이 파일)
#     · 3절  = 모델(mjModel, 설계도) vs 상태(mjData, 매 스텝 변함)
#     · 5절  = 상태값 qpos(관절각)·ctrl(모터 명령)
#     · 6절  = 시뮬 루프 mj_step (한 스텝 = 힘·접촉 계산 + 적분)
#     · 11절 = 뷰어(launch_passive) 조작
#  ▷ 이 스크립트의 흐름: 키로 포즈 선택 → ctrl 설정 → mj_step 으로
#     시뮬이 움직임 → 그 결과 qpos(실제 관절각)를 읽어 실물 서보로 전송.
#
#  ※ 2일차는 처음부터 ESP 없이 갑니다.
#     컴퓨터 → Waveshare(USB 모드, 점퍼 B) → 서보  (hand_driver 직결)
#
#  준비 : pip install feetech-servo-sdk mujoco
#         Waveshare 어댑터 = USB 모드로 컴퓨터에 직접 연결 (점퍼 B)
#  실행(★ 맥):  mjpython day2_1_sim_stream_real.py
#        (윈도우/리눅스):  python day2_1_sim_stream_real.py
#  조작 : (터미널 창) 0~4 = 포즈 번호 입력 후 엔터   ·   q = 종료
#         (3D 창) 마우스로 시점만 — 11절 뷰어 조작 참고
# ============================================================
import time
import threading
from pathlib import Path
import mujoco
import mujoco.viewer

BACKEND    = "both"     # "both"(시뮬+실물) / "sim"(시뮬만)
SPEED_STEP = 0.04       # 시뮬 움직임 속도
STREAM_HZ  = 12         # 실물로 보내는 빈도(초당)

# ── 시뮬 ── (→ MuJoCo_자료 3절: 모델 vs 상태)
HAND = "AH_Left"
HERE = Path(__file__).resolve().parent
MODEL = HERE / "AHSimulation" / HAND / "mjcf" / "scene.xml"
model = mujoco.MjModel.from_xml_path(str(MODEL))   # 설계도 로드(고정, 안 변함) → 3절
data  = mujoco.MjData(model)                        # 상태 그릇(qpos·qvel·ctrl, 매 스텝 변함) → 3절

# STEP1은 포즈 스트리밍(IK 아님) → 손끝의 빨간 IK 목표구슬은 숨김
# mj_name2id: 이름("finger1_target") → 내부 번호(id) 로 찾기 (→ 10절 API)
for _i in range(1, 5):
    _bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"finger{_i}_target")
    if _bid >= 0:
        for _g in range(model.ngeom):
            if model.geom_bodyid[_g] == _bid:
                model.geom_rgba[_g] = [0, 0, 0, 0]   # rgba 알파=0 → 안 보이게(설계도값 직접 수정)

# 각 액추에이터가 구동하는 관절의 qpos 주소 (실제 각도 읽기용) → 5절 qpos
# actuator_trnid[i,0] = i번 모터가 물리는 관절 → 그 관절의 qpos 배열 위치를 미리 구해둠
JADR = [model.jnt_qposadr[model.actuator_trnid[i, 0]] for i in range(8)]

SIM = {"thumb": 3, "index": 0, "mid": 1, "pinky": 2}
E, N, F = -0.8, 0.0, 1.2
POSES = {
    "0": ("중립",     [N, N, N, N]),
    "1": ("하나",     [F, E, F, F]),
    "2": ("둘",       [F, E, E, F]),
    "3": ("셋",       [F, E, E, E]),
    "4": ("넷(폄)",   [E, E, E, E]),
}
def pose_to_ctrl(flex4):
    c = [0.0] * 8
    vals = {"thumb": flex4[0], "index": flex4[1], "mid": flex4[2], "pinky": flex4[3]}
    for name, fsim in SIM.items():
        v = vals[name]; c[fsim*2] = +v; c[fsim*2+1] = -v
    return c

# ── 실물 (Waveshare 직결, hand_driver — ESP 없음) ──
def flex_to_bend(v):                          # 시뮬 라디안 → 실물 bend(-80~300)
    return max(-80, min(300, int(v / 1.2 * 300)))

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

# ── 스트리밍: 시뮬의 실제 관절각 → 실물 (별도 스레드) ──
def stream_loop():
    period = 1.0 / STREAM_HZ
    while state["run"]:
        if hand is not None:
            # 시뮬 각 손가락의 실제 굽힘값 읽기 (두 모터각의 차 / 2) → 5절: 굽힘=(모터1−모터2)/2
            # data.qpos = 지금 이 순간의 관절 각도(물리가 갱신한 실제값). 명령(ctrl)이 아니라 결과를 읽음.
            fx = [(data.qpos[JADR[f*2]] - data.qpos[JADR[f*2+1]]) / 2 for f in range(4)]
            # anatomical [엄지,검지,중지약지,새끼] = 시뮬 finger [3,0,1,2]
            bends = [flex_to_bend(fx[3]), flex_to_bend(fx[0]),
                     flex_to_bend(fx[1]), flex_to_bend(fx[2])]
            try:
                hand.set_free(bends, [0, 0, 0, 0])   # 굽힘만 스트리밍
            except Exception:
                pass
        time.sleep(period)

# ── 시뮬 제어(키보드) ──
state = {"target": pose_to_ctrl([N, N, N, N]), "run": True}
def reader():
    print("=" * 50)
    print(f"  시뮬 → 실물 스트리밍  (BACKEND={BACKEND})")
    print("  시뮬을 움직이면 실물이 따라옵니다.")
    print("  포즈: " + " ".join(f"{k}{v[0]}" for k, v in POSES.items()))
    print("  q = 종료")
    print("=" * 50)
    while state["run"]:
        try:
            s = input("포즈 번호 > ").strip()
        except EOFError:
            break
        if s in ("q", "quit"): state["run"] = False; break
        elif s in POSES:
            name, flex4 = POSES[s]; state["target"] = pose_to_ctrl(flex4)
            print(f"  → {s} · {name}")
        else:
            print("  0~4 중에서")

open_real()
threading.Thread(target=reader, daemon=True).start()
if BACKEND != "sim":
    threading.Thread(target=stream_loop, daemon=True).start()

cur = [0.0] * 8
# 메인 시뮬 루프 (→ 6절: ctrl 설정 → mj_step → 화면 sync 반복). 맥은 mjpython 필수.
with mujoco.viewer.launch_passive(model, data) as viewer:   # 대화형 3D 창(내가 직접 스텝) → 11절
    while viewer.is_running() and state["run"]:
        tgt = state["target"]
        for k in range(8):                          # 목표로 급히 튀지 않게 SPEED_STEP 만큼씩 접근(부드럽게)
            diff = tgt[k] - cur[k]
            if abs(diff) <= SPEED_STEP: cur[k] = tgt[k]
            else:                       cur[k] += SPEED_STEP if diff > 0 else -SPEED_STEP
            data.ctrl[k] = cur[k]                   # 8개 모터 명령 세팅 → 5절 ctrl
        mujoco.mj_step(model, data)                 # 물리 한 스텝: 힘·접촉 계산 후 qpos/qvel 적분 → 6절
        viewer.sync()                               # 계산 결과를 3D 창에 그림
        time.sleep(0.004)

state["run"] = False
time.sleep(0.2)
if hand is not None:
    try:
        hand.close()      # 중립으로 + 포트 닫기
    except Exception:
        pass
print("\n종료!")
