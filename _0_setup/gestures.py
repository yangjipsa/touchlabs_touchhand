"""
Amazing Hand 제스처 모음 (메뉴에서 골라 실행). 서보별 중립보정(offsets.py) 반영.
사용: (GUI 닫고) venv 활성화 후  python gestures.py
"""
from scservo_sdk import *
import time, random
from offsets import mid, clamp

from portfinder import find_port
PORT  = find_port()
SPEED = 600          # 값 높을수록 빠름 (최대 ~1000)
FLEX  = 300          # 굽힘(주먹)
EXT   = 80           # 폄(펴기)
SWAY  = 110          # 좌우
SPREAD = 65          # 브이(V) 벌리는 정도
THUMB_FLEX = 180     # 주먹 시 엄지쪽(4번) 굽힘 (다른 손가락 FLEX보다 적게)
THUMB_TUCK = 120     # 주먹 시 엄지쪽 트는 각도 ※ THUMB_FLEX+THUMB_TUCK ≤ 300 (±90°)

FINGERS = [("검지", 1, 2), ("중지", 3, 4), ("약지", 5, 6), ("엄지쪽", 7, 8)]

ph = PortHandler(PORT)
sc = scscl(ph)
if not ph.openPort():
    print("❌ 포트 못 엶 (GUI 등 닫기)"); exit()
ph.setBaudRate(1000000)
for _, a, b in FINGERS:
    sc.write1ByteTxRx(a, 40, 1)
    sc.write1ByteTxRx(b, 40, 1)

def w(i, p):
    sc.WritePos(i, clamp(i, p), 0, SPEED)   # ±90° + 물리범위 안전 클램프

def finger(idx, flex, sway=0):        # idx 0~3, +flex=굽힘
    _, a, b = FINGERS[idx]
    w(a, mid(a) - flex + sway)
    w(b, mid(b) + flex + sway)

def pose(fl, sw=(0, 0, 0, 0)):
    for i in range(4):
        finger(i, fl[i], sw[i])

def sway4(s):        # 좌우 흔들기용: 엄지쪽(4번)만 반대 방향
    return (s, s, s, -s)

# ── 제스처들 ──
def g_neutral(): pose((0, 0, 0, 0));                 print("· 중립")
def g_open():    pose((-EXT,)*4);                    print("🖐️ 펴기")

def g_fist():    # 주먹 — 엄지쪽(4번)은 각도 틀어서 안쪽으로 감기게
    finger(0, FLEX)
    finger(1, FLEX)
    finger(2, FLEX)
    finger(3, THUMB_FLEX, THUMB_TUCK)
    print("✊ 주먹")
def g_point():   pose((-EXT, FLEX, FLEX, FLEX));     print("☝️ 가리키기")
def g_count(n):  pose(tuple(-EXT if i < n else FLEX for i in range(4))); print(f"🔢 {n}")

def g_peace():   # 검지·중지 뻗기 → 잠시 후 살짝 벌림
    print("✌️ 브이")
    finger(0, -EXT); finger(1, -EXT)     # 검지·중지 뻗기 (벌림 없이)
    finger(2, FLEX); finger(3, FLEX)     # 나머지 접기
    time.sleep(1.0)                      # 잠시 (뜸)
    v = SPREAD // 2                      # 살짝 벌림 (지금의 절반)
    finger(0, -EXT, -v)
    finger(1, -EXT, +v)

def g_scissors(): # ✂️ 가위: 검지·중지 뻗기 (벌림 없음 — 브이와 구분)
    print("✂️ 가위")
    finger(0, -EXT); finger(1, -EXT)
    finger(2, FLEX); finger(3, FLEX)

def g_beckon():
    print("🫱 이리와")
    pose((-EXT,)*4); time.sleep(0.5)      # 항상 '펴기'에서 시작 (이전 상태와 무관)
    for _ in range(4):
        pose((FLEX,)*4); time.sleep(0.28)  # 접기 (이리와)
        pose((-EXT,)*4); time.sleep(0.28)  # 펴기
    g_open()

def g_drum():
    print("🥁 드럼")
    for _ in range(2):
        for i in range(4):
            finger(i, FLEX); time.sleep(0.10)
            finger(i, -EXT); time.sleep(0.05)
    g_open()

def g_wave():
    print("👋 손 흔들기")
    pose((-EXT,)*4); time.sleep(0.4)
    for _ in range(4):
        pose((-EXT,)*4, sway4(SWAY));  time.sleep(0.28)
        pose((-EXT,)*4, sway4(-SWAY)); time.sleep(0.28)
    g_open()

def g_rps():
    print("✊✌️🖐️ 가위바위보")
    g_fist();     time.sleep(0.7)
    g_scissors(); time.sleep(0.7)
    g_open();     time.sleep(0.7)

# ── 재미있는 동작들 ──
def g_ripple():          # 🌊 물결: 손가락 사이로 굽힘이 이동
    print("🌊 물결")
    pose((-EXT,)*4); time.sleep(0.3)
    for _ in range(3):
        for i in range(4):
            finger(i, FLEX)
            if i > 0: finger(i-1, -EXT)
            time.sleep(0.13)
        finger(3, -EXT); time.sleep(0.13)
    g_open()

def g_piano():           # 🎹 피아노: 랜덤 손가락 톡톡
    print("🎹 피아노")
    for _ in range(14):
        i = random.randint(0, 3)
        finger(i, FLEX // 2); time.sleep(0.07)
        finger(i, -EXT);      time.sleep(0.07)
    g_open()

def g_spider():          # 🕷️ 거미: 손가락 교대로 꿈틀
    print("🕷️ 거미")
    for _ in range(4):
        pose((FLEX//2, -EXT, FLEX//2, -EXT)); time.sleep(0.22)
        pose((-EXT, FLEX//2, -EXT, FLEX//2)); time.sleep(0.22)
    g_open()

def g_tremble():         # 😰 부들부들: 빠른 미세 떨림
    print("😰 부들부들")
    for _ in range(16):
        pose((25,)*4);  time.sleep(0.045)
        pose((-25,)*4); time.sleep(0.045)
    g_neutral()

def g_tada():            # ✨ 짜잔: 주먹→확 펴며 부채꼴
    print("✨ 짜잔")
    g_fist(); time.sleep(0.6)
    pose((-EXT,)*4, (-SWAY, -SWAY//3, SWAY//3, SWAY)); time.sleep(0.6)
    for _ in range(2):
        pose((-EXT,)*4, sway4(SWAY));  time.sleep(0.13)
        pose((-EXT,)*4, sway4(-SWAY)); time.sleep(0.13)
    g_open()

def g_no():              # 🙅 도리도리: 검지 세우고 좌우로 까딱
    print("🙅 도리도리 (싫어)")
    finger(0, -EXT); finger(1, FLEX); finger(2, FLEX); finger(3, FLEX)
    time.sleep(0.4)
    for _ in range(4):
        finger(0, -EXT, SWAY);  time.sleep(0.18)
        finger(0, -EXT, -SWAY); time.sleep(0.18)
    finger(0, -EXT, 0); time.sleep(0.2)
    g_open()

def g_heartbeat():       # 💓 두근두근: 두 번씩 톡톡 펄스
    print("💓 두근두근")
    for _ in range(3):
        pose((70,)*4); time.sleep(0.11)
        pose((0,)*4);  time.sleep(0.11)
        pose((70,)*4); time.sleep(0.11)
        pose((0,)*4);  time.sleep(0.5)
    g_neutral()

def g_alive():           # 🌀 꼬물꼬물: 랜덤 미세 움직임 (살아있는 듯)
    print("🌀 꼬물꼬물 (Ctrl+C 로 메뉴 복귀)")
    try:
        while True:
            i = random.randint(0, 3)
            finger(i, random.randint(-EXT, FLEX//2), random.randint(-40, 40))
            time.sleep(random.uniform(0.15, 0.5))
    except KeyboardInterrupt:
        pass
    g_neutral()

def g_yes():             # 🙆 끄덕끄덕: 동의(응)
    print("🙆 끄덕끄덕 (응)")
    for _ in range(2):
        pose((100,)*4);  time.sleep(0.22)
        pose((-EXT,)*4); time.sleep(0.22)
    g_neutral()

def g_gun():             # 🔫 손가락 총: 검지 겨눔 + 반동
    print("🔫 손가락 총")
    finger(0, -EXT); finger(1, -EXT//2); finger(2, FLEX); finger(3, FLEX)
    time.sleep(0.6)
    for _ in range(2):
        finger(0, 40);   time.sleep(0.10)   # 반동
        finger(0, -EXT); time.sleep(0.28)
    g_open()

def g_bloom():           # 🌸 꽃 피기: 주먹 → 천천히 펴며 부채꼴
    print("🌸 꽃 피기")
    g_fist(); time.sleep(0.7)
    for amp in range(FLEX, -EXT - 1, -30):
        pose((amp,)*4); time.sleep(0.11)
    pose((-EXT,)*4, (-SWAY, -SWAY//3, SWAY//3, SWAY)); time.sleep(0.6)
    g_open()

def g_launch():          # 🚀 카운트다운 → 발사 (엄지→검지→중지→약지 순으로 접기)
    print("🚀 카운트다운")
    fold_order = [3, 0, 1, 2]              # 엄지쪽, 검지, 중지, 약지
    folded = set()
    pose((-EXT,)*4); time.sleep(0.55)      # 다 펴고 시작
    for idx in fold_order:
        folded.add(idx)
        pose(tuple(FLEX if i in folded else -EXT for i in range(4)))
        time.sleep(0.55)
    time.sleep(0.2)
    g_tada()                               # 발사!

def g_robot():           # 🤖 로봇: 딱딱한 스텝 동작
    print("🤖 로봇")
    for _ in range(6):
        fl = tuple(random.choice([-EXT, 0, FLEX//2, FLEX]) for _ in range(4))
        pose(fl); time.sleep(0.22)
    g_neutral()

def g_dance():           # 🕺 춤: 리듬 스웨이 + 물결
    print("🕺 춤")
    for _ in range(3):
        pose((FLEX//2,)*4, sway4(SWAY));  time.sleep(0.24)
        pose((-EXT,)*4,    sway4(-SWAY)); time.sleep(0.24)
    for i in range(4):
        finger(i, FLEX); time.sleep(0.1)
    for i in range(4):
        finger(i, -EXT); time.sleep(0.1)
    g_open()

MENU = """
─────── 기본 ───────
 1 주먹✊   2 펴기🖐️   3 가리키기☝️   4 브이✌️   5 숫자(1~4)   0 중립
─────── 동작 ───────
 6 이리와🫱   7 드럼🥁   8 손흔들기👋   9 가위바위보
─────── 재미 ───────
 a 물결🌊   b 피아노🎹   c 거미🕷️   d 부들부들😰
 e 짜잔✨   f 도리도리🙅   g 두근두근💓   h 꼬물꼬물🌀
 i 끄덕끄덕🙆   j 손가락총🔫   k 꽃피기🌸   l 카운트다운🚀
 m 로봇🤖   n 춤🕺
 q 종료
> """

ACTIONS = {
    '1': g_fist, '2': g_open, '3': g_point, '4': g_peace, '0': g_neutral,
    '6': g_beckon, '7': g_drum, '8': g_wave, '9': g_rps,
    'a': g_ripple, 'b': g_piano, 'c': g_spider, 'd': g_tremble,
    'e': g_tada, 'f': g_no, 'g': g_heartbeat, 'h': g_alive,
    'i': g_yes, 'j': g_gun, 'k': g_bloom, 'l': g_launch,
    'm': g_robot, 'n': g_dance,
}

try:
    g_neutral()
    while True:
        c = input(MENU).strip().lower()
        if c == 'q':
            break
        elif c == '5':
            n = input("  몇? (1~4): ").strip()
            if n.isdigit(): g_count(max(1, min(4, int(n))))
        elif c in ACTIONS:
            ACTIONS[c]()
        else:
            print("  ? 메뉴에서 골라주세요")
except KeyboardInterrupt:
    pass

g_neutral(); time.sleep(0.3)
ph.closePort()
print("종료.")
