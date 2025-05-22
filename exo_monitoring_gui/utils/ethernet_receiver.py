#!/usr/bin/env python3
import socket
import struct
import time  # for internal timing

# === Configuration ===
LISTEN_IP       = '0.0.0.0'
LISTEN_PORT     = 5001
TRIAL_END_MARKER = b'\x4E' # MOD01 : Added trial end marker

def recv_all(sock, size):
    """Block until exactly `size` bytes have been received."""
    data = b''
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError("Client disconnected")
        data += packet
    return data

def decode_packet(data, cfg):
    """Decode one sensor+controller data packet."""
    offset = 0
    ts = struct.unpack_from('>I', data, offset)[0]; offset += 4

    pmmg = []
    for _ in range(len(cfg['pmmg_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        pmmg.append(raw / 10000.0); offset += 2

    fsr = []
    for _ in range(len(cfg['fsr_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        fsr.append(raw / 10000.0); offset += 2

    imu = []
    for _ in range(len(cfg['imu_ids'])):
        w = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        x = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        y = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        z = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        imu.append((w, x, y, z))

    emg = []
    for _ in range(len(cfg['emg_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        emg.append(raw / 10000.0); offset += 2

    btn_raw = struct.unpack_from('>5B', data, offset)
    buttons = dict(zip(['A','B','X','Y','OK'], [bool(v) for v in btn_raw]))
    offset += 5

    jx, jy = struct.unpack_from('>2h', data, offset)
    offset += 4

    recv_crc = struct.unpack_from('>I', data, offset)[0]
    calc_crc = sum(data[:offset]) & 0xFFFFFFFF
    return {
        'timestamp_ms': ts,
        'pmmg': pmmg,
        'fsr': fsr,
        'imu': imu,
        'emg': emg,
        'buttons': buttons,
        'joystick': (jx, jy),
        'crc_valid': (recv_crc == calc_crc)
    }

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Good practice
    server.bind((LISTEN_IP, LISTEN_PORT))
    server.listen(1)
    print(f"[INFO] Listening on {LISTEN_IP}:{LISTEN_PORT}...")

    ## MOD02 : Revised the logic for receiving config (retry logic added)
    try:
        while True:
            try:
                conn, addr = server.accept()
            ## MOD05 : Add keyboard interrupt (but not working sometimes...)    
            except KeyboardInterrupt:
                print("\n[INFO] Shutting down server.")
                break
            print(f"[INFO] Connection from {addr}")

            try:
                # Configuration reception loop (as per user's MOD02)
                while True:
                    while True:
                        hdr = recv_all(conn, 4)
                        lp, lf, li, le = struct.unpack('>4B', hdr)
                        total = lp + lf + li + le
                        ids = recv_all(conn, total)
                        crc_bytes = recv_all(conn, 4)
                        recv_crc = struct.unpack('>I', crc_bytes)[0]
                        if recv_crc != ((sum(hdr) + sum(ids)) & 0xFFFFFFFF):
                            print("[ERROR] SensorConfig CRC mismatch, retrying...")
                            continue
                        break # CRC OK

                    # decode IDs
                    offset = 0
                    pmmg_ids    = list(ids[offset:offset+lp]); offset += lp
                    fsr_ids     = list(ids[offset:offset+lf]); offset += lf
                    raw_imu_ids = list(ids[offset:offset+li]); offset += li
                    emg_ids     = list(ids[offset:offset+le])
                    num_imus = len(raw_imu_ids) // 4
                    imu_ids = [raw_imu_ids[i*4] for i in range(num_imus)]

                    cfg = {
                        'pmmg_ids': pmmg_ids,
                        'fsr_ids':  fsr_ids,
                        'imu_ids':  imu_ids,
                        'emg_ids':  emg_ids,
                        # Adding these for completeness, similar to what receive_initial_config_from_client did
                        'raw_imu_ids': raw_imu_ids,
                        'len_pmmg': lp,
                        'len_fsr': lf,
                        'len_imu': li, # This is len_imu_components
                        'len_emg': le,
                        'num_imus': num_imus
                    }
                    print(f"[INFO] Received SensorConfig: { {k: v for k,v in cfg.items() if k in ['pmmg_ids', 'fsr_ids', 'imu_ids', 'emg_ids']} }")

                    # calculate packet size
                    packet_size = (
                        4 +             # timestamp
                        len(pmmg_ids)*2 + # pmmg
                        len(fsr_ids)*2 +  # fsr
                        len(imu_ids)*4*2 +# imu (4 values × int16)
                        len(emg_ids)*2 +  # emg
                        5 +             # buttons
                        4 +             # joystick
                        4               # CRC
                    )
                    break # Config received and processed, exit config loop

                ## MOD03 : Read data packets until trial-end marker
                while True:
                    first = conn.recv(1)
                    if not first:
                        raise ConnectionError("Client disconnected")
                  
                    
                    if packet_size <= 1:
                        print(f"[ERROR] Invalid packet size {packet_size} in start_server. Cannot read rest of packet.")
                        raise ValueError("Calculated packet size is too small for a data packet.")
                        
                    rest = recv_all(conn, packet_size - 1)
                    data = first + rest
                    parsed = decode_packet(data, cfg)

                    print(
                        f"[sensor_ts={parsed['timestamp_ms']} ms] "
                        f"pMMG={parsed['pmmg']} FSR={parsed['fsr']} "
                        f"IMU={parsed['imu']} EMG={parsed['emg']} "
                        f"Buttons={parsed['buttons']} "
                        f"Joystick={parsed['joystick']} CRC_OK={parsed['crc_valid']}"
                    )

            except ConnectionError as e:
                print(f"[ERROR] {e}")
            except ValueError as e:
                print(f"[ERROR] Value error with {addr}: {e}")
            except Exception as e:
                print(f"[ERROR] Unexpected error with client {addr}: {e}")
            finally:
                ## MOD04 : Print different message
                conn.close()
                print("[INFO] Connection closed, waiting for new connection...")

    finally:
        server.close()
        print("[INFO] Server shut down.")

if __name__ == '__main__':
    start_server()