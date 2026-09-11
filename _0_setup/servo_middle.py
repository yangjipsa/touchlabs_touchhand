"""
SCS0009 영점 정렬 도우미 — 서보를 중립(512)으로 보내고 유지.
이 상태에서 서보 혼/손가락을 중립 자세로 정렬하세요.
사용: (GUI 닫고) venv 활성화 후  python servo_middle.py
Ctrl+C 로 종료.
"""
from scservo_sdk import *
import time

PORT = "/dev/cu.wchusbserial5B790178891"
ID   = 1
MID  = 511          # SCS0009 중립

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (다른 프로그램 닫기)"); exit()
ph.setBaudRate(1000000)

sc.write1ByteTxRx(ID, 40, 1)        # 토크 ON
sc.WritePos(ID, MID, 0, 150)        # 중립으로 천천히
print(f"→ ID {ID} 를 중립({MID})으로 이동. 이 위치에서 혼/손가락 정렬하세요.")
print("   (Ctrl+C 로 종료)")

try:
    while True:
        pos, _, _ = sc.ReadPos(ID)
        print(f"   현재 위치 = {pos}   ", end="\r")
        time.sleep(0.3)
except KeyboardInterrupt:
    print("\n종료.")
ph.closePort()
