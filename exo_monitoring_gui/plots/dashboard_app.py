import sys
import os
import time
import numpy as np
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QMenuBar, QComboBox, QMessageBox, QRadioButton, QButtonGroup, QGroupBox, QTableWidget, QTableWidgetItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QCursor
from PyQt5.QtWidgets import QScrollArea
import pyqtgraph as pg



# Ajouter le chemin du répertoire parent de data_generator au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Ajouter l'import du model_3d_viewer et du dialogue de mapping
from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog
# Supprimer l'importation du simulateur et ajouter les imports nécessaires pour Ethernet
# from data_generator.sensor_simulator import SensorSimulator
import socket
import struct
import threading
from utils.ethernet_receiver import recv_all, decode_packet, decode_config

# Classe pour exécuter le serveur Ethernet dans un thread séparé
class EthernetServerThread(QThread):
    connection_ready = pyqtSignal(tuple)  # Émet (client_socket, addr) quand un client se connecte
    server_error = pyqtSignal(str)        # Émet un message d'erreur
    server_started = pyqtSignal()         # Émet un signal quand le serveur démarre

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
                    # Attendre un client avec un timeout pour pouvoir vérifier self.running périodiquement
                    self.server_socket.settimeout(1.0)
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"[INFO] Client connected from {addr}")
                        # Émettre le signal avec les informations du client
                        self.connection_ready.emit((client_socket, addr))
                        # Une fois qu'un client est connecté, on peut attendre la fin du thread
                        # car le dashboard ne gère qu'un client à la fois
                        break
                    except socket.timeout:
                        # Le timeout a expiré, vérifier si on doit toujours attendre
                        continue
                except Exception as e:
                    if self.running:  # Seulement émettre si ce n'est pas une fermeture volontaire
                        self.server_error.emit(f"Error accepting client: {str(e)}")
                    break
                
        except Exception as e:
            self.server_error.emit(f"Server error: {str(e)}")
        finally:
            self.cleanup()

    def stop(self):
        self.running = False
        self.cleanup()
        self.wait()  # Attendre que le thread se termine

    def cleanup(self):
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

# Classe pour traiter l'initialisation du client dans un thread séparé
class ClientInitThread(QThread):
    init_success = pyqtSignal(dict, int)  # Émet config et packet_size en cas de succès
    init_error = pyqtSignal(str)          # Émet un message d'erreur

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        
    def run(self):
        try:
            # --- 1) Lire l'en-tête des longueurs (4 octets) ---
            hdr = recv_all(self.client_socket, 4)
            len_pmmg, len_fsr, len_imu, len_emg = struct.unpack('>4B', hdr)
            total_ids = len_pmmg + len_fsr + len_imu + len_emg

            # --- 2) Lire exactement les octets des ID ---
            id_bytes = recv_all(self.client_socket, total_ids)

            # --- 3) Lire le CRC de 4 octets ---
            crc_bytes = recv_all(self.client_socket, 4)
            recv_crc = struct.unpack('>I', crc_bytes)[0]
            
            # --- 4) Décoder chaque liste d'ID ---
            offset = 0
            pmmg_ids = list(id_bytes[offset:offset+len_pmmg]); offset += len_pmmg
            fsr_ids = list(id_bytes[offset:offset+len_fsr]); offset += len_fsr
            raw_imu_ids = list(id_bytes[offset:offset+len_imu]); offset += len_imu
            emg_ids = list(id_bytes[offset:offset+len_emg])

            # Traitement des IDs IMU - un IMU a 4 valeurs (w,x,y,z)
            num_imus = len(raw_imu_ids) // 4
            if num_imus > 0:
                imu_ids = []
                for i in range(num_imus):
                    # Extraire l'ID de l'IMU à partir du premier octet de chaque groupe de 4
                    imu_id = raw_imu_ids[i*4]
                    imu_ids.append(imu_id)
                    print(f"[INFO] IMU {i+1} détecté avec ID {imu_id} (composantes w,x,y,z)")
            else:
                imu_ids = []
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

            # --- 5) Calculer la taille du paquet de données ---
            packet_size = (
                4 +                            # timestamp
                len(pmmg_ids)*2 +              # pmmg
                len(fsr_ids)*2 +               # fsr
                len(imu_ids)*4*2 +             # imu (4 valeurs × int16)
                len(emg_ids)*2 +               # emg
                5 +                            # buttons
                4 +                            # joystick
                4                              # CRC
            )
            
            # Émettre le signal de succès avec la configuration et la taille du paquet
            self.init_success.emit(sensor_config, packet_size)
            
        except Exception as e:
            self.init_error.emit(f"Failed to initialize client: {str(e)}")
            try:
                if self.client_socket:
                    self.client_socket.close()
            except:
                pass

class DashboardApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        # Style global de l'application
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #e8e8e8;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover:!selected {
                background: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTreeWidget, QTableWidget {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: white;
            }
            QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 10px;
                min-height: 25px;
            }
            QLineEdit {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QScrollArea {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: white;
            }
        """)
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1600, 900)
        self.setMinimumSize(1400, 800)
        self.setStyleSheet("background-color: white; color: black;")

        self.parent = parent
        self.current_file = self.parent.subject_file
        # Supprimer l'initialisation du simulateur et ajouter les variables Ethernet
        # self.simulator = SensorSimulator()
        # Variables pour le serveur et le client Ethernet
        self.server_thread = None
        self.client_socket = None
        self.sensor_config = None
        self.packet_size = 0
        self.is_server_running = False

        self.recording = False  # Ajouter l'attribut recording
        self.recording_stopped = False  # Ajoute ceci juste après
        self.main_bar_re = self.some_method()
        self.main_bar_re._create_menubar()
    
        self.clear_plot = self.main_bar_re._create_action(
            "&Clear the plot",
            lambda: self.main_bar_re.clear_plot(),
            "Ctrl+M",
            tip="Clear the plot"
        )

        self.refresh_the_connected_systeme = self.main_bar_re._create_action(
            "&Refresh the connected systeme",
            lambda: self.main_bar_re.refresh_the_connected_systeme(),
            "Ctrl+M",
            tip="Refresh the connected systeme"
        )

        self.request_h5_file = self.main_bar_re._create_action(
            "&Request a .h5 file",
            lambda: self.main_bar_re.request_h5_file(*request_valus(self), self.current_file),
            "Ctrl+M",
            tip="Request a .h5 file"
        )
        menubar = self.menuBar()

        edit_menu = menubar.addMenu('&Edit')
        edit_menu.addAction(self.clear_plot)
        edit_menu.addAction(self.refresh_the_connected_systeme)
        edit_menu.addAction(self.request_h5_file)

        def request_valus(self):
            from utils.ethernet_receiver import li, pmmg_l, fsr_l, imu_l, emg_l
            return li, pmmg_l, fsr_l, imu_l, emg_l
        
        self.request_h5_file.setEnabled(False)  # Désactiver le bouton au départ
        self.clear_plot.setEnabled(False)  # Désactiver le bouton au départ
        self.refresh_the_connected_systeme.setEnabled(False)  # Désactiver le bouton au départ

        # Initialisation prudente des structures de données pour l'enregistrement
        self.recorded_data = {
            "EMG": [[] for _ in range(8)],   # 8 EMGs max
            "IMU": [[] for _ in range(1)],   # Initialisé avec 1 IMU, sera mis à jour lors de la connexion
            "pMMG": [[] for _ in range(8)]   # 8 pMMGs max
        }

        # Initialiser les mappages de capteurs
        self.emg_mappings = {}
        self.pmmg_mappings = {}

        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(40)  # Mettre à jour les données toutes les 40 ms
        self.load_mappings()  # Charger les mappages sauvegardés au démarrage

    def some_method(self):
        from utils.Menu_bar import MainBar
        return MainBar(self)
    
    def init_ui(self):
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Titles
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Connected Systems"), stretch=1)
        title_layout.addWidget(QLabel("Graphics / Visual Zone"), stretch=2)
        title_layout.addWidget(QLabel("3D Perspective"), stretch=1)
        main_layout.addLayout(title_layout)

        # Main content layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # Connected Systems Panel (gauche)
        self.connected_systems = QTreeWidget()
        self.connected_systems.setHeaderHidden(True)
        self.connected_systems.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            QTreeWidget::item:selected {
                background-color: lightblue;
            }
        """)
        self.connected_systems.setVisible(True)
        self.connected_systems.itemClicked.connect(self.on_sensor_clicked)

        # Organisation des capteurs par sous-groupes
        sensors = ["EMG Data", "IMU Data", "pMMG Data"]
        for sensor_group in sensors:
            group_item = QTreeWidgetItem([sensor_group])
            self.connected_systems.addTopLevelItem(group_item)
            if sensor_group == "IMU Data":
                num_sensors = 6
            else:
                num_sensors = 8
            for i in range(1, num_sensors + 1):
                sensor_item = QTreeWidgetItem([f"{sensor_group[:-5]}{i}"])
                sensor_item.setForeground(0, QBrush(QColor("gray")))  # Gris pour déconnecté
                sensor_item.setHidden(False)  # Affiché par défaut
                group_item.addChild(sensor_item)
            group_item.setExpanded(True)  # Ouvrir la liste déroulante par défaut

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

        # Choix du mode d'affichage
        self.display_mode_group = QButtonGroup()
        self.display_mode_layout = QHBoxLayout()

        self.single_sensor_mode = QRadioButton("1 sensor per plot")
        self.group_sensor_mode = QRadioButton("Plots by sensor groups")
        self.display_mode_group.addButton(self.single_sensor_mode)
        self.display_mode_group.addButton(self.group_sensor_mode)
        self.single_sensor_mode.setChecked(True)

        self.display_mode_layout.addWidget(self.single_sensor_mode)
        self.display_mode_layout.addWidget(self.group_sensor_mode)
        left_panel.addLayout(self.display_mode_layout)

        # Graphics / Visual Zone (centre)
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout()
        self.middle_placeholder.setLayout(self.middle_layout)

        # Ajouter un QScrollArea pour la section "Graphics / Visual Zone"
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.middle_placeholder)

        middle_panel = QVBoxLayout()
        middle_panel.addWidget(scroll_area)

        # 3D Perspective (droite)
        right_panel = QVBoxLayout()
        label_3d_title = QLabel("3D Perspective")
        label_3d_title.setAlignment(Qt.AlignCenter)
        label_3d_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_panel.addWidget(label_3d_title)

        # Remplacer le label statique par le widget 3D
        self.model_3d_widget = Model3DWidget()
        right_panel.addWidget(self.model_3d_widget, stretch=3)

        # Ajouter un bouton pour contrôler l'animation
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        right_panel.addWidget(self.animate_button)

        # Ajouter un bouton pour réinitialiser la vue du modèle 3D
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_model_view)
        right_panel.addWidget(self.reset_view_button)

        # Ajouter le bouton "Configure Sensor Mapping" en bas à droite
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.setStyleSheet("font-size: 14px; padding: 8px 20px;")
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        right_panel.addWidget(self.config_button)

        # Ajouter le bouton "Set Up Default Assignments"
        self.default_config_button = QPushButton("Set Up Default Assignments")
        self.default_config_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                text-align: center;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #8E24AA;
            }
            QPushButton:pressed {
                background-color: #7B1FA2;
            }
        """)
        self.default_config_button.clicked.connect(self.setup_default_mappings)
        right_panel.addWidget(self.default_config_button)

        # Ajout des panneaux gauche / centre / droite
        content_layout.addLayout(left_panel, stretch=1)  # Réduire la largeur de la section "Connected Systems"
        content_layout.addLayout(middle_panel, stretch=4)  # Augmenter la largeur de la section "Graphics / Visual Zone"
        content_layout.addLayout(right_panel, stretch=2)
        
        # Footer
        footer_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_sensors)
        self.record_button = QPushButton("Record Start")
        self.record_button.clicked.connect(self.toggle_recording)

        # Style moderne pour les boutons
        button_style = """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 8px 16px;
            color: #333;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
        }

        QPushButton:pressed {
            background-color: #d0d0d0;
            border: 1px solid #b0b0b0;
        }

        QPushButton:disabled {
            background-color: #f9f9f9;
            border: 1px solid #e0e0e0;
            color: #a0a0a0;
        }
        """

        # Boutons spéciaux
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
        }

        QPushButton:hover {
            background-color: #43a047;
        }

        QPushButton:pressed {
            background-color: #388e3c;
        }
        """

        animate_button_style = """
        QPushButton {
            background-color: #2196f3;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #1e88e5;
        }

        QPushButton:pressed {
            background-color: #1976d2;
        }
        """

        reset_view_button_style = """
        QPushButton {
            background-color: #9e9e9e;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #8e8e8e;
        }

        QPushButton:pressed {
            background-color: #757575;
        }
        """

        config_button_style = """
        QPushButton {
            background-color: #ff9800;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #fb8c00;
        }

        QPushButton:pressed {
            background-color: #f57c00;
        }
        """

        # Appliquer les styles aux boutons
        self.animate_button.setStyleSheet(animate_button_style)
        self.reset_view_button.setStyleSheet(reset_view_button_style)
        self.config_button.setStyleSheet(config_button_style)
        self.connect_button.setStyleSheet(button_style)
        self.record_button.setStyleSheet(record_button_style)
        
        for btn in (self.connect_button, self.record_button):
            footer_layout.addWidget(btn)

        main_layout.addLayout(footer_layout)

        # Initialiser les graphiques
        self.plots = {}
        self.plot_data = {}
        self.highlighted_sensors = set()
        self.group_plots = {}
        self.group_plot_data = {}

        # Connecter le signal de changement de mode
        self.display_mode_group.buttonClicked.connect(self.on_display_mode_changed)

    def connect_sensors(self):
        """Démarrer le serveur Ethernet si ce n'est pas déjà fait et mettre à jour l'affichage des capteurs."""
        if not self.is_server_running:
            # Démarrer le serveur Ethernet dans un thread séparé
            try:
                self.server_thread = EthernetServerThread()
                self.server_thread.connection_ready.connect(self.on_client_connected)
                self.server_thread.server_error.connect(self.on_server_error)
                self.server_thread.server_started.connect(self.on_server_started)
                self.server_thread.start()
                
                # Mettre à jour l'interface pour montrer que le serveur démarre
                self.connect_button.setText("Starting...")
                self.connect_button.setEnabled(False)  # Désactiver pendant le démarrage
            except Exception as e:
                QMessageBox.critical(self, "Server Error", f"Could not start Ethernet server: {str(e)}")
        else:
            # Si le serveur est déjà en cours d'exécution, tenter de l'arrêter
            self.stop_ethernet_server()
            self.connect_button.setText("Connect")
            # Remettre les capteurs en gris (déconnecté)
            for i in range(self.connected_systems.topLevelItemCount()):
                group_item = self.connected_systems.topLevelItem(i)
                for j in range(group_item.childCount()):
                    sensor_item = group_item.child(j)
                    sensor_item.setForeground(0, QBrush(QColor("gray")))
    
    def on_server_started(self):
        """Appelé quand le serveur Ethernet a démarré avec succès."""
        self.is_server_running = True
        self.connect_button.setText("Waiting for device...")
        QMessageBox.information(self, "Server Started", 
                               "Ethernet server started successfully. Waiting for device connection...")

    def on_client_connected(self, client_info):
        """Appelé quand un client se connecte au serveur Ethernet."""
        client_socket, addr = client_info
        self.client_socket = client_socket
        
        # Initialiser le client dans un thread séparé pour éviter de bloquer l'UI
        self.client_init_thread = ClientInitThread(client_socket)
        self.client_init_thread.init_success.connect(self.on_client_init_success)
        self.client_init_thread.init_error.connect(self.on_client_init_error)
        self.client_init_thread.start()
        
        # Mettre à jour l'interface pour montrer qu'on initialise la connexion
        self.connect_button.setText("Initializing...")

    def on_client_init_success(self, sensor_config, packet_size):
        """Appelé quand l'initialisation du client a réussi."""
        self.sensor_config = sensor_config
        self.packet_size = packet_size
        
        # Mettre à jour l'interface pour montrer les capteurs connectés
        self.update_sensor_tree_from_config()
        
        # Réinitialiser les structures de données pour correspondre aux capteurs connectés
        num_imus = self.sensor_config.get('num_imus', 0)
        self.recorded_data["IMU"] = [[] for _ in range(max(1, num_imus))]  # Au moins 1 pour éviter les erreurs
        
        # Mettre à jour l'état du bouton
        self.connect_button.setText("Disconnect")
        self.connect_button.setEnabled(True)
        
        # Activer le bouton d'enregistrement
        self.record_button.setEnabled(True)
        
        # Afficher un message de succès
        len_emg = len(self.sensor_config.get('emg_ids', []))
        num_imus = self.sensor_config.get('num_imus', 0)
        len_pmmg = len(self.sensor_config.get('pmmg_ids', []))
        
        QMessageBox.information(self, "Connection Success", 
                               f"Connecté au dispositif ! Détecté {len_emg} EMG, {num_imus} IMU, {len_pmmg} pMMG.")

    def on_client_init_error(self, error_msg):
        """Appelé en cas d'erreur lors de l'initialisation du client."""
        print(f"[ERROR] {error_msg}")
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        QMessageBox.critical(self, "Connection Error", error_msg)

    def on_server_error(self, error_msg):
        """Appelé en cas d'erreur du serveur Ethernet."""
        print(f"[ERROR] {error_msg}")
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.is_server_running = False
        QMessageBox.critical(self, "Server Error", error_msg)

    def stop_ethernet_server(self):
        """Arrête le serveur Ethernet et nettoie les ressources."""
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

    def update_sensor_tree_from_config(self):
        """Met à jour l'arbre des capteurs (self.connected_systems) 
        basé sur la configuration reçue (self.sensor_config)."""
        if not self.sensor_config:
            return

        # D'abord, on cache tous les capteurs pour ne réafficher que ceux configurés
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                group_item.child(j).setHidden(True)

        # Mettre à jour EMG
        emg_group_item = self.find_sensor_group_item("EMG Data")
        if emg_group_item:
            # Cacher d'abord tous les EMGs
            for i in range(emg_group_item.childCount()):
                emg_group_item.child(i).setHidden(True)
                
            # Actualiser uniquement les éléments EMG réellement connectés
            num_emg_configured = len(self.sensor_config.get('emg_ids', []))
            if num_emg_configured == 0:
                print("[INFO] Aucun capteur EMG détecté")
            else:
                for i in range(min(num_emg_configured, emg_group_item.childCount())):
                    sensor_id_from_config = self.sensor_config['emg_ids'][i]
                    sensor_item = emg_group_item.child(i)
                    sensor_item.setText(0, f"EMG{sensor_id_from_config}")
                    sensor_item.setForeground(0, QBrush(QColor("green")))
                    sensor_item.setHidden(False)
                    print(f"[INFO] EMG {i+1} affiché: EMG{sensor_id_from_config}")

        # Mettre à jour IMU
        imu_group_item = self.find_sensor_group_item("IMU Data")
        if imu_group_item:
            num_imu_configured = len(self.sensor_config.get('imu_ids', []))
            # Cacher d'abord tous les IMUs
            for i in range(imu_group_item.childCount()):
                imu_group_item.child(i).setHidden(True)
                
            # Afficher uniquement les IMUs détectés
            for i in range(min(num_imu_configured, imu_group_item.childCount())):
                sensor_id_from_config = self.sensor_config['imu_ids'][i]
                sensor_item = imu_group_item.child(i)
                sensor_item.setText(0, f"IMU{sensor_id_from_config}")
                sensor_item.setForeground(0, QBrush(QColor("green")))
                sensor_item.setHidden(False)
                print(f"[INFO] IMU {i+1} affiché: IMU{sensor_id_from_config}")

        # Mettre à jour pMMG
        pmmg_group_item = self.find_sensor_group_item("pMMG Data")
        if pmmg_group_item and self.sensor_config.get('pmmg_ids'):
            # Cacher d'abord tous les pMMGs
            for i in range(pmmg_group_item.childCount()):
                pmmg_group_item.child(i).setHidden(True)
                
            # Actualiser uniquement les éléments pMMG réellement connectés
            num_pmmg_configured = len(self.sensor_config.get('pmmg_ids', []))
            if num_pmmg_configured == 0:
                print("[INFO] Aucun capteur pMMG détecté")
            else:
                for i in range(min(num_pmmg_configured, pmmg_group_item.childCount())):
                    sensor_id_from_config = self.sensor_config['pmmg_ids'][i]
                    sensor_item = pmmg_group_item.child(i)
                    sensor_item.setText(0, f"pMMG{sensor_id_from_config}")
                    sensor_item.setForeground(0, QBrush(QColor("green")))
                    sensor_item.setHidden(False)
                    print(f"[INFO] pMMG {i+1} affiché: pMMG{sensor_id_from_config}")

        # Pour appliquer les mappages (nom des parties du corps)
        self.refresh_sensor_tree()
  
        # Créer les graphiques de groupe si mode "Graphiques par groupe" et pas déjà existants
        if self.group_sensor_mode.isChecked() and not self.group_plots:
            self.create_group_plots()

    def find_sensor_group_item(self, group_name):
        """Trouve un item de groupe de capteurs par son nom."""
        for i in range(self.connected_systems.topLevelItemCount()):
            item = self.connected_systems.topLevelItem(i)
            if item.text(0) == group_name:
                return item
        return None

    def show_sensors(self):
        # Méthode désormais redondante avec update_sensor_tree_from_config
        if not self.client_socket or not self.sensor_config:
            print("[INFO] No sensor data available. Connect to sensors first.")
            return
        
        # Si on a des données de capteurs, on les affiche
        self.update_sensor_tree_from_config()

    def create_group_plots(self):
        # Vérifier si les graphiques de groupe existent déjà
        if not self.group_plots:
            # Créer les graphiques de groupe pour EMG et pMMG uniquement
            for group in ["EMG", "pMMG"]:
                plot_widget = pg.PlotWidget(title=group)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(group, color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget)
                self.group_plots[group] = plot_widget
                self.group_plot_data[group] = {}

    def update_matched_part(self, text):
        self.matched_part_combo.clear()
        if text == "Upper body w/o head":
            self.matched_part_combo.addItems([
                "pectorals_l", "deltoid_l", "biceps_l", "forearm_l", "dorsalis_major_l",
                "pectorals_r", "deltoid_r", "biceps_r", "forearm_r", "dorsalis_major_r"
            ])
        elif text == "Upper body w/ head":
            self.matched_part_combo.addItems(["pectorals_L", "Deltoid_L", "Biceps_L", "forearm_L", "dorsalis major_L", "pectorals_R", "Deltoid_R", "Biceps_R", "forearm_R",  "dorsalis major_R"])
        elif text == "Lower body":
            self.matched_part_combo.addItems(["Quadriceps_L", "ishcio-hamstrings_L", "calves_L", "glutes_L", "Quadriceps_R", "ishcio-hamstrings_R", "calves_R", "glutes_R"])

    def update_matched_sensors(self, text):
        # Mettre à jour les options de Matched Sensors en fonction de la sélection de Matched Part
        if text:
            self.matched_sensors_combo.clear()
            sensors = ["EMG1", "EMG2", "EMG3", "EMG4", "EMG5", "EMG6", "EMG7", "EMG8",
                       "IMU1", "IMU2", "IMU3", "IMU4", "IMU5", "IMU6",
                       "pMMG1", "pMMG2", "pMMG3", "pMMG4", "pMMG5", "pMMG6", "pMMG7", "pMMG8"]
            self.matched_sensors_combo.addItems(sensors)

    def update_sensor_label(self, text):
        # Mettre à jour le label du capteur avec le Matched Part sélectionné
        self.selected_sensor = text

    def confirm_selection(self):
        # Confirmer la sélection et mettre à jour le label du capteur
        if hasattr(self, 'selected_sensor') and self.selected_sensor and self.matched_part_combo.currentText():
            for i in range(self.connected_systems.topLevelItemCount()):
                group_item = self.connected_systems.topLevelItem(i)
                for j in range(group_item.childCount()):
                    sensor_item = group_item.child(j)
                    if sensor_item.text(0).startswith(self.selected_sensor):
                        matched_part = self.matched_part_combo.currentText()
                        sensor_item.setText(0, f"{self.selected_sensor} ({matched_part})")
                        # Mettre à jour les données du capteur avec le "matched part"
                        self.update_sensor_data(sensor_item.text(0), matched_part)

    def update_sensor_data(self, sensor_name, matched_part):
        # Mettre à jour les données du capteur avec le "matched part"
        pass

    def on_sensor_clicked(self, item, column):
        # Vérifier si le capteur est connecté
        if item.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Error", "The sensor is not connected. Please connect the sensor first.")
            return

        sensor_name = item.text(0).split()[0]  # Extraire le nom du capteur
        if sensor_name in self.plots or sensor_name in self.highlighted_sensors:
            # Désélectionner le capteur
            self.remove_sensor_plot(sensor_name)
        else:
            self.plot_sensor_data(item.text(0))

    def plot_sensor_data(self, sensor_name):
        # Afficher les données enregistrées si l'enregistrement est stoppé
        if self.recording_stopped:
            if self.group_sensor_mode.isChecked():
                sensor_group = sensor_name.split()[0][:-1]
                if sensor_group in self.group_plots:
                    plot_widget = self.group_plots[sensor_group]
                    if sensor_name.startswith("IMU"):
                        index = int(sensor_name[3]) - 1
                        quaternion = self.recorded_data["IMU"][index]
                        for i, axis in enumerate(['w', 'x', 'y', 'z']):
                            plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=f"{sensor_name}_{axis}")
                    else:
                        sensor_num = int(''.join(filter(str.isdigit, sensor_name)))
                        if sensor_name.startswith("EMG"):
                            index = sensor_num - 1
                            plot_widget.plot(self.recorded_data["EMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][sensor_num - 1], width=2), name=sensor_name)
                        elif sensor_name.startswith("pMMG"):
                            index = sensor_num - 1
                            plot_widget.plot(self.recorded_data["pMMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][sensor_num - 1], width=2), name=sensor_name)
                    plot_widget.addLegend()
                    self.highlight_sensor(sensor_name.split()[0])
                return
            else:
                plot_widget = pg.PlotWidget(title=sensor_name)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(sensor_name, color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget)
                self.plots[sensor_name.split()[0]] = plot_widget

                if sensor_name.startswith("EMG"):
                    index = int(sensor_name[3]) - 1
                    plot_widget.plot(self.recorded_data["EMG"][index], clear=True, pen=pg.mkPen('b', width=2))
                elif sensor_name.startswith("pMMG"):
                    index = int(sensor_name[4]) - 1
                    plot_widget.plot(self.recorded_data["pMMG"][index], clear=True, pen=pg.mkPen('b', width=2))
                elif sensor_name.startswith("IMU"):
                    index = int(sensor_name[3]) - 1
                    quaternion = self.recorded_data["IMU"][index]
                    plot_widget.clear()
                    for i, axis in enumerate(['w', 'x', 'y', 'z']):
                        plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)
                    plot_widget.addLegend()
                self.highlight_sensor(sensor_name.split()[0])
                return

        # --- Mode temps réel (enregistrement en cours) ---
        if self.group_sensor_mode.isChecked():
            if sensor_name.startswith("IMU"):
                plot_widget = pg.PlotWidget(title=sensor_name)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(sensor_name, color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget)
                self.plots[sensor_name.split()[0]] = plot_widget
                self.plot_data[sensor_name.split()[0]] = np.zeros(100)
                self.highlight_sensor(sensor_name.split()[0])
            else:
                sensor_group = sensor_name.split()[0][:-1]
                if sensor_group in self.group_plots:
                    if sensor_name not in self.group_plot_data[sensor_group]:
                        self.group_plot_data[sensor_group][sensor_name] = np.zeros(100)
                    self.highlight_sensor(sensor_name.split()[0])
        else:
            plot_widget = pg.PlotWidget(title=sensor_name)
            plot_widget.setBackground('#1e1e1e')
            plot_widget.getAxis('left').setTextPen('white')
            plot_widget.getAxis('bottom').setTextPen('white')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setTitle(sensor_name, color='white', size='14pt')
            self.middle_layout.addWidget(plot_widget)
            self.plots[sensor_name.split()[0]] = plot_widget
            self.plot_data[sensor_name.split()[0]] = np.zeros(100)
            self.highlight_sensor(sensor_name.split()[0])

    def remove_sensor_plot(self, sensor_name):
        # Supprimer le graphique du capteur de la section "2D Plots"
        if sensor_name in self.plots:
            plot_widget = self.plots.pop(sensor_name)
            plot_widget.setParent(None)
            plot_widget.deleteLater()

            # Retirer la surbrillance du capteur
            self.unhighlight_sensor(sensor_name)
        else:
            # Correction : utiliser le nom complet (avec matched part) pour la suppression dans les groupes
            self.remove_sensor_curve_from_group(sensor_name)
            self.unhighlight_sensor(sensor_name)

    def remove_sensor_curve_from_group(self, sensor_name):
        # Correction : supprimer toutes les courbes associées à ce capteur (avec ou sans matched part)
        # sensor_name peut être "EMG1" ou "EMG1 (Biceps)"
        # On doit supprimer toutes les clés qui commencent par le nom de base (ex: "EMG1")
        sensor_group = sensor_name.split()[0][:-1]
        if sensor_group in self.group_plots:
            plot_widget = self.group_plots[sensor_group]
            # Supprimer toutes les courbes dont le nom commence par sensor_name.split()[0]
            base_sensor = sensor_name.split()[0]
            # Supprimer les courbes du plot
            items_to_remove = []
            for item in plot_widget.listDataItems():
                # item.name() peut être None si pas de nom, donc on vérifie
                if hasattr(item, 'name') and item.name():
                    # On retire si le nom commence par le nom de base du capteur (ex: "EMG1")
                    if item.name().startswith(base_sensor):
                        items_to_remove.append(item)
            for item in items_to_remove:
                plot_widget.removeItem(item)
            # Supprimer les références dans group_plot_data
            keys_to_remove = []
            for k in self.group_plot_data[sensor_group]:
                if k.split()[0] == base_sensor:
                    keys_to_remove.append(k)
            for k in keys_to_remove:
                del self.group_plot_data[sensor_group][k]

    def highlight_sensor(self, sensor_name):
        # Mettre en surbrillance le capteur sélectionné
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("lightblue")))
                    self.highlighted_sensors.add(sensor_name)

    def unhighlight_sensor(self, sensor_name):
        # Retirer la surbrillance du capteur
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("white")))
                    self.highlighted_sensors.discard(sensor_name)

    def update_data(self):
        # Mettre à jour les données des graphiques en temps réel
        if self.recording:
            # Récupérer les données depuis Ethernet au lieu du simulateur
            if self.client_socket and self.sensor_config and self.packet_size > 0:
                try:
                    # Lire un paquet de données et le décoder
                    data_packet = recv_all(self.client_socket, self.packet_size)
                    packet = decode_packet(data_packet, self.sensor_config)
                    
                    # Vérification CRC et filtrage des données potentiellement corrompues
                    if not packet['crc_valid']:
                        
                        print("[WARNING] Invalid CRC for data packet. Checking data validity...")
                        
                        # Compteur de paquets corrompus consécutifs
                        if not hasattr(self, 'corrupted_packets_count'):
                            self.corrupted_packets_count = 0
                        self.corrupted_packets_count += 1
                        
                        # Si trop de paquets corrompus consécutifs, on considère que c'est une erreur grave
                        if self.corrupted_packets_count > 5:
                            print("[ERROR] Too many corrupted packets in a row. Data may be unreliable.")
                            self.corrupted_packets_count = 0  # Réinitialiser pour la prochaine tentative
                            return
                        
                        # Filtrage supplémentaire des données suspectes
                        if self._contains_invalid_data(packet):
                            print("[WARNING] Packet contains invalid data. Skipping.")
                            return
                    else:
                        # Réinitialiser le compteur de paquets corrompus quand on reçoit un paquet valide
                        self.corrupted_packets_count = 0

                    # Enregistrer les données
                    # Pour chaque type de capteur, nous devons mapper les données reçues (basées sur les IDs du serveur)
                    # aux index attendus par l'interface (0-7 pour EMG et pMMG, 0-5 pour IMU)
                    
                    # Mapper les données EMG - Adapter pour les IDs spécifiques (25, 26, 27, etc.)
                    if 'emg' in packet and packet['emg']:
                        for i, emg_id in enumerate(self.sensor_config.get('emg_ids', [])):
                            if i < len(packet['emg']) and i < len(self.recorded_data["EMG"]):
                                value = packet['emg'][i]
                                # Vérification de validité avant d'enregistrer
                                if -10.0 <= value <= 10.0:  # Plage valide typique pour EMG
                                    self.recorded_data["EMG"][i].append(value)
                    
                    # Mapper les données pMMG
                    if 'pmmg' in packet and packet['pmmg']:
                        for i, pmmg_id in enumerate(self.sensor_config.get('pmmg_ids', [])):
                            if i < len(packet['pmmg']) and i < len(self.recorded_data["pMMG"]):
                                value = packet['pmmg'][i]
                                # Vérification de validité avant d'enregistrer
                                if -10.0 <= value <= 10.0:  # Plage valide typique pour pMMG
                                    self.recorded_data["pMMG"][i].append(value)
                    
                    # Mapper les données IMU
                    if 'imu' in packet and packet['imu']:
                        for i, imu_id in enumerate(self.sensor_config.get('imu_ids', [])):
                            if i < len(packet['imu']) and i < len(self.recorded_data["IMU"]):
                                quaternion = packet['imu'][i]
                                # Vérification de validité du quaternion
                                if self._is_valid_quaternion(quaternion):
                                    self.recorded_data["IMU"][i].append(quaternion)
                                    
                                    # Mettre à jour le modèle 3D avec les données IMU
                                    # Un IMU contient 4 valeurs (wxyz), ce n'est pas 4 IMUs différents
                                    try:
                                        self.model_3d_widget.apply_imu_data(imu_id, quaternion)
                                    except Exception as e:
                                        print(f"Error updating 3D model: {e}")
                    
                    # Mettre à jour les graphiques individuels
                    for sensor_name_key, plot_widget in self.plots.items():
                        # sensor_name_key est "EMG25", "IMU5", etc.
                        sensor_type = ''.join(filter(str.isalpha, sensor_name_key))  # EMG, IMU, pMMG
                        sensor_num_str = ''.join(filter(str.isdigit, sensor_name_key))
                        if not sensor_num_str: continue  # Ignorer si pas de numéro
                        
                        # Trouver l'ID du capteur
                        sensor_id = int(sensor_num_str)
                        
                        # Trouver l'index correspondant dans les données reçues
                        if sensor_type == "EMG":
                            try:
                                if sensor_id in self.sensor_config['emg_ids']:
                                    data_index = self.sensor_config['emg_ids'].index(sensor_id)
                                    if data_index < len(packet['emg']):
                                        value = packet['emg'][data_index]
                                        if -10.0 <= value <= 10.0:  # Vérifier la validité
                                            self.plot_data[sensor_name_key] = np.roll(self.plot_data[sensor_name_key], -1)
                                            self.plot_data[sensor_name_key][-1] = value
                                            plot_widget.plot(self.plot_data[sensor_name_key], clear=True, pen=pg.mkPen('b', width=2))
                            except (ValueError, KeyError, IndexError):
                                pass
                        elif sensor_type == "pMMG":
                            try:
                                if 'pmmg_ids' in self.sensor_config and sensor_id in self.sensor_config['pmmg_ids']:
                                    data_index = self.sensor_config['pmmg_ids'].index(sensor_id)
                                    if data_index < len(packet['pmmg']):
                                        value = packet['pmmg'][data_index]
                                        if -10.0 <= value <= 10.0:  # Vérifier la validité
                                            self.plot_data[sensor_name_key] = np.roll(self.plot_data[sensor_name_key], -1)
                                            self.plot_data[sensor_name_key][-1] = value
                                            plot_widget.plot(self.plot_data[sensor_name_key], clear=True, pen=pg.mkPen('b', width=2))
                            except (ValueError, KeyError, IndexError):
                                pass
                        elif sensor_type == "IMU":
                            try:
                                if sensor_id in self.sensor_config['imu_ids']:
                                    data_index = self.sensor_config['imu_ids'].index(sensor_id)
                                    if data_index < len(packet['imu']):
                                        quaternion = packet['imu'][data_index]
                                        if self._is_valid_quaternion(quaternion):
                                            plot_widget.clear()
                                            for i, axis in enumerate(['w', 'x', 'y', 'z']):
                                                plot_data_key = f"{sensor_name_key}_{axis}"
                                                # S'assurer que la clé existe dans self.plot_data
                                                if plot_data_key not in self.plot_data:
                                                    self.plot_data[plot_data_key] = np.zeros(100)
                                                self.plot_data[plot_data_key] = np.roll(self.plot_data[plot_data_key], -1)
                                                self.plot_data[plot_data_key][-1] = quaternion[i]
                                                plot_widget.plot(self.plot_data[plot_data_key], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)
                                            plot_widget.addLegend()
                            except (ValueError, KeyError, IndexError):
                                pass
                    
                    # Mettre à jour les graphiques par groupe
                    for sensor_group_name, plot_widget in self.group_plots.items():
                        plot_widget.clear()
                        for full_sensor_name_ui, data_array_np in self.group_plot_data[sensor_group_name].items():
                            sensor_base = full_sensor_name_ui.split()[0]  # Prendre juste "EMG25", pas "EMG25 (Biceps)"
                            sensor_type = ''.join(filter(str.isalpha, sensor_base))
                            sensor_num_str = ''.join(filter(str.isdigit, sensor_base))
                            if not sensor_num_str: continue
                            sensor_id = int(sensor_num_str)
                            
                            if sensor_type == "EMG" and sensor_group_name == "EMG":
                                try:
                                    if sensor_id in self.sensor_config['emg_ids']:
                                        data_index = self.sensor_config['emg_ids'].index(sensor_id)
                                        if data_index < len(packet['emg']):
                                            value = packet['emg'][data_index]
                                            if -10.0 <= value <= 10.0:  # Vérifier la validité
                                                self.group_plot_data[sensor_group_name][full_sensor_name_ui] = np.roll(self.group_plot_data[sensor_group_name][full_sensor_name_ui], -1)
                                                self.group_plot_data[sensor_group_name][full_sensor_name_ui][-1] = value
                                                # Déterminer la couleur
                                                ui_idx = sensor_id % 8  # Utiliser modulo pour s'assurer que l'index est dans la plage
                                                colors = ['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w']
                                                plot_widget.plot(self.group_plot_data[sensor_group_name][full_sensor_name_ui], 
                                                            pen=pg.mkPen(colors[ui_idx], width=2), 
                                                            name=full_sensor_name_ui)
                                except (ValueError, KeyError, IndexError):
                                    pass
                            elif sensor_type == "pMMG" and sensor_group_name == "pMMG":
                                try:
                                    if 'pmmg_ids' in self.sensor_config and sensor_id in self.sensor_config['pmmg_ids']:
                                        data_index = self.sensor_config['pmmg_ids'].index(sensor_id)
                                        if data_index < len(packet['pmmg']):
                                            value = packet['pmmg'][data_index]
                                            if -10.0 <= value <= 10.0:  # Vérifier la validité
                                                self.group_plot_data[sensor_group_name][full_sensor_name_ui] = np.roll(self.group_plot_data[sensor_group_name][full_sensor_name_ui], -1)
                                                self.group_plot_data[sensor_group_name][full_sensor_name_ui][-1] = value
                                                ui_idx = sensor_id % 8
                                                color_idx = ui_idx
                                                colors = ['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w']
                                                plot_widget.plot(self.group_plot_data[sensor_group_name][full_sensor_name_ui], 
                                                            pen=pg.mkPen(colors[color_idx], width=2), 
                                                            name=full_sensor_name_ui)
                                except (ValueError, KeyError, IndexError):
                                    pass
                            elif sensor_type == "IMU" and sensor_base.startswith("IMU"):
                                try:
                                    if sensor_id in self.sensor_config['imu_ids']:
                                        data_index = self.sensor_config['imu_ids'].index(sensor_id)
                                        if data_index < len(packet['imu']):
                                            quaternion = packet['imu'][data_index]
                                            if self._is_valid_quaternion(quaternion):
                                                for i, axis in enumerate(['w', 'x', 'y', 'z']):
                                                    axis_key = f"{full_sensor_name_ui}_{axis}"
                                                    if axis_key not in self.group_plot_data[sensor_group_name]:
                                                        self.group_plot_data[sensor_group_name][axis_key] = np.zeros(100)
                                                    self.group_plot_data[sensor_group_name][axis_key] = np.roll(self.group_plot_data[sensor_group_name][axis_key], -1)
                                                    self.group_plot_data[sensor_group_name][axis_key][-1] = quaternion[i]
                                                    plot_widget.plot(self.group_plot_data[sensor_group_name][axis_key], 
                                                                pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), 
                                                                name=f"{full_sensor_name_ui}_{axis}")
                                except (ValueError, KeyError, IndexError):
                                    pass
                        plot_widget.addLegend()
                        
                except ConnectionResetError:
                    print("[ERROR] Connection reset by peer.")
                    self.client_socket = None
                    self.connect_button.setText("Connect")
                    QMessageBox.warning(self, "Connection Lost", "Connection to the device was reset.")
                except struct.error as e:
                    # Problème de décodage de structure, probablement un paquet malformé
                    print(f"[ERROR] Struct unpacking error: {e}. Packet size may be incorrect.")
                    # Optionnel: tenter de resynchroniser en lisant quelques octets supplémentaires
                    try:
                        # Lire quelques octets pour tenter de se resynchroniser
                        extra_bytes = self.client_socket.recv(16, socket.MSG_DONTWAIT)
                        print(f"[INFO] Read {len(extra_bytes)} extra bytes to try to resynchronize.")
                    except:
                        pass
                except socket.timeout:
                    print("[WARNING] Socket timeout while receiving data.")
                except Exception as e:
                    print(f"[ERROR] Failed to receive/process data: {e}")
            else:
                # L'utilisateur est en mode enregistrement mais sans connexion Ethernet valide
                if self.recording and not self.client_socket:
                    print("[WARNING] Recording active but no Ethernet connection.")
                pass
    
    def _contains_invalid_data(self, packet):
        """Vérifie si un paquet contient des données manifestement invalides"""
        # Vérifier les EMG
        for value in packet['emg']:
            if not isinstance(value, (int, float)) or abs(value) > 10.0:
                return True
                
        # Vérifier les pMMG
        for value in packet['pmmg']:
            if not isinstance(value, (int, float)) or abs(value) > 10.0:
                return True
                
        # Vérifier les IMU (quaternions)
        for i, quaternion in enumerate(packet['imu']):
            if not self._is_valid_quaternion(quaternion):
                print(f"[DEBUG] IMU {i} quaternion invalide: {quaternion}")
                return True
                
        return False
        
    def _is_valid_quaternion(self, quaternion):
        """Vérifie si un quaternion est valide"""
        # Vérifier que le quaternion est une liste ou un tuple de 4 éléments
        if not isinstance(quaternion, (list, tuple)) or len(quaternion) != 4:
            print(f"[DEBUG] Format quaternion invalide: {type(quaternion)}, longueur: {len(quaternion) if hasattr(quaternion, '__len__') else 'N/A'}")
            return False
            
        # Les composantes d'un quaternion doivent être des nombres
        for i, component in enumerate(quaternion):
            if not isinstance(component, (int, float)):
                print(f"[DEBUG] Composante {i} non numérique: {type(component)}")
                return False
                
        # On accepte presque toutes les valeurs, en vérifiant juste qu'elles ne sont pas aberrantes
        # Les quaternions peuvent être non normalisés selon l'implémentation matérielle
        for i, component in enumerate(quaternion):
            if abs(component) > 100.0:  # Valeurs très éloignées suggèrent des données corrompues
                print(f"[DEBUG] Valeur aberrante dans quaternion: composante {i} = {component}")
                return False
                
        return True

    def on_display_mode_changed(self):
        if hasattr(self, 'recording') and self.recording:
            QMessageBox.warning(self, 'Warning', "You cannot change the display mode once recording has started.")
            # Revenir au mode précédent
            if self.single_sensor_mode.isChecked():
                self.group_sensor_mode.setChecked(True)
            else:
                self.single_sensor_mode.setChecked(True)
        else:
            reply = QMessageBox.question(self, 'Change Mode',
                                         "Are you sure you want to change the display mode?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.update_display_mode()
            else:
                # Revenir au mode précédent
                if self.single_sensor_mode.isChecked():
                    self.group_sensor_mode.setChecked(True)
                else:
                    self.single_sensor_mode.setChecked(True)

    def update_display_mode(self):
        # Effacer les graphiques actuels
        for plot_widget in self.plots.values():
            plot_widget.setParent(None)
            plot_widget.deleteLater()
        self.plots.clear()
        self.plot_data.clear()

        for plot_widget in self.group_plots.values():
            plot_widget.setParent(None)
            plot_widget.deleteLater()
        self.group_plots.clear()
        self.group_plot_data.clear()

        # Reconstruire les graphiques en fonction du mode sélectionné
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()
        else:
            # Re-sélectionner les capteurs précédemment sélectionnés
            for sensor_name in self.highlighted_sensors:
                self.plot_sensor_data(sensor_name)

    def start_recording(self):
        self.recording = True
        self.recording_stopped = False
        
        # Déterminer le nombre correct d'IMUs depuis la configuration
        num_imus = getattr(self.sensor_config, 'num_imus', 0) if self.sensor_config else 0
        if num_imus == 0:
            print("[WARNING] Aucun IMU détecté, initialisation avec 1 IMU par défaut")
            num_imus = 1  # Au moins un pour éviter les problèmes
            
        # Initialiser les structures de données pour l'enregistrement
        self.recorded_data = {
            "EMG": [[] for _ in range(8)],           # 8 EMGs max
            "IMU": [[] for _ in range(num_imus)],    # Nombre réel d'IMUs
            "pMMG": [[] for _ in range(8)]           # 8 pMMGs max
        }
        
        print(f"[INFO] Début de l'enregistrement avec {num_imus} IMUs")
        self.record_button.setText("Record Stop")

    def stop_recording(self):
        self.recording = False
        self.recording_stopped = True
        self.record_button.setText("Record Start")
        self.record_button.setStyleSheet("""
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
        }
        QPushButton:hover {
            background-color: #43a047;
        }
        QPushButton:pressed {
            background-color: #388e3c;
        }
        QPushButton:disabled {
            background-color: #e0e0e0;
            border: 1px solid #d0d0d0;
            color: #a0a0a0;
        }
        """)
        self.record_button.setEnabled(False)  # Désactiver le bouton
        self.show_recorded_data()
        self.request_h5_file.setEnabled(True)  # Désactiver le bouton au départ
        self.clear_plot.setEnabled(True)  # Désactiver le bouton au départ
        self.refresh_the_connected_systeme.setEnabled(True)  # Désactiver le bouton au départ

    def show_recorded_data(self):
        # Afficher les données enregistrées sur les graphiques existants
        if not any(self.recorded_data["EMG"][0]) and not any(self.recorded_data["IMU"][0]) and not any(self.recorded_data["pMMG"][0]):
            QMessageBox.warning(self, 'Warning', "No data recorded.")
            return

        # Arrêter la génération de données
        self.timer.stop()

        # Afficher les données enregistrées sur les graphiques existants
        for sensor_name, plot_widget in self.plots.items():
            if sensor_name.startswith("EMG"):
                index = int(sensor_name[3]) - 1
                plot_widget.plot(self.recorded_data["EMG"][index], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("pMMG"):
                index = int(sensor_name[4]) - 1
                plot_widget.plot(self.recorded_data["pMMG"][index], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("IMU"):
                index = int(sensor_name[3]) - 1
                quaternion = self.recorded_data["IMU"][index]
                plot_widget.clear()
                for i, axis in enumerate(['w', 'x', 'y', 'z']):
                    plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)

                plot_widget.addLegend()

        for sensor_group, plot_widget in self.group_plots.items():
            plot_widget.clear()
            for sensor_name, data in self.group_plot_data[sensor_group].items():
                if sensor_name.startswith("IMU"):
                    index = int(sensor_name[3]) - 1
                    quaternion = self.recorded_data["IMU"][index]
                    for i, axis in enumerate(['w', 'x', 'y', 'z']):
                        plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=f"{sensor_name}_{axis}")
                else:
                    # Extraire le numéro du capteur en ignorant les "matched parts"
                    sensor_num = int(''.join(filter(str.isdigit, sensor_name)))
                    if sensor_name.startswith("EMG"):
                        index = sensor_num - 1
                        plot_widget.plot(self.recorded_data["EMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][sensor_num - 1], width=2), name=sensor_name)
                    elif sensor_name.startswith("pMMG"):
                        index = sensor_num - 1
                        plot_widget.plot(self.recorded_data["pMMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][sensor_num - 1], width=2), name=sensor_name)

            plot_widget.addLegend()

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            # Vérifier si nous sommes connectés à un dispositif
            if not self.client_socket and not self.is_server_running:
                QMessageBox.warning(self, "Not Connected", 
                                   "Please connect to a device before starting recording.")
                return
                
            if self.record_button.isEnabled():
                self.start_recording()

    def toggle_animation(self):
        """Toggle stickman walking animation."""
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")
        
        # Change button color based on animation state
        if is_walking:
            self.animate_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                text-align: center;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
            """)
        else:
            self.animate_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                text-align: center;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1e88e5;
            }
            QPushButton:pressed {
                background-color: #1976d2;
            }
            """)

    def reset_model_view(self):
        """Réinitialiser la vue avec animation et retour visuel"""
        # Obtenir les rotations actuelles
        start_rotation = (self.model_3d_widget.model_viewer.rotation_x,
                        self.model_3d_widget.model_viewer.rotation_y,
                        self.model_3d_widget.model_viewer.rotation_z)
        
        # Créer un timer pour animer le retour à zéro
        steps = 10
        timer = QTimer(self)
        step_counter = [0]  # Utiliser une liste pour pouvoir la modifier dans la closure
        
        def animation_step():
            step_counter[0] += 1
            progress = step_counter[0] / steps
            
            # Interpolation linéaire vers zéro
            x = start_rotation[0] * (1 - progress)
            y = start_rotation[1] * (1 - progress)
            z = start_rotation[2] * (1 - progress)
            
            self.model_3d_widget.model_viewer.rotation_x = x
            self.model_3d_widget.model_viewer.rotation_y = y
            self.model_3d_widget.model_viewer.rotation_z = z
            self.model_3d_widget.model_viewer.update()
            
            if step_counter[0] >= steps:
                timer.stop()
        
        timer.timeout.connect(animation_step)
        timer.start(20)  # 50 FPS

    def open_sensor_mapping_dialog(self):
        """Ouvrir le dialogue de configuration des capteurs"""
        # Récupérer les mappages actuels
        current_mappings = {
            'EMG': getattr(self, 'emg_mappings', {}), 
            'IMU': self.model_3d_widget.get_current_mappings(),
            'pMMG': getattr(self, 'pmmg_mappings', {})
        }

        dialog = SensorMappingDialog(self, current_mappings)
        
        # Connecter le signal aux méthodes de mise à jour
        dialog.mappings_updated.connect(self.update_sensor_mappings)
        
        dialog.exec_()

    def update_sensor_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        """Mettre à jour les mappages de capteurs après fermeture du dialogue"""
        # Mettre à jour les mappages IMU
        for imu_id, body_part in imu_mappings.items():
            self.model_3d_widget.map_imu_to_body_part(imu_id, body_part)
        
        # Stocker les mappages EMG et pMMG
        self.emg_mappings = emg_mappings
        self.pmmg_mappings = pmmg_mappings
        
        # Mettre à jour les mappages dans le modèle 3D
        self.model_3d_widget.model_viewer.set_emg_mapping(emg_mappings)
        self.model_3d_widget.model_viewer.set_pmmg_mapping(pmmg_mappings)
        
        # Mettre à jour l'interface utilisateur pour refléter les nouveaux mappages
        self.refresh_sensor_tree()
        self.save_mappings()  # Sauvegarder les changements immédiatement

    def refresh_sensor_tree(self):
        """Mettre à jour l'arbre des capteurs pour refléter les mappages actuels"""
        # Parcourir tous les éléments de l'arbre
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            sensor_type = group_item.text(0).split()[0]  # "EMG", "IMU" ou "pMMG"
            
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_name = sensor_item.text(0).split()[0]  # Ex: "EMG1", "IMU2", etc.
                
                if sensor_name.startswith("IMU"):
                    sensor_id = int(sensor_name[3:])
                    mappings = self.model_3d_widget.get_current_mappings()
                    if sensor_id in mappings:
                        body_part = mappings[sensor_id]
                        body_part_ui = self._convert_model_part_to_ui(body_part)
                        sensor_item.setText(0, f"{sensor_name} ({body_part_ui})")
                
                elif sensor_name.startswith("EMG") and hasattr(self, 'emg_mappings'):
                    sensor_id = int(sensor_name[3:])
                    if sensor_id in self.emg_mappings:
                        body_part = self.emg_mappings[sensor_id]
                        body_part_ui = self._convert_model_part_to_ui(body_part)
                        sensor_item.setText(0, f"{sensor_name} ({body_part_ui})")
                
                elif sensor_name.startswith("pMMG") and hasattr(self, 'pmmg_mappings'):
                    sensor_id = int(sensor_name[4:])
                    if sensor_id in self.pmmg_mappings:
                        body_part = self.pmmg_mappings[sensor_id]
                        body_part_ui = self._convert_model_part_to_ui(body_part)
                        sensor_item.setText(0, f"{sensor_name} ({body_part_ui})")

    def _convert_model_part_to_ui(self, model_part):
        """Convertit les noms des parties du modèle 3D vers des noms plus lisibles pour l'UI."""
        mapping = {
            'head': 'Head',
            'neck': 'Neck',
            'torso': 'Torso',
        }
        return mapping.get(model_part, model_part)

    def save_mappings(self):
        """Save sensor mappings to a JSON file"""
        mappings = {
            'EMG': self.emg_mappings,
            'IMU': self.model_3d_widget.get_current_mappings(),
            'pMMG': self.pmmg_mappings
        }
        
        # Convert keys to strings for JSON serialization
        serializable_mappings = {}
        for sensor_type, mapping in mappings.items():
            serializable_mappings[sensor_type] = {str(k): v for k, v in mapping.items()}
        
        filepath = os.path.join(os.path.dirname(__file__), 'sensor_mappings.json')
        with open(filepath, 'w') as f:
            json.dump(serializable_mappings, f, indent=2)

    def load_mappings(self):
        """Load sensor mappings from a JSON file"""
        filepath = os.path.join(os.path.dirname(__file__), 'sensor_mappings.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    mappings = json.load(f)
                
                # Convert string keys back to integers
                if 'EMG' in mappings:
                    self.emg_mappings = {int(k): v for k, v in mappings['EMG'].items()}
                if 'pMMG' in mappings:
                    self.pmmg_mappings = {int(k): v for k, v in mappings['pMMG'].items()}
                    
                # Update IMU mappings directly
                if 'IMU' in mappings:
                    for imu_id, body_part in {int(k): v for k, v in mappings['IMU'].items()}.items():
                        self.model_3d_widget.map_imu_to_body_part(imu_id, body_part)
                
                # Refresh the UI to reflect loaded mappings
                self.refresh_sensor_tree()
                return True
            except Exception as e:
                print(f"Error loading mappings: {e}")
        return False

    def setup_default_mappings(self):
        """Permet à l'utilisateur de définir ses propres assignations par défaut"""
        # Récupérer les mappages actuels
        current_mappings = {
            'EMG': getattr(self, 'emg_mappings', {}), 
            'IMU': self.model_3d_widget.get_current_mappings(),
            'pMMG': getattr(self, 'pmmg_mappings', {})
        }

        # Afficher un dialogue pour configurer les mappages par défaut
        dialog = SensorMappingDialog(self, current_mappings)
        
        # Connecter le signal pour mettre à jour les mappages
        dialog.mappings_updated.connect(self.save_as_default_mappings)
        
        # Afficher un message pour expliquer la fonction
        QMessageBox.information(
            self, 
            "Default Assignments Setup",
            "Configure your sensor mappings as you prefer.\n"
            "These settings will be saved as the default configuration for future use."
        )
        
        dialog.exec_()

    def save_as_default_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        """Sauvegarder les mappages actuels comme configuration par défaut"""
        # Mettre à jour les mappages actuels
        self.update_sensor_mappings(emg_mappings, imu_mappings, pmmg_mappings)
        
        # Sauvegarder les mappages comme configuration par défaut
        default_mappings = {
            'EMG': emg_mappings,
            'IMU': imu_mappings,
            'pMMG': pmmg_mappings
        }
        
        # Convertir les clés en chaînes pour la sérialisation JSON
        serializable_mappings = {}
        for sensor_type, mapping in default_mappings.items():
            serializable_mappings[sensor_type] = {str(k): v for k, v in mapping.items()}
        
        # Sauvegarder dans un fichier séparé pour les mappages par défaut
        filepath = os.path.join(os.path.dirname(__file__), 'default_sensor_mappings.json')
        with open(filepath, 'w') as f:
            json.dump(serializable_mappings, f, indent=2)
        
        QMessageBox.information(
            self, 
            "Default Saved",
            "Your sensor assignments have been saved as the default configuration."
        )

    def closeEvent(self, event):
        """Called when the application is closed"""
        self.save_mappings()  # Sauvegarder les mappages à la fermeture
        
        # Nettoyer les ressources du serveur Ethernet
        self.stop_ethernet_server()
        
        event.accept()

    def create_specific_tab(self, sensor_type, i):
        label = QLabel(f"{sensor_type} {i}")
        label.setStyleSheet(f"""
            color: {self._get_color_for_type(sensor_type)};
            font-weight: bold;
            font-size: 14px;
            padding: 3px;
        """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    dashboard.show()
    sys.exit(app.exec_())
