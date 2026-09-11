# TouchHand PhysicalAI — SourceCode

**피지컬 AI 교육 키트** (Amazing Hand 로봇 손) 실습 소스코드. TouchLabs.

| 폴더 | 내용 |
|---|---|
| `_0_setup/` | 서보 세팅 GUI 툴 — ID·중립 설정 (PC ↔ Waveshare 직결) |
| `_1_withESP32/` | **Day1** — ESP32 기초(네오픽셀·스위치·부저) → 서보세팅 스케치 → 손제어(직접 / LLM 대화) |
| `_2_tinyML/` | **TinyML** — 카메라 손동작 인식 (웹캡처 수집 → Edge Impulse 학습 → 추론 → 손 연동) |
| `_3_withMujoco/` | **Day2** — MuJoCo 시뮬레이션 sim2real (IK · 파지 · 모양 인식) |

각 폴더의 `README.md`에 배선·업로드 옵션·실행법이 있습니다. 강의자료는 별도(강사 제공).

## 시작 전
- **API 키**: LLM 제어(`_1_withESP32/day1_5·6`)는 각자 `api_key.txt`를 그 폴더에 만들어 넣습니다. **저장소에는 포함되지 않습니다**(`.gitignore`).
- **Edge Impulse 라이브러리**(`*_inferencing`)는 용량이 커서 미포함 — 학습 후 각자 설치. 설치 후 **overflow 패치(30→200)** 필요 (`_2_tinyML/README.md` 참고).

## 라이선스 · 출처
- 로봇 손: **Amazing Hand** — Pollen Robotics (SW **Apache 2.0** / HW **CC BY 4.0**)
- 교육용 확장·수업 코드: TouchLabs
