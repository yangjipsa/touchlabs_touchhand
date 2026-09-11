"""
Amazing Hand 손 흔들기(waving) — 손을 편 다음 좌우로 살랑살랑 👋
서보별 중립보정(offsets.py) 반영.
  servo_a = mid(a) - flex + sway
  servo_b = mid(b) + flex + sway
  (flex>0 = 굽힘, flex<0 = 폄, sway = 좌우)
사용: (GUI 닫고) venv 활성화 후  python hand_wave.py   (Ctrl+C 중단→중립)
"""
from scservo_sdk import *
import time
from offsets import mid, clamp

from portfinder import find_port
PORT  = find_port()
SPEED = 600          # 값 높을수록 빠름 (최대 ~1000)
OPEN  = 80           # 손 펴는 정도
SWAY  = 110          # 좌우 흔들기 진폭
TIMES = 4

FINGERS = [("검지", 1, 2), ("중지", 3, 4), ("약지", 5, 6), ("엄지쪽", 7, 8)]

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (GUI 등 닫기)"); exit()
ph.setBaudRate(1000000)

for _, a, b in FINGERS:
    sc.write1ByteTxRx(a, 40, 1)
    sc.write1ByteTxRx(b, 40, 1)

def w(i, p):
    sc.WritePos(i, clamp(i, p), 0, SPEED)   # ±90° 안전 클램프

THUMB_IDX = 3        # 엄지쪽 손가락 (FINGERS 인덱스)

def hand(flex, sway):
    for idx, (_, a, b) in enumerate(FINGERS):
        s = -sway if idx == THUMB_IDX else sway   # 엄지쪽만 반대 방향으로 흔들기
        w(a, mid(a) - flex + s)
        w(b, mid(b) + flex + s)

try:
    hand(0, 0); time.sleep(0.6)
    print("🖐️ 손 펴기")
    hand(-OPEN, 0); time.sleep(0.8)

    print("👋 흔들기")
    for _ in range(TIMES):
        hand(-OPEN, +SWAY); time.sleep(0.35)
        hand(-OPEN, -SWAY); time.sleep(0.35)
    hand(-OPEN, 0); time.sleep(0.3)

    hand(0, 0); time.sleep(0.5)
    print("✅ 완료")
except KeyboardInterrupt:
    print("\n중단 — 중립 복귀")
    hand(0, 0); time.sleep(0.5)

ph.closePort()
