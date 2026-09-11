#!/usr/bin/env python3
# ============================================================
#  Amazing Hand - 파이썬 직접 드라이버 (컴퓨터 → Waveshare → 서보)
#  XIAO 없이 컴퓨터가 서보를 직접 제어 + '실제 위치 읽기'.
#  → sim2real 백엔드: 시뮬↔실물, 리얼리티 갭 측정, 폐루프.
#
#  준비 : pip install feetech-servo-sdk
#         Waveshare 어댑터 = USB 모드로 컴퓨터에 직접 연결
#         (맥: /dev/cu.wchusbserial... , 윈도우: COMx)
#  사용 : from hand_driver import HandDriver
#         hand = HandDriver()
#         hand.set_free([300,-80,-80,300],[0,0,0,0])  # [엄지,검지,중지약지,새끼]
#         print(hand.read())        # 실제 각 손가락 (bend, sway)
# ============================================================
import time

try:
    from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS
    from serial.tools import list_ports
except ImportError as e:
    raise ImportError("필요: pip install feetech-servo-sdk  (오류: %s)" % e)

# ── SCS 레지스터 ──
ADDR_TORQUE     = 40
ADDR_GOAL_POS   = 42     # WritePos (big-endian)
ADDR_PRES_POS   = 56     # ReadPos
ADDR_MAX_TORQUE = 16     # Max Torque (EEPROM, 0~1000) — 쥐는 힘 상한
ADDR_LOCK       = 48     # 0=EEPROM 잠금해제, 1=잠금

# ★ 손가락 보호: 서보 최대 토크 상한(%). 낮출수록 약하게 쥠(부품 파손 방지).
#   None 이면 제한 안 함. EEPROM이라 전원 꺼도 유지(값 같으면 재기록 안 함).
MAX_TORQUE_PCT = 55

# ── 손 모델 (실물, offsets.py / 펌웨어와 동일) ──
MID = 511
OFFSET = {1: 0, 2: +14, 3: -16, 4: -28, 5: +10, 6: -20, 7: +8, 8: +7}
LIMIT = 307
SPEED = 600

# 손가락 순서 0엄지 1검지 2중지약지 3새끼  →  (a,b) 서보 ID  (실측 매핑)
SA = [7, 1, 3, 5]
SB = [8, 2, 4, 6]
SDIR = +1        # 왼손. 오른손이면 -1
BDIR = +1

FLEX, EXT, SWAY, SPREAD = 300, 80, 110, 65
THUMB_FLEX, THUMB_TUCK = 180, 120


def _mid(sid): return max(0, min(1023, MID + OFFSET.get(sid, 0)))
def _clamp(sid, p):
    m = _mid(sid)
    return max(0, min(1023, max(m - LIMIT, min(m + LIMIT, int(p)))))

def _find_port():
    for p in list_ports.comports():
        d = p.device
        if ("wchusb" in d or "usbserial" in d or "usbmodem" in d
                or d.upper().startswith("COM")):
            return d
    return None


class HandDriver:
    def __init__(self, port=None, baud=1000000):
        if port is None:
            port = _find_port()
            if port is None:
                raise RuntimeError("서보 포트를 못 찾음 (Waveshare USB 모드 연결 확인)")
        self.ph = PortHandler(port)
        self.pk = PacketHandler(1)            # 1 = big-endian (SCS 계열)
        if not self.ph.openPort():
            raise RuntimeError(f"포트 열기 실패: {port}")
        self.ph.setBaudRate(baud)
        self.port = port
        self.speed = SPEED               # 이동 속도 (작을수록 느리고 부드러움)
        for sid in range(1, 9):
            self.pk.write1ByteTxRx(self.ph, sid, ADDR_TORQUE, 1)   # 토크 ON
        if MAX_TORQUE_PCT is not None:
            self.set_torque_limit(MAX_TORQUE_PCT)                  # ★ 쥐는 힘 상한(손 보호)
        self.neutral()
        print("✅ 손 드라이버 연결:", port)

    def set_torque_limit(self, pct=MAX_TORQUE_PCT):
        """서보 최대 토크(쥐는 힘) 상한을 pct(%)로. EEPROM이라 값 같으면 재기록 안 함(수명 보호)."""
        val = int(max(0, min(100, pct)) / 100 * 1000)             # 0~1000
        changed = 0
        for sid in range(1, 9):
            cur, comm, _ = self.pk.read2ByteTxRx(self.ph, sid, ADDR_MAX_TORQUE)
            if comm == COMM_SUCCESS and cur == val:
                continue                                          # 이미 같은 값 → 건너뜀
            self.pk.write1ByteTxRx(self.ph, sid, ADDR_LOCK, 0)    # EEPROM 잠금해제
            self.pk.write2ByteTxRx(self.ph, sid, ADDR_MAX_TORQUE, val)
            self.pk.write1ByteTxRx(self.ph, sid, ADDR_LOCK, 1)    # 재잠금
            changed += 1
        print(f"🛡  서보 최대 토크 {pct}% 제한 (손가락 보호){'' if changed else ' — 이미 설정됨'}")

    # ── 저수준 ──
    def _write_pos(self, sid, pos, speed=None):
        if speed is None: speed = self.speed
        pos = _clamp(sid, pos); speed = int(speed)
        data = [(pos >> 8) & 0xFF, pos & 0xFF, 0, 0, (speed >> 8) & 0xFF, speed & 0xFF]
        self.pk.writeTxRx(self.ph, sid, ADDR_GOAL_POS, len(data), data)

    def _read_pos(self, sid):
        val, comm, err = self.pk.read2ByteTxRx(self.ph, sid, ADDR_PRES_POS)
        return val if comm == COMM_SUCCESS else None

    # ── 손가락 ──
    def finger(self, idx, flex, sway=0):
        flex *= BDIR; sway *= SDIR
        self._write_pos(SA[idx], _mid(SA[idx]) - flex + sway)
        self._write_pos(SB[idx], _mid(SB[idx]) + flex + sway)

    def set_free(self, bends, sways=(0, 0, 0, 0)):
        """[엄지,검지,중지약지,새끼] 굽힘/좌우 직접 지정 (시뮬 스트리밍용)"""
        for i in range(4):
            self.finger(i, bends[i], sways[i])

    def neutral(self):
        for i in range(4):
            self.finger(i, 0, 0)

    # ── ★ 실제 위치 읽기 (sim2real 핵심) ──
    def read(self):
        """실제 각 손가락의 (bend, sway) 계산 → 명령값과 비교하면 리얼리티 갭"""
        out = []
        for i in range(4):
            a, b = SA[i], SB[i]
            pa, pb = self._read_pos(a), self._read_pos(b)
            if pa is None or pb is None:
                out.append((None, None)); continue
            da = pa - _mid(a)          # = -flex*BDIR + sway*SDIR
            db = pb - _mid(b)          # = +flex*BDIR + sway*SDIR
            bend = (db - da) / 2 / BDIR
            sway = (db + da) / 2 / SDIR
            out.append((round(bend, 1), round(sway, 1)))
        return out   # [(bend,sway) 엄지, 검지, 중지약지, 새끼]

    # ── 포즈 (실물 펌웨어와 동일) ──
    def pose(self, n):
        E, F = -EXT, FLEX
        if n == 5:   # 주먹
            self.finger(0, THUMB_FLEX, THUMB_TUCK); self.finger(1, F); self.finger(2, F); self.finger(3, F); return
        if n == 6:   # 가위
            self.finger(0, F); self.finger(1, E); self.finger(2, E); self.finger(3, F); return
        if n == 7:   # 보
            for i in range(4): self.finger(i, E); return
        if n == 8:   # 브이
            v = SPREAD // 2
            self.finger(0, F); self.finger(1, E, -v); self.finger(2, E, +v); self.finger(3, F); return
        if n == 9:   # 가리키기
            self.finger(0, F); self.finger(1, E); self.finger(2, F); self.finger(3, F); return
        if n in (1, 2, 3, 4):        # 숫자: 검지→중지약지→새끼→엄지
            up = set([1, 2, 3, 0][:n])
            for i in range(4): self.finger(i, E if i in up else F)
            return
        self.neutral()               # 0 중립

    def close(self):
        self.neutral(); time.sleep(0.3); self.ph.closePort()


# ── 단독 실행 데모 ──
if __name__ == "__main__":
    hand = HandDriver()
    for name, n in [("주먹", 5), ("펴기", 7), ("브이", 8)]:
        hand.pose(n); time.sleep(1.0)
        print(f"{name}: 실제 (bend,sway) =", hand.read())
    hand.close()
    print("완료.")
