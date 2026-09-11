#!/usr/bin/env python3
# ============================================================
#  모양 인식 - 실물로 직접 가르치기 (sim2real 갭 해결 / 잡기 최소화)
#   도형당 몇 번만 잡아 '풀'에 모으고, 학습 시 풀에서 랜덤 재조합(부트스트랩)해
#   많은 표본을 만들어 학습 → 실제 잡는 횟수를 확 줄임(손가락 보호).
#
#  준비 : pip install feetech-servo-sdk scikit-learn joblib numpy
#         Waveshare USB 직결 (점퍼 B)
#  실행 : python3 day2_보정_shape_teach_real.py     (뷰어 불필요)
#
#  ▶ 키 (엔터 없이 하나만):
#     1/2/3 = 도형 선택(구/타원/정육면체)
#     c     = 한 번 잡아 풀에 추가 (도형당 5번 정도면 충분)
#     t     = 학습(풀에서 재조합)   b = 맞혀보기(4번 잡아 예측)
#     s     = 저장(shape_model.pkl)  o = 펴기   q = 종료
# ============================================================
import sys, time
import numpy as np
import joblib
from pathlib import Path
from shape_common import SHAPES, EMOJI, N_GRASP, FEAT_VERSION, extract_features
from sklearn.ensemble import RandomForestClassifier
import grip_config as GC

HERE = Path(__file__).resolve().parent
rng = np.random.default_rng()
_cfg = GC.load()
OPEN_BEND, CLOSE_TARGET, SETTLE = _cfg["OPEN_BEND"], _cfg["CLOSE_TARGET"], _cfg["SETTLE"]
FREECLOSE = _cfg["FREECLOSE"]     # STEP3 'k' 캘리브 [엄지,검지,중지약지,새끼]
AUG = 80          # 도형당 재조합으로 만들 학습 표본 수

# ── ★ 특징 v2용 기준 (day2_6 과 동일 정의): free=빈손 끝까지, open=펼침 ──
#    특징 순서 [검지,중지약지,새끼,엄지] = anat[1,2,3,0]
if FREECLOSE:
    REF = (np.array([FREECLOSE[1], FREECLOSE[2], FREECLOSE[3], FREECLOSE[0]], float),
           np.array([OPEN_BEND]*4, float))
else:
    REF = (np.array([CLOSE_TARGET]*4, float), np.array([OPEN_BEND]*4, float))

try:
    import termios, tty
    def _getch():
        fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
        try: tty.setcbreak(fd); return sys.stdin.read(1)
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
except Exception:
    def _getch(): return (sys.stdin.readline().strip()[:1] or " ")

hand = None
try:
    from hand_driver import HandDriver
    hand = HandDriver(); hand.speed = 200
except Exception as e:
    print("⚠️  실물 손 없음 → 데모(랜덤)로 흐름만:", e)

def one_grasp():
    """한 번 잡고 [검지,중지약지,새끼,엄지] 깊이 반환. 읽은 뒤 편다."""
    if hand is not None:
        hand.set_free([CLOSE_TARGET]*4, [0]*4); time.sleep(SETTLE)
        rd = hand.read()   # [엄지,검지,중지약지,새끼]
        d = [rd[i][0] if rd[i][0] is not None else CLOSE_TARGET for i in range(4)]
        hand.set_free([OPEN_BEND]*4, [0]*4)
        return np.array([d[1], d[2], d[3], d[0]])
    else:
        return np.random.normal(0, 1, 4)

POOL = {i: [] for i in range(len(SHAPES))}   # 도형별 개별 잡기 모음
clf = {"m": None}
sel = {"i": 0}
tbuf = []                                    # 맞혀보기용 임시 버퍼

def pool_counts():
    return [len(POOL[i]) for i in range(len(SHAPES))]

def train():
    labels = [i for i in range(len(SHAPES)) if len(POOL[i]) >= 2]
    if len(labels) < 2:
        print("  ⚠️  최소 2종류 · 종류당 2번 이상 잡아야 함. 지금 풀:",
              {SHAPES[i]: len(POOL[i]) for i in range(len(SHAPES)) if POOL[i]}); return
    X, y = [], []
    for i in labels:
        pool = POOL[i]
        for _ in range(AUG):                                  # 풀에서 N_GRASP개 복원추출 = 표본 1개
            combo = [pool[rng.integers(len(pool))] for _ in range(N_GRASP)]
            X.append(extract_features(combo, ref=REF)); y.append(i)
    X, y = np.array(X), np.array(y)
    m = RandomForestClassifier(n_estimators=200, random_state=0).fit(X, y)
    clf["m"] = m
    print(f"  ✅ 학습 완료! 잡기 풀 {pool_counts()} → 재조합 {len(y)}표본, 학습셋 {(m.predict(X)==y).mean()*100:.0f}%  (b로 테스트)")

def save():
    if clf["m"] is None: print("  ⚠️  먼저 t로 학습하세요."); return
    joblib.dump({"clf": clf["m"], "shapes": SHAPES, "n_grasp": N_GRASP,
                 "feat_version": FEAT_VERSION}, HERE/"shape_model.pkl")
    print("  💾 저장: shape_model.pkl → 이제 day2_6_shape_grasp.py가 이 실물 모델을 씀")

def banner():
    print("="*62)
    print("  실물로 직접 가르치기 (잡기 최소화 · 부트스트랩)")
    print("  1/2/3 = 도형 선택(" + " ".join(f"{i+1}{EMOJI[s]}{s}" for i,s in enumerate(SHAPES)) + ")")
    print(f"  c=한번잡아 풀에추가(도형당 5번쯤)  b=맞혀보기  t=학습  s=저장  o=펴기  q=종료")
    print("  ※ 매번 물체를 조금씩 돌려 잡으면 좋아요(다양한 각도). 손가락 보호를 위해 힘은 grip_config에서.")
    if not FREECLOSE:
        print("  ⚠️  STEP3(day2_3)에서 k 로 빈손 캘리브를 먼저 하세요 — 없으면 크기 특징이 부정확합니다.")
    print("="*62)
    print(f"  지금 도형: {EMOJI[SHAPES[0]]} {SHAPES[0]}  · 풀 {pool_counts()}")

def main():
    banner()
    if hand is not None: hand.set_free([OPEN_BEND]*4, [0]*4)
    mode = {"v": "collect"}
    while True:
        s = _getch().lower()
        if s in ("q", "\x03"): break
        elif s in ("1", "2", "3"):
            i = int(s)-1
            if i < len(SHAPES):
                sel["i"] = i; print(f"  → 지금 도형: {EMOJI[SHAPES[i]]} {SHAPES[i]}  · 풀 {pool_counts()}")
        elif s == "o":
            if hand is not None: hand.set_free([OPEN_BEND]*4, [0]*4)
            print("  → 펴기")
        elif s == "t": train()
        elif s == "s": save()
        elif s == "c":                                   # 한 번 잡아 풀에 추가
            depth = one_grasp(); POOL[sel["i"]].append(depth)
            print(f"     깊이[검지 중지약지 새끼 엄지]={np.round(depth,0).astype(int)}  "
                  f"➕ {EMOJI[SHAPES[sel['i']]]}{SHAPES[sel['i']]} 풀 {len(POOL[sel['i']])}개  (t=학습)")
        elif s == "b":                                   # 맞혀보기: N_GRASP번 잡아 예측
            if clf["m"] is None: print("  ⚠️  먼저 모으고 t로 학습하세요."); continue
            if mode["v"] != "test": tbuf.clear(); mode["v"] = "test"
            depth = one_grasp(); tbuf.append(depth)
            print(f"  ✊ {len(tbuf)}/{N_GRASP} 깊이={np.round(depth,0).astype(int)}")
            if len(tbuf) >= N_GRASP:
                p = clf["m"].predict_proba(extract_features(tbuf, ref=REF).reshape(1,-1))[0]; pi = int(p.argmax())
                order = np.argsort(p)[::-1]
                print(f"  🤖 이건 {EMOJI[SHAPES[pi]]} '{SHAPES[pi]}'! (확신 {p.max()*100:.0f}%)  "
                      + " ".join(f"{SHAPES[j]} {p[j]*100:.0f}%" for j in order))
                tbuf.clear(); mode["v"] = "collect"
            else:
                print(f"  → 조금 돌리고 다시 b  [{len(tbuf)}/{N_GRASP}]")
    if hand is not None: hand.close()
    print("\n종료!")

if __name__ == "__main__":
    main()
