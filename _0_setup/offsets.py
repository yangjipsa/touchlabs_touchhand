"""
서보별 중립 보정(offset) — 단일 소스.
servo_tune.py 로 찾은 값. 여기 한 곳만 수정하면 모든 스크립트에 반영됨.
mid(i) = 511 + OFFSET[i]  (해당 서보의 '진짜 중립' 위치)
"""
MID = 511

OFFSET = {
    1: 0,
    2: +14,
    3: -16,
    4: -28,
    5: +10,
    6: -20,
    7: +8,
    8: +7,
}

def mid(i):
    return max(0, min(1023, MID + OFFSET.get(i, 0)))

# 서보 최대 회전 = 중심 ±90° (≈ ±307 스텝). 이 범위 넘으면 안전하게 잘라줌.
LIMIT = 307

def clamp(i, p):
    lo, hi = mid(i) - LIMIT, mid(i) + LIMIT
    p = max(lo, min(hi, p))          # ±90° 제한
    return max(0, min(1023, p))      # 물리 범위(0~1023) 제한
