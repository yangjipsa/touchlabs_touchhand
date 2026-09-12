#!/usr/bin/env python3
# ============================================================
#  실물 잡기 진단 — 도형별로 손가락이 실제 어떻게 읽히나 확인   [보정 도구]
#  실물 서보만 사용(MuJoCo 없음). 실물이 도형을 잡을 때의 '손가락 깊이'를
#  눈으로 확인해 sim2real 갭·개체차를 진단하는 도구.
#
#  ▷ 강의자료 연결(MuJoCo_자료.md):
#     · 8절 = 잡기 = 손가락이 물체에 막혀 멈춤. 그 '막힌 깊이'가 판정 신호.
#     · 이 값이 시뮬 학습(STEP4)과 다르면 sim2real 보정이 필요 → 보정 스크립트로 재학습.
#     · CLOSE_TARGET·OPEN_BEND·SETTLE 등은 grip_config(STEP3에서 세팅)에서 공유.
#
#  준비 : pip install feetech-servo-sdk numpy   ·   Waveshare USB 직결
#  실행 : python3 day2_보정_check_real.py     (3D 뷰어 불필요)
#  키   : c = 한 번 잡아 값 보기   o = 펴기   q = 종료  (엔터 없이)
#  → 구/타원/정육면체를 각각 2~3번 잡아 출력 숫자를 붙여주세요.
# ============================================================
import sys, time
import numpy as np
import grip_config as GC
_cfg = GC.load()
OPEN_BEND, CLOSE_TARGET, SETTLE = _cfg["OPEN_BEND"], _cfg["CLOSE_TARGET"], _cfg["SETTLE"]

try:
    import termios, tty
    def _getch():
        fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
        try: tty.setcbreak(fd); return sys.stdin.read(1)
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
except Exception:
    def _getch(): return (sys.stdin.readline().strip()[:1] or " ")

try:
    from hand_driver import HandDriver
    hand = HandDriver(); hand.speed = 200
except Exception as e:
    print("❌ 실물 손 필요:", e); sys.exit(1)

NAMES = ["엄지", "검지", "중지약지", "새끼"]

def read_open():
    hand.set_free([OPEN_BEND]*4, [0]*4); time.sleep(1.0)
    rd = hand.read()
    return [rd[i][0] if rd[i][0] is not None else None for i in range(4)]

def grasp():
    hand.set_free([CLOSE_TARGET]*4, [0]*4); time.sleep(SETTLE)   # 닫기 명령 → 다 움직일 때까지 대기
    rd = hand.read()                                             # 서보 피드백 = 실제 멈춘 깊이(→ 8절)
    depth = [rd[i][0] if rd[i][0] is not None else None for i in range(4)]
    hand.set_free([OPEN_BEND]*4, [0]*4)                          # 바로 펴서 다음 잡기 준비
    return depth

print("="*60)
print("  실물 잡기 진단   c=잡기  o=펴기  q=종료   (CLOSE_TARGET=%d)" % CLOSE_TARGET)
print("  ※ 구/타원/정육면체 각 2~3번 잡고, 아래 [엄지 검지 중지약지 새끼] 줄을 붙여주세요")
print("="*60)
base = read_open()
print("  펴짐(기준) [엄지 검지 중지약지 새끼] =", [None if v is None else int(v) for v in base])

while True:
    s = _getch().lower()
    if s in ("q", "\x03"): break
    elif s == "o":
        hand.set_free([OPEN_BEND]*4, [0]*4); print("  → 펴기")
    elif s == "c":
        d = grasp()
        line = [None if v is None else int(v) for v in d]
        # 기준 대비 얼마나 더 닫혔나(=막힘 정도)
        delta = [None if (d[i] is None or base[i] is None) else int(d[i]-base[i]) for i in range(4)]
        print(f"  ✊ 깊이[엄지 검지 중지약지 새끼] = {line}   (기준대비 {delta})")
        # None(읽기실패) 경고
        if any(v is None for v in d):
            print("     ⚠️ 일부 손가락 읽기 실패(None) — 통신/전원 확인")
hand.close(); print("\n종료!")
