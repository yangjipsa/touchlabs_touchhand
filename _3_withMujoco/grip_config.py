#!/usr/bin/env python3
# ============================================================
#  잡기 설정 공유 — STEP 3(day2_3_grasp_sim)에서 세팅/캘리브레이션한 값을
#  STEP 6(day2_6_shape_grasp)이 그대로 이어받게 하는 공용 설정.
#  같은 실물 손이므로 빈손 기준(FREECLOSE)·힘(CLOSE_TARGET)이 그대로 통함.
#
#  파일: grip_cal.json (같은 폴더에 자동 생성)
# ============================================================
import json
from pathlib import Path

_F = Path(__file__).resolve().parent / "grip_cal.json"

DEFAULT = {
    "OPEN_BEND":    -80,     # 펴기
    "CLOSE_TARGET": 140,     # 쥐는 힘/깊이 — 낮출수록 약하게 쥠
    "GAP":          12,      # 감지 예민도(캘리브 없을 때 폴백) — 낮출수록 예민
    "MARGIN":       12,      # 캘리브 기준보다 이만큼 덜 닫히면 '잡음'
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
