"""
Amazing Hand 손가락 테스트 + 주먹/펴기 데모 (서보별 중립보정 반영)
+amp = 굽힘(flex/curl),  -amp = 폄(extend)
중립은 offsets.py 의 mid(i) 사용.
사용: (GUI 닫고) venv 활성화 후  python finger_test.py   (Ctrl+C 중단→중립복귀)
"""
from scservo_sdk import *
import time
from offsets import mid, clamp

from portfinder import find_port
PORT  = find_port()
SPEED = 600     # 값 높을수록 빠름 (최대 ~1000)
FLEX  = 300     # 굽힘(주먹) 진폭
EXT   = 70      # 폄 진폭

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

def set_finger(a, b, amp):        # +amp = 굽힘, 서보별 중립 기준
    w(a, mid(a) - amp)
    w(b, mid(b) + amp)

def set_all(amp):
    for _, a, b in FINGERS:
        set_finger(a, b, amp)

try:
    set_all(0); time.sleep(1.0)

    print("[1] 손가락 하나씩 까딱")
    for name, a, b in FINGERS:
        print(f"   → {name}")
        set_finger(a, b, FLEX);  time.sleep(0.6)
        set_finger(a, b, -EXT);  time.sleep(0.6)
        set_finger(a, b, 0);     time.sleep(0.4)

    print("[2] 웨이브")
    for _, a, b in FINGERS:
        set_finger(a, b, FLEX); time.sleep(0.25)
    time.sleep(0.4)
    for _, a, b in FINGERS:
        set_finger(a, b, 0); time.sleep(0.25)

    print("[3] 주먹 쥐기 / 펴기")
    for _ in range(2):
        set_all(FLEX);  time.sleep(0.9)
        set_all(-EXT);  time.sleep(0.9)

    print("\n✅ 데모 완료 — 중립 복귀")
    set_all(0); time.sleep(0.6)
except KeyboardInterrupt:
    print("\n중단 — 중립 복귀")
    set_all(0); time.sleep(0.6)

ph.closePort()
