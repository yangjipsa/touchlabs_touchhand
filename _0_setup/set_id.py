"""
SCS0009 ID 변경 — 연결된 서보 1개를 지정 ID로 변경.
사용: (GUI 닫고) venv 활성화 후
      python set_id.py <새ID>      예) python set_id.py 3
※ 반드시 서보를 1개만 연결하고 실행 (여러 개면 충돌)
"""
import sys, time
from scservo_sdk import *

from portfinder import find_port
PORT = find_port()   # 자동탐지 (실패 시 "/dev/cu.wchusbserial..." 직접 지정)
REG_ID, REG_LOCK = 5, 48

if len(sys.argv) < 2:
    print("사용법: python set_id.py <새ID>   (예: python set_id.py 1)")
    sys.exit()
NEW_ID = int(sys.argv[1])

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (GUI/다른 프로그램 닫기)"); sys.exit()
ph.setBaudRate(1000000)

# 연결된 서보 1개 찾기 (ID 0~30 스캔)
cur = None
for i in range(0, 31):
    if sc.ping(i)[1] == COMM_SUCCESS:
        cur = i; break
if cur is None:
    print("❌ 서보를 못 찾음 — 1개만 연결했는지, 전원/케이블 확인")
    ph.closePort(); sys.exit()
print(f"현재 ID = {cur} 발견")

if cur == NEW_ID:
    print(f"이미 ID {NEW_ID} 입니다. 변경 불필요.")
    ph.closePort(); sys.exit()

# ID 변경 (EEPROM 잠금 해제 → ID 쓰기 → 재잠금)
sc.write1ByteTxRx(cur, REG_LOCK, 0);      time.sleep(0.02)
sc.write1ByteTxRx(cur, REG_ID, NEW_ID);   time.sleep(0.02)
sc.write1ByteTxRx(NEW_ID, REG_LOCK, 1);   time.sleep(0.05)

if sc.ping(NEW_ID)[1] == COMM_SUCCESS:
    print(f"✅ ID {cur} → {NEW_ID} 변경 완료! (전원 꺼도 유지됨)")
else:
    print("⚠️ 검증 실패 — 전원 재인가 후 python scan_servo.py 로 재확인")
ph.closePort()
