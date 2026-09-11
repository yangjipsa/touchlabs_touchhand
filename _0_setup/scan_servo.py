"""
Feetech 서보 스캔 — SC(scscl) + ST(sms_sts) 프로토콜 + 여러 baud 자동 시도
사용: (GUI/Thonny 다 닫고) venv 활성화 후  python scan_servo.py
"""
from scservo_sdk import *

PORT = "/dev/cu.wchusbserial5B790178891"   # VCP 드라이버 설치 후 새 포트
BAUDS = [1000000, 500000, 250000, 115200, 57600, 128000]

# 사용 가능한 프로토콜 클래스 모으기
protocols = []
try:
    protocols.append(("SC(scscl)", scscl))
except NameError:
    pass
try:
    protocols.append(("ST(sms_sts)", sms_sts))
except NameError:
    pass
print("사용 프로토콜:", [p[0] for p in protocols])
print(f"포트: {PORT}\n")

found = False
for baud in BAUDS:
    ph = PortHandler(PORT)
    if not ph.openPort():
        print("❌ 포트를 못 엽니다 — GUI/Thonny가 포트를 잡고 있는지 확인하세요.")
        break
    ph.setBaudRate(baud)
    for pname, cls in protocols:
        pk = cls(ph)
        for sid in range(0, 21):          # ID 0~20
            res = pk.ping(sid)            # (model, comm_result, error)
            if res[1] == COMM_SUCCESS:
                print(f"✅ 발견! baud={baud}, 프로토콜={pname}, ID={sid}, model={res[0]}")
                found = True
    ph.closePort()
    print(f"   (baud {baud} 스캔 완료)")

print()
print("🎉 서보 찾음!" if found else "❌ 모든 baud/프로토콜에서 못 찾음 → 점퍼 2개 다 B인지, 케이블, 서보 확인")
