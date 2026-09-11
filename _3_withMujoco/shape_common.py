#!/usr/bin/env python3
# ============================================================
#  모양 인식 - 공용 모듈 (시뮬 훈련 day2_4a_shape_learn.py 과 실제손 day2_6_shape_grasp.py 가 공유)
#
#  핵심 개념(피지컬 AI):
#   · 손가락이 물체를 둘러 만지면 각 손가락 깊이 = 물체 단면 윤곽을 잼
#   · 한 번(4손가락)으론 부족 → 물체를 돌려가며 여러 번 = '능동 지각'
#   · 특징을 '차이 기반 + 표준화' 로 뽑으면 실제 손 보정이 달라도 견딤(sim2real)
# ============================================================
import numpy as np

# 3가지 3D 물체 (손이 잡을 때 손가락 깊이 패턴으로 구분)
#   구(공) · 타원(럭비공/계란) · 정육면체  =  둥근 / 길쭉한 / 각진
SHAPES = ["구", "타원", "정육면체"]
EMOJI  = {"구": "⚪", "타원": "🏉", "정육면체": "🧊"}

N_GRASP = 4                                        # 잡는 횟수(돌려가며). 4번=위치 흔들려도 강건
# 실제 손 4손가락의 대략 접촉 각도: 검지·중지약지·새끼(붙어서 부채꼴) + 엄지(맞은편)
FINGER_ANG = np.deg2rad([-20.0, 0.0, 20.0, 180.0])  # [검지, 중지약지, 새끼, 엄지]

# ── 모양의 단면 윤곽: 각도 φ 에서 중심까지 반지름 r(φ) ──
def _polygon(n, R, rot=0.0, inner=None):
    if inner is None:
        a = rot + np.arange(n) * 2*np.pi/n
        return np.c_[R*np.cos(a), R*np.sin(a)]
    a = rot + np.arange(2*n) * np.pi/n
    rr = np.where(np.arange(2*n) % 2 == 0, R, inner)
    return np.c_[rr*np.cos(a), rr*np.sin(a)]

def _ray_r(verts, phi):
    ux, uy = np.cos(phi), np.sin(phi)
    best = np.inf
    N = len(verts)
    for i in range(N):
        p, q = verts[i], verts[(i+1) % N]
        ex, ey = q[0]-p[0], q[1]-p[1]
        det = ex*uy - ey*ux
        if abs(det) < 1e-12:
            continue
        t = (ex*p[1] - ey*p[0]) / det
        s = (ux*p[1] - uy*p[0]) / det
        if t > 1e-9 and -1e-9 <= s <= 1+1e-9:
            best = min(best, t)
    return best if np.isfinite(best) else 1.0

def radial_profile(shape, phis, yaw=0.0, scale=1.0):
    """모양을 yaw 돌리고 scale 키운 뒤, 각 각도에서의 반지름 배열."""
    p = np.atleast_1d(phis) - yaw
    if shape == "구":                              # 단면 = 원
        return np.full_like(p, float(scale))
    if shape == "타원":                                # 단면 = 타원(럭비공 눕힌 것)
        a, b = scale*1.0, scale*0.55
        return a*b / np.sqrt((b*np.cos(p))**2 + (a*np.sin(p))**2)
    if shape == "삼각뿔":                              # 단면 = 삼각형
        v = _polygon(3, scale*1.25)
    elif shape == "정육면체":                          # 단면 = 사각형
        v = _polygon(4, scale*1.15, rot=np.pi/4)
    else:
        raise ValueError(shape)
    return np.array([_ray_r(v, q) for q in p])

# ── 시뮬: 한 번 잡을 때 4손가락 '판독값'(깊이) 생성 ──
#    실제 손: 깊이가 클수록 = 많이 닫힘 = 반지름 작은 곳(늦게 막힘)
#    reading = offset - gain*radius  (+ 잡음).  gain/offset 은 손마다 다름 → 랜덤화
def simulate_readings(shape, yaw, scale, gain, offset, noise):
    r = radial_profile(shape, FINGER_ANG, yaw, scale)
    return offset - gain*r + np.random.normal(0, noise, len(FINGER_ANG))

# ── ★ 특징 추출 (시뮬·실제 공용, 핵심) ──
#    grasps = N_GRASP 개의 4원소 판독값 리스트 [검지,중지약지,새끼,엄지]
#    모든 특징을 '차이 기반 + 표준화' → 손 보정(gain/offset) 이 달라도 불변
def extract_features(grasps):
    grasps = [np.asarray(g, float) for g in grasps]
    allv = np.concatenate(grasps)
    sd = allv.std() + 1e-9
    z = np.sort((allv - allv.mean()) / sd)          # 표준화된 깊이 분포(정렬)
    per = []
    for r in grasps:
        slope = r[2] - r[0]                          # 부채꼴 3손가락 기울기
        curv  = r[0] + r[2] - 2*r[1]                 #   〃      휘어짐(곡률)
        tvf   = r[3] - r[:3].mean()                  # 엄지 vs 나머지(맞은편 대비)
        per.append([abs(slope), curv, tvf])
    per = np.array(per) / sd                          # gain 소거
    feat = list(z)
    for c in range(per.shape[1]):
        col = per[:, c]
        feat += [col.mean(), col.std(), col.max(), col.min()]
    return np.array(feat)
