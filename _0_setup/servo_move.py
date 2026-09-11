"""
SCS0009 이동 테스트 — 서보를 안전 범위(450~570)로 천천히 움직여봄
사용: (Servo Tool GUI 닫고) venv 활성화 후  python servo_move.py
"""
from scservo_sdk import *
import time

from portfinder import find_port
PORT  = find_port()
ID    = 1
SPEED = 200          # 작을수록 천천히 (0=최고속)

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트를 못 엽니다 — GUI 등 다른 프로그램 닫았는지 확인")
    exit()
ph.setBaudRate(1000000)

def show():
    pos, res, err = sc.ReadPos(ID)
    print(f"   현재 위치 = {pos}")

# 토크 ON (레지스터 40)
sc.write1ByteTxRx(ID, 40, 1)
print("토크 ON, 현재 위치 확인:")
show()

# 안전 범위에서 천천히 왕복 (SCS0009 = 0~1023, 중립 512)
for target in [450, 511, 570, 511]:
    print(f"→ {target} 로 이동")
    sc.WritePos(ID, target, 0, SPEED)   # (id, 위치, time=0, speed)
    time.sleep(1.0)
    show()

ph.closePort()
print("\n✅ 완료! 서보가 움직였으면 제어 성공.")
