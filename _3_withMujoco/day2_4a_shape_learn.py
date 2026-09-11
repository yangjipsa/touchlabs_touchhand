#!/usr/bin/env python3
# ============================================================
#  모양 인식 ① 시뮬로 학습  (MuJoCo 물리 접촉 + 3축 회전)
#
#  MuJoCo 가상 손이 물체를 '실제로' 4번(3D로 굴려가며) 잡을 때의
#  손가락 깊이 → 3가지 도형(구·타원·정육면체) 분류기 학습.
#  · 3축 랜덤 자세로 잡으므로 어느 방향이든 인식 (능동 지각)
#  · 시뮬·실물이 똑같이 '손가락 깊이'를 쓰므로 일관됨(sim2real)
#
#  실행:  python3 day2_4a_shape_learn.py       (하드웨어 불필요, ~1분)
#  결과:  shape_model.pkl  +  day2_4a_shape_learn.png
#  준비:  pip install numpy scikit-learn matplotlib joblib mujoco
# ============================================================
import numpy as np
import mujoco
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "AppleGothic"; matplotlib.rcParams["axes.unicode_minus"] = False
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix
import joblib

import day2_5_shape_grasp_sim as G
from shape_common import SHAPES, N_GRASP, extract_features

rng = np.random.default_rng(0)
N_PER = 350          # 도형당 표본 수
NOISE = 0.03         # 센서 잡음(실물 대비 여유)
# ── 도메인 랜덤화(sim2real 핵심): 표본마다 '가상 손'을 다르게 만들어,
#    손가락별 보정·쥐는 힘이 달라도 견디는 모델 → 실물로 전이가 잘 됨.
DR_GAIN  = (0.70, 1.30)   # 손가락별 읽기 배율 랜덤
DR_OFF   = (-0.35, 0.35)  # 손가락별 읽기 오프셋 랜덤
DR_CLOSE = (1.20, 1.60)   # 쥐는 정도(닫힘 깊이) 랜덤

model = G.build_model(); data = mujoco.MjData(model); FQ = G.finger_q(model)
BID  = {s: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY, f"OBJ_{s}") for s in SHAPES}

def place(active, pos):
    for s in SHAPES:
        model.body_pos[BID[s]] = pos if s == active else G.AWAY_POS

def grasp(active, quat, close=1.4):
    """물체를 quat 자세로 두고 손을 close 만큼 닫아(물리) 손가락 깊이 읽기."""
    model.body_quat[BID[active]] = quat        # 정적 body 방향 = 물체 회전
    mujoco.mj_resetData(model, data); cur = -0.8
    for _ in range(G.CLOSE_STEPS):
        cur += np.clip(close - cur, -0.03, 0.03); data.ctrl[:] = G.ctrl_v(cur)
        mujoco.mj_step(model, data)
    return G.read_flex(data, FQ) + rng.normal(0, NOISE, 4)

def sample(shape):
    place(shape, G.jitter_pos(rng))            # 샘플당 물체 위치 랜덤(한자리 놓고 돌리기)
    gain  = rng.uniform(*DR_GAIN, 4)           # 이 표본의 '가상 손' 손가락별 보정
    off   = rng.uniform(*DR_OFF, 4)
    close = rng.uniform(*DR_CLOSE)             # 쥐는 정도도 랜덤
    return extract_features([gain*grasp(shape, G.rand_quat(rng), close) + off for _ in range(N_GRASP)])

print("="*52)
print(f"  MuJoCo 물리 학습 : {len(SHAPES)}도형 × {N_PER} × {N_GRASP}번잡기(3D자세)")
print("="*52)
X, y = [], []
for ci, s in enumerate(SHAPES):
    for _ in range(N_PER):
        X.append(sample(s)); y.append(ci)   # sample() 안에서 위치 랜덤 배치
    print(f"  {G.EMOJI[s]} {s} 수집 완료 ({N_PER})")
X, y = np.array(X), np.array(y)

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1, stratify=y)
clf = RandomForestClassifier(n_estimators=300, random_state=1, n_jobs=-1).fit(Xtr, ytr)
pred = clf.predict(Xte); acc = accuracy_score(yte, pred); cm = confusion_matrix(yte, pred)

print(f"\n  전체 정확도: {acc*100:.1f}%\n  혼동행렬 (행=정답, 열=예측)")
print("        " + " ".join(f"{s:>4}" for s in SHAPES))
for i, s in enumerate(SHAPES):
    print(f"  {s:>4}  " + " ".join(f"{cm[i][j]:>4}" for j in range(len(SHAPES))))

joblib.dump({"clf": clf, "shapes": SHAPES, "n_grasp": N_GRASP}, "shape_model.pkl")
print("\n  ✅ 분류기 저장: shape_model.pkl")

# ── 성적표 그림 (혼동행렬) ──
fig, ax = plt.subplots(figsize=(5.2, 4.6))
ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(SHAPES))); ax.set_xticklabels(SHAPES)
ax.set_yticks(range(len(SHAPES))); ax.set_yticklabels(SHAPES)
ax.set_xlabel("예측"); ax.set_ylabel("정답"); ax.set_title(f"MuJoCo 물리학습 (정확도 {acc*100:.1f}%)")
for i in range(len(SHAPES)):
    for j in range(len(SHAPES)):
        ax.text(j, i, cm[i][j], ha="center", va="center",
                color="white" if cm[i][j] > cm.max()/2 else "black")
plt.tight_layout(); plt.savefig("day2_4a_shape_learn.png", dpi=110)
print("  ✅ 성적표 그림: day2_4a_shape_learn.png")
