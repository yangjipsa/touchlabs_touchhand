#!/usr/bin/env python3
# ============================================================
#  모양 인식 - 3D 프린트용 STL 생성 (실물 테스트용 3종 도형)
#   구 · 타원(럭비공) · 정육면체
#
#  ★ 손이 쥘 때 느끼는 '단면'이 분류 신호:
#     구→원  타원→타원  정육면체→사각형
#  ※ 타원(럭비공)은 눕혀서(긴 축 수평) 잡아야 타원 단면이 나옴.
#  ※ 크기 85mm = 손 자연 아귀(~84mm)에 맞춤. 시뮬(day2_5_shape_grasp_sim.SIZE)과 '같은 크기'여야 구분됨.
#
#  실행:  python3 day2_부록_shape_print_stl.py   →  stl/구.stl …
#  프린트: PLA, 채움 15%.  정육면체는 면으로 세우기.
# ============================================================
import numpy as np
from pathlib import Path

# 실물 프린트 치수(mm) — 시뮬(day2_5_shape_grasp_sim.SIZE)과 '동일 85mm'여야 함.
#   크기가 다르면 잡는 방식이 달라져 육면체/타원을 구분 못함 → 시뮬=실물=85mm 통일 후 재학습.
SPEC = {
    "구":       ("ellipsoid", dict(a=42.5, b=42.5, c=42.5)),  # 지름 85mm 공
    "타원":     ("ellipsoid", dict(a=68.5, b=29.5, c=29.5)),  # 137(긴축) x 59 럭비공(비율 2.3:1)
    "정육면체": ("cube",      dict(s=85.0)),                   # 85 정육면체
}

def cylinder(r, H, nseg=120):
    ph = np.linspace(0, 2*np.pi, nseg, endpoint=False)
    poly = np.c_[r*np.cos(ph), r*np.sin(ph)]
    bot = [(x, y, 0.0) for x, y in poly]; top = [(x, y, H) for x, y in poly]
    cb, ct = (0, 0, 0.0), (0, 0, H); T = []
    for i in range(nseg):
        j = (i+1) % nseg
        T += [(bot[i], bot[j], top[j]), (bot[i], top[j], top[i]),
              (cb, bot[j], bot[i]), (ct, top[i], top[j])]
    return T

def ellipsoid(a, b, c, nu=48, nv=24):
    """럭비공: 긴 축 a를 수평(x)으로. 바닥에 눕도록 z는 짧은 축."""
    U = np.linspace(0, 2*np.pi, nu, endpoint=False)
    V = np.linspace(-np.pi/2, np.pi/2, nv)
    def P(u, v): return (a*np.cos(v)*np.cos(u), b*np.cos(v)*np.sin(u), c*np.sin(v) + c)
    T = []
    for i in range(nu):
        iu = (i+1) % nu
        for k in range(nv-1):
            p1, p2, p3, p4 = P(U[i],V[k]), P(U[iu],V[k]), P(U[iu],V[k+1]), P(U[i],V[k+1])
            T += [(p1, p2, p3), (p1, p3, p4)]
    return T

def tetra(edge):
    r = edge/np.sqrt(3); h = edge*np.sqrt(2/3)
    base = [(r, 0), (-r/2, r*np.sqrt(3)/2), (-r/2, -r*np.sqrt(3)/2)]
    b0, b1, b2 = [(x, y, 0.0) for x, y in base]; ap = (0.0, 0.0, h)
    return [(b0, b2, b1), (b0, b1, ap), (b1, b2, ap), (b2, b0, ap)]

def cube(s):
    h = s/2.0
    v = [(x, y, z) for z in (0.0, s) for y in (-h, h) for x in (-h, h)]
    q = [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    T = []
    for a, b, c, d in q:
        T += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return T

def normal(a, b, c):
    n = np.cross(np.subtract(b, a), np.subtract(c, a)); L = np.linalg.norm(n)
    return (n/L) if L > 1e-12 else np.zeros(3)

def write_stl(path, tris, name):
    with open(path, "w") as f:
        f.write(f"solid {name}\n")
        for a, b, c in tris:
            nx, ny, nz = normal(a, b, c)
            f.write(f" facet normal {nx:.5f} {ny:.5f} {nz:.5f}\n  outer loop\n")
            for v in (a, b, c): f.write(f"   vertex {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")

MAKE = {"cylinder": cylinder, "ellipsoid": ellipsoid, "tetra": tetra, "cube": cube}

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "stl"; out.mkdir(exist_ok=True)
    print("="*56)
    print("  3D 프린트용 도형 3종 (실제 3D 형태)")
    print("="*56)
    for shape, (kind, kw) in SPEC.items():
        tris = MAKE[kind](**kw)
        write_stl(out/f"{shape}.stl", tris, shape)
        dims = " ".join(f"{k}={v:.0f}" for k, v in kw.items())
        print(f"  {shape:<7} [{kind:9}] {dims:22} → stl/{shape}.stl  ({len(tris)}면)")
    print("\n  프린트: PLA, 채움 15%.  ※ 타원(럭비공)은 눕혀서 잡기.")
    print("  손 아귀에 안 맞으면 SPEC 치수만 조절(비율 유지).")
