# Day 2 — MuJoCo sim2real 모양 인식 (파일 안내)

피지컬 AI 2일차 실습 폴더. Mac은 3D 뷰어 스크립트를 `mjpython`으로 실행.

## 실행 순서 파일

| STEP | 파일 | 역할 | 실행(Mac) |
|---|---|---|---|
| 준비 | `hand_driver.py` | 실물 서보 직결 드라이버(제어+읽기, 토크제한) | import용 · 연결확인 `python3 hand_driver.py` |
| 1 | `day2_1_sim_stream_real.py` | 시뮬 → 실물 스트리밍 | `mjpython` |
| 2 | `day2_2_sim_ik_real.py` | 빨간 점(IK) 드래그 제어 | `mjpython` |
| 3 | `day2_3_grasp_sim.py` | 잡기 감지 + 캘리브(`k`)·힘(`+/-`) | `mjpython` |
| 4① | `day2_4a_shape_learn.py` | 자동 대량 학습(도메인 랜덤화) → `shape_model.pkl` | `python3` |
| 4② | `day2_4b_shape_teach.py` | (시뮬) 직접 굴려·옮겨 가르치기 | `mjpython` |
| 5 | `day2_5_shape_grasp_sim.py` | 학습 결과 시뮬 테스트 | `mjpython` |
| 6 | `day2_6_shape_grasp.py` | 학습 결과 실물 테스트 (sim2real) | `mjpython` / `python3` |

## 보정·진단·공용

| 파일 | 역할 |
|---|---|
| `day2_보정_shape_teach_real.py` | **실물 파인튜닝**(부트스트랩, 도형당 5번) → `shape_model.pkl` |
| `day2_보정_check_real.py` | 실물 손가락 깊이 진단 |
| `shape_common.py` | 도형·특징 추출(sim·실물 공유) |
| `grip_config.py` | 실물 잡기 설정 공유(STEP3↔6) → `grip_cal.json` |
| `day2_부록_shape_print_stl.py` | 테스트 도형 STL 생성(85mm) |

## 데이터·자산 (같이 배포)

- `AHSimulation/` — MuJoCo 손 모델(`AH_Left/mjcf/scene.xml` 등)
- `objmesh/`, `stl/` — 물체 메시 / 생성된 도형 STL
- `shape_model.pkl` — 학습된 분류기(있으면 바로 STEP 5·6 가능)

## 필요 패키지

```
pip install mujoco feetech-servo-sdk scikit-learn numpy joblib matplotlib
pip install mink loop-rate-limiters daqp         # STEP 2(IK) 전용
```
- Mac 3D 뷰어: `mjpython`
- 실물: Waveshare USB 모드(점퍼 B) + CH343 드라이버

## 안전 (하드웨어 보호)

- `hand_driver.py`의 `MAX_TORQUE_PCT`(기본 55) = 서보 최대 토크 제한(자동 적용)
- `grip_config.py`의 `CLOSE_TARGET` = 닫기 목표(낮출수록 약하게)

## 모양 인식 모델 2종 (골라 쓰기)

| 파일 | 무엇 | 언제 |
|---|---|---|
| **`shape_model.pkl`** (기본) | **시뮬 학습본** — MuJoCo 물리 + 도메인 랜덤화, 도형당 500표본 | 기본값. 손 개체차에 강건해 **누구 손이든** 무난 |
| **`shape_model_보정_실물.pkl`** | **실물 보정본** — `day2_보정_shape_teach_real` 로 실제 손에서 학습 | **이 키트의 그 손**에서 더 정확. 시뮬본이 실물에서 자꾸 틀릴 때 |

**실물 보정본으로 바꾸기**
```bash
cp shape_model.pkl shape_model_시뮬.pkl        # 원본 백업(한 번만)
cp shape_model_보정_실물.pkl shape_model.pkl   # 교체 → day2_6 이 이걸 씀
```
되돌리려면 `cp shape_model_시뮬.pkl shape_model.pkl`.

> ⚠️ **보정본은 `grip_cal.json`(빈손 기준 FREECLOSE·힘 CLOSE_TARGET)과 한 세트**입니다.
> `grip_cal.json`은 손 개체별 값이라 저장소에 없다 — 보정본을 쓰려면 먼저 `day2_3`에서 **`k`**로 이 손의 기준을 만든다(자동 생성). 손을 다시 캘리브하면 기준이 바뀌므로 **보정본도 다시 학습**한다.
> 직접 만들려면: `day2_3`에서 `k` 캘리브 → `python day2_보정_shape_teach_real.py` → 도형당 5번 `c` → `t` → `s`

> `_archive/` = 수업에 안 쓰는 실험용 파일 보관(무시해도 됨).
