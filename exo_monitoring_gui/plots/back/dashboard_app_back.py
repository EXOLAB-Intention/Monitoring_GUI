import sys
import os
import time
import numpy as np
import json
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import pyqtgraph as pg
import socket
import struct
import threading

# Ajouter le chemin du répertoire parent de data_generator au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.ethernet_receiver import recv_all, decode_packet
from plots.model_3d_viewer import Model3DWidget # Garder pour la logique 3D

class EthernetServerThread(QThread):
    connection_ready = pyqtSignal(tuple)
    server_error = pyqtSignal(str)
    server_started = pyqtSignal()

    def __init__(self, listen_ip='0.0.0.0', listen_port=5001):
        super().__init__()
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.server_socket = None
        self.running = False

    def run(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.listen_ip, self.listen_port))
            self.server_socket.listen(1)
            self.running = True
            
            print(f"[INFO] Server started on {self.listen_ip}:{self.listen_port}")
            self.server_started.emit()
            
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"[INFO] Client connected from {addr}")
                        self.connection_ready.emit((client_socket, addr))
                        break
                    except socket.timeout:
                        continue
                except Exception as e:
                    if self.running:
                        self.server_error.emit(f"Error accepting client: {str(e)}")
                    break
                
        except Exception as e:
            self.server_error.emit(f"Server error: {str(e)}")
        finally:
            self.cleanup()

    def stop(self):
        self.running = False
        self.cleanup()
        self.wait()

    def cleanup(self):
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

class ClientInitThread(QThread):
    init_success = pyqtSignal(dict, int)
    init_error = pyqtSignal(str)

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        
    def run(self):
        try:
            hdr = recv_all(self.client_socket, 4)
            len_pmmg, len_fsr, len_imu, len_emg = struct.unpack('>4B', hdr)
            total_ids = len_pmmg + len_fsr + len_imu + len_emg
            id_bytes = recv_all(self.client_socket, total_ids)
            crc_bytes = recv_all(self.client_socket, 4)
            # recv_crc = struct.unpack('>I', crc_bytes)[0] # CRC non utilisé pour l'instant
            
            offset = 0
            pmmg_ids = list(id_bytes[offset:offset+len_pmmg]); offset += len_pmmg
            fsr_ids = list(id_bytes[offset:offset+len_fsr]); offset += len_fsr
            raw_imu_ids = list(id_bytes[offset:offset+len_imu]); offset += len_imu
            emg_ids = list(id_bytes[offset:offset+len_emg])

            num_imus = len(raw_imu_ids) // 4
            imu_ids = []
            if num_imus > 0:
                for i in range(num_imus):
                    imu_id = raw_imu_ids[i*4]
                    imu_ids.append(imu_id)
                    print(f"[INFO] IMU {i+1} détecté avec ID {imu_id} (composantes w,x,y,z)")
            else:
                print("[INFO] Aucun IMU détecté")

            sensor_config = {
                'pmmg_ids': pmmg_ids,
                'fsr_ids': fsr_ids,
                'imu_ids': imu_ids,
                'raw_imu_ids': raw_imu_ids,
                'emg_ids': emg_ids,
                'len_pmmg': len_pmmg,
                'len_fsr': len_fsr,
                'len_imu': len_imu,
                'len_emg': len_emg,
                'num_imus': num_imus
            }

            packet_size = (
                4 +
                len(pmmg_ids)*2 +
                len(fsr_ids)*2 +
                len(imu_ids)*4*2 +
                len(emg_ids)*2 +
                5 +
                4 +
                4
            )
            
            self.init_success.emit(sensor_config, packet_size)
            
        except Exception as e:
            self.init_error.emit(f"Failed to initialize client: {str(e)}")
            try:
                if self.client_socket:
                    self.client_socket.close()
            except:
                pass

class DashboardAppBack:
    def __init__(self, ui):
        self.ui = ui  # Référence à l'interface utilisateur (DashboardApp)
        self.server_thread = None
        self.client_socket = None
        self.sensor_config = None
        self.packet_size = 0
        self.is_server_running = False
        self.recording = False
        self.recording_stopped = False
        self.recorded_data = {
            "EMG": [[] for _ in range(8)],
            "IMU": [[] for _ in range(1)],
            "pMMG": [[] for _ in range(8)]
        }
        self.emg_mappings = {}
        self.pmmg_mappings = {}
        self.plot_data = {} # Pour les données en temps réel des graphiques individuels
        self.group_plot_data = {} # Pour les données en temps réel des graphiques groupés

        self.timer = QTimer() # Pas de self.ui ici, QTimer n'a pas besoin d'un parent direct pour fonctionner
        self.timer.timeout.connect(self.update_data)
        # self.timer.start(40) # Le démarrage du timer sera géré par l'UI

    def connect_sensors(self):
        if not self.is_server_running:
            try:
                self.server_thread = EthernetServerThread()
                self.server_thread.connection_ready.connect(self.on_client_connected)
                self.server_thread.server_error.connect(self.on_server_error)
                self.server_thread.server_started.connect(self.on_server_started)
                self.server_thread.start()
                self.ui.connect_button.setText("Starting...")
                self.ui.connect_button.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self.ui, "Server Error", f"Could not start Ethernet server: {str(e)}")
        else:
            self.stop_ethernet_server()
            self.ui.connect_button.setText("Connect")
            self.ui.reset_sensor_display() # L'UI gère la mise à jour de l'arbre

    def on_server_started(self):
        self.is_server_running = True
        self.ui.connect_button.setText("Waiting for device...")
        QMessageBox.information(self.ui, "Server Started", 
                               "Ethernet server started successfully. Waiting for device connection...")

    def on_client_connected(self, client_info):
        client_socket, addr = client_info
        self.client_socket = client_socket
        
        self.client_init_thread = ClientInitThread(client_socket)
        self.client_init_thread.init_success.connect(self.on_client_init_success)
        self.client_init_thread.init_error.connect(self.on_client_init_error)
        self.client_init_thread.start()
        self.ui.connect_button.setText("Initializing...")

    def on_client_init_success(self, sensor_config, packet_size):
        self.sensor_config = sensor_config
        self.packet_size = packet_size
        
        self.ui.update_sensor_tree_from_config(self.sensor_config) # L'UI met à jour l'arbre
        
        num_imus = self.sensor_config.get('num_imus', 0)
        self.recorded_data["IMU"] = [[] for _ in range(max(1, num_imus))]
        
        self.ui.connect_button.setText("Disconnect")
        self.ui.connect_button.setEnabled(True)
        self.ui.record_button.setEnabled(True)
        
        len_emg = len(self.sensor_config.get('emg_ids', []))
        num_imus = self.sensor_config.get('num_imus', 0)
        len_pmmg = len(self.sensor_config.get('pmmg_ids', []))
        
        QMessageBox.information(self.ui, "Connection Success", 
                               f"Connecté au dispositif ! Détecté {len_emg} EMG, {num_imus} IMU, {len_pmmg} pMMG.")

    def on_client_init_error(self, error_msg):
        print(f"[ERROR] {error_msg}")
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        self.ui.connect_button.setText("Connect")
        self.ui.connect_button.setEnabled(True)
        QMessageBox.critical(self.ui, "Connection Error", error_msg)

    def on_server_error(self, error_msg):
        print(f"[ERROR] {error_msg}")
        self.ui.connect_button.setText("Connect")
        self.ui.connect_button.setEnabled(True)
        self.is_server_running = False
        QMessageBox.critical(self.ui, "Server Error", error_msg)

    def stop_ethernet_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
            self.server_thread = None
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        self.is_server_running = False
        self.sensor_config = None
        self.packet_size = 0
        print("[INFO] Ethernet server stopped.")
        self.ui.reset_sensor_display()


    def update_data(self):
        if self.recording:
            if self.client_socket and self.sensor_config and self.packet_size > 0:
                try:
                    data_packet = recv_all(self.client_socket, self.packet_size)
                    packet = decode_packet(data_packet, self.sensor_config)
                    
                    if not packet['crc_valid']:
                        print("[WARNING] Invalid CRC for data packet. Checking data validity...")
                        if not hasattr(self, 'corrupted_packets_count'):
                            self.corrupted_packets_count = 0
                        self.corrupted_packets_count += 1
                        if self.corrupted_packets_count > 5:
                            print("[ERROR] Too many corrupted packets in a row. Data may be unreliable.")
                            self.corrupted_packets_count = 0
                            return
                        if self._contains_invalid_data(packet):
                            print("[WARNING] Packet contains invalid data. Skipping.")
                            return
                    else:
                        self.corrupted_packets_count = 0

                    # Enregistrement des données
                    if 'emg' in packet and packet['emg']:
                        for i, emg_id in enumerate(self.sensor_config.get('emg_ids', [])):
                            if i < len(packet['emg']) and i < len(self.recorded_data["EMG"]):
                                value = packet['emg'][i]
                                if -10.0 <= value <= 10.0:
                                    self.recorded_data["EMG"][i].append(value)
                    
                    if 'pmmg' in packet and packet['pmmg']:
                        for i, pmmg_id in enumerate(self.sensor_config.get('pmmg_ids', [])):
                            if i < len(packet['pmmg']) and i < len(self.recorded_data["pMMG"]):
                                value = packet['pmmg'][i]
                                if -10.0 <= value <= 10.0:
                                    self.recorded_data["pMMG"][i].append(value)
                    
                    if 'imu' in packet and packet['imu']:
                        for i, imu_id in enumerate(self.sensor_config.get('imu_ids', [])):
                            if i < len(packet['imu']) and i < len(self.recorded_data["IMU"]):
                                quaternion = packet['imu'][i]
                                if self._is_valid_quaternion(quaternion):
                                    self.recorded_data["IMU"][i].append(quaternion)
                                    try:
                                        # La mise à jour du modèle 3D doit se faire via l'UI
                                        self.ui.model_3d_widget.apply_imu_data(imu_id, quaternion)
                                    except Exception as e:
                                        print(f"Error updating 3D model: {e}")
                    
                    # Mise à jour des graphiques (gérée par l'UI)
                    self.ui.update_live_plots(packet) # Nouvelle méthode dans l'UI
                                        
                except ConnectionResetError:
                    print("[ERROR] Connection reset by peer.")
                    self.client_socket = None
                    self.ui.connect_button.setText("Connect")
                    QMessageBox.warning(self.ui, "Connection Lost", "Connection to the device was reset.")
                except struct.error as e:
                    print(f"[ERROR] Struct unpacking error: {e}. Packet size may be incorrect.")
                    try:
                        extra_bytes = self.client_socket.recv(16, socket.MSG_DONTWAIT)
                        print(f"[INFO] Read {len(extra_bytes)} extra bytes to try to resynchronize.")
                    except:
                        pass
                except socket.timeout:
                    print("[WARNING] Socket timeout while receiving data.")
                except Exception as e:
                    print(f"[ERROR] Failed to receive/process data: {e}")
            else:
                if self.recording and not self.client_socket:
                    print("[WARNING] Recording active but no Ethernet connection.")
    
    def _contains_invalid_data(self, packet):
        for value in packet.get('emg', []):
            if not isinstance(value, (int, float)) or abs(value) > 10.0: return True
        for value in packet.get('pmmg', []):
            if not isinstance(value, (int, float)) or abs(value) > 10.0: return True
        for i, quaternion in enumerate(packet.get('imu', [])):
            if not self._is_valid_quaternion(quaternion):
                print(f"[DEBUG] IMU {i} quaternion invalide: {quaternion}")
                return True
        return False
        
    def _is_valid_quaternion(self, quaternion):
        if not isinstance(quaternion, (list, tuple)) or len(quaternion) != 4:
            print(f"[DEBUG] Format quaternion invalide: {type(quaternion)}, longueur: {len(quaternion) if hasattr(quaternion, '__len__') else 'N/A'}")
            return False
        for i, component in enumerate(quaternion):
            if not isinstance(component, (int, float)):
                print(f"[DEBUG] Composante {i} non numérique: {type(component)}")
                return False
            if abs(component) > 100.0:
                print(f"[DEBUG] Valeur aberrante dans quaternion: composante {i} = {component}")
                return False
        return True

    def start_recording(self):
        self.recording = True
        self.recording_stopped = False
        
        num_imus = self.sensor_config.get('num_imus', 0) if self.sensor_config else 0
        if num_imus == 0:
            print("[WARNING] Aucun IMU détecté, initialisation avec 1 IMU par défaut")
            num_imus = 1
            
        self.recorded_data = {
            "EMG": [[] for _ in range(8)],
            "IMU": [[] for _ in range(num_imus)],
            "pMMG": [[] for _ in range(8)]
        }
        
        print(f"[INFO] Début de l'enregistrement avec {num_imus} IMUs")
        self.ui.record_button.setText("Record Stop")
        self.timer.start(40) # Démarrer le timer ici

    def stop_recording(self):
        self.recording = False
        self.recording_stopped = True
        self.timer.stop() # Arrêter le timer ici
        self.ui.record_button.setText("Record Start")
        self.ui.record_button.setStyleSheet("""
        QPushButton {
            background-color: #4caf50; /* ... styles ... */
        } 
        /* ... autres styles ... */
        """) # Le style complet est dans l'UI
        self.ui.record_button.setEnabled(False)
        self.ui.show_recorded_data_on_plots(self.recorded_data) # L'UI gère l'affichage

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            if not self.client_socket and not self.is_server_running:
                QMessageBox.warning(self.ui, "Not Connected", 
                                   "Please connect to a device before starting recording.")
                return
            if self.ui.record_button.isEnabled(): # Vérifier si le bouton est actif dans l'UI
                self.start_recording()

    # Les méthodes de gestion des mappings (save, load, default) restent ici car elles sont purement logiques
    def save_mappings(self):
        # Utiliser self.ui.model_3d_widget pour accéder aux mappings IMU
        mappings = {
            'EMG': self.emg_mappings,
            'IMU': self.ui.model_3d_widget.get_current_mappings(),
            'pMMG': self.pmmg_mappings
        }
        serializable_mappings = {}
        for sensor_type, mapping in mappings.items():
            serializable_mappings[sensor_type] = {str(k): v for k, v in mapping.items()}
        
        filepath = os.path.join(os.path.dirname(__file__), '../sensor_mappings.json') # Ajuster le chemin
        try:
            with open(filepath, 'w') as f:
                json.dump(serializable_mappings, f, indent=2)
            print(f"Mappings saved to {filepath}")
        except Exception as e:
            print(f"Error saving mappings: {e}")


    def load_mappings(self):
        filepath = os.path.join(os.path.dirname(__file__), '../sensor_mappings.json') # Ajuster le chemin
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    mappings = json.load(f)
                
                if 'EMG' in mappings:
                    self.emg_mappings = {int(k): v for k, v in mappings['EMG'].items()}
                if 'pMMG' in mappings:
                    self.pmmg_mappings = {int(k): v for k, v in mappings['pMMG'].items()}
                    
                if 'IMU' in mappings:
                    # La mise à jour du modèle 3D doit passer par l'UI
                    self.ui.apply_imu_mappings({int(k): v for k, v in mappings['IMU'].items()})

                # Demander à l'UI de rafraîchir l'arbre des capteurs
                self.ui.refresh_sensor_tree_with_mappings(self.emg_mappings, self.pmmg_mappings) # Nouvelle méthode dans l'UI
                print(f"Mappings loaded from {filepath}")
                return True
            except Exception as e:
                print(f"Error loading mappings: {e}")
        return False

    def update_sensor_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        """Mettre à jour les mappages de capteurs après fermeture du dialogue"""
        # Mettre à jour les mappages IMU via l'UI
        self.ui.apply_imu_mappings(imu_mappings)
        
        self.emg_mappings = emg_mappings
        self.pmmg_mappings = pmmg_mappings
        
        # Mettre à jour les mappages dans le modèle 3D via l'UI
        self.ui.model_3d_widget.model_viewer.set_emg_mapping(emg_mappings)
        self.ui.model_3d_widget.model_viewer.set_pmmg_mapping(pmmg_mappings)
        
        self.ui.refresh_sensor_tree_with_mappings(self.emg_mappings, self.pmmg_mappings)
        self.save_mappings()

    def get_current_mappings_for_dialog(self):
        return {
            'EMG': self.emg_mappings,
            'IMU': self.ui.model_3d_widget.get_current_mappings(),
            'pMMG': self.pmmg_mappings
        }

    def save_as_default_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        self.update_sensor_mappings(emg_mappings, imu_mappings, pmmg_mappings) # Met à jour et sauvegarde les mappings courants
        
        default_mappings = {
            'EMG': emg_mappings,
            'IMU': imu_mappings,
            'pMMG': pmmg_mappings
        }
        serializable_mappings = {}
        for sensor_type, mapping in default_mappings.items():
            serializable_mappings[sensor_type] = {str(k): v for k, v in mapping.items()}
        
        filepath = os.path.join(os.path.dirname(__file__), '../default_sensor_mappings.json') # Ajuster le chemin
        try:
            with open(filepath, 'w') as f:
                json.dump(serializable_mappings, f, indent=2)
            QMessageBox.information(
                self.ui, 
                "Default Saved",
                "Your sensor assignments have been saved as the default configuration."
            )
            print(f"Default mappings saved to {filepath}")
        except Exception as e:
            print(f"Error saving default mappings: {e}")
            QMessageBox.critical(self.ui, "Error", f"Could not save default mappings: {e}")

    def cleanup_on_close(self):
        self.save_mappings()
        self.stop_ethernet_server()

