#!/usr/bin/env python3
# ============================================================
#  잡기 설정 공유 — STEP 3(day2_3_grasp_sim)에서 세팅/캘리브레이션한 값을
#  STEP 6(day2_6_shape_grasp)이 그대로 이어받게 하는 공용 설정.
#
#  ★ 학생용 — 손 개체마다 값이 다를 수 있음. 잡기 판정이 잘 안 되면
#    아래 DEFAULT 를 조정하거나, day2_3 실행 중 키로 즉시 바꿀 수 있음.
#
#  ┌ 잘 안 될 때 어디를 고치나 ─────────────────────────────┐
#  │ 물체 쥐었는데 "안 잡음"   → MARGIN 낮추기(8→6) 또는       │
#  │                            CLOSE_TARGET 높이기(110→130)  │
#  │ 빈손인데 "잡음"으로 뜸    → MARGIN 높이기(8→12)           │
#  │ 손가락마다 제각각         → day2_3 에서 k 로 재캘리브      │
#  └────────────────────────────────────────────────────────┘
#
#  캘리브(권장): day2_3 실행 → 물체 치우고 k → 자기 손 빈손 기준(FREECLOSE)이
#    grip_cal.json(로컬 자동 생성, 저장소엔 안 올라감)에 저장됨.
#    이후 그 값이 아래 DEFAULT 를 덮어씀. 손을 바꾸면 k 로 다시.
#
#  파일: grip_cal.json (같은 폴더에 자동 생성, 학생마다 다름 → git 제외)
# ============================================================
import json
from pathlib import Path

_F = Path(__file__).resolve().parent / "grip_cal.json"

# ── 학생이 조정하는 기본값 (grip_cal.json 이 있으면 그 값이 우선) ──
DEFAULT = {
    "OPEN_BEND":    -80,     # 펴기
    "CLOSE_TARGET": 110,     # 쥐는 힘/깊이 — 낮출수록 약하게 쥠(하드웨어 보호), 높일수록 확실히 쥠
    "GAP":          12,      # 감지 예민도(캘리브 없을 때 폴백) — 낮출수록 예민
    "MARGIN":       8,       # 캘리브 기준보다 이만큼 덜 닫히면 '잡음' — 낮출수록 예민
    "SETTLE":       1.3,     # 명령 후 판정까지 대기(초)
    "FREECLOSE":    None,    # 빈손 기준 깊이 [엄지,검지,중지약지,새끼] (k로 측정하면 채워짐)
}


def load():
    """저장된 설정을 읽어 dict 반환 (없으면 기본값)."""
    cfg = dict(DEFAULT)
    try:
        cfg.update(json.loads(_F.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save(**kw):
    """일부 값만 갱신해 저장 (예: save(FREECLOSE=[...], CLOSE_TARGET=130))."""
    cfg = load()
    cfg.update(kw)
    _F.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg
