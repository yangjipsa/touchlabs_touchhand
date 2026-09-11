#!/usr/bin/env python3
# ============================================================
#  Amazing Hand  -  LLM (Claude / Gemini 각도 생성 제어)
# ============================================================
#  Author   : yangjipsa
#  Company  : TouchLabs (touchlabs.kr)
#  Version  : 2.0
#  Date     : 2026-08-25
#  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
#  Purpose  : LLM 에게 손 구조(손가락별 굽힘/좌우)를 알려주고,
#             사용자의 말에 맞는 동작을 'LLM 이 직접 각도로 생성'한다.
#             (정해진 메뉴에서 고르는 게 아니라, 키프레임을 만들어냄)
#             구조: 입력 -> LLM -> 키프레임(각도들) -> USB시리얼 -> XIAO
#  Needs    : pip install pyserial requests
#  Key      : 3가지 중 아무거나 (우선순위 위->아래)
#               1) 코드 상단 CLAUDE_API_KEY / GEMINI_API_KEY 변수
#               2) 같은 폴더의 api_key.txt 파일  <- 추천 (코드엔 안 남음)
#               3) 환경변수 ANTHROPIC_API_KEY / GEMINI_API_KEY
#             PROVIDER 로 Claude/Gemini 선택.
#  Upload   : XIAO 에 day1_3_command.ino 먼저 업로드
#  Run      : python day1_6_LLM_create.py
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
#   1) 이 변수에 직접 붙여넣기
#   2) 같은 폴더의 KEY_FILE(기본: api_key.txt) 에 적어두기  ← 추천(코드엔 안 남음)
#   3) 환경변수 (ANTHROPIC_API_KEY / GEMINI_API_KEY)
CLAUDE_API_KEY = ""        # "sk-ant-..."
GEMINI_API_KEY = ""        # "AIza..."
KEY_FILE = "api_key.txt"   # 이 파일에 키를 적어두면 자동으로 읽음 (남에게 공유 금지!)

# 모델 선택 — 원하는 줄의 주석(#)만 풀고 나머지는 #으로 막기
# CLAUDE_MODEL = "claude-haiku-4-5"    # 가장 빠르고 저렴
CLAUDE_MODEL = "claude-sonnet-5"       # 똑똑+빠름 (각도 생성엔 이 정도 추천)
# CLAUDE_MODEL = "claude-opus-5"       # 가장 똑똑함, 비쌈
# CLAUDE_MODEL = "claude-opus-4-8"     # Opus 계열, 강력

GEMINI_MODEL = "gemini-2.5-flash"      # 빠르고 저렴
# GEMINI_MODEL = "gemini-2.5-pro"      # 더 똑똑, 느리고 비쌈

PORT        = None         # None = 자동탐색
BAUD        = 115200
SER_TIMEOUT = 0.3
CMD_TIMEOUT = 10           # F(각도적용) 응답은 빠름
MAX_FRAMES  = 12           # LLM 이 만드는 키프레임 최대 개수
# --------------------------------------

# LLM 에게 주는 '헤더'(시스템 프롬프트) — 손 구조와 출력 형식을 알려준다.
# 손가락 순서 [엄지, 검지, 중지약지, 새끼].  b=굽힘, s=좌우.
SYSTEM = """너는 4손가락 로봇 손을 직접 움직이는 제어기다.
사용자의 말에 맞는 손 동작을 '키프레임'들로 만들어 JSON 으로만 답한다.

[손 구조]
- 손가락 4개, 순서는 항상 [엄지, 검지, 중지약지, 새끼]
  (사람의 중지와 약지는 이 손에서 '중지약지' 한 손가락으로 합쳐져 있음)
- 각 손가락은 두 값으로 제어한다:
    b (굽힘): -80 = 완전히 폄,  0 = 중립,  +300 = 완전히 접음(주먹)
    s (좌우): -110 ~ +110  (0 = 가운데)
- 값이 범위를 넘으면 하드웨어가 자동으로 안전 제한한다.

[동작 = 키프레임의 연속]
- 키프레임 하나 = 그 순간의 손 모양 + 유지시간(ms):
    {"b":[엄지,검지,중지약지,새끼], "s":[엄지,검지,중지약지,새끼], "t":유지ms}
- 정지 포즈는 키프레임 1개. 움직이는 동작은 여러 개(최대 12개)를 번갈아 만들어 표현.
- t 는 보통 150~500.

[출력 형식]  (다른 텍스트 없이 JSON 만)
{"say":"한 줄 대사", "frames":[ {키프레임}, ... ]}

규칙:
- 너는 귀여운 '로봇'이다. say 는 30자 이내의 짧고 자연스러운 한국어 한 문장
- say 에 어울리는 이모지를 1개 정도 자연스럽게 넣어라 (🤖✋👋✌️ 등)
- 인사/작별에는 손 흔들기 같은 동작
- 숫자는 검지→중지약지→새끼→엄지 순으로 편다. 손가락이 4개라 5 이상은 불가

예시)  (순서 = [엄지, 검지, 중지약지, 새끼])
주먹: {"say":"꽉! ✊","frames":[{"b":[300,300,300,300],"s":[0,0,0,0],"t":500}]}
브이: {"say":"브이! ✌️","frames":[{"b":[300,-80,-80,300],"s":[0,-25,25,0],"t":600}]}
가리키기: {"say":"저기! 👉","frames":[{"b":[300,-80,300,300],"s":[0,0,0,0],"t":600}]}
손흔들기: {"say":"안녕! 👋","frames":[
  {"b":[-80,-80,-80,-80],"s":[-90,90,90,90],"t":250},
  {"b":[-80,-80,-80,-80],"s":[90,-90,-90,-90],"t":250},
  {"b":[-80,-80,-80,-80],"s":[-90,90,90,90],"t":250},
  {"b":[-80,-80,-80,-80],"s":[90,-90,-90,-90],"t":250}]}"""


def build_system():
    return SYSTEM


# ---------------- API 키 파일 읽기 ----------------
def load_key_file():
    """스크립트 옆의 KEY_FILE 에서 키를 읽는다.
       형식: 'NAME = 키' 여러 줄, 또는 키 하나만 적힌 파일도 인식. '#' 줄은 무시."""
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
        json={"model": CLAUDE_MODEL, "max_tokens": 700, "system": system, "messages": history},
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
              "generationConfig": {"maxOutputTokens": 700, "temperature": 0.7}},
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


def parse_response(text):
    """LLM 응답 JSON -> (say, frames).  frames = [ (b[4], s[4], t_ms), ... ]"""
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
        say = str(d.get("say", ""))
        frames = []
        for fr in (d.get("frames") or [])[:MAX_FRAMES]:
            b, sw = fr.get("b"), fr.get("s")
            if isinstance(b, list) and isinstance(sw, list) and len(b) == 4 and len(sw) == 4:
                b = [int(x) for x in b]
                sw = [int(x) for x in sw]
                ms = int(fr.get("t", 300))
                frames.append((b, sw, max(50, min(3000, ms))))
        if frames:
            return say or "네!", frames
    except Exception:
        pass
    return "음... 잘 모르겠어요 🤖", [([0, 0, 0, 0], [0, 0, 0, 0], 400)]


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


def play_frames(ser, frames):
    """키프레임들을 순서대로 손에 적용 (각 프레임 = F 명령 + 유지시간)."""
    for (b, sw, ms) in frames:
        cmd = "F " + ",".join(str(x) for x in (b + sw))
        send_hand(ser, cmd)
        time.sleep(ms / 1000.0)


# ---------------- 메인 ----------------
def main():
    ser = open_hand()
    print("=" * 50)
    print(f"  Amazing Hand - {PROVIDER.upper()} 각도 생성 제어")
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

            say, frames = parse_response(raw)
            print(f"로봇 > {say}   ({len(frames)}프레임)")
            play_frames(ser, frames)
    finally:
        send_hand(ser, "N")
        ser.close()
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
