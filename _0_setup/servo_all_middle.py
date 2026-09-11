"""
연결된 모든 SCS0009 서보를 중립으로 보내고 유지 — 조립/영점용.
서보별 보정은 offsets.py 에서 관리 (거기만 수정).
사용: (GUI 닫고) venv 활성화 후  python servo_all_middle.py   (Ctrl+C 종료)
"""
from scservo_sdk import *
import time
from offsets import mid, OFFSET

from portfinder import find_port
PORT  = find_port()
SPEED = 150

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (GUI/다른 프로그램 닫기)"); exit()
ph.setBaudRate(1000000)

ids = [i for i in range(0, 31) if sc.ping(i)[1] == COMM_SUCCESS]
print("발견된 서보 ID:", ids if ids else "없음")
if not ids:
    print("❌ 서보 없음 — 전원(5V)/케이블/점퍼 확인"); ph.closePort(); exit()

for i in ids:
    sc.write1ByteTxRx(i, 40, 1)           # 토크 ON
    sc.WritePos(i, mid(i), 0, SPEED)      # 보정된 중립으로
    off = OFFSET.get(i, 0)
    print(f"   ID {i} → {mid(i)}" + (f" (offset {off:+d})" if off else ""))

print("\n→ 중립 홀드 중. 이 상태에서 조립/정렬하세요. (Ctrl+C 종료)")
try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n종료.")
ph.closePort()
