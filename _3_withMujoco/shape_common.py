#!/usr/bin/env python3
# ============================================================
#  모양 인식 - 공용 모듈 (시뮬 훈련 day2_4a_shape_learn.py 과 실제손 day2_6_shape_grasp.py 가 공유)
#
#  핵심 개념(피지컬 AI):
#   · 손가락이 물체를 둘러 만지면 각 손가락 깊이 = 물체 단면 윤곽을 잼
#   · 한 번(4손가락)으론 부족 → 물체를 돌려가며 여러 번 = '능동 지각'
#   · 특징을 '차이 기반 + 표준화' 로 뽑으면 실제 손 보정이 달라도 견딤(sim2real)
#   · ★ v2: '막힌 비율'(빈손 기준 대비) 특징 추가 → 크기 정보까지 반영하면서도
#          손가락별 gain/offset 이 수식상 완전히 소거됨(무차원)
# ============================================================
import time
import numpy as np

# 3가지 3D 물체 (손이 잡을 때 손가락 깊이 패턴으로 구분)
#   구(공) · 타원(럭비공/계란) · 정육면체  =  둥근 / 길쭉한 / 각진
SHAPES = ["구", "타원", "정육면체"]
EMOJI  = {"구": "⚪", "타원": "🏉", "정육면체": "🧊"}

N_GRASP = 4                                        # 잡는 횟수(돌려가며). 4번=위치 흔들려도 강건
FEAT_VERSION = 2                                   # 특징 형식 버전 (모델 pkl 에 기록 → 불일치 시 재학습 안내)
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

# ── 시뮬(해석식 데모용): 한 번 잡을 때 4손가락 '판독값'(깊이) 생성 ──
#    실제 손: 깊이가 클수록 = 많이 닫힘 = 반지름 작은 곳(늦게 막힘)
#    reading = offset - gain*radius  (+ 잡음).  gain/offset 은 손마다 다름 → 랜덤화
def simulate_readings(shape, yaw, scale, gain, offset, noise):
    r = radial_profile(shape, FINGER_ANG, yaw, scale)
    return offset - gain*r + np.random.normal(0, noise, len(FINGER_ANG))

# ── ★ 특징 추출 (시뮬·실제 공용, 핵심) ──
#    grasps = N_GRASP 개의 4원소 판독값 리스트 [검지,중지약지,새끼,엄지]
#    ref    = (free4, open4) 같은 순서.  free = 빈손으로 끝까지 닫았을 때 깊이(STEP3 'k' 캘리브 = FREECLOSE),
#             open = 펼쳤을 때 깊이.  둘 다 '그 손'의 값이므로 gain/offset 이 자동 소거됨.
#    - 정규화 특징(패턴): 손 보정(gain/offset) 무관
#    - 막힌 비율 f = (free - depth)/(free - open): 0(안 막힘, 빈손과 같음) ~ 1(전혀 안 닫힘)
#        → 큰 물체일수록 일찍 막혀 f 큼 = '크기' 정보. gain/offset 은 분자·분모에서 소거.
def extract_features(grasps, ref=None):
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
    if ref is not None:                               # ★ v2 크기(막힌 비율) 특징 8개
        free, opn = np.asarray(ref[0], float), np.asarray(ref[1], float)
        rng_ = free - opn
        rng_ = np.where(np.abs(rng_) < 1e-6, 1e-6, rng_)
        F = np.clip(np.array([(free - g) / rng_ for g in grasps]), -0.5, 1.5)   # (N_GRASP, 4)
        feat += [F.mean(), F.std(), F.min(), F.max()] + list(F.mean(axis=0))
    return np.array(feat)

# ── 뷰어 보조 (윈도우·저사양 노트북 대응) ──
class Pacer:
    """렌더 속도와 무관하게 물리를 실시간에 맞춰 돌리기.
    매 프레임 substeps() 만큼 mj_step 하면, 렌더가 느린 PC 에서도 손이 '힘없이 느리게' 보이지 않음."""
    def __init__(self, dt, max_sub=12):
        self.dt, self.max_sub = float(dt), int(max_sub)
        self.t = time.perf_counter(); self.acc = 0.0
    def substeps(self):
        now = time.perf_counter(); self.acc += now - self.t; self.t = now
        n = int(self.acc / self.dt)
        n = max(1, min(n, self.max_sub))
        self.acc -= n * self.dt
        if self.acc > self.dt * self.max_sub: self.acc = 0.0   # 렌더가 너무 느리면 누적 버림(폭주 방지)
        return n

def frame_camera(viewer, lookat=(0.02, 0.01, 0.07), distance=0.36, azimuth=150.0, elevation=-22.0):
    """3D 창 카메라를 손+물체가 한눈에 들어오게 고정(창이 좁아 양옆이 잘리는 문제 완화).
    마우스로 드래그/휠 하면 그 뒤로는 자유롭게 바뀜."""
    try:
        c = viewer.cam
        c.lookat[:] = lookat; c.distance = distance; c.azimuth = azimuth; c.elevation = elevation
    except Exception:
        pass
