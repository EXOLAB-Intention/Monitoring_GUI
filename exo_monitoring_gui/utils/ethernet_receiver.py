import socket
import struct

# === Configuration ===
LISTEN_IP = '0.0.0.0'
LISTEN_PORT = 5001
li = []
pmmg_l = None
fsr_l = None
emg_l = None
imu_l = None
# ======================

def recv_all(sock, size):
    """Block until exactly `size` bytes have been received."""
    data = b''
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError("Client disconnected")
        data += packet
    return data

def decode_config(data):
    """Decode the initial SensorConfig packet."""
    global pmmg_l, fsr_l, emg_l, imu_l
    # Channel counts: pmmg, fsr, imu, emg (uint8 each)
    pmmg, fsr, imu, emg = struct.unpack('>4B', data[0:4])
    # CRC check (uint32)
    recv_crc = struct.unpack('>I', data[4:8])[0]
    calc_crc = sum(data[0:4]) & 0xFFFFFFFF
    
    # imu représente le nombre de VALEURS d'IMU, pas le nombre d'IMUs
    # Un IMU unique a généralement 4 valeurs (w,x,y,z)
    num_actual_imus = imu // 4
    
    print(f"[INFO] Received SensorConfig: {pmmg} pMMG, {fsr} FSR, {imu} IMU values ({num_actual_imus} IMUs), {emg} EMG")
    pmmg_l = pmmg
    fsr_l = fsr
    emg_l = emg
    imu_l = num_actual_imus
    return {
        'pmmg': pmmg,
        'fsr': fsr,
        'imu': imu,
        'emg': emg,
        'num_actual_imus': num_actual_imus,
        'crc_valid': (recv_crc == calc_crc)
    }

def decode_packet(data, cfg):
    """Decode one sensor+controller data packet using the given config."""
    offset = 0
    # Timestamp (uint32)
    timestamp = struct.unpack_from('>I', data, offset)[0]
    offset += 4

    # pMMG channels
    pmmg = []
    for _ in range(len(cfg['pmmg_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        pmmg.append(raw / 10000.0)
        offset += 2

    # FSR channels
    fsr = []
    for _ in range(len(cfg['fsr_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        fsr.append(raw / 10000.0)
        offset += 2

    # IMU quaternions (w, x, y, z per unit)
    imu = []
    for _ in range(len(cfg['imu_ids'])):
        w = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        x = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        y = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        z = struct.unpack_from('>h', data, offset)[0] / 10000.0; offset += 2
        imu.append((w, x, y, z))

    # EMG channels
    emg = []
    for _ in range(len(cfg['emg_ids'])):
        raw = struct.unpack_from('>h', data, offset)[0]
        emg.append(raw / 10000.0)
        offset += 2

    # Buttons (5 bytes, each as uint8)
    btn_raw = struct.unpack_from('>5B', data, offset)
    button_labels = ['A', 'B', 'X', 'Y', 'OK']
    buttons = {label: bool(val) for label, val in zip(button_labels, btn_raw)}
    offset += 5

    # Joystick (2 × int16)
    joystick_x, joystick_y = struct.unpack_from('>2h', data, offset)
    offset += 4

    # CRC (uint32)
    recv_crc = struct.unpack_from('>I', data, offset)[0]
    calc_crc = sum(data[:offset]) & 0xFFFFFFFF
    valid_crc = (recv_crc == calc_crc)

    

    return {
        'timestamp_ms': timestamp,
        'pmmg': pmmg,
        'fsr': fsr,
        'imu': imu,
        'emg': emg,
        'buttons': buttons,
        'joystick': (joystick_x, joystick_y),
        'crc_valid': valid_crc
    }



def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((LISTEN_IP, LISTEN_PORT))
    server.listen(1)
    print(f"[INFO] Listening on {LISTEN_IP}:{LISTEN_PORT}...")

    conn, addr = server.accept()
    print(f"[INFO] Connection from {addr}")

    try:
        # --- 1) Read the 4-byte lengths header ---
        hdr = recv_all(conn, 4)
        len_pmmg, len_fsr, len_imu, len_emg = struct.unpack('>4B', hdr)
        total_ids = len_pmmg + len_fsr + len_imu + len_emg

        # --- 2) Read exactly the ID bytes ---
        id_bytes = recv_all(conn, total_ids)

        # --- 3) Read the 4-byte CRC ---
        crc_bytes = recv_all(conn, 4)
        recv_crc = struct.unpack('>I', crc_bytes)[0]
        calc_crc = (sum(hdr) + sum(id_bytes)) & 0xFFFFFFFF

        if recv_crc != calc_crc:
            print("[ERROR] SensorConfig CRC mismatch")
            return


        # --- 4) Decode each ID list ---
        offset = 0
        pmmg_ids = list(id_bytes[offset:offset+len_pmmg]); offset += len_pmmg
        fsr_ids  = list(id_bytes[offset:offset+len_fsr]);  offset += len_fsr
        raw_imu_ids  = list(id_bytes[offset:offset+len_imu]);  offset += len_imu
        emg_ids  = list(id_bytes[offset:offset+len_emg])

        # Traitement des IDs IMU
        # Chaque IMU occupe 4 positions consécutives dans raw_imu_ids (pour w,x,y,z)
        # Nous ne gardons que l'ID principal (première position) de chaque groupe de 4
        num_imus = len(raw_imu_ids) // 4
        if num_imus > 0:
            imu_ids = []
            for i in range(num_imus):
                # Extraire l'ID de l'IMU à partir du premier octet de chaque groupe de 4
                imu_id = raw_imu_ids[i*4]
                imu_ids.append(imu_id)
                
                # Vérifier que les quatre octets du même IMU ont le même ID
                group_ids = raw_imu_ids[i*4:i*4+4]
                if len(set(group_ids)) > 1:
                    print(f"[WARNING] IMU {i+1} a des IDs différents pour ses composantes: {group_ids}")
                else:
                    print(f"[INFO] IMU {i+1} détecté avec ID {imu_id} (composantes w,x,y,z)")
        else:
            imu_ids = []
            print("[INFO] Aucun IMU détecté")

        cfg = {
            'pmmg_ids': pmmg_ids,
            'fsr_ids':  fsr_ids,
            'imu_ids':  imu_ids,
            'emg_ids':  emg_ids,
        }
        print(f"[INFO] Received SensorConfig: {cfg}")

        # --- 5) Compute data-packet size from the actual counts ---
        packet_size = (
            4 +                             # timestamp
            len(pmmg_ids)*2 +               # pmmg
            len(fsr_ids)*2 +                # fsr
            len(imu_ids)*4*2 +              # imu (4 values × int16)
            len(emg_ids)*2 +                # emg
            5 +                             # buttons
            4 +                             # joystick
            4                               # CRC
        )

        
        
        while True:
            data = recv_all(conn, packet_size)
            parsed = decode_packet(data, cfg)

            # construct dynamic output line
            output = f"[{parsed['timestamp_ms']} ms] "

            # pMMG sensors
            for sid, val in zip(cfg['pmmg_ids'], parsed['pmmg']):
                output += f"pMMG{sid}={val:.3f} "

            # FSR sensors
            for sid, val in zip(cfg['fsr_ids'], parsed['fsr']):
                output += f"FSR{sid}={val:.3f} "

            # IMU sensors
            for sid, (w, x, y, z) in zip(cfg['imu_ids'], parsed['imu']):
                output += f"IMU{sid}=(w={w:.4f},x={x:.4f},y={y:.4f},z={z:.4f}) "

            # EMG sensors
            for sid, val in zip(cfg['emg_ids'], parsed['emg']):
                output += f"EMG{sid}={val:.3f} "

            # Buttons
            buttons = parsed['buttons']
            btn_str = " ".join(f"{name}={int(state)}" for name, state in buttons.items())
            output += f"Buttons: {btn_str} "

            # Joystick
            jx, jy = parsed['joystick']
            output += f"Joystick: X={jx},Y={jy}"

            li.append(output)
        
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        conn.close()
        server.close()
        print("[INFO] Server closed.")

if __name__ == '__main__':
    start_server()