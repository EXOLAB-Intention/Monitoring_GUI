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
import pandas as pd

# Ajouter le chemin du répertoire parent de data_generator au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.ethernet_receiver import recv_all, decode_packet

# Constante pour le trial end marker
TRIAL_END_MARKER = b'\x4E'

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
            self.server_socket.settimeout(None) 
            self.running = True
            
            print(f"[INFO] Server started on {self.listen_ip}:{self.listen_port}. Waiting indefinitely for a client connection...")
            self.server_started.emit()
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    
                    if not self.running:
                        try:
                            client_socket.close()
                        except Exception:
                            pass 
                        break

                    print(f"[INFO] Client connected from {addr}")
                    self.connection_ready.emit((client_socket, addr))
                    self.running = False
                    break
                
                except OSError as e:
                    if self.running:
                        self.server_error.emit(f"Error accepting client connection: {str(e)}")
                    self.running = False 
                    break
                except Exception as e:
                    if self.running:
                        self.server_error.emit(f"Unexpected error in server loop: {str(e)}")
                    self.running = False 
                    break 
                
        except Exception as e:
            self.server_error.emit(f"Server setup error: {str(e)}")
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
        
        # Ne pas créer un deuxième MainBar, utiliser celui de l'UI
        # try:
        #     from utils.Menu_bar import MainBar
        #     self.main_bar_re = MainBar(self.ui)
        # except Exception as e:
        #     print(f"Error initializing MainBar: {e}")
        #     self.main_bar_re = None

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
        # Si on était dans un état post-enregistrement, préparer un nouveau trial
        if self.recording_stopped:
            self.prepare_new_trial()
            
        client_socket, addr = client_info
        self.client_socket = client_socket
        
        # Ajouter un timeout pour le socket client
        try:
            client_socket.settimeout(60.0)  # 5 secondes de timeout
        except Exception as e:
            print(f"[WARNING] Failed to set socket timeout: {e}")
        
        self.client_init_thread = ClientInitThread(client_socket)
        self.client_init_thread.init_success.connect(self.on_client_init_success)
        self.client_init_thread.init_error.connect(self.on_client_init_error)
        self.client_init_thread.start()
        self.ui.connect_button.setText("Initializing...")

    def on_client_init_success(self, sensor_config, packet_size):
        self.sensor_config = sensor_config
        
        # Ajouter les champs manquants pour la compatibilité avec le reste du code
        if 'raw_imu_ids' not in self.sensor_config:
            # Reconstituer raw_imu_ids à partir des imu_ids
            raw_imu_ids = []
            for imu_id in sensor_config.get('imu_ids', []):
                raw_imu_ids.extend([imu_id, imu_id, imu_id, imu_id])
            self.sensor_config['raw_imu_ids'] = raw_imu_ids
            self.sensor_config['len_pmmg'] = len(sensor_config.get('pmmg_ids', []))
            self.sensor_config['len_fsr'] = len(sensor_config.get('fsr_ids', []))
            self.sensor_config['len_imu'] = len(raw_imu_ids)
            self.sensor_config['len_emg'] = len(sensor_config.get('emg_ids', []))
            self.sensor_config['num_imus'] = len(sensor_config.get('imu_ids', []))
        
        self.packet_size = packet_size
        
        # Mettre à jour l'interface avec les capteurs disponibles
        # Cela déclenchera aussi l'ouverture de la boîte de dialogue
        self.ui.update_sensor_tree_from_config(self.sensor_config)
        
        num_imus = self.sensor_config.get('num_imus', 0)
        self.recorded_data["IMU"] = [[] for _ in range(max(1, num_imus))]
        
        self.ui.connect_button.setText("Disconnect")
        self.ui.connect_button.setEnabled(True)
        self.ui.record_button.setEnabled(True)
        record_button_style = """
        QPushButton {
            background-color: #4caf50;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }"""
        self.ui.record_button.setStyleSheet(record_button_style)

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
            try:
                # Réduire drastiquement le flush du buffer qui cause du lag
                if hasattr(self, '_last_flush_time'):
                    current_time = time.time()
                    if current_time - self._last_flush_time < 1.0:  # Flush max 1x par seconde
                        pass  # Skip flush
                    else:
                        self.flush_socket_buffer()
                        self._last_flush_time = current_time
                else:
                    self._last_flush_time = time.time()
                    self.flush_socket_buffer()
                
                if not self.client_socket:
                    print("[ERROR] Client socket is None during recording")
                    return
                
                # Receive data with timeout handling
                try:
                    self.client_socket.settimeout(0.01)  # Réduire le timeout à 10ms
                    data = recv_all(self.client_socket, self.packet_size)
                    if not data:
                        return
                except socket.timeout:
                    # Ne plus imprimer les timeouts socket pour éviter le spam
                    return
                except Exception as e:
                    if hasattr(self, '_last_socket_error_time'):
                        current_time = time.time()
                        if current_time - self._last_socket_error_time > 5.0:  # Log une fois toutes les 5 secondes
                            print(f"[ERROR] Error receiving data: {e}")
                            self._last_socket_error_time = current_time
                    else:
                        print(f"[ERROR] Error receiving data: {e}")
                        self._last_socket_error_time = time.time()
                    return
                finally:
                    try:
                        self.client_socket.settimeout(None)  # Reset to blocking
                    except:
                        pass
                
                # Decode packet with error handling
                try:
                    packet = decode_packet(data, self.sensor_config)
                    if not packet:
                        return
                except Exception as e:
                    if hasattr(self, '_last_decode_error_time'):
                        current_time = time.time()
                        if current_time - self._last_decode_error_time > 5.0:
                            print(f"[ERROR] Error decoding packet: {e}")
                            self._last_decode_error_time = current_time
                    else:
                        print(f"[ERROR] Error decoding packet: {e}")
                        self._last_decode_error_time = time.time()
                    return
                
                # Validate packet data
                if self._contains_invalid_data(packet):
                    self.corrupted_packets_count += 1
                    if self.corrupted_packets_count % 100 == 0:  # Réduire la fréquence de log
                        print(f"[WARNING] {self.corrupted_packets_count} corrupted packets detected")
                    return
                
                # Store data for recording (optimisé)
                if 'emg' in packet:
                    for i, value in enumerate(packet['emg']):
                        if i < len(self.recorded_data["EMG"]):
                            self.recorded_data["EMG"][i].append(value)
                
                if 'pmmg' in packet:
                    for i, value in enumerate(packet['pmmg']):
                        if i < len(self.recorded_data["pMMG"]):
                            self.recorded_data["pMMG"][i].append(value)
                
                if 'imu' in packet:
                    for i, quaternion in enumerate(packet['imu']):
                        if self._is_valid_quaternion(quaternion):
                            if i < len(self.recorded_data["IMU"]):
                                self.recorded_data["IMU"][i].append(quaternion)
                
                # Apply to 3D model BEAUCOUP moins fréquemment pour éviter le lag
                if 'imu' in packet and packet['imu']:
                    if not hasattr(self, '_last_3d_update_time'):
                        self._last_3d_update_time = time.time()
                        
                    current_time = time.time()
                    if current_time - self._last_3d_update_time >= 0.033:  # Max 30 FPS pour le 3D
                        try:
                            self.ui.apply_imu_data_to_3d_model(packet['imu'])
                            self._last_3d_update_time = current_time
                        except Exception as e:
                            if hasattr(self, '_last_3d_error_time'):
                                if current_time - self._last_3d_error_time > 5.0:
                                    print(f"[ERROR] Error applying IMU data to 3D model: {e}")
                                    self._last_3d_error_time = current_time
                            else:
                                print(f"[ERROR] Error applying IMU data to 3D model: {e}")
                                self._last_3d_error_time = current_time
                
                # Update live plots (également moins fréquent)
                if not hasattr(self, '_last_plot_update_time'):
                    self._last_plot_update_time = time.time()
                    
                current_time = time.time()
                if current_time - self._last_plot_update_time >= 0.05:  # Max 20 FPS pour les plots
                    try:
                        self.ui.update_live_plots(packet)
                        self._last_plot_update_time = current_time
                    except Exception as e:
                        if hasattr(self, '_last_plot_error_time'):
                            if current_time - self._last_plot_error_time > 5.0:
                                print(f"[ERROR] Error updating live plots: {e}")
                                self._last_plot_error_time = current_time
                        else:
                            print(f"[ERROR] Error updating live plots: {e}")
                            self._last_plot_error_time = current_time
                    
            except Exception as e:
                if hasattr(self, '_last_general_error_time'):
                    current_time = time.time()
                    if current_time - self._last_general_error_time > 10.0:  # Log une fois toutes les 10 secondes
                        print(f"[ERROR] General error in update_data: {e}")
                        import traceback
                        traceback.print_exc()
                        self._last_general_error_time = current_time
                else:
                    print(f"[ERROR] General error in update_data: {e}")
                    import traceback
                    traceback.print_exc()
                    self._last_general_error_time = time.time()

    def _contains_invalid_data(self, packet):
        for value in packet.get('emg', []):
            if not isinstance(value, (int, float)) or abs(value) > 10.0: return True
        for value in packet.get('pmmg', []):
            if not isinstance(value, (int, float)) or abs(value) > 10.0: return True
        for i, quaternion in enumerate(packet.get('imu', [])):
            if not self._is_valid_quaternion(quaternion):
                return True
        return False
        
    def _is_valid_quaternion(self, quaternion):
        """Vérifie si un quaternion est valide et le normalise si nécessaire.
        
        Un quaternion valide doit avoir 4 composantes numériques et une norme non nulle.
        """
        if not isinstance(quaternion, (list, tuple)) or len(quaternion) != 4:
            return False
            
        # Vérifier que toutes les composantes sont numériques
        for i, component in enumerate(quaternion):
            if not isinstance(component, (int, float)):
                return False
            if abs(component) > 100.0:  # Valeur aberrante
                return False
        
        # Calculer la norme du quaternion
        norm_squared = sum(c*c for c in quaternion)
        
        # Vérifier que la norme n'est pas trop proche de zéro
        if norm_squared < 1e-10:
            return False
            
        return True

    def flush_socket_buffer(self):
        """Vide le buffer du socket pour éviter les données résiduelles - VERSION OPTIMISÉE."""
        if not self.client_socket:
            return
            
        try:
            self.client_socket.settimeout(0.001)  # Timeout très court - 1ms
            total_flushed = 0
            max_flush = 5  # Limiter le nombre d'itérations pour éviter les blocages
            
            for _ in range(max_flush):
                try:
                    chunk = self.client_socket.recv(1024)
                    if not chunk:
                        break
                    total_flushed += len(chunk)
                except socket.timeout:
                    break
                except:
                    break
            
            # Log seulement si on a flush une quantité significative
            if total_flushed > 2000:  # Seulement si plus de 2KB
                print(f"[INFO] Flushed {total_flushed} bytes from socket buffer")
                
        except Exception as e:
            pass  # Ignorer les erreurs de flush pour éviter le spam
        finally:
            try:
                self.client_socket.settimeout(None)
            except:
                pass

    def start_recording(self):
        # Réinitialiser le compteur de paquets corrompus
        self.corrupted_packets_count = 0
        
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
        print(f"[INFO] Timer starting with 40ms interval")
        self.ui.record_button.setText("Record Stop")
        
        # Désactiver "Refresh Connected System" pendant l'acquisition de données
        if hasattr(self.ui, 'main_bar_re') and self.ui.main_bar_re is not None:
            if hasattr(self.ui.main_bar_re, 'set_refresh_connected_system_enabled'):
                try:
                    self.ui.main_bar_re.set_refresh_connected_system_enabled(False)
                except Exception as e:
                    print(f"[ERROR] Error disabling refresh_connected_system during recording: {e}")
        
        self.timer.start(40) # Démarrer le timer ici
        print(f"[INFO] Timer started, is active: {self.timer.isActive()}")

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
        
        #Activer "Clear Plot" et "Request H5 File" après l'arrêt de l'enregistrement
        if hasattr(self.ui, 'main_bar_re') and self.ui.main_bar_re is not None:
            if hasattr(self.ui.main_bar_re, 'edit_Boleen'):
                try:
                    self.ui.main_bar_re.edit_Boleen(True)  # Active Clear Plot et Request H5 File
                except Exception as e:
                    print(f"[ERROR] Error calling edit_Boleen: {e}")
            
            # Réactiver "Refresh Connected System" si les capteurs sont encore connectés
            if self.sensor_config and hasattr(self.ui.main_bar_re, 'set_refresh_connected_system_enabled'):
                try:
                    self.ui.main_bar_re.set_refresh_connected_system_enabled(True)
                except Exception as e:
                    print(f"[ERROR] Error re-enabling refresh_connected_system after recording: {e}")

    def clear_plots_only(self):
        """Nettoie seulement les graphiques et données d'enregistrement, maintient tous les settings."""
        # Réinitialiser l'état pour permettre un nouveau trial
        self.recording_stopped = False
        
        # Réinitialiser le compteur de paquets corrompus
        self.corrupted_packets_count = 0
        
        # Vider les données enregistrées
        num_imus = self.sensor_config.get('num_imus', 0) if self.sensor_config else 1
        self.recorded_data = {
            "EMG": [[] for _ in range(8)],
            "IMU": [[] for _ in range(max(1, num_imus))],
            "pMMG": [[] for _ in range(8)]
        }
        
        # Vider les données de plot en temps réel
        self.plot_data.clear()
        self.group_plot_data.clear()
        
        # Demander à l'UI de nettoyer les graphiques
        self.ui.clear_all_plots()
        
        # Désactiver "Clear Plot" et "Request H5 File" après nettoyage (mais garder Refresh Connected System activé)
        if hasattr(self.ui, 'main_bar_re') and self.ui.main_bar_re is not None:
            if hasattr(self.ui.main_bar_re, 'edit_Boleen'):
                try:
                    self.ui.main_bar_re.edit_Boleen(False)  # Désactive Clear Plot et Request H5 File
                except Exception as e:
                    print(f"[ERROR] Error calling edit_Boleen: {e}")
        
        # Réactiver le bouton d'enregistrement si on a une connexion
        if self.client_socket:
            self.ui.record_button.setText("Record Start")
            self.ui.record_button.setEnabled(True)
            print("[INFO] System ready for new trial - Record button enabled")

    def prepare_new_trial(self):
        """Prépare l'interface pour un nouveau trial en nettoyant les données et graphiques."""
        # Arrêter l'enregistrement si en cours
        if self.recording:
            self.recording = False
            self.timer.stop()
        
        # Réinitialiser les états
        self.recording_stopped = False
        
        # Utiliser la méthode de nettoyage simple
        self.clear_plots_only()

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
        """Met à jour les mappings des capteurs dans le backend et l'interface 3D."""
        try:
            # Stocker les mappings dans le backend
            self.emg_mappings = emg_mappings
            self.pmmg_mappings = pmmg_mappings
            
            # Appliquer les mappings IMU au modèle 3D
            if hasattr(self.ui, 'model_3d_widget') and self.ui.model_3d_widget:
                # Nettoyer les anciens mappings
                self.ui.model_3d_widget.model_viewer.imu_mapping.clear()
                
                # Appliquer les nouveaux mappings IMU
                for imu_id, body_part in imu_mappings.items():
                    success = self.ui.model_3d_widget.model_viewer.map_imu_to_body_part(int(imu_id), body_part)
                    if success:
                        print(f"[BACKEND] Successfully mapped IMU {imu_id} to {body_part}")
                    else:
                        print(f"[BACKEND] Failed to map IMU {imu_id} to {body_part}")
                
                # Stocker les mappings EMG et pMMG directement (pas de méthode set_emg_mapping)
                self.ui.model_3d_widget.model_viewer.emg_mapping = emg_mappings.copy()
                self.ui.model_3d_widget.model_viewer.pmmg_mapping = pmmg_mappings.copy()
            
            # Rafraîchir l'affichage de l'arbre des capteurs
            if hasattr(self.ui, 'refresh_sensor_tree_with_mappings'):
                self.ui.refresh_sensor_tree_with_mappings(emg_mappings, pmmg_mappings)
                
        except Exception as e:
            print(f"[ERROR] Error updating sensor mappings: {e}")
            import traceback
            traceback.print_exc()

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


    def export_recorded_data_to_csv(self, filename="recorded_data.csv"):
        """Export all recorded sensor data to a CSV file."""
        data = self.recorded_data
        # Exemple simple pour EMG, IMU, pMMG (à adapter selon la structure réelle)
        rows = []
        max_len = max(len(lst) for sensor_type in data for lst in data[sensor_type])
        for i in range(max_len):
            row = {}
            for sensor_type in data:
                for idx, sensor_data in enumerate(data[sensor_type]):
                    key = f"{sensor_type}{idx+1}"
                    value = sensor_data[i] if i < len(sensor_data) else None
                    row[key] = value
            rows.append(row)
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        print(f"Data exported to {filename}")