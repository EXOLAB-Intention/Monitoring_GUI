#!/usr/bin/env python3
import socket
import os
import sys
import time

# ——— Configuration (fixed to script’s folder) ———
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = "C:\\Users\\sidib\\Documents\\GitHub\\Monitoring_GUI\\datas\\recuperation"
SERVER_IP  = '192.168.4.1'        # Jetson AP 기본 IP
PORT       = 5002                 # file_sender_node 포트

def request_files():
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        print(f"[INFO] Connecting to {SERVER_IP}:{PORT}…")
        with socket.create_connection((SERVER_IP, PORT), timeout=10) as s:
            # 파일 개수 수신
            raw = b''
            while not raw.endswith(b'\n'):
                raw += s.recv(1)
            num = int(raw.decode().strip())
            print(f"[INFO] Server will send {num} file(s)")

            for i in range(num):
                # “filename|size\n” 헤더
                header = b''
                while not header.endswith(b'\n'):
                    header += s.recv(1)
                fname, fsize = header.decode().strip().split('|')
                fsize = int(fsize)

                dst = os.path.join(OUT_DIR, fname)
                print(f"[INFO] Receiving ({i+1}/{num}): {fname} ({fsize} bytes)")

                with open(dst, 'wb') as f:
                    rem = fsize
                    while rem > 0:
                        chunk = s.recv(min(4096, rem))
                        if not chunk:
                            raise ConnectionError("Transfer interrupted")
                        f.write(chunk)
                        rem -= len(chunk)

                print(f"[INFO] Saved → {dst}")

        print("[INFO] All files received.")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

if __name__ == '__main__':
    request_files()
