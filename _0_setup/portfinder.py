"""
Waveshare 서보 어댑터 포트 자동 탐지 (하드코딩 대신).
맥: /dev/cu.wchusbserial... / usbserial / usbmodem,  윈도우: COMx
사용:  from portfinder import find_port ;  PORT = find_port()
"""
from serial.tools import list_ports


def find_port(prefer=None):
    cands = []
    for p in list_ports.comports():
        d = p.device
        if ("wchusb" in d or "usbserial" in d or "usbmodem" in d
                or d.upper().startswith("COM")):
            cands.append(d)
    if prefer and prefer in cands:
        return prefer
    if not cands:
        raise RuntimeError(
            "❌ Waveshare 포트를 못 찾음 — USB(USB모드) 연결 + VCP 드라이버 확인")
    if len(cands) > 1:
        print("여러 포트 발견:", cands, "→ 첫 번째 사용:", cands[0])
    return cands[0]
