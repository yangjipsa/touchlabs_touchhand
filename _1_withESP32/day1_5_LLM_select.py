#!/usr/bin/env python3
# ============================================================
#  Amazing Hand  -  LLM Select (정해진 동작 중 LLM 이 선택)
# ============================================================
#  Author   : yangjipsa
#  Company  : TouchLabs (touchlabs.kr)
#  Version  : 1.0
#  Date     : 2026-08-25
#  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
#  Purpose  : LLM 에게 '정해진 동작 목록'을 주고, 사용자의 말에
#             가장 어울리는 동작 하나를 '고르게' 한다.
#             (각도를 생성하지 않음 -> 안정적·예측가능)
#             구조: 입력 -> LLM -> 동작 번호 -> USB시리얼 -> XIAO
#             ※ LLM 이 각도를 '생성'하는 버전은 day1_6_LLM_create.py
#  Needs    : pip install pyserial requests
#  Key      : 3가지 중 아무거나 (우선순위 위->아래)
#               1) 코드 상단 CLAUDE_API_KEY / GEMINI_API_KEY 변수
#               2) 같은 폴더의 api_key.txt 파일  <- 추천
#               3) 환경변수 ANTHROPIC_API_KEY / GEMINI_API_KEY
#             PROVIDER 로 Claude/Gemini 선택.
#  Upload   : XIAO 에 day1_3_command.ino 먼저 업로드
#  Run      : python day1_5_LLM_select.py
# ------------------------------------------------------------
#  Copyright (c) 2026 TouchLabs.  All rights reserved.
#  This code is the property of TouchLabs and is provided for the
#  Amazing Hand product / education kit. Unauthorized copying,
#  distribution, or modification is prohibited.
# ============================================================

import os
import sys
import json
import glob
import time
import requests

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pyserial 이 필요합니다:  pip install pyserial")
    sys.exit(1)

# ---------------- 설정 ----------------
PROVIDER = "claude"        # "claude" 또는 "gemini"

# ★ API 키 — 아래 3가지 중 아무거나 (위에서부터 우선순위)
CLAUDE_API_KEY = ""        # "sk-ant-..."
GEMINI_API_KEY = ""        # "AIza..."
KEY_FILE = "api_key.txt"   # 이 파일에 키를 적어두면 자동으로 읽음 (남에게 공유 금지!)

# 모델 선택 — 원하는 줄의 주석(#)만 풀고 나머지는 #으로 막기
CLAUDE_MODEL = "claude-haiku-4-5"     # 가장 빠르고 저렴 (선택 방식엔 이걸로 충분)
# CLAUDE_MODEL = "claude-sonnet-5"    # 똑똑+빠름, 중간 가격
# CLAUDE_MODEL = "claude-opus-5"      # 가장 똑똑함, 비쌈
# CLAUDE_MODEL = "claude-opus-4-8"    # Opus 계열, 강력

GEMINI_MODEL = "gemini-2.5-flash"     # 빠르고 저렴
# GEMINI_MODEL = "gemini-2.5-pro"     # 더 똑똑, 느리고 비쌈

PORT        = None
BAUD        = 115200
SER_TIMEOUT = 0.3
CMD_TIMEOUT = 60           # 모션이 끝나야 OK
# --------------------------------------

# 펌웨어(day1_3_command.ino)의 표와 일치
POSES = {
    0: "중립", 1: "하나", 2: "둘", 3: "셋", 4: "넷",
}
MOTIONS = {
    1: "노노", 2: "가위바위보", 3: "박수", 4: "따봉", 5: "브이", 6: "손흔들기",
}  # m1 노노(기본) + m2~6 (STEP 3 바이브 코딩 결과)

SYSTEM = """너는 4손가락 로봇 손을 조종하는 귀여운 로봇이다.
사용자의 말에 가장 어울리는 동작 하나를 아래 목록에서 골라 JSON 으로만 답한다.

[포즈] 정지 자세
%POSES%

[모션] 움직이는 동작
%MOTIONS%

출력 형식 (다른 텍스트 없이 JSON 만):
{"type":"pose"|"motion","n":번호,"say":"한 줄 대사"}

규칙:
- say 는 30자 이내의 짧고 자연스러운 한국어 한 문장 + 어울리는 이모지 1개 정도 (🤖✋👋✌️ 등)
- 목록에 어울리는 게 없으면 {"type":"pose","n":0,"say":"..."}
- 인사/작별에는 손흔들기(motion 6)
- 숫자를 물으면 해당 포즈(1~4), 5 이상은 손가락 4개라 불가 -> 중립(0)
- 가위바위보를 하자고 하면 motion 2"""


def build_system():
    p = "\n".join(f"  {k} : {v}" for k, v in POSES.items())
    m = "\n".join(f"  {k} : {v}" for k, v in MOTIONS.items())
    return SYSTEM.replace("%POSES%", p).replace("%MOTIONS%", m)


# ---------------- API 키 파일 읽기 ----------------
def load_key_file():
    keys = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), KEY_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip().strip('"').strip("'")
                else:
                    keys["_bare"] = line.strip('"').strip("'")
    except FileNotFoundError:
        pass
    return keys

FILE_KEYS = load_key_file()


# ---------------- LLM ----------------
def ask_claude(system, history):
    key = (CLAUDE_API_KEY or FILE_KEYS.get("ANTHROPIC_API_KEY") or FILE_KEYS.get("CLAUDE_API_KEY")
           or FILE_KEYS.get("_bare") or os.environ.get("ANTHROPIC_API_KEY"))
    if not key:
        raise RuntimeError(f'Claude 키 없음: 상단 CLAUDE_API_KEY / {KEY_FILE} / 환경변수 ANTHROPIC_API_KEY 중 하나에 넣으세요')
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": CLAUDE_MODEL, "max_tokens": 200, "system": system, "messages": history},
        timeout=30,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", [])).strip()


def ask_gemini(system, history):
    key = (GEMINI_API_KEY or FILE_KEYS.get("GEMINI_API_KEY") or FILE_KEYS.get("GOOGLE_API_KEY")
           or FILE_KEYS.get("_bare") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    if not key:
        raise RuntimeError(f'Gemini 키 없음: 상단 GEMINI_API_KEY / {KEY_FILE} / 환경변수 GEMINI_API_KEY 중 하나에 넣으세요')
    contents = [{"role": ("model" if h["role"] == "assistant" else "user"),
                 "parts": [{"text": h["content"]}]} for h in history]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    r = requests.post(
        url,
        headers={"content-type": "application/json"},
        json={"system_instruction": {"parts": [{"text": system}]},
              "contents": contents,
              "generationConfig": {"maxOutputTokens": 200, "temperature": 0.7}},
        timeout=30,
    )
    r.raise_for_status()
    cand = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in cand).strip()


def ask_llm(history):
    system = build_system()
    if PROVIDER == "gemini":
        return ask_gemini(system, history)
    return ask_claude(system, history)


def parse_action(text):
    """LLM 응답 JSON -> (type, n, say).  실패하면 중립."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    s, e = t.find("{"), t.rfind("}")
    if s >= 0 and e > s:
        t = t[s:e + 1]
    try:
        d = json.loads(t)
        typ = d.get("type")
        n = int(d.get("n", 0) or 0)
        say = str(d.get("say", ""))
        if typ == "pose" and n in POSES:
            return "pose", n, say
        if typ == "motion" and n in MOTIONS:
            return "motion", n, say
    except Exception:
        pass
    return "pose", 0, "음... 잘 모르겠어요 🤖"


def name_of(typ, n):
    return POSES.get(n, "?") if typ == "pose" else MOTIONS.get(n, "?")


# ---------------- 시리얼(손) ----------------
def find_port():
    if PORT:
        return PORT
    cands = [p.device for p in list_ports.comports()
             if "usbmodem" in p.device or "usbserial" in p.device or "wchusb" in p.device
             or p.device.upper().startswith("COM")]
    cands += glob.glob("/dev/cu.usbmodem*")
    return sorted(set(cands))[0] if cands else None


def wait_reply(ser, deadline):
    while time.time() < deadline:
        line = ser.readline().decode(errors="ignore").strip()
        if line in ("OK", "ERR"):
            return line == "OK"
    return False


def open_hand():
    port = find_port()
    if not port:
        print("❌ XIAO 포트를 못 찾음. USB 연결 확인, 또는 상단 PORT 지정.")
        print("   보이는 포트:", [p.device for p in list_ports.comports()])
        sys.exit(1)
    print("🔌 손 연결:", port)
    ser = serial.Serial(port, BAUD, timeout=SER_TIMEOUT)
    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.write(b"N\n")
    print("✅ 손 준비 완료" if wait_reply(ser, time.time() + 3)
          else "⚠️  응답 없음 (펌웨어/시리얼모니터 확인) — 그래도 진행")
    return ser


def send_hand(ser, cmd):
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    return wait_reply(ser, time.time() + CMD_TIMEOUT)


# ---------------- 메인 ----------------
def main():
    ser = open_hand()
    print("=" * 50)
    print(f"  Amazing Hand - {PROVIDER.upper()} 동작 선택 제어")
    print("  종료: quit / 손 초기화: reset")
    print("=" * 50)

    history = []
    try:
        while True:
            try:
                user = input("\n나 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user in ("quit", "exit", "q"):
                break
            if user == "reset":
                send_hand(ser, "N"); history = []
                print("로봇 > 중립으로 돌아왔어요 🤖")
                continue

            history.append({"role": "user", "content": user})
            try:
                raw = ask_llm(history)
            except Exception as e:
                print("  ! LLM 오류:", e)
                history.pop()
                continue
            history.append({"role": "assistant", "content": raw})
            history = history[-12:]

            typ, n, say = parse_action(raw)
            print(f"로봇 > {say}   [{name_of(typ, n)}]")
            send_hand(ser, ("P" if typ == "pose" else "M") + str(n))
    finally:
        send_hand(ser, "N")
        ser.close()
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
