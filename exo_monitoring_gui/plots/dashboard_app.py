'''
Fix the issue where IMU sensors do not appear in the 2D Plot after pressing record stop and being in the plot mode by sensor group.
'''
import time  # Ajouter time pour les optimisations
import sys
import os
import traceback
import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox, 
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea, QGroupBox,
    QSizePolicy  # Added missing QSizePolicy import
)
from PyQt5.QtCore import Qt, QTimer # QThread, pyqtSignal are in the backend
from PyQt5.QtGui import QColor, QBrush # QCursor is no longer directly used here

# Add the parent directory and backend folder to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'back')))

from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog
# Import logic from the backend file
from plots.back.dashboard_app_back import DashboardAppBack  # Utiliser un chemin absolu


class DashboardApp(QMainWindow):
    def __init__(self, subject_file=None, parent_revi=None, file_list=None):
        super().__init__()
        # Store the subject file for later use
        self.subject_file = subject_file
        self.parent_revi = parent_revi
        self.file_list = file_list if file_list is not None else None
        self._last_plot_update = 0
        self._plot_update_interval_ms = 50  # 20 FPS max au lieu de 30
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
        self.subject_file = subject_file
        self.backend = DashboardAppBack(self)

        self.init_ui()
        self.backend.load_mappings()

        self.curves = {}
        self.group_curves = {}
        
        # Initialiser main_bar_re correctement
        try:
            from utils.Menu_bar import MainBar
            self.main_bar_re = MainBar(self)
            
            if hasattr(self.main_bar_re, '_create_menubar'):
                self.main_bar_re._create_menubar()
                
            if hasattr(self.main_bar_re, 'edit_creation_date'):
                self.main_bar_re.edit_creation_date()
                
            if hasattr(self.main_bar_re, '_all_false_or_true'):
                self.main_bar_re._all_false_or_true(False)
                
            # Désactiver le menu Edit au démarrage
            if hasattr(self.main_bar_re, 'edit_Boleen'):
                self.main_bar_re.edit_Boleen(False)
            if hasattr(self.main_bar_re, 'set_refresh_connected_system_enabled'):
                self.main_bar_re.set_refresh_connected_system_enabled(False)
        except Exception as e:
            print(f"[ERROR] Error initializing MainBar: {e}")
            import traceback
            traceback.print_exc()
            self.main_bar_re = None

        print("Debug 56")
        print(self.parent_revi)      
        if self.parent_revi is not None:
            print("[Debug 2 le s]")
            self.main_bar_re.request_h5_file_action.disconnect()
            self.main_bar_re.request_h5_file_action.triggered.connect(
                lambda: self.main_bar_re.request_h5_file_review(self.subject_file, self.file_list)
            )

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Connected Systems"), stretch=1)
        title_layout.addWidget(QLabel("Graphics / Visual Zone"), stretch=2)
        title_layout.addWidget(QLabel("3D Perspective"), stretch=1)
        main_layout.addLayout(title_layout)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout, stretch=1)

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
        self.connected_systems.itemClicked.connect(self.on_sensor_clicked)

        # Ne plus créer les groupes par défaut - ils seront créés uniquement quand des capteurs sont détectés
        # Les groupes seront ajoutés dynamiquement dans update_sensor_tree_from_config()

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

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

        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout()
        self.middle_placeholder.setLayout(self.middle_layout)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.middle_placeholder)
        middle_panel = QVBoxLayout()
        middle_panel.addWidget(scroll_area)

        right_panel = QVBoxLayout()
        label_3d_title = QLabel("3D Perspective")
        label_3d_title.setAlignment(Qt.AlignCenter)
        label_3d_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_panel.addWidget(label_3d_title)
        
        # Création du modèle 3D dans un conteneur dédié avec une taille fixe
        self.model_3d_container = QWidget()
        self.model_3d_container.setMinimumSize(350, 400)
        self.model_3d_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Forcer la transparence COMPLÈTE du conteneur
        self.model_3d_container.setAttribute(Qt.WA_TranslucentBackground)
        self.model_3d_container.setStyleSheet("background: transparent; border: none;")

        model_3d_layout = QVBoxLayout(self.model_3d_container)
        # Réduire les marges au minimum absolu
        model_3d_layout.setContentsMargins(0, 0, 0, 0)
        model_3d_layout.setSpacing(0)

        self.model_3d_widget = Model3DWidget()
        print(f"Created 3D model widget: {self.model_3d_widget}")

        # Forcer des dimensions visibles pour le widget 3D
        self.model_3d_widget.setMinimumSize(300, 300)
        self.model_3d_widget.setVisible(True)
        # Forcer également la transparence du widget 3D
        self.model_3d_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.model_3d_widget.setStyleSheet("background: transparent; border: none;")

        # Ajouter au layout et s'assurer qu'il occupe tout l'espace
        model_3d_layout.addWidget(self.model_3d_widget, 1)
        right_panel.addWidget(self.model_3d_container, stretch=3)
        
        # Réorganisation des boutons en groupes logiques avec des QGroupBox
        # Groupe 1: Contrôles de visualisation
        view_controls_group = QGroupBox("Visualisation")
        view_controls_layout = QHBoxLayout()
        
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
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
        
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_model_view)
        self.reset_view_button.setStyleSheet("""
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
        """)
        
        view_controls_layout.addWidget(self.animate_button)
        view_controls_layout.addWidget(self.reset_view_button)
        view_controls_group.setLayout(view_controls_layout)
        right_panel.addWidget(view_controls_group)
        
        # Groupe 2: Configuration des capteurs
        sensor_config_group = QGroupBox("Configuration des capteurs")
        sensor_config_layout = QVBoxLayout()
        
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        self.config_button.setEnabled(False)  # Disable the button by default
        
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
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.default_config_button.clicked.connect(self.setup_default_mappings)
        
        sensor_config_layout.addWidget(self.config_button)
        sensor_config_layout.addWidget(self.default_config_button)
        sensor_config_group.setLayout(sensor_config_layout)
        right_panel.addWidget(sensor_config_group)
        
        # Groupe 3: Fonctionnalités avancées
        advanced_features_group = QGroupBox("Advanced Features")
        advanced_features_layout = QVBoxLayout()
        
        self.motion_prediction_button = QPushButton("Enable Smart Movement")
        self.motion_prediction_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.motion_prediction_button.clicked.connect(self.toggle_motion_prediction)
        
        # Ajouter des informations d'état
        self.motion_state_label = QLabel("Status: Inactive")
        self.motion_state_label.setStyleSheet("color: #666; font-style: italic;")
        self.motion_state_label.setAlignment(Qt.AlignCenter)
        
        advanced_features_layout.addWidget(self.motion_prediction_button)
        advanced_features_layout.addWidget(self.motion_state_label)
        advanced_features_group.setLayout(advanced_features_layout)
        right_panel.addWidget(advanced_features_group)
        
        # Groupe 4: Calibration T-pose
        calibration_group = QGroupBox("T-pose Calibration")
        calibration_layout = QVBoxLayout()
        
        calibration_buttons_layout = QHBoxLayout()
        self.calibration_start_button = QPushButton("Calibration T-pose")
        self.calibration_start_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
            QPushButton:pressed {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.calibration_start_button.clicked.connect(self.start_tpose_calibration)
        self.calibration_start_button.setEnabled(False)

        self.calibration_stop_button = QPushButton("Stop")
        self.calibration_stop_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #E53935;
            }
            QPushButton:pressed {
                background-color: #D32F2F;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.calibration_stop_button.clicked.connect(self.stop_tpose_calibration)
        self.calibration_stop_button.setEnabled(False)

        self.calibration_reset_button = QPushButton("Reset")
        self.calibration_reset_button.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.calibration_reset_button.clicked.connect(self.reset_tpose_calibration)
        self.calibration_reset_button.setEnabled(False)
        
        calibration_buttons_layout.addWidget(self.calibration_start_button)
        calibration_buttons_layout.addWidget(self.calibration_stop_button)
        calibration_buttons_layout.addWidget(self.calibration_reset_button)
        
        # Ajouter un label d'état pour la calibration
        self.calibration_status_label = QLabel("Status: Calibration required")
        self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
        self.calibration_status_label.setAlignment(Qt.AlignCenter)
        
        calibration_layout.addLayout(calibration_buttons_layout)
        calibration_layout.addWidget(self.calibration_status_label)
        calibration_group.setLayout(calibration_layout)
        right_panel.addWidget(calibration_group)

        # Timer pour mettre à jour le statut de calibration
        self.calibration_status_timer = QTimer(self)
        self.calibration_status_timer.timeout.connect(self.update_calibration_status_ui)
        self.calibration_status_timer.start(500)  # Mise à jour toutes les 500ms
        
        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(middle_panel, stretch=4)
        content_layout.addLayout(right_panel, stretch=2)
        
        footer_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.backend.connect_sensors)
        self.record_button = QPushButton("Record Start")
        self.record_button.clicked.connect(self.backend.toggle_recording)
        self.record_button.setEnabled(False)
        
        button_style = ("""
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
        """)
        record_button_style = ("""
        QPushButton {
            background-color: #E0E0E0;
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
        """)
        animate_button_style = ("""
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
        reset_view_button_style = ("""
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
        """)
        config_button_style = ("""
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
        """)

        self.animate_button.setStyleSheet(animate_button_style)
        self.reset_view_button.setStyleSheet(reset_view_button_style)
        self.config_button.setStyleSheet(config_button_style)
        self.connect_button.setStyleSheet(button_style)
        self.record_button.setStyleSheet(record_button_style)
        
        for btn in (self.connect_button, self.record_button):
            footer_layout.addWidget(btn)
        main_layout.addLayout(footer_layout)

        self.plots = {}
        self.highlighted_sensors = set()
        self.group_plots = {}

        self.display_mode_group.buttonClicked.connect(self.on_display_mode_changed)

    def update_live_plots(self, packet):
        """Met à jour les graphiques en temps réel avec optimisations anti-lag."""
        current_time = time.time() * 1000  # ms
        if current_time - self._last_plot_update < self._plot_update_interval_ms:
            return  # Skip frame to avoid overloading UI
        self._last_plot_update = current_time

        # EMG individuel - optimisé
        if 'emg' in packet and packet['emg']:
            for i, emg_value in enumerate(packet['emg']):
                sensor_base = f"EMG{self.backend.sensor_config['emg_ids'][i]}" if self.backend.sensor_config and 'emg_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['emg_ids']) else f"EMG{i+1}"
                if sensor_base in self.curves:
                    data = self.backend.plot_data.get(sensor_base)
                    if data is not None:
                        data = np.roll(data, -1)
                        data[-1] = emg_value
                        self.backend.plot_data[sensor_base] = data
                        self.curves[sensor_base].setData(data)

        # EMG groupe - optimisé
        if 'emg' in packet and packet['emg'] and "EMG" in self.group_plots:
            for i, emg_value in enumerate(packet['emg']):
                sensor_base = f"EMG{self.backend.sensor_config['emg_ids'][i]}" if self.backend.sensor_config and 'emg_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['emg_ids']) else f"EMG{i+1}"
                curve_key = sensor_base
                if curve_key in self.group_curves:
                    data = self.backend.group_plot_data["EMG"].get(curve_key)
                    if data is not None:
                        data = np.roll(data, -1)
                        data[-1] = emg_value
                        self.backend.group_plot_data["EMG"][curve_key] = data
                        self.group_curves[curve_key].setData(data)

        # pMMG individuel - optimisé
        if 'pmmg' in packet and packet['pmmg']:
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_base = f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}" if self.backend.sensor_config and 'pmmg_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['pmmg_ids']) else f"pMMG{i+1}"
                if sensor_base in self.curves:
                    data = self.backend.plot_data.get(sensor_base)
                    if data is not None:
                        data = np.roll(data, -1)
                        data[-1] = pmmg_value
                        self.backend.plot_data[sensor_base] = data
                        self.curves[sensor_base].setData(data)

        # pMMG groupe - optimisé
        if 'pmmg' in packet and packet['pmmg'] and "pMMG" in self.group_plots:
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_base = f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}" if self.backend.sensor_config and 'pmmg_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['pmmg_ids']) else f"pMMG{i+1}"
                curve_key = sensor_base
                if curve_key in self.group_curves:
                    data = self.backend.group_plot_data["pMMG"].get(curve_key)
                    if data is not None:
                        data = np.roll(data, -1)
                        data[-1] = pmmg_value
                        self.backend.group_plot_data["pMMG"][curve_key] = data
                        self.group_curves[curve_key].setData(data)

        # IMU individuel (4 composantes) - optimisé
        if 'imu' in packet and packet['imu']:
            for i, quaternion in enumerate(packet['imu']):
                sensor_base = f"IMU{self.backend.sensor_config['imu_ids'][i]}" if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['imu_ids']) else f"IMU{i+1}"
                for j, axis in enumerate(['w', 'x', 'y', 'z']):
                    curve_key = f"{sensor_base}_{axis}"
                    if curve_key in self.curves:
                        data = self.backend.plot_data.get(curve_key)
                        if data is not None:
                            data = np.roll(data, -1)
                            data[-1] = quaternion[j]
                            self.backend.plot_data[curve_key] = data
                            self.curves[curve_key].setData(data)

        # IMU groupe - optimisé
        if 'imu' in packet and packet['imu'] and "IMU" in self.group_plots:
            for i, quaternion in enumerate(packet['imu']):
                sensor_base = f"IMU{self.backend.sensor_config['imu_ids'][i]}" if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config and i < len(self.backend.sensor_config['imu_ids']) else f"IMU{i+1}"
                for j, axis in enumerate(['w', 'x', 'y', 'z']):
                    curve_key = f"{sensor_base}_{axis}"
                    if curve_key in self.group_curves:
                        data = self.backend.group_plot_data["IMU"].get(curve_key)
                        if data is not None:
                            data = np.roll(data, -1)
                            data[-1] = quaternion[j]
                            self.backend.group_plot_data["IMU"][curve_key] = data
                            self.group_curves[curve_key].setData(data)

    def apply_imu_data_to_3d_model(self, imu_data_list):
        """Applique les données IMU au modèle 3D avec limitation de fréquence."""
        if not hasattr(self, 'model_3d_widget') or not self.model_3d_widget:
            return
        if not self.backend.sensor_config or 'imu_ids' not in self.backend.sensor_config:
            return

        configured_imu_ids = self.backend.sensor_config['imu_ids']
        
        for i, quaternion_data in enumerate(imu_data_list):
            if i < len(configured_imu_ids):
                imu_id = configured_imu_ids[i]
                try:
                    success = self.model_3d_widget.apply_imu_data(imu_id, quaternion_data)
                    if not success:
                        print(f"[DASHBOARD_DEBUG] Failed to apply IMU {imu_id} data")
                except Exception as e:
                    print(f"[DASHBOARD_DEBUG] Error applying IMU {imu_id} data: {e}")
        
        # Pas de force update - laisser le système de batch update gérer

    def reset_sensor_display(self):
        # Completely clear all sensor groups and items
        self.connected_systems.clear()
        
        # Disable calibration buttons when disconnecting
        self.calibration_start_button.setEnabled(False)
        self.calibration_stop_button.setEnabled(False)
        self.calibration_reset_button.setEnabled(False)
        self.calibration_start_button.setText("Calibration (requires IMUs)")
        
        # Désactiver "Refresh Connected System" lors de la déconnexion
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'set_refresh_connected_system_enabled'):
                try:
                    self.main_bar_re.set_refresh_connected_system_enabled(False)
                except Exception as e:
                    print(f"[WARNING] Error disabling refresh connected system: {e}")

    def update_sensor_tree_from_config(self, sensor_config):
        if not sensor_config: return

        # First clear all existing sensors and groups
        self.reset_sensor_display()

        # List to store available sensors for display in the dialog
        available_sensors = {
            'EMG': [],
            'IMU': [],
            'pMMG': []
        }

        # Add EMGs only if they exist
        if sensor_config.get('emg_ids'):
            emg_group_item = QTreeWidgetItem(["EMG Data"])
            self.connected_systems.addTopLevelItem(emg_group_item)
            emg_group_item.setExpanded(True)
            
            for idx, sensor_id in enumerate(sensor_config.get('emg_ids', [])):
                sensor_item = QTreeWidgetItem([f"EMG{sensor_id}"])
                sensor_item.setForeground(0, QBrush(QColor("green")))
                emg_group_item.addChild(sensor_item)
                available_sensors['EMG'].append(sensor_id)

        # Add IMUs only if they exist
        if sensor_config.get('imu_ids'):
            imu_group_item = QTreeWidgetItem(["IMU Data"])
            self.connected_systems.addTopLevelItem(imu_group_item)
            imu_group_item.setExpanded(True)
            
            for idx, sensor_id in enumerate(sensor_config.get('imu_ids', [])):
                sensor_item = QTreeWidgetItem([f"IMU{sensor_id}"])
                sensor_item.setForeground(0, QBrush(QColor("green")))
                imu_group_item.addChild(sensor_item)
                available_sensors['IMU'].append(sensor_id)

        # Add pMMGs only if they exist
        if sensor_config.get('pmmg_ids'):
            pmmg_group_item = QTreeWidgetItem(["pMMG Data"])
            self.connected_systems.addTopLevelItem(pmmg_group_item)
            pmmg_group_item.setExpanded(True)
            
            for idx, sensor_id in enumerate(sensor_config.get('pmmg_ids', [])):
                sensor_item = QTreeWidgetItem([f"pMMG{sensor_id}"])
                sensor_item.setForeground(0, QBrush(QColor("green")))
                pmmg_group_item.addChild(sensor_item)
                available_sensors['pMMG'].append(sensor_id)
        
        # Enable the configuration button
        self.config_button.setEnabled(True)
        
        # Activer/désactiver les boutons de calibration en fonction de la présence d'IMUs
        has_imus = bool(sensor_config.get('imu_ids', []))
        self.calibration_start_button.setEnabled(has_imus)
        self.calibration_reset_button.setEnabled(has_imus)
        if not has_imus:
            self.calibration_start_button.setText("Calibration (requires IMUs)")
        else:
            self.calibration_start_button.setText("T-pose Calibration")
        
        # CORRECTION : Activer le menu Edit quand les capteurs sont connectés au lieu de le désactiver
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'set_refresh_connected_system_enabled'):
                try:
                    self.main_bar_re.set_refresh_connected_system_enabled(True)
                except Exception as e:
                    print(f"[WARNING] Error enabling refresh connected system: {e}")
        
        # Create group plots if necessary
        if self.group_sensor_mode.isChecked() and not self.group_plots:
            self.create_group_plots()
            
        # Toujours ouvrir automatiquement la boîte de dialogue de configuration des capteurs
        # après chaque connexion réussie, avec délai pour laisser l'interface se mettre à jour
        self.open_sensor_mapping_dialog(available_sensors)

    def find_sensor_group_item(self, group_name):
        for i_find_group in range(self.connected_systems.topLevelItemCount()):
            item = self.connected_systems.topLevelItem(i_find_group)
            if item.text(0) == group_name: return item
        return None

    def create_group_plots(self):
        """Crée les graphiques de groupe selon les capteurs disponibles."""
        if self.backend.sensor_config:
            # Créer le graphique EMG si il y a des capteurs EMG et qu'il n'existe pas déjà
            if self.backend.sensor_config.get('emg_ids') and "EMG" not in self.group_plots:
                plot_widget_emg = pg.PlotWidget(title="EMG Group")
                plot_widget_emg.setBackground('#1e1e1e')
                plot_widget_emg.getAxis('left').setTextPen('white')
                plot_widget_emg.getAxis('bottom').setTextPen('white')
                plot_widget_emg.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_emg.setTitle("EMG Group", color='white', size='14pt')
                plot_widget_emg.addLegend()
                self.middle_layout.addWidget(plot_widget_emg)
                self.group_plots["EMG"] = plot_widget_emg
                self.backend.group_plot_data["EMG"] = {}

            # Créer le graphique pMMG si il y a des capteurs pMMG et qu'il n'existe pas déjà
            if self.backend.sensor_config.get('pmmg_ids') and "pMMG" not in self.group_plots:
                plot_widget_pmmg = pg.PlotWidget(title="pMMG Group")
                plot_widget_pmmg.setBackground('#1e1e1e')
                plot_widget_pmmg.getAxis('left').setTextPen('white')
                plot_widget_pmmg.getAxis('bottom').setTextPen('white')
                plot_widget_pmmg.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_pmmg.setTitle("pMMG Group", color='white', size='14pt')
                plot_widget_pmmg.addLegend()
                self.middle_layout.addWidget(plot_widget_pmmg)
                self.group_plots["pMMG"] = plot_widget_pmmg
                self.backend.group_plot_data["pMMG"] = {}
            
            # Créer le graphique IMU si il y a des capteurs IMU et qu'il n'existe pas déjà
            if self.backend.sensor_config.get('imu_ids') and "IMU" not in self.group_plots:
                plot_widget_imu = pg.PlotWidget(title="IMU Group")
                plot_widget_imu.setBackground('#1e1e1e')
                plot_widget_imu.getAxis('left').setTextPen('white')
                plot_widget_imu.getAxis('bottom').setTextPen('white')
                plot_widget_imu.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_imu.setTitle("IMU Group", color='white', size='14pt')
                plot_widget_imu.addLegend()
                self.middle_layout.addWidget(plot_widget_imu)
                self.group_plots["IMU"] = plot_widget_imu
                self.backend.group_plot_data["IMU"] = {}

    def open_sensor_mapping_dialog(self, available_sensors=None):
        # Check if sensors are connected
        if not self.backend.sensor_config:
            QMessageBox.warning(self, "No Sensors", "Please connect sensors before configuring the mapping.")
            return
        
        try:
            print("[DEBUG] Opening sensor mapping dialog from dashboard...")
            
            # Si ce n'est pas la première fois, charger les mappages existants
            curr_maps = self.backend.get_current_mappings_for_dialog()
            print(f"[DEBUG] Current mappings retrieved: {curr_maps}")
            
            # Créer et afficher la boîte de dialogue
            dialog = SensorMappingDialog(self, curr_maps, available_sensors)
            dialog.mappings_updated.connect(self.backend.update_sensor_mappings)
            
            # ✅ SOLUTION : Utiliser exec_() pour afficher le dialogue de manière modale
            print("[DEBUG] Showing sensor mapping dialog...")
            result = dialog.exec_()
            
            if result == dialog.Accepted:
                print("[DEBUG] Sensor mapping dialog accepted")
            else:
                print("[DEBUG] Sensor mapping dialog cancelled")
                
        except Exception as e:
            print(f"[ERROR] Exception in open_sensor_mapping_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Dialog Error",
                f"Error opening sensor mapping dialog:\n{str(e)}\n\nPlease try again or restart the application."
            )
    def refresh_sensor_tree_with_mappings(self, emg_mappings, pmmg_mappings):
        for i_rf_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_rf_group)
            for j_rf_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_rf_sensor)
                if sensor_item.isHidden(): 
                    continue
                orig_text = sensor_item.text(0)
                s_base_rf = orig_text.split()[0]
                new_s_text = s_base_rf
                s_id_str_rf = ''.join(filter(str.isdigit, s_base_rf))
                if s_id_str_rf:
                    s_id_rf = int(s_id_str_rf)
                    if s_base_rf.startswith("EMG") and s_id_rf in emg_mappings:
                        new_s_text = f"{s_base_rf} ({emg_mappings[s_id_rf]})"
                    elif s_base_rf.startswith("pMMG") and s_id_rf in pmmg_mappings:
                        new_s_text = f"{s_base_rf} ({pmmg_mappings[s_id_rf]})"
                sensor_item.setText(0, new_s_text)

    def _convert_model_part_to_ui(self, model_part_name):
        return {'head': 'Head', 'neck': 'Neck', 'torso': 'Torso'}.get(model_part_name, model_part_name.replace('_', ' ').title())

    def setup_default_mappings(self):
        # Check if sensors are connected
        if not self.backend.sensor_config:
            QMessageBox.warning(self, "No Sensors", "Please connect sensors before configuring the mapping.")
            return
        
        curr_maps_def = self.backend.get_current_mappings_for_dialog()
        dialog_def = SensorMappingDialog(self, curr_maps_def)
        dialog_def.mappings_updated.connect(self.backend.save_as_default_mappings)
        QMessageBox.information(self, "Default Assignments Setup", "Configure sensor mappings...\nThese will be saved as default.")
        dialog_def.exec_()

    def apply_imu_mappings(self, imu_mappings_apply):
        for imu_id_apply, body_part_apply in imu_mappings_apply.items():
            self.model_3d_widget.map_imu_to_body_part(int(imu_id_apply), body_part_apply)
        self.refresh_sensor_tree_with_mappings(self.backend.emg_mappings, self.backend.pmmg_mappings)

    def closeEvent(self, event_close):
        # Force la réinitialisation du modèle 3D avant la fermeture
        if hasattr(self, 'model_3d_widget') and self.model_3d_widget:
            try:
                self.model_3d_widget.reset_view()
            except:
                pass
        self.backend.cleanup_on_close()
        event_close.accept()

    # Ajouter cette nouvelle méthode pour réinitialiser l'affichage 3D
    def force_reset_3d_view(self):
        """Force la réinitialisation complète de l'affichage 3D."""
        if hasattr(self, 'model_3d_widget') and self.model_3d_widget:
            try:
                # Réinitialise la vue
                self.model_3d_widget.reset_view()
                
                # Force une mise à jour
                self.model_3d_widget.update()
                
                # Réinitialise le conteneur si nécessaire
                if hasattr(self, 'model_3d_container'):
                    self.model_3d_container.update()
                    self.model_3d_container.repaint()
                    
                print("3D view reset successfully")
            except Exception as e:
                print(f"Error resetting 3D view: {e}")
                traceback.print_exc()

    def toggle_motion_prediction(self):
        """Enable or disable smart movement prediction."""
        try:
            # Change button appearance during processing
            self.motion_prediction_button.setEnabled(False)
            self.motion_prediction_button.setText("Processing...")
            self.motion_prediction_button.setStyleSheet("""
                QPushButton {
                    background-color: #777777;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: white;
                    font-size: 14px;
                    font-weight: 500;
                    text-align: center;
                    min-width: 120px;
                }
            """)
            
            # Allow UI to refresh
            QApplication.processEvents()
            
            # Perform the action
            is_enabled = self.model_3d_widget.toggle_motion_prediction()
            
            # Update button appearance based on result
            if is_enabled:
                self.motion_prediction_button.setText("Smart Movement: ACTIVE")
                self.motion_state_label.setText("Status: Active - Motion predicted")
                self.motion_state_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                self.motion_prediction_button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
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
                        background-color: #43A047;
                    }
                    QPushButton:pressed {
                        background-color: #388E3C;
                    }
                """)
            else:
                self.motion_prediction_button.setText("Smart Movement: INACTIVE")
                self.motion_state_label.setText("Status: Inactive")
                self.motion_state_label.setStyleSheet("color: #666; font-style: italic;")
                self.motion_prediction_button.setStyleSheet("""
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
            
            self.motion_prediction_button.setEnabled(True)
            return is_enabled
        except Exception as e:
            QMessageBox.warning(self, "Prediction Error", 
                               f"An error occurred while activating prediction: {str(e)}")
            self.motion_prediction_button.setText("Smart Movement: ERROR")
            self.motion_state_label.setText("Status: Error detected")
            self.motion_state_label.setStyleSheet("color: #F44336; font-weight: bold;")
            self.motion_prediction_button.setEnabled(True)
            return False

    def update_calibration_status_ui(self):
        """Updates the user interface based on calibration status."""
        try:
            if hasattr(self.model_3d_widget, 'get_calibration_status'):
                status = self.model_3d_widget.get_calibration_status()
                if status:
                    status_text = status.get('status_text', 'Unknown status')
                    progress = status.get('progress', 0)
                    is_complete = status.get('complete', False)
                    
                    # Update UI elements based on status
                    if is_complete:
                        self.calibration_status_label.setText("Status: Calibration complete")
                        self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        self.calibration_start_button.setText("T-pose Calibration")
                        self.calibration_start_button.setEnabled(True)
                        self.calibration_stop_button.setEnabled(False)
                        self.calibration_reset_button.setEnabled(True)
                    elif status.get('mode', False):
                        self.calibration_status_label.setText(f"Status: Calibrating ({progress}%)")
                        self.calibration_status_label.setStyleSheet("color: #FFA000; font-weight: bold;")
                    else:
                        self.calibration_status_label.setText("Status: Calibration required")
                        self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
        except Exception as e:
            print(f"[WARNING] Error updating calibration status: {e}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def start_tpose_calibration(self):
        """Démarre la calibration T-pose."""
        print("[UI_DEBUG] start_tpose_calibration called")
        try:
            # Check if sensors are connected
            if not self.backend.sensor_config or not self.backend.sensor_config.get('imu_ids'):
                QMessageBox.warning(self, "Calibration impossible", 
                               "Aucun capteur IMU n'est connecté.\n"
                               "Veuillez d'abord connecter des IMUs.")
                return False
                
            # Check if IMUs are mapped
            if not self.model_3d_widget.get_current_mappings():
                QMessageBox.warning(self, "Calibration impossible", 
                               "Aucun capteur IMU n'est assigné à une partie du corps.\n"
                               "Veuillez d'abord configurer le mapping des capteurs.")
                return False
                
            result = self.model_3d_widget.start_tpose_calibration()
            if not result:
                QMessageBox.warning(self, "Calibration impossible", 
                               "Impossible de démarrer la calibration.\n"
                               "Vérifiez que des capteurs IMU sont connectés.")
                return False
                
            self.calibration_start_button.setEnabled(False)
            self.calibration_stop_button.setEnabled(True)
            self.calibration_reset_button.setEnabled(False)
            self.calibration_start_button.setText("Calibration en cours...")
            self.calibration_status_label.setText("Status: Waiting for T-pose")
            self.calibration_status_label.setStyleSheet("color: #FFA000; font-weight: bold;")
            return result
        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", 
                               f"An error occurred while starting calibration: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return False

    def stop_tpose_calibration(self):
        """Arrête la calibration T-pose."""
        print("[UI_DEBUG] stop_tpose_calibration called")
        try:
            result = self.model_3d_widget.stop_tpose_calibration()
            self.calibration_start_button.setEnabled(True)
            self.calibration_stop_button.setEnabled(False)
            self.calibration_reset_button.setEnabled(True)
            
            if result:
                self.calibration_start_button.setText("T-pose Calibration")
                self.calibration_status_label.setText("Status: Calibration complete")
                self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.calibration_start_button.setText("T-pose Calibration")
                self.calibration_status_label.setText("Status: Calibration failed")
                self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return result
        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", 
                               f"An error occurred while stopping calibration: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return False

    def reset_tpose_calibration(self):
        """Remet à zéro la calibration T-pose."""
        print("[UI_DEBUG] reset_tpose_calibration called")
        try:
            self.model_3d_widget.reset_calibration()
            self.calibration_start_button.setText("T-pose Calibration")
            self.calibration_start_button.setEnabled(True)
            self.calibration_stop_button.setEnabled(False)
            self.calibration_reset_button.setEnabled(False)
            self.calibration_status_label.setText("Status: Calibration reset")
            self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
        except Exception as e:
            QMessageBox.critical(self, "Reset Error", 
                               f"An error occurred during reset: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def toggle_animation(self):
        """Active ou désactive l'animation du modèle 3D."""
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")
        anim_style_on = """QPushButton { background-color: #f44336; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #e53935; } QPushButton:pressed { background-color: #d32f2f; }"""
        anim_style_off = """QPushButton { background-color: #2196f3; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #1e88e5; } QPushButton:pressed { background-color: #1976d2; }"""
        self.animate_button.setStyleSheet(anim_style_on if is_walking else anim_style_off)

    def reset_model_view(self):
        """Réinitialise la vue du modèle 3D à sa position par défaut."""
        if hasattr(self, 'model_3d_widget') and self.model_3d_widget:
            self.model_3d_widget.reset_view()
            self.update()

    def on_display_mode_changed(self, button_clicked=None):
        """Gère le changement de mode d'affichage (single sensor vs group)."""
        if self.group_sensor_mode.isChecked():
            self.update_display_mode_ui()
            self.create_group_plots()
        else:
            self.update_display_mode_ui()

    def update_display_mode_ui(self):
        """Met à jour l'interface utilisateur lors du changement de mode d'affichage."""
        if self.group_sensor_mode.isChecked():
            for plot in self.plots.values():
                plot.setParent(None)
                plot.deleteLater()
            self.plots.clear()
        else:
            for group_plot in self.group_plots.values():
                group_plot.setParent(None)
                group_plot.deleteLater()
            self.group_plots.clear()

    def show_recorded_data_on_plots(self, recorded_data):
        """Displays recorded data on plots."""
        rec_data = self.backend.recorded_data # Use backend's copy
        has_any_data = False
        for sensor_key in ["EMG", "IMU", "pMMG"]:
            if rec_data.get(sensor_key) and any(rec_data[sensor_key]) and any(d for d in rec_data[sensor_key] if d):
                has_any_data = True
                break
        
        if not has_any_data:
            QMessageBox.warning(self, 'Warning', "No data has been recorded.")
            self.record_button.setEnabled(True)
            if self.backend.client_socket: 
                self.connect_button.setText("Disconnect")
                self.connect_button.setEnabled(True)
            else: 
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
            return

        # S'assurer que les graphiques de groupe existent si en mode groupe
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()
        
        # Afficher automatiquement tous les capteurs avec des données enregistrées
        self.auto_display_all_sensors_with_data()

    def auto_display_all_sensors_with_data(self):
        """Automatically displays all sensors that have recorded data."""
        rec_data = self.backend.recorded_data
        
        # Vérifier si on a une configuration de capteurs
        if not self.backend.sensor_config:
            print("[WARNING] No sensor configuration available")
            return
        
        # Parcourir les données EMG - trier par ordre croissant d'ID
        if rec_data.get("EMG") and self.backend.sensor_config.get('emg_ids'):
            emg_ids = self.backend.sensor_config['emg_ids']
            emg_data_with_ids = []
            for idx, data in enumerate(rec_data["EMG"]):
                if data and idx < len(emg_ids):
                    emg_data_with_ids.append((idx, emg_ids[idx], data))
            emg_data_with_ids.sort(key=lambda x: x[1])
            for idx, emg_id, data in emg_data_with_ids:
                sensor_base = f"EMG{emg_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
        
        # Parcourir les données pMMG - trier par ordre croissant d'ID
        if rec_data.get("pMMG") and self.backend.sensor_config.get('pmmg_ids'):
            pmmg_ids = self.backend.sensor_config['pmmg_ids']
            pmmg_data_with_ids = []
            for idx, data in enumerate(rec_data["pMMG"]):
                if data and idx < len(pmmg_ids):
                    pmmg_data_with_ids.append((idx, pmmg_ids[idx], data))
            pmmg_data_with_ids.sort(key=lambda x: x[1])
            for idx, pmmg_id, data in pmmg_data_with_ids:
                sensor_base = f"pMMG{pmmg_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
        
        # Parcourir les données IMU - trier par ordre croissant d'ID
        if rec_data.get("IMU") and self.backend.sensor_config.get('imu_ids'):
            imu_ids = self.backend.sensor_config['imu_ids']
            imu_data_with_ids = []
            for idx, data in enumerate(rec_data["IMU"]):
                if data and idx < len(imu_ids):
                    imu_data_with_ids.append((idx, imu_ids[idx], data))
            imu_data_with_ids.sort(key=lambda x: x[1])
            for idx, imu_id, data in imu_data_with_ids:
                sensor_base = f"IMU{imu_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)

    def find_sensor_item_by_base_name(self, sensor_name_base):
        """Trouve l'élément capteur dans l'arborescence par son nom de base."""
        for i_find_item_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_find_item_group)
            for j_find_item_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_find_item_sensor)
                if sensor_item.text(0).startswith(sensor_name_base): 
                    return sensor_item
        return None

    def plot_recorded_sensor_data(self, sensor_name_full, sensor_name_base):
        """Affiche les données enregistrées pour un capteur spécifique."""
        try:
            # Créer ou mettre à jour le graphique selon le mode d'affichage
            if self.group_sensor_mode.isChecked():
                self.add_recorded_data_to_group_plot(sensor_name_full, sensor_name_base)
            else:
                self.create_individual_plot_with_recorded_data(sensor_name_full, sensor_name_base)
                
            self.highlight_sensor_item(sensor_name_base)
        except Exception as e:
            print(f"[ERROR] Error plotting recorded data for {sensor_name_base}: {e}")

    def add_recorded_data_to_group_plot(self, sensor_name_full, sensor_group_type):
        """Ajoute les données enregistrées au graphique de groupe."""
        # Déterminer le type de capteur pour savoir quel graphique de groupe utiliser
        if sensor_name_full.startswith("EMG"):
            group_type = "EMG"
        elif sensor_name_full.startswith("pMMG"):
            group_type = "pMMG"
        elif sensor_name_full.startswith("IMU"):
            group_type = "IMU"
        else:
            return
        
        # S'assurer que le graphique de groupe existe
        if group_type not in self.group_plots:
            self.create_group_plots()
        
        if group_type in self.group_plots:
            self.add_sensor_curve_to_group_plot(sensor_name_full, group_type)

    def create_individual_plot_with_recorded_data(self, sensor_name_full, sensor_name_base):
        """Crée un graphique individuel avec les données enregistrées."""
        # Créer le graphique s'il n'existe pas déjà
        if sensor_name_base not in self.plots:
            is_imu = sensor_name_base.startswith("IMU")
            self.create_individual_plot(sensor_name_full, sensor_name_base, is_imu)

    def highlight_sensor_item(self, sensor_name_base):
        """Surligne l'élément capteur dans l'arborescence."""
        item = self.find_sensor_item_by_base_name(sensor_name_base)
        if item:
            item.setSelected(True)
            self.highlighted_sensors.add(sensor_name_base)

    def on_sensor_clicked(self, item, column):
        """Gère le clic sur un élément capteur."""
        try:
            sensor_text = item.text(0)
            sensor_name_base = sensor_text.split()[0]
            
            if sensor_name_base in self.highlighted_sensors:
                # Désélectionner
                item.setSelected(False)
                self.highlighted_sensors.discard(sensor_name_base)
                # Supprimer le graphique si nécessaire
                if sensor_name_base in self.plots:
                    self.plots[sensor_name_base].setParent(None)
                    self.plots[sensor_name_base].deleteLater()
                    del self.plots[sensor_name_base]
            else:
                # Sélectionner
                item.setSelected(True)
                self.highlighted_sensors.add(sensor_name_base)
                # Créer le graphique si nécessaire
                is_imu = sensor_name_base.startswith("IMU")
                self.create_individual_plot(sensor_text, sensor_name_base, is_imu)
        except Exception as e:
            print(f"[ERROR] Error in sensor click handler: {e}")

    def create_individual_plot(self, sensor_name_full, sensor_name_base, is_group_mode_imu=False):
        """Crée un graphique individuel pour un capteur."""
        if sensor_name_base in self.plots:
            return

        plot_widget = pg.PlotWidget(title=sensor_name_full)
        plot_widget.setBackground('#1e1e1e')
        plot_widget.getAxis('left').setTextPen('white')
        plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
        plot_widget.setProperty("sensor_base_name", sensor_name_base)

        # Insérer le widget dans la bonne position
        insert_index = len([p for p in self.plots.values() if p.isVisible()])
        self.middle_layout.insertWidget(insert_index, plot_widget)
        self.plots[sensor_name_base] = plot_widget

        # Créer les courbes avec des buffers numpy
        if sensor_name_base.startswith("IMU"):
            for j, axis_l in enumerate(['w', 'x', 'y', 'z']):
                curve_key = f"{sensor_name_base}_{axis_l}"
                self.backend.plot_data[curve_key] = np.zeros(100)
                pen = pg.mkPen(color=(0, 255, 0, 200), width=2) if axis_l == 'w' else pg.mkPen(width=1)
                curve = plot_widget.plot(self.backend.plot_data[curve_key], pen=pen, name=curve_key)
                self.curves[curve_key] = curve
        else:
            self.backend.plot_data[sensor_name_base] = np.zeros(100)
            curve = plot_widget.plot(self.backend.plot_data[sensor_name_base], pen=pg.mkPen('b', width=2))
            self.curves[sensor_name_base] = curve

        if is_group_mode_imu:
            self.highlighted_sensors.add(sensor_name_base)

    def add_sensor_curve_to_group_plot(self, sensor_name_full, sensor_group_type):
        """Ajoute une courbe pour un capteur spécifique à un graphique de groupe."""
        if sensor_group_type not in self.group_plots:
            self.create_group_plots()
            if sensor_group_type not in self.group_plots:
                return

        if sensor_group_type not in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_group_type] = {}

        sensor_base_name_add = sensor_name_full.split()[0]
        if sensor_base_name_add.startswith("IMU"):
            for axis_label in ['w', 'x', 'y', 'z']:
                curve_key = f"{sensor_base_name_add}_{axis_label}"
                if curve_key not in self.backend.group_plot_data[sensor_group_type]:
                    self.backend.group_plot_data[sensor_group_type][curve_key] = np.zeros(100)
                pen = pg.mkPen(color=(0, 255, 0, 200), width=2) if axis_label == 'w' else pg.mkPen(width=1)
                if curve_key not in self.group_curves:
                    curve = self.group_plots[sensor_group_type].plot(self.backend.group_plot_data[sensor_group_type][curve_key], pen=pen, name=curve_key)
                    self.group_curves[curve_key] = curve
        else:
            if sensor_name_full not in self.backend.group_plot_data[sensor_group_type]:
                self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
            if sensor_name_full not in self.group_curves:
                curve = self.group_plots[sensor_group_type].plot(self.backend.group_plot_data[sensor_group_type][sensor_name_full], pen=pg.mkPen('b', width=2), name=sensor_name_full)
                self.group_curves[sensor_name_full] = curve

        self.highlight_sensor_item(sensor_base_name_add)

    def _replot_sorted_curves_in_group_plot(self, sensor_group_type):
        """Réorganise les courbes dans un graphique de groupe."""
        # Cette méthode peut être implémentée si nécessaire pour réorganiser les courbes
        pass

    def update_calibration_status_ui(self):
        """Updates the user interface based on calibration status."""
        try:
            if hasattr(self.model_3d_widget, 'get_calibration_status'):
                status = self.model_3d_widget.get_calibration_status()
                if status:
                    status_text = status.get('status_text', 'Unknown status')
                    progress = status.get('progress', 0)
                    is_complete = status.get('complete', False)
                    
                    # Update UI elements based on status
                    if is_complete:
                        self.calibration_status_label.setText("Status: Calibration complete")
                        self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        self.calibration_start_button.setText("T-pose Calibration")
                        self.calibration_start_button.setEnabled(True)
                        self.calibration_stop_button.setEnabled(False)
                        self.calibration_reset_button.setEnabled(True)
                    elif status.get('mode', False):
                        self.calibration_status_label.setText(f"Status: Calibrating ({progress}%)")
                        self.calibration_status_label.setStyleSheet("color: #FFA000; font-weight: bold;")
                    else:
                        self.calibration_status_label.setText("Status: Calibration required")
                        self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
        except Exception as e:
            print(f"[WARNING] Error updating calibration status: {e}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def start_tpose_calibration(self):
        """Démarre la calibration T-pose."""
        print("[UI_DEBUG] start_tpose_calibration called")
        try:
            # Check if sensors are connected
            if not self.backend.sensor_config or not self.backend.sensor_config.get('imu_ids'):
                QMessageBox.warning(self, "Calibration impossible", 
                               "Aucun capteur IMU n'est connecté.\n"
                               "Veuillez d'abord connecter des IMUs.")
                return False
                
            # Check if IMUs are mapped
            if not self.model_3d_widget.get_current_mappings():
                QMessageBox.warning(self, "Calibration impossible", 
                               "Aucun capteur IMU n'est assigné à une partie du corps.\n"
                               "Veuillez d'abord configurer le mapping des capteurs.")
                return False
                
            result = self.model_3d_widget.start_tpose_calibration()
            if not result:
                QMessageBox.warning(self, "Calibration impossible", 
                               "Impossible de démarrer la calibration.\n"
                               "Vérifiez que des capteurs IMU sont connectés.")
                return False
                
            self.calibration_start_button.setEnabled(False)
            self.calibration_stop_button.setEnabled(True)
            self.calibration_reset_button.setEnabled(False)
            self.calibration_start_button.setText("Calibration en cours...")
            self.calibration_status_label.setText("Status: Waiting for T-pose")
            self.calibration_status_label.setStyleSheet("color: #FFA000; font-weight: bold;")
            return result
        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", 
                               f"An error occurred while starting calibration: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return False

    def stop_tpose_calibration(self):
        """Arrête la calibration T-pose."""
        print("[UI_DEBUG] stop_tpose_calibration called")
        try:
            result = self.model_3d_widget.stop_tpose_calibration()
            self.calibration_start_button.setEnabled(True)
            self.calibration_stop_button.setEnabled(False)
            self.calibration_reset_button.setEnabled(True)
            
            if result:
                self.calibration_start_button.setText("T-pose Calibration")
                self.calibration_status_label.setText("Status: Calibration complete")
                self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.calibration_start_button.setText("T-pose Calibration")
                self.calibration_status_label.setText("Status: Calibration failed")
                self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return result
        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", 
                               f"An error occurred while stopping calibration: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return False

    def reset_tpose_calibration(self):
        """Remet à zéro la calibration T-pose."""
        print("[UI_DEBUG] reset_tpose_calibration called")
        try:
            self.model_3d_widget.reset_calibration()
            self.calibration_start_button.setText("T-pose Calibration")
            self.calibration_start_button.setEnabled(True)
            self.calibration_stop_button.setEnabled(False)
            self.calibration_reset_button.setEnabled(False)
            self.calibration_status_label.setText("Status: Calibration reset")
            self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
        except Exception as e:
            QMessageBox.critical(self, "Reset Error", 
                               f"An error occurred during reset: {str(e)}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def toggle_animation(self):
        """Active ou désactive l'animation du modèle 3D."""
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")
        anim_style_on = """QPushButton { background-color: #f44336; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #e53935; } QPushButton:pressed { background-color: #d32f2f; }"""
        anim_style_off = """QPushButton { background-color: #2196f3; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #1e88e5; } QPushButton:pressed { background-color: #1976d2; }"""
        self.animate_button.setStyleSheet(anim_style_on if is_walking else anim_style_off)

    def reset_model_view(self):
        """Réinitialise la vue du modèle 3D à sa position par défaut."""
        if hasattr(self, 'model_3d_widget') and self.model_3d_widget:
            self.model_3d_widget.reset_view()
            self.update()

    def on_display_mode_changed(self, button_clicked=None):
        """Gère le changement de mode d'affichage (single sensor vs group)."""
        if self.group_sensor_mode.isChecked():
            self.update_display_mode_ui()
            self.create_group_plots()
        else:
            self.update_display_mode_ui()

    def update_display_mode_ui(self):
        """Met à jour l'interface utilisateur lors du changement de mode d'affichage."""
        if self.group_sensor_mode.isChecked():
            for plot in self.plots.values():
                plot.setParent(None)
                plot.deleteLater()
            self.plots.clear()
        else:
            for group_plot in self.group_plots.values():
                group_plot.setParent(None)
                group_plot.deleteLater()
            self.group_plots.clear()

    def show_recorded_data_on_plots(self, recorded_data):
        """Displays recorded data on plots."""
        rec_data = self.backend.recorded_data # Use backend's copy
        has_any_data = False
        for sensor_key in ["EMG", "IMU", "pMMG"]:
            if rec_data.get(sensor_key) and any(rec_data[sensor_key]) and any(d for d in rec_data[sensor_key] if d):
                has_any_data = True
                break
        
        if not has_any_data:
            QMessageBox.warning(self, 'Warning', "No data has been recorded.")
            self.record_button.setEnabled(True)
            if self.backend.client_socket: 
                self.connect_button.setText("Disconnect")
                self.connect_button.setEnabled(True)
            else: 
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
            return

        # S'assurer que les graphiques de groupe existent si en mode groupe
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()
        
        # Afficher automatiquement tous les capteurs avec des données enregistrées
        self.auto_display_all_sensors_with_data()

    def auto_display_all_sensors_with_data(self):
        """Automatically displays all sensors that have recorded data."""
        rec_data = self.backend.recorded_data
        
        # Vérifier si on a une configuration de capteurs
        if not self.backend.sensor_config:
            print("[WARNING] No sensor configuration available")
            return
        
        # Parcourir les données EMG - trier par ordre croissant d'ID
        if rec_data.get("EMG") and self.backend.sensor_config.get('emg_ids'):
            emg_ids = self.backend.sensor_config['emg_ids']
            emg_data_with_ids = []
            for idx, data in enumerate(rec_data["EMG"]):
                if data and idx < len(emg_ids):
                    emg_data_with_ids.append((idx, emg_ids[idx], data))
            emg_data_with_ids.sort(key=lambda x: x[1])
            for idx, emg_id, data in emg_data_with_ids:
                sensor_base = f"EMG{emg_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
        
        # Parcourir les données pMMG - trier par ordre croissant d'ID
        if rec_data.get("pMMG") and self.backend.sensor_config.get('pmmg_ids'):
            pmmg_ids = self.backend.sensor_config['pmmg_ids']
            pmmg_data_with_ids = []
            for idx, data in enumerate(rec_data["pMMG"]):
                if data and idx < len(pmmg_ids):
                    pmmg_data_with_ids.append((idx, pmmg_ids[idx], data))
            pmmg_data_with_ids.sort(key=lambda x: x[1])
            for idx, pmmg_id, data in pmmg_data_with_ids:
                sensor_base = f"pMMG{pmmg_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
        
        # Parcourir les données IMU - trier par ordre croissant d'ID
        if rec_data.get("IMU") and self.backend.sensor_config.get('imu_ids'):
            imu_ids = self.backend.sensor_config['imu_ids']
            imu_data_with_ids = []
            for idx, data in enumerate(rec_data["IMU"]):
                if data and idx < len(imu_ids):
                    imu_data_with_ids.append((idx, imu_ids[idx], data))
            imu_data_with_ids.sort(key=lambda x: x[1])
            for idx, imu_id, data in imu_data_with_ids:
                sensor_base = f"IMU{imu_id}"
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                self.plot_recorded_sensor_data(sensor_full, sensor_base)

    def clear_all_plots(self):
        """Nettoie tous les graphiques existants pour préparer un nouveau trial."""
        try:
            # Nettoyer les graphiques individuels
            for plot_widget in list(self.plots.values()):
                if plot_widget:
                    plot_widget.setParent(None)
                    plot_widget.deleteLater()
            self.plots.clear()
            
            # Nettoyer les graphiques de groupe
            for group_plot_widget in list(self.group_plots.values()):
                if group_plot_widget:
                    group_plot_widget.setParent(None)
                    group_plot_widget.deleteLater()
            self.group_plots.clear()
            
            # Nettoyer les dictionnaires de courbes
            self.curves.clear()
            self.group_curves.clear()
            
            # Réinitialiser les ensembles de capteurs mis en évidence
            if hasattr(self, 'highlighted_sensors'):
                self.highlighted_sensors.clear()
            
            # Nettoyer les couleurs de mise en évidence dans l'arbre des capteurs
            for i_clear_group in range(self.connected_systems.topLevelItemCount()):
                group_item = self.connected_systems.topLevelItem(i_clear_group)
                if group_item:
                    for j_clear_sensor in range(group_item.childCount()):
                        sensor_item = group_item.child(j_clear_sensor)
                        if sensor_item:
                            sensor_item.setBackground(0, QBrush(QColor("white")))
                            
            print("[INFO] All plots cleared successfully")
            
        except Exception as e:
            print(f"[ERROR] Error in clear_all_plots: {e}")
            import traceback
            traceback.print_exc()

    def clear_plots_from_menu(self):
        """Méthode appelée par le menu Edit > Clear plots."""
        try:
            if hasattr(self.backend, 'clear_plots_only'):
                self.backend.clear_plots_only()
                # Remettre le bouton Record à l'état initial
                self.reset_record_button_for_new_trial()
                # Message moins intrusif dans la status bar
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage("Plots cleared - Ready for new trial", 5000)  # 5 secondes
                print("[INFO] Plots cleared from menu - System ready for new trial")
            else:
                # Fallback si la méthode backend n'existe pas
                print("[WARNING] backend.clear_plots_only() not found, using fallback")
                self.clear_all_plots()
                self.reset_record_button_for_new_trial()
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage("Plots cleared - Ready for new trial", 5000)
        except Exception as e:
            print(f"[ERROR] Error in clear_plots_from_menu: {e}")
            QMessageBox.warning(self, "Clear Plots Error", f"An error occurred while clearing plots: {str(e)}")

    def reset_record_button_for_new_trial(self):
        """Remet le bouton Record à l'état initial pour permettre un nouveau trial."""
        try:
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
            self.record_button.setStyleSheet(record_button_style)
            self.record_button.setText("Record Start")
            print("[INFO] Record button reset for new trial")
        except Exception as e:
            print(f"[ERROR] Error resetting record button: {e}")

    def prepare_for_new_trial(self):
        """Prépare l'interface pour un nouveau trial."""
        try:
            self.clear_all_plots()
            print("[INFO] Interface prepared for new trial")
        except Exception as e:
            print(f"[ERROR] Error preparing for new trial: {e}")
