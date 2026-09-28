# ============================================================
#  scscl 호환 모듈 — SDK 버전 차이 흡수
#
#  문제: PyPI feetech-servo-sdk (0.1.0 / 0.2.0 / 1.0.0 전부)에는
#        scscl 클래스가 없다. 옛 Feetech GitHub SDK 에만 있음.
#        → pip 로 새로 설치한 PC 에서 "NameError: scscl" 발생.
#  해결: 설치된 SDK 에 scscl 이 있으면 그대로 쓰고,
#        없으면 저수준 PacketHandler 위에 같은 사용법의 scscl 을 만든다.
#
#  사용: from scscl_compat import *      (from scservo_sdk import * 대신)
# ============================================================
from scservo_sdk import *

try:
    scscl                                   # 옛 GitHub SDK — 그대로 사용
except NameError:
    # SCS 계열(SCS0009) 레지스터
    _GOAL_POSITION = 42                     # 목표위치(2) + 시간(2) + 속도(2)
    _PRESENT_POSITION = 56

    class scscl:
        """옛 scscl 과 같은 호출 방식: sc.ping(id), sc.WritePos(id, pos, time, speed) ..."""

        def __init__(self, port_handler):
            self.ph = port_handler
            self.pk = PacketHandler(1)      # 1 = SCS 계열 바이트 순서(STS 는 0)

        def ping(self, scs_id):
            return self.pk.ping(self.ph, scs_id)

        def write1ByteTxRx(self, scs_id, address, data):
            return self.pk.write1ByteTxRx(self.ph, scs_id, address, data)

        def read1ByteTxRx(self, scs_id, address):
            return self.pk.read1ByteTxRx(self.ph, scs_id, address)

        def write2ByteTxRx(self, scs_id, address, data):
            return self.pk.write2ByteTxRx(self.ph, scs_id, address, data)

        def read2ByteTxRx(self, scs_id, address):
            return self.pk.read2ByteTxRx(self.ph, scs_id, address)

        def WritePos(self, scs_id, position, time, speed):
            data = [SCS_LOBYTE(position), SCS_HIBYTE(position),
                    SCS_LOBYTE(time), SCS_HIBYTE(time),
                    SCS_LOBYTE(speed), SCS_HIBYTE(speed)]
            return self.pk.writeTxRx(self.ph, scs_id, _GOAL_POSITION, len(data), data)

        def ReadPos(self, scs_id):
            return self.pk.read2ByteTxRx(self.ph, scs_id, _PRESENT_POSITION)
