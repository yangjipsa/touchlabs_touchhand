#!/usr/bin/env python3
# ============================================================
#  TouchLabs Amazing Hand - 로봇손 세팅 도구 (Waveshare USB 직결)
#  서보 ID 설정 + 중립 정렬을 한 곳에서.  손 10대 세팅용.
#
#  준비 : Waveshare 어댑터 = USB 모드(점퍼 2개 B), 컴퓨터에 직결
#         venv 활성화 후 실행
#  실행 : python hand_setup.py
#
#  손가락↔서보 (실측): 검지=1,2 / 중지약지=3,4 / 새끼=5,6 / 엄지=7,8
# ============================================================
from scservo_sdk import *
from serial.tools import list_ports
import sys, time

BAUD = 1000000
REG_TORQUE, REG_ID, REG_LOCK = 40, 5, 48
MID = 511
NAMES = {1:"검지-A", 2:"검지-B", 3:"중지약지-A", 4:"중지약지-B",
         5:"새끼-A", 6:"새끼-B", 7:"엄지-A", 8:"엄지-B"}
ORDER = [1, 2, 3, 4, 5, 6, 7, 8]          # ID 순서대로 설정할 때

# ── 포트 자동 탐지 (맥 wchusbserial / 윈도우 COM) ──
def find_port():
    cands = []
    for p in list_ports.comports():
        d = p.device
        if ("wchusb" in d or "usbserial" in d or "usbmodem" in d
                or d.upper().startswith("COM")):
            cands.append(d)
    return cands

def open_bus():
    ports = find_port()
    if not ports:
        print("❌ Waveshare 포트를 못 찾음. USB 연결 + VCP 드라이버 확인.")
        manual = input("   포트를 직접 입력(엔터=취소): ").strip()
        if not manual: return None, None
        ports = [manual]
    port = ports[0]
    if len(ports) > 1:
        print("포트 여러 개:")
        for i, p in enumerate(ports): print(f"   {i}) {p}")
        sel = input(f"번호 선택(엔터={ports[0]}): ").strip()
        if sel.isdigit() and int(sel) < len(ports): port = ports[int(sel)]
    ph = PortHandler(port)
    if not ph.openPort():
        print(f"❌ 포트 열기 실패: {port}  (GUI/다른 프로그램 닫기)")
        return None, None
    ph.setBaudRate(BAUD)
    print(f"✅ 연결: {port}  ({BAUD} baud)")
    return ph, scscl(ph)

# ── 스캔 ──
def scan(sc, lo=0, hi=30):
    found = []
    for i in range(lo, hi+1):
        if sc.ping(i)[1] == COMM_SUCCESS:
            found.append(i)
    return found

def find_single(sc):
    """연결된 서보가 딱 1개인지 확인하고 그 ID 반환 (없거나 여러개면 None)."""
    f = scan(sc)
    if len(f) == 1: return f[0]
    if len(f) == 0: print("   ❌ 서보 없음 — 전원/케이블 확인"); return None
    print(f"   ⚠️  서보 {len(f)}개 감지 {f} — ID설정은 '1개만' 연결하세요"); return None

# ── ID 변경 (EEPROM 잠금해제 → ID쓰기 → 재잠금) ──
def set_id(sc, cur, new):
    if cur == new:
        print(f"   이미 ID {new} 입니다."); return True
    sc.write1ByteTxRx(cur, REG_LOCK, 0);    time.sleep(0.03)
    sc.write1ByteTxRx(cur, REG_ID, new);    time.sleep(0.03)
    sc.write1ByteTxRx(new, REG_LOCK, 1);    time.sleep(0.05)
    ok = sc.ping(new)[1] == COMM_SUCCESS
    print(f"   {'✅' if ok else '⚠️'} ID {cur} → {new} {'완료(전원꺼도 유지)' if ok else '검증실패-전원재인가 후 재확인'}")
    return ok

# ── 중립 이동 ──
def go_mid(sc, ids, pos=MID, speed=150):
    for i in ids:
        sc.write1ByteTxRx(i, REG_TORQUE, 1)
        sc.WritePos(i, pos, 0, speed)

def torque_off(sc, ids):
    for i in ids: sc.write1ByteTxRx(i, REG_TORQUE, 0)

# ── 메뉴 동작 ──
def m_scan(sc):
    f = scan(sc)
    if not f: print("   서보 없음"); return
    print(f"   연결된 서보 {len(f)}개:")
    for i in f:
        pos = sc.ReadPos(i)[0]
        print(f"     ID {i:2d}  {NAMES.get(i,'?'):8s}  위치 {pos}")

def m_set_one(sc):
    print("\n[ID 하나 설정]  ★ 서보를 '1개만' 연결하세요")
    input("   준비되면 Enter...")
    cur = find_single(sc)
    if cur is None: return
    print(f"   현재 ID = {cur}")
    s = input("   새 ID (1~8, 엔터=취소): ").strip()
    if s.isdigit(): set_id(sc, cur, int(s))

def m_set_sequence(sc):
    print("\n[ID 순서대로 설정 1→8]  하나씩 꽂으며 자동 할당")
    print("  각 단계에서 '그 서보 하나만' 연결하고 Enter (s=건너뛰기, q=중단)")
    for tgt in ORDER:
        c = input(f"\n  ▶ ID {tgt} ({NAMES[tgt]}) 로 만들 서보 연결 후 Enter > ").strip().lower()
        if c == "q": break
        if c == "s": continue
        cur = find_single(sc)
        if cur is None:
            again = input("     다시 시도? (Enter=예 / s=건너뛰기): ").strip().lower()
            if again == "s": continue
            cur = find_single(sc)
            if cur is None: continue
        set_id(sc, cur, tgt)
    print("\n  → 완료. '스캔'으로 1~8 다 있는지 확인하세요.")

def m_mid_all(sc):
    f = scan(sc)
    if not f: print("   서보 없음"); return
    go_mid(sc, f)
    print(f"   → {f} 전부 중립({MID})으로 이동. 이 자세에서 혼/손가락 정렬하세요.")

def m_mid_one(sc):
    s = input("   중립으로 보낼 ID: ").strip()
    if not s.isdigit(): return
    i = int(s); go_mid(sc, [i])
    print(f"   → ID {i} 중립 이동. (r=위치읽기 반복은 튜닝 메뉴에서)")

def m_tune(sc):
    s = input("   튜닝할 서보 ID: ").strip()
    if not s.isdigit(): return
    i = int(s); sc.write1ByteTxRx(i, REG_TORQUE, 1); pos = MID
    sc.WritePos(i, pos, 0, 100)
    print("   +N/-N=상대이동  숫자=절대  r=읽기  q=종료(offset 출력)")
    while True:
        cmd = input(f"   [ID {i}] 목표 {pos} (offset {pos-MID:+d}) > ").strip()
        if cmd == "q": break
        if cmd == "r": print("     실제:", sc.ReadPos(i)[0]); continue
        try: pos = pos + int(cmd) if cmd[:1] in "+-" else int(cmd)
        except ValueError: continue
        pos = max(0, min(1023, pos)); sc.WritePos(i, pos, 0, 100)
    print(f"   >>> ID {i}: 중립 {pos}, offset {pos-MID:+d}  (offsets.py 에 반영)")

def m_torque_off(sc):
    f = scan(sc); torque_off(sc, f)
    print(f"   → {f} 토크 해제. 손으로 움직여 확인 가능.")

def m_wiggle(sc):
    """어느 ID가 어느 손가락인지 하나씩 살짝 움직여 확인."""
    f = scan(sc)
    if not f: print("   서보 없음"); return
    go_mid(sc, f); time.sleep(0.5)
    for i in f:
        print(f"   ID {i} ({NAMES.get(i,'?')}) 움직임...")
        sc.WritePos(i, MID+120, 0, 200); time.sleep(0.6)
        sc.WritePos(i, MID, 0, 200); time.sleep(0.5)
    print("   → 확인 완료.")

MENU = """
──────────── Amazing Hand 세팅 ────────────
  1) 스캔 (연결된 서보 ID/위치)
  2) ID 하나 설정  (서보 1개 연결 → 지정 ID)
  3) ID 순서대로 1→8 설정  (하나씩 꽂으며)
  4) 전체 중립(511)으로  (정렬용)
  5) 특정 ID 중립으로
  6) 중립 미세튜닝 (offset 찾기)
  7) 토크 해제 (전체)
  8) 손가락 확인 (하나씩 까딱)
  0) 종료
────────────────────────────────────────────"""

def main():
    ph, sc = open_bus()
    if sc is None: return
    actions = {"1":m_scan,"2":m_set_one,"3":m_set_sequence,"4":m_mid_all,
               "5":m_mid_one,"6":m_tune,"7":m_torque_off,"8":m_wiggle}
    try:
        while True:
            print(MENU)
            c = input("선택 > ").strip()
            if c == "0": break
            fn = actions.get(c)
            if fn: fn(sc)
            else: print("   ? 메뉴 번호를 고르세요")
    except KeyboardInterrupt:
        print("\n중단.")
    finally:
        ph.closePort(); print("종료.")

if __name__ == "__main__":
    main()
