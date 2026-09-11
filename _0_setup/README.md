# Day1 서보 세팅 도구 (SCS0009 · Amazing Hand)

서보 **ID 부여 + 중립(511) 정렬 + 오프셋 튜닝**을 터미널에서 하는 도구.
**강사가 조립·정비 시** 사용 (학생 키트는 세팅 완료 상태로 배포).

## 실행

```bash
cd Day1_서보세팅
pip install feetech-servo-sdk pyserial      # scservo_sdk 제공 패키지
python hand_setup.py
```
- 연결: Waveshare **점퍼 B (USB 직결)** + **CH343 드라이버**, 서보 전원 **5V**. (ESP 불필요)
- 포트 자동탐지 (`cu.wchusbserial…`). 다른 프로그램이 포트 잡고 있으면 닫기.

## hand_setup.py 메뉴

| 번호 | 기능 |
|---|---|
| 1 | 스캔 (연결된 서보 ID/위치) |
| 2 | ID 하나 설정 (서보 **1개만** 연결) |
| 3 | **ID 순서대로 1→8** (하나씩 꽂으며) ← ID 세팅 표준 |
| 4 | **전체 중립(511)** (이 자세에서 조립·정렬) |
| 5 | 특정 ID 중립 |
| 6 | 중립 미세튜닝 → `offset` 출력 (`offsets.py`에 반영) |
| 7 | 토크 해제 |
| 8 | 손가락 확인 (ID별로 까딱) |
| 0 | 종료 |

## 세팅 순서 (요약)

1. `3` → 서보 **하나씩** 꽂으며 ID 1~8 할당
2. `1` 스캔으로 1~8 다 있는지 확인
3. `4` 전체 중립 → 혼·손가락 **조립/정렬**
4. 필요 시 `6` 튜닝으로 서보별 offset 뽑아 `offsets.py`에 기입

## 손가락 ↔ 서보 ID

검지 = 1,2 / 중지약지 = 3,4 / 새끼 = 5,6 / 엄지 = 7,8

## 참고

- 개별 스크립트: `set_id.py`(ID 하나), `servo_all_middle.py`(전체 중립), `scan_servo.py`(스캔) — 모두 `hand_setup.py`에 통합돼 있어 보통은 `hand_setup.py` 하나면 충분.
- 실행·포트·환경 정본: `강의자료/환경_실행_가이드.html`
- `main.py`(PyQt6 GUI)는 선택 — 쓰려면 `pip install PyQt6` 후 `python main.py`.
