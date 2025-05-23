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
from utils.ethernet_receiver import recv_all, decode_packet, TRIAL_END_MARKER
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
            # Logique d'initialisation (précédemment dans receive_initial_config_from_client)
            # Cette logique est basée sur la section MOD02 de start_server du user
            while True: # Boucle pour la config avec retry CRC
                hdr = recv_all(self.client_socket, 4) # lp, lf, li, le lengths
                len_pmmg, len_fsr, len_imu_components, len_emg = struct.unpack('>4B', hdr)
                total_ids_to_read = len_pmmg + len_fsr + len_imu_components + len_emg

                ids_data = recv_all(self.client_socket, total_ids_to_read)
                
                crc_bytes = recv_all(self.client_socket, 4)
                received_config_crc = struct.unpack('>I', crc_bytes)[0]
                
                calculated_config_crc = (sum(hdr) + sum(ids_data)) & 0xFFFFFFFF
                
                if received_config_crc != calculated_config_crc:
                    print("[ERROR] ClientInitThread: SensorConfig CRC mismatch, retrying...")
                    # Dans un contexte de thread, un simple continue peut boucler rapidement
                    # S'assurer que le client a une chance de renvoyer ou gérer le timeout
                    # Pour l'instant, on suppose que recv_all lèvera une exception en cas de problème majeur
                    time.sleep(0.1) # Petite pause pour éviter de surcharger en cas de boucle rapide
                    continue 
                print("[INFO] ClientInitThread: SensorConfig CRC OK.")
                break # CRC OK, sortir de la boucle de config

            # Décodage des IDs (comme dans MOD02)
            offset = 0
            pmmg_ids    = list(ids_data[offset:offset+len_pmmg]); offset += len_pmmg
            fsr_ids     = list(ids_data[offset:offset+len_fsr]);  offset += len_fsr
            raw_imu_ids = list(ids_data[offset:offset+len_imu_components]); offset += len_imu_components
            emg_ids     = list(ids_data[offset:offset+len_emg])

            num_imus = len(raw_imu_ids) // 4
            imu_ids = [] 
            if num_imus > 0:
                for i in range(num_imus):
                    imu_id = raw_imu_ids[i*4]
                    imu_ids.append(imu_id)
                    # Le print détaillé des IMUs est déjà fait dans la config originale, 
                    # on peut le garder léger ici ou le supprimer pour le ClientInitThread
                    print(f"[INFO] ClientInitThread: IMU {i+1} (ID {imu_id}) detected.") 
            else:
                print("[INFO] ClientInitThread: No IMUs detected from config.")

            sensor_config = {
                'pmmg_ids': pmmg_ids,
                'fsr_ids':  fsr_ids,
                'imu_ids':  imu_ids,       
                'emg_ids':  emg_ids,
                'raw_imu_ids': raw_imu_ids, 
                'len_pmmg': len_pmmg,
                'len_fsr':  len_fsr,
                'len_imu':  len_imu_components, 
                'len_emg':  len_emg,
                'num_imus': num_imus
            }
            # Utiliser un format de log similaire à celui de start_server pour la config
            print(f"[INFO] ClientInitThread: Received SensorConfig: { {k: v for k,v in sensor_config.items() if k in ['pmmg_ids', 'fsr_ids', 'imu_ids', 'emg_ids']} }")

            # Calcul de la taille des paquets (comme dans MOD02)
            packet_size = (
                4 +                             # timestamp (uint32)
                len(pmmg_ids)*2 +               # pMMG data (int16 per channel)
                len(fsr_ids)*2 +                # FSR data (int16 per channel)
                len(imu_ids)*4*2 +              # IMU data (4 components * int16 per IMU unit)
                len(emg_ids)*2 +                # EMG data (int16 per channel)
                5 +                             # buttons (5 * uint8)
                4 +                             # joystick (2 * int16)
                4                               # CRC (uint32)
            )
            print(f"[INFO] ClientInitThread: Calculated data packet size: {packet_size}")
            self.init_success.emit(sensor_config, packet_size)
            
        except ConnectionError as e: 
            error_msg = f"Client disconnected during initialization: {str(e)}"
            print(f"[ERROR] {error_msg}")
            self.init_error.emit(error_msg)
            try:
                if self.client_socket:
                    self.client_socket.close()
            except: pass
        except Exception as e:
            error_msg = f"Failed to initialize client: {str(e)}"
            print(f"[ERROR] {error_msg}")
            self.init_error.emit(error_msg)
            try:
                if self.client_socket:
                    self.client_socket.close()
            except: pass

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
        
        try:
            from utils.Menu_bar import MainBar
            self.main_bar_re = MainBar(self.ui)
        except Exception as e:
            print(f"Error initializing MainBar: {e}")
            self.main_bar_re = None

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
        
        # Mettre à jour l'interface avec les capteurs disponibles
        self.ui.update_sensor_tree_from_config(self.sensor_config)
        
        num_imus = self.sensor_config.get('num_imus', 0)
        self.recorded_data["IMU"] = [[] for _ in range(max(1, num_imus))]
        
        self.ui.connect_button.setText("Disconnect")
        self.ui.connect_button.setEnabled(True)
        self.ui.record_button.setEnabled(True)
        
        len_emg = len(self.sensor_config.get('emg_ids', []))
        num_imus = self.sensor_config.get('num_imus', 0)
        len_pmmg = len(self.sensor_config.get('pmmg_ids', []))

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
                    # Lire le premier octet pour vérifier le TRIAL_END_MARKER
                    first_byte = self.client_socket.recv(1)
                    if not first_byte:
                        raise ConnectionError("Client disconnected (recv returned empty)")

                    if first_byte == TRIAL_END_MARKER:
                        print("[INFO] Trial end marker received by DashboardAppBack.")
                        self.handle_trial_end()
                        return # Arrêter le traitement pour ce cycle

                    # Lire le reste du paquet
                    if self.packet_size <= 1:
                        print(f"[ERROR] Invalid packet_size {self.packet_size} in DashboardAppBack, cannot read rest of packet.")
                        # Gérer l'erreur, peut-être déconnecter ou afficher un message
                        self.handle_connection_error("Invalid packet size detected")
                        return
                        
                    remaining_bytes_to_read = self.packet_size - 1
                    if remaining_bytes_to_read < 0:
                        print(f"[ERROR] Negative remaining bytes ({remaining_bytes_to_read}) in DashboardAppBack. Packet size: {self.packet_size}")
                        self.handle_connection_error("Invalid packet calculation detected")
                        return

                    rest_of_packet = recv_all(self.client_socket, remaining_bytes_to_read)
                    data_packet = first_byte + rest_of_packet
                    
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
                                    except AttributeError: # model_3d_widget might not be ready
                                        print(f"[WARNING] model_3d_widget not available for IMU update.")
                                    except Exception as e:
                                        print(f"Error updating 3D model: {e}")
                    
                    # Mise à jour des graphiques (gérée par l'UI)
                    self.ui.update_live_plots(packet) # Nouvelle méthode dans l'UI
                                        
                    self.ui.reset_sensor_display()
                    self.ui.connect_button.setText("Connect")
                    self.ui.connect_button.setEnabled(True)
                    self.ui.record_button.setEnabled(False) # Désactiver l'enregistrement si déconnecté
                    if self.recording: # Si on enregistrait, arrêter proprement
                        self.stop_recording()
                    QMessageBox.warning(self.ui, "Connection Lost", f"Connection to the device was lost or trial ended: ")
                except ConnectionResetError:
                    print("[ERROR] Connection reset by peer.")
                    self.handle_connection_error("Connection reset by peer")
                except ConnectionAbortedError:
                    print("[ERROR] Connection aborted.")
                    self.handle_connection_error("Connection aborted by software in your host machine")
                except socket.timeout:
                    print("[WARNING] Socket timeout while receiving data.")
                    # Optionnel: Gérer le timeout, peut-être compter les timeouts et déconnecter après N tentatives
                except struct.error as e:
                    print(f"[ERROR] Struct unpacking error: {e}. Packet size may be incorrect.")
                    # Essayer de vider le buffer ou se reconnecter ? Pour l'instant, on signale l'erreur.
                    self.handle_connection_error(f"Data packet structure error: {e}")
                except Exception as e:
                    print(f"[ERROR] Failed to receive/process data: {e}")
                    # Gérer d'autres erreurs potentielles, peut-être déconnecter
                    self.handle_connection_error(f"Generic error during data processing: {e}")
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
        
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'edit_Boleen'):
                try:
                    self.main_bar_re.edit_Boleen(True)
                except Exception as e:
                    print(f"Error calling edit_Boleen: {e}")

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

    def handle_trial_end(self):
        """Gère la réception du marqueur de fin d'essai."""
        if self.recording:
            self.stop_recording()
            QMessageBox.information(self.ui, "Trial Ended", "Trial ended and recording stopped.")
        else:
            QMessageBox.information(self.ui, "Trial Ended", "Trial ended by device.")
        
        # Fermer le socket client actuel et réinitialiser l'état
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                print(f"[WARNING] Error closing client socket on trial end: {e}")
            self.client_socket = None
        
        self.sensor_config = None
        self.packet_size = 0
        self.ui.connect_button.setText("Connect") # Permettre une nouvelle connexion
        self.ui.connect_button.setEnabled(True)
        self.ui.record_button.setEnabled(False)
        self.ui.reset_sensor_display() # Effacer l'arbre des capteurs, etc.
        
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'edit_Boleen'):
                try:
                    self.main_bar_re.edit_Boleen(True)
                except Exception as e:
                    print(f"Error calling edit_Boleen: {e}")
        
        print("[INFO] Client disconnected due to trial end. Ready for new connection.")

    def handle_connection_error(self, reason="Unknown error"):
        """Gère les erreurs de connexion et la déconnexion."""
        print(f"[ERROR] Handling connection error: {reason}")
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        self.sensor_config = None
        self.packet_size = 0
        # Pas besoin de modifier is_server_running ici car le serveur écoute toujours
        self.ui.connect_button.setText("Connect")
        self.ui.connect_button.setEnabled(True)
        self.ui.record_button.setEnabled(False)
        if self.recording: # Si on enregistrait, arrêter proprement
            self.timer.stop()
            self.recording = False
            self.ui.record_button.setText("Record Start")
            # Réinitialiser le style via l'UI si nécessaire, ex: self.ui.set_record_button_style_start()
            print("[INFO] Recording stopped due to connection error.")

        self.ui.reset_sensor_display()
        QMessageBox.warning(self.ui, "Connection Problem", f"Disconnected from device: {reason}")

