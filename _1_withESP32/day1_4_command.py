#!/usr/bin/env python3
# ============================================================
#  Amazing Hand  -  Command (직접 제어, LLM 없음)
# ============================================================
#  Author   : yangjipsa
#  Company  : TouchLabs (touchlabs.kr)
#  Version  : 1.0
#  Date     : 2026-08-25
#  Product  : Amazing Hand (SCS0009 · 4손가락 8서보)
#  Purpose  : 번호를 입력하면 로봇 손이 정해진 포즈/모션을 한다.
#             LLM 없이 USB 시리얼로 XIAO(command 펌웨어)를 직접 제어.
#             동작 확인·수업 데모·다음 단계(LLM) 준비용.
#  Needs    : pip install pyserial
#  Upload   : XIAO 에 day1_3_command.ino 먼저 업로드
#             (Arduino 시리얼 모니터는 닫아둘 것)
#  Run      : python day1_4_command.py
#  Protocol : P<n> 포즈 / M<n> 모션 / F .. 자유 / N 중립  -> XIAO 가 OK/ERR
# ------------------------------------------------------------
#  Copyright (c) 2026 TouchLabs.  All rights reserved.
#  This code is the property of TouchLabs and is provided for the
#  Amazing Hand product / education kit. Unauthorized copying,
#  distribution, or modification is prohibited.
# ============================================================

import sys
import glob
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pyserial 이 필요합니다:  pip install pyserial")
    sys.exit(1)

# ---------------- 설정 ----------------
PORT        = None        # None = 자동탐색. 고정하려면 "/dev/cu.usbmodem..." 로.
BAUD        = 115200
SER_TIMEOUT = 0.3
CMD_TIMEOUT = 60          # 긴 모션 완료까지 대기
# --------------------------------------

# 펌웨어(day1_3_command.ino)의 표와 일치
POSES = {
    0: "중립", 1: "하나", 2: "둘", 3: "셋", 4: "넷",
}
MOTIONS = {
    1: "노노", 2: "가위바위보", 3: "박수", 4: "따봉", 5: "브이", 6: "손흔들기",
}  # m1 노노(기본) + m2~6 (STEP 3 바이브 코딩 결과)


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
    time.sleep(2.0)                          # 포트 열 때 XIAO 리셋·부팅 대기
    # 핸드셰이크: N 을 여러 번 보내며 OK/READY 를 기다림
    #  (포트 개방 시 리셋되어 첫 응답이 유실되거나 READY 만 오는 경우 대비)
    ok = False
    for _ in range(8):                       # 최대 약 4초
        ser.reset_input_buffer()
        ser.write(b"N\n")
        end = time.time() + 0.5
        while time.time() < end:
            line = ser.readline().decode(errors="ignore").strip()
            if line in ("OK", "ERR", "READY"):
                ok = True
                break
        if ok:
            break
    print("✅ 손 준비 완료" if ok
          else "⚠️  응답 없음 — day1_3_command 업로드? 시리얼 모니터 닫힘? (그래도 진행)")
    return ser


def send_hand(ser, cmd):
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    return wait_reply(ser, time.time() + CMD_TIMEOUT)


# ---------------- 메뉴 ----------------
def show_menu():
    print("─" * 50)
    print("포즈 p:", " ".join(f"{k}{v}" for k, v in POSES.items()))
    print("모션 m:", " ".join(f"{k}{v}" for k, v in MOTIONS.items()))
    print("기타  : N중립  q종료   (예: p3 / m1)")


def main():
    ser = open_hand()
    print("=" * 50)
    print("  Amazing Hand - 직접 제어")
    print("=" * 50)
    show_menu()
    try:
        while True:
            try:
                s = input("\n입력 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not s:
                continue
            c = s[0].lower()
            arg = s[1:].strip()
            if c == 'q':
                break
            elif c == 'n':
                send_hand(ser, "N"); print("▶ 중립")
            elif c == 'p':
                n = int(arg) if arg.lstrip('-').isdigit() else -1
                if n in POSES:
                    print(f"▶ 포즈 {n} · {POSES[n]}"); send_hand(ser, f"P{n}")
                else:
                    print("! 없는 포즈 번호")
            elif c == 'm':
                n = int(arg) if arg.lstrip('-').isdigit() else -1
                if n in MOTIONS:
                    print(f"▶ 모션 {n} · {MOTIONS[n]} ...", flush=True)
                    print("  완료" if send_hand(ser, f"M{n}") else "  ! 응답 없음")
                else:
                    print("! 없는 모션 번호")
            else:
                print("! 모르는 명령 (예: p3 / m1 / N)")
            show_menu()          # 실행 후 메뉴 다시 표시
    finally:
        send_hand(ser, "N")
        ser.close()
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
