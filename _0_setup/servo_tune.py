"""
서보 중립 미세 튜닝 — 서보를 조금씩 움직여 '진짜 중심'을 찾는다.
톱니(스플라인) 때문에 혼이 정확히 안 맞을 때, 소프트웨어로 중립값을 보정.
사용: (GUI 닫고) venv 활성화 후  python servo_tune.py
"""
from scservo_sdk import *

PORT = "/dev/cu.wchusbserial5B790178891"

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (GUI 등 닫기)"); exit()
ph.setBaudRate(1000000)

ID = int(input("튜닝할 서보 ID: ").strip())
sc.write1ByteTxRx(ID, 40, 1)          # 토크 ON
pos = 511
sc.WritePos(ID, pos, 0, 100)          # 일단 511로

print("""
명령:
  +N / -N  : 상대 이동   (예: +5, -10)  ← 미세조정은 이걸로
  숫자      : 그 위치로   (예: 520)
  r        : 실제 위치 읽기
  q        : 종료 (최종 중립값/offset 출력)
""")

while True:
    cmd = input(f"[ID {ID}] 목표 {pos} (offset {pos-511:+d}) > ").strip()
    if not cmd:
        continue
    if cmd == 'q':
        break
    if cmd == 'r':
        p, _, _ = sc.ReadPos(ID)
        print("   실제 위치 =", p)
        continue
    try:
        pos = pos + int(cmd) if cmd[0] in '+-' else int(cmd)
    except ValueError:
        print("   ? 다시 입력")
        continue
    pos = max(0, min(1023, pos))
    sc.WritePos(ID, pos, 0, 100)

print(f"\n>>> ID {ID}:  중립값 = {pos},  offset = {pos-511:+d}")
print("    → servo_all_middle.py 의 OFFSET 딕셔너리에 넣으세요.")
ph.closePort()
