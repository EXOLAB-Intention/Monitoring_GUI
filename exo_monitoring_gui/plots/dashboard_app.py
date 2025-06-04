'''
Fix the issue where IMU sensors do not appear in the 2D Plot after pressing record stop and being in the plot mode by sensor group.
'''
import sys
import os
import numpy as np # Kept for np.zeros, np.roll
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox, 
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea, QGroupBox,
    QSizePolicy  # Added missing QSizePolicy import
)
from PyQt5.QtCore import Qt, QTimer # QThread, pyqtSignal are in the backend
from PyQt5.QtGui import QColor, QBrush # QCursor is no longer directly used here
import pyqtgraph as pg

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
        # Global application style
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
        self.model_3d_container.setMinimumSize(350, 400)  # Reverted to original size
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
        self.model_3d_widget.setMinimumSize(300, 300)  # Reverted to original size
        self.model_3d_widget.setVisible(True)
        # Forcer également la transparence du widget 3D
        self.model_3d_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.model_3d_widget.setStyleSheet("background: transparent; border: none;")

        # Ajouter au layout et s'assurer qu'il occupe tout l'espace
        model_3d_layout.addWidget(self.model_3d_widget, 1)
        right_panel.addWidget(self.model_3d_container, stretch=3)  # Reverted to original stretch
        
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

    def reset_sensor_display(self):
        # Completely clear all sensor groups and items
        self.connected_systems.clear()
        
        # Disable calibration buttons when disconnecting
        self.calibration_start_button.setEnabled(False)
        self.calibration_stop_button.setEnabled(False)
        self.calibration_reset_button.setEnabled(False)
        self.calibration_start_button.setText("Calibration (requires IMUs)")

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
                print(f"Added EMG sensor: EMG{sensor_id}")  # Debug log

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
        
        # Disable Edit menu when new sensors connect
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'edit_Boleen'):
                try:
                    self.main_bar_re.edit_Boleen(False)
                except Exception as e:
                    print(f"Error calling edit_Boleen on connection: {e}")
        
        # Create group plots if necessary
        if self.group_sensor_mode.isChecked() and not self.group_plots:
            self.create_group_plots()
            
        # Toujours ouvrir automatiquement la boîte de dialogue de configuration des capteurs
        # après chaque connexion réussie, avec délai pour laisser l'interface se mettre à jour
        QTimer.singleShot(500, lambda: self.open_sensor_mapping_dialog(available_sensors))

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
        """Opens the sensor mapping dialog with proper error handling and non-modal behavior."""
        # Check if sensors are connected
        if not self.backend.sensor_config:
            QMessageBox.warning(self, "No Sensors", "Please connect sensors before configuring the mapping.")
            return
        
        try:
            # Si ce n'est pas la première fois, charger les mappages existants
            curr_maps = self.backend.get_current_mappings_for_dialog()
            
            # Créer et afficher la boîte de dialogue
            dialog = SensorMappingDialog(self, curr_maps, available_sensors)
            dialog.mappings_updated.connect(self.backend.update_sensor_mappings)
            
            # Make dialog non-modal to avoid blocking the main thread
            dialog.setWindowModality(Qt.NonModal)
            
            # Déplacer la fenêtre de dialogue au premier plan et la mettre en évidence
            dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            dialog.activateWindow()
            dialog.raise_()
            dialog.show()  # Use show() instead of exec_() for non-modal behavior
            
            # Debug message to confirm dialog is displayed
            print("Sensor mapping dialog opened successfully")
        except Exception as e:
            print(f"Error opening sensor mapping dialog: {e}")
            import traceback
            traceback.print_exc()

    def setup_default_mappings(self):
        """Sets up default mappings with proper error handling and non-modal behavior."""
        # Check if sensors are connected
        if not self.backend.sensor_config:
            QMessageBox.warning(self, "No Sensors", "Please connect sensors before configuring the mapping.")
            return
        
        try:
            curr_maps_def = self.backend.get_current_mappings_for_dialog()
            dialog_def = SensorMappingDialog(self, curr_maps_def)
            dialog_def.mappings_updated.connect(self.backend.save_as_default_mappings)
            
            # Make dialog non-modal
            dialog_def.setWindowModality(Qt.NonModal)
            
            QMessageBox.information(self, "Default Assignments Setup", 
                               "Configure sensor mappings...\nThese will be saved as default.")
            
            # Show instead of exec_
            dialog_def.show()
            dialog_def.activateWindow()
            dialog_def.raise_()
            
            # Debug message
            print("Default mapping dialog opened successfully")
        except Exception as e:
            print(f"Error opening default mapping dialog: {e}")
            import traceback
            traceback.print_exc()
        
    def refresh_sensor_tree_with_mappings(self, emg_mappings, pmmg_mappings):
        for i_rf_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_rf_group)
            for j_rf_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_rf_sensor)
                if sensor_item.isHidden(): continue
                orig_text = sensor_item.text(0)
                s_base_rf = orig_text.split()[0]
                new_s_text = s_base_rf
                s_id_str_rf = ''.join(filter(str.isdigit, s_base_rf))
                if s_id_str_rf:
                    s_id_rf = int(s_id_str_rf)
                    if s_base_rf.startswith("IMU"):
                        imu_maps_curr = self.model_3d_widget.get_current_mappings()
                        if s_id_rf in imu_maps_curr:
                            new_s_text = f"{s_base_rf} ({self._convert_model_part_to_ui(imu_maps_curr[s_id_rf])})"
                    elif s_base_rf.startswith("EMG") and s_id_rf in emg_mappings:
                        new_s_text = f"{s_base_rf} ({self._convert_model_part_to_ui(emg_mappings[s_id_rf])})"
                    elif s_base_rf.startswith("pMMG") and s_id_rf in pmmg_mappings:
                        new_s_text = f"{s_base_rf} ({self._convert_model_part_to_ui(pmmg_mappings[s_id_rf])})"
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
                    
                print("3D view reset successfully")
            except Exception as e:
                print(f"Error resetting 3D view: {e}")
                import traceback
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
                
                if status['mode']:  # Calibration in progress
                    progress = status.get('progress', 0)
                    self.calibration_start_button.setText(f"Calibration {progress}%")
                    self.calibration_status_label.setText(f"Status: Calibration in progress ({progress}%)")
                    self.calibration_status_label.setStyleSheet("color: #FFA000; font-weight: bold;")
                elif status['complete']:  # Calibration completed
                    self.calibration_start_button.setText("Completed ✅")
                    self.calibration_status_label.setText("Status: Calibration successful")
                    self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.calibration_start_button.setStyleSheet("""
                        QPushButton {
                            background-color: #4CAF50;
                            border: none;
                            border-radius: 6px;
                            padding: 6px 12px;
                            color: white;
                            font-size: 12px;
                            font-weight: 500;
                            text-align: center;
                            min-width: 100px;
                        }
                    """)
                    self.calibration_start_button.setEnabled(True)
                    self.calibration_stop_button.setEnabled(False)
                    self.calibration_reset_button.setEnabled(True)
                else:  # No calibration or reset
                    self.calibration_status_label.setText("Status: Calibration required")
                    self.calibration_status_label.setStyleSheet("color: #666; font-style: italic;")
                    
        except Exception as e:
            print(f"[WARNING] Error updating calibration status: {e}")
            self.calibration_status_label.setText(f"Status: Error ({str(e)[:20]}...)")
            self.calibration_status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def start_tpose_calibration(self):
        """Starts T-pose calibration."""
        try:
            # Check if sensors are connected
            if not self.backend.sensor_config or not self.backend.sensor_config.get('imu_ids'):
                QMessageBox.warning(self, "Calibration not possible", 
                               "No IMU sensor is connected.\n"
                               "Please connect IMUs first.")
                return False
                
            # Check if IMUs are mapped
            if not self.model_3d_widget.get_current_mappings():
                QMessageBox.warning(self, "Calibration not possible", 
                               "No IMU sensor is assigned to a body part.\n"
                               "Please configure sensor mapping first.")
                return False
                
            result = self.model_3d_widget.start_tpose_calibration()
            if not result:
                QMessageBox.warning(self, "Calibration not possible", 
                               "Unable to start calibration.\n"
                               "Check that IMU sensors are connected.")
                return False
                
            self.calibration_start_button.setEnabled(False)
            self.calibration_stop_button.setEnabled(True)
            self.calibration_reset_button.setEnabled(False)
            self.calibration_start_button.setText("Calibration in progress...")
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
        """Stops T-pose calibration."""
        try:
            result = self.model_3d_widget.stop_tpose_calibration()
            self.calibration_start_button.setEnabled(True)
            self.calibration_stop_button.setEnabled(False)
            self.calibration_reset_button.setEnabled(True)
            
            if result:
                self.calibration_start_button.setText("Completed ✅")
                self.calibration_status_label.setText("Status: Calibration successful")
                self.calibration_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.calibration_start_button.setText("Calibration failed ❌")
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
        """Resets T-pose calibration."""
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
        
        # Afficher les informations sur les données enregistrées
        print(f"[DEBUG] === RECORDED DATA ===")
        for sensor_type in ["EMG", "pMMG", "IMU"]:
            if rec_data.get(sensor_type):
                print(f"[DEBUG] {sensor_type}: {len(rec_data[sensor_type])} sensors")
                for i, data in enumerate(rec_data[sensor_type]):
                    if data:
                        print(f"[DEBUG]   Sensor {i}: {len(data)} points")
        print(f"[DEBUG] =================================")
        
        # Parcourir les données EMG - trier par ordre croissant d'ID
        if rec_data.get("EMG") and self.backend.sensor_config.get('emg_ids'):
            emg_ids = self.backend.sensor_config['emg_ids']
            # Créer une liste de tuples (idx, emg_id, data) et trier par emg_id
            emg_data_with_ids = []
            for idx, data in enumerate(rec_data["EMG"]):
                if data and idx < len(emg_ids):
                    emg_data_with_ids.append((idx, emg_ids[idx], data))
            
            # Trier par emg_id (ordre croissant)
            emg_data_with_ids.sort(key=lambda x: x[1])
            
            for idx, emg_id, data in emg_data_with_ids:
                sensor_base = f"EMG{emg_id}"
                # Trouver l'élément dans l'arbre des capteurs
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                
                # Forcer l'affichage des données enregistrées complètes
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
        
        # Parcourir les données pMMG - trier par ordre croissant d'ID
        if rec_data.get("pMMG") and self.backend.sensor_config.get('pmmg_ids'):
            pmmg_ids = self.backend.sensor_config['pmmg_ids']
            # Créer une liste de tuples (idx, pmmg_id, data) et trier par pmmg_id
            pmmg_data_with_ids = []
            for idx, data in enumerate(rec_data["pMMG"]):
                if data and idx < len(pmmg_ids):
                    pmmg_data_with_ids.append((idx, pmmg_ids[idx], data))
            
            # Trier par pmmg_id (ordre croissant)
            pmmg_data_with_ids.sort(key=lambda x: x[1])
            
            for idx, pmmg_id, data in pmmg_data_with_ids:
                sensor_base = f"pMMG{pmmg_id}"
                # Trouver l'élément dans l'arbre des capteurs
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                
                # Forcer l'affichage des données enregistrées complètes
                self.plot_recorded_sensor_data(sensor_full, sensor_base)
    
        # Parcourir les données IMU - trier par ordre croissant d'ID
        if rec_data.get("IMU") and self.backend.sensor_config.get('imu_ids'):
            imu_ids = self.backend.sensor_config['imu_ids']
            # Créer une liste de tuples (idx, imu_id, data) et trier par imu_id
            imu_data_with_ids = []
            for idx, data in enumerate(rec_data["IMU"]):
                if data and idx < len(imu_ids):
                    imu_data_with_ids.append((idx, imu_ids[idx], data))
            
            # Trier par imu_id (ordre croissant)
            imu_data_with_ids.sort(key=lambda x: x[1])
            
            for idx, imu_id, data in imu_data_with_ids:
                sensor_base = f"IMU{imu_id}"
                # Trouver l'élément dans l'arbre des capteurs
                item = self.find_sensor_item_by_base_name(sensor_base)
                sensor_full = item.text(0) if item else sensor_base
                
                # Forcer l'affichage des données enregistrées complètes
                self.plot_recorded_sensor_data(sensor_full, sensor_base)

    def on_sensor_clicked(self, item_clicked, column):
        """Gère le clic sur un capteur dans l'arborescence."""
        if item_clicked.childCount() > 0:
            # C'est un groupe, pas un capteur
            return
            
        if item_clicked.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Error", "The sensor is not connected. Please connect the sensor first.")
            return

        sensor_name_full = item_clicked.text(0)
        sensor_name_base = sensor_name_full.split()[0]

        if self.backend.recording_stopped:
            self.plot_recorded_sensor_data(sensor_name_full, sensor_name_base)
        else:
            if self.single_sensor_mode.isChecked():
                if sensor_name_base in self.plots:
                    self.remove_sensor_plot(sensor_name_base)
                else:
                    self.create_individual_plot(sensor_name_full, sensor_name_base)
            elif self.group_sensor_mode.isChecked():
                if sensor_name_base.startswith("IMU"):
                    if sensor_name_base in self.plots:
                        self.remove_sensor_plot(sensor_name_base)
                    else:
                        self.create_individual_plot(sensor_name_full, sensor_name_base, is_group_mode_imu=True)
                else:
                    sensor_group_type = "EMG" if sensor_name_base.startswith("EMG") else "pMMG"
                    if sensor_group_type in self.group_plots:
                        if sensor_name_full in self.backend.group_plot_data.get(sensor_group_type, {}):
                            self.remove_sensor_curve_from_group_plot(sensor_name_full, sensor_group_type)
                        else:
                            self.add_sensor_curve_to_group_plot(sensor_name_full, sensor_group_type)
    
    def create_individual_plot(self, sensor_name_full, sensor_name_base, is_group_mode_imu=False):
        """Creates an individual plot for a sensor."""
        if sensor_name_base in self.plots:
            return  # Plot already exists
            
        # Extract data type (EMG, IMU, pMMG)
        sensor_type = None
        if sensor_name_base.startswith("EMG"):
            sensor_type = "EMG"
        elif sensor_name_base.startswith("IMU"):
            sensor_type = "IMU"
        elif sensor_name_base.startswith("pMMG"):
            sensor_type = "pMMG"
        else:
            print(f"Unknown sensor type for {sensor_name_base}")
            return
            
        # Create plot widget
        plot_widget = pg.PlotWidget(title=sensor_name_full)
        plot_widget.setBackground('#1e1e1e')
        plot_widget.getAxis('left').setTextPen('white')
        plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
        
        # Add the plot to the middle layout
        self.middle_layout.addWidget(plot_widget)
        self.plots[sensor_name_base] = plot_widget
        
        # Initialize plot data in backend
        self.backend.plot_data[sensor_name_base] = []
        
        # If this is recorded data mode, plot the recorded data
        if self.backend.recording_stopped:
            self.plot_recorded_sensor_data(sensor_name_full, sensor_name_base)
            
        # Add sensor to highlighted set
        self.highlighted_sensors.add(sensor_name_base)
    
    def remove_sensor_plot(self, sensor_name_base):
        """Removes a sensor's individual plot."""
        if sensor_name_base in self.plots:
            plot_widget = self.plots[sensor_name_base]
            self.middle_layout.removeWidget(plot_widget)
            plot_widget.deleteLater()
            del self.plots[sensor_name_base]
            self.highlighted_sensors.discard(sensor_name_base)
            
            # Clean up backend data
            if sensor_name_base in self.backend.plot_data:
                del self.backend.plot_data[sensor_name_base]
    
    def plot_recorded_sensor_data(self, sensor_name_full, sensor_name_base):
        """Plots recorded data for a sensor."""
        # Extract sensor type and ID
        sensor_type = None
        sensor_id = -1
        
        if sensor_name_base.startswith("EMG"):
            sensor_type = "EMG"
            sensor_id = int(sensor_name_base[3:])
        elif sensor_name_base.startswith("IMU"):
            sensor_type = "IMU"
            sensor_id = int(sensor_name_base[3:])
        elif sensor_name_base.startswith("pMMG"):
            sensor_type = "pMMG"
            sensor_id = int(sensor_name_base[4:])
        else:
            print(f"Unknown sensor type for {sensor_name_base}")
            return
            
        # Get the recorded data
        rec_data = self.backend.recorded_data
        
        # Create or get the plot
        if self.single_sensor_mode.isChecked():
            if sensor_name_base not in self.plots:
                self.create_individual_plot(sensor_name_full, sensor_name_base)
            plot_widget = self.plots[sensor_name_base]
            plot_widget.clear()
            
            # IMU data (quaternions) require special handling
            if sensor_type == "IMU":
                # Find array index for this IMU ID
                imu_ids = self.backend.sensor_config.get('imu_ids', [])
                if sensor_id in imu_ids:
                    idx = imu_ids.index(sensor_id)
                    if idx < len(rec_data[sensor_type]) and rec_data[sensor_type][idx]:
                        # For IMU, plot the 4 quaternion components
                        components = ['w', 'x', 'y', 'z']
                        colors = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
                        
                        # Create time axis
                        x_values = list(range(len(rec_data[sensor_type][idx])))
                        
                        # Plot each component
                        for i in range(4):
                            y_values = [q[i] for q in rec_data[sensor_type][idx]]
                            pen = pg.mkPen(color=colors[i], width=2)
                            plot_widget.plot(x_values, y_values, pen=pen, name=f"{components[i]}")
            else:
                # For EMG and pMMG
                sensor_ids = self.backend.sensor_config.get(f'{sensor_type.lower()}_ids', [])
                if sensor_id in sensor_ids:
                    idx = sensor_ids.index(sensor_id)
                    if idx < len(rec_data[sensor_type]) and rec_data[sensor_type][idx]:
                        # Plot the signal
                        x_values = list(range(len(rec_data[sensor_type][idx])))
                        y_values = rec_data[sensor_type][idx]
                        pen = pg.mkPen(color=(0, 255, 255), width=2)
                        plot_widget.plot(x_values, y_values, pen=pen)
        elif self.group_sensor_mode.isChecked():
            # Group mode plotting
            if sensor_type in self.group_plots:
                # Add to existing group plot
                self.add_sensor_curve_to_group_plot(sensor_name_full, sensor_type)
    
    def update_live_plots(self, packet):
        """Updates plots with live data from the packet."""
        # Skip if not recording or no packet data
        if not packet or not self.backend.recording:
            return
            
        # Process different sensor types
        # EMG data
        if 'emg' in packet and packet['emg'] and self.backend.sensor_config.get('emg_ids'):
            for i, emg_id in enumerate(self.backend.sensor_config.get('emg_ids', [])):
                if i < len(packet['emg']):
                    sensor_name = f"EMG{emg_id}"
                    value = packet['emg'][i]
                    
                    # Update individual plot if visible
                    if sensor_name in self.highlighted_sensors and sensor_name in self.plots:
                        if sensor_name not in self.backend.plot_data:
                            self.backend.plot_data[sensor_name] = []
                        
                        data = self.backend.plot_data[sensor_name]
                        data.append(value)
                        
                        # Limit data length for performance
                        if len(data) > 500:
                            data = data[-500:]
                            self.backend.plot_data[sensor_name] = data
                            
                        # Update the plot
                        plot_widget = self.plots[sensor_name]
                        plot_widget.clear()
                        x_values = list(range(len(data)))
                        pen = pg.mkPen(color=(0, 255, 255), width=2)
                        plot_widget.plot(x_values, data, pen=pen)
                    
                    # Update group plot if in group mode
                    if self.group_sensor_mode.isChecked() and "EMG" in self.group_plots:
                        if "EMG" not in self.backend.group_plot_data:
                            self.backend.group_plot_data["EMG"] = {}
                        
                        if sensor_name not in self.backend.group_plot_data["EMG"]:
                            self.backend.group_plot_data["EMG"][sensor_name] = []
                            
                        group_data = self.backend.group_plot_data["EMG"][sensor_name]
                        group_data.append(value)
                        
                        # Limit data length
                        if len(group_data) > 500:
                            group_data = group_data[-500:]
                            self.backend.group_plot_data["EMG"][sensor_name] = group_data
                            
                        # Update the group plot
                        if sensor_name in self.curves:
                            self.group_plots["EMG"].removeItem(self.curves[sensor_name])
                            
                        x_values = list(range(len(group_data)))
                        color = self._get_curve_color(i)
                        pen = pg.mkPen(color=color, width=2)
                        self.curves[sensor_name] = self.group_plots["EMG"].plot(
                            x_values, group_data, pen=pen, name=f"EMG{emg_id}")
        
        # pMMG data
        if 'pmmg' in packet and packet['pmmg'] and self.backend.sensor_config.get('pmmg_ids'):
            for i, pmmg_id in enumerate(self.backend.sensor_config.get('pmmg_ids', [])):
                if i < len(packet['pmmg']):
                    sensor_name = f"pMMG{pmmg_id}"
                    value = packet['pmmg'][i]
                    
                    # Update individual plot if visible
                    if sensor_name in self.highlighted_sensors and sensor_name in self.plots:
                        if sensor_name not in self.backend.plot_data:
                            self.backend.plot_data[sensor_name] = []
                        
                        data = self.backend.plot_data[sensor_name]
                        data.append(value)
                        
                        # Limit data length for performance
                        if len(data) > 500:
                            data = data[-500:]
                            self.backend.plot_data[sensor_name] = data
                            
                        # Update the plot
                        plot_widget = self.plots[sensor_name]
                        plot_widget.clear()
                        x_values = list(range(len(data)))
                        pen = pg.mkPen(color=(255, 0, 255), width=2)
                        plot_widget.plot(x_values, data, pen=pen)
                    
                    # Update group plot if in group mode
                    if self.group_sensor_mode.isChecked() and "pMMG" in self.group_plots:
                        if "pMMG" not in self.backend.group_plot_data:
                            self.backend.group_plot_data["pMMG"] = {}
                        
                        if sensor_name not in self.backend.group_plot_data["pMMG"]:
                            self.backend.group_plot_data["pMMG"][sensor_name] = []
                            
                        group_data = self.backend.group_plot_data["pMMG"][sensor_name]
                        group_data.append(value)
                        
                        # Limit data length
                        if len(group_data) > 500:
                            group_data = group_data[-500:]
                            self.backend.group_plot_data["pMMG"][sensor_name] = group_data
                            
                        # Update the group plot
                        if sensor_name in self.curves:
                            self.group_plots["pMMG"].removeItem(self.curves[sensor_name])
                            
                        x_values = list(range(len(group_data)))
                        color = self._get_curve_color(i)
                        pen = pg.mkPen(color=color, width=2)
                        self.curves[sensor_name] = self.group_plots["pMMG"].plot(
                            x_values, group_data, pen=pen, name=f"pMMG{pmmg_id}")
        
        # IMU data (quaternions)
        if 'imu' in packet and packet['imu'] and self.backend.sensor_config.get('imu_ids'):
            for i, imu_id in enumerate(self.backend.sensor_config.get('imu_ids', [])):
                if i < len(packet['imu']):
                    sensor_name = f"IMU{imu_id}"
                    quaternion = packet['imu'][i]
                    
                    # Update individual plot if visible
                    if sensor_name in self.highlighted_sensors and sensor_name in self.plots:
                        if sensor_name not in self.backend.plot_data:
                            self.backend.plot_data[sensor_name] = [[] for _ in range(4)]  # 4 components: w, x, y, z
                        
                        # Append each component
                        for j in range(4):
                            self.backend.plot_data[sensor_name][j].append(quaternion[j])
                            
                            # Limit data length
                            if len(self.backend.plot_data[sensor_name][j]) > 500:
                                self.backend.plot_data[sensor_name][j] = self.backend.plot_data[sensor_name][j][-500:]
                        
                        # Update the plot
                        plot_widget = self.plots[sensor_name]
                        plot_widget.clear()
                        
                        components = ['w', 'x', 'y', 'z']
                        colors = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
                        
                        for j in range(4):
                            data = self.backend.plot_data[sensor_name][j]
                            x_values = list(range(len(data)))
                            pen = pg.mkPen(color=colors[j], width=2)
                            plot_widget.plot(x_values, data, pen=pen, name=components[j])
                    
                    # Update group plot if in group mode
                    if self.group_sensor_mode.isChecked() and "IMU" in self.group_plots:
                        if "IMU" not in self.backend.group_plot_data:
                            self.backend.group_plot_data["IMU"] = {}
                        
                        if sensor_name not in self.backend.group_plot_data["IMU"]:
                            self.backend.group_plot_data["IMU"][sensor_name] = [[] for _ in range(4)]
                        
                        # Append each component
                        for j in range(4):
                            self.backend.group_plot_data["IMU"][sensor_name][j].append(quaternion[j])
                            
                            # Limit data length
                            if len(self.backend.group_plot_data["IMU"][sensor_name][j]) > 500:
                                self.backend.group_plot_data["IMU"][sensor_name][j] = self.backend.group_plot_data["IMU"][sensor_name][j][-500:]
                        
                        # Update curves in group plot
                        components = ['w', 'x', 'y', 'z']
                        colors = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
                        
                        for j in range(4):
                            curve_name = f"{sensor_name}_{components[j]}"
                            
                            if curve_name in self.curves:
                                self.group_plots["IMU"].removeItem(self.curves[curve_name])
                            
                            data = self.backend.group_plot_data["IMU"][sensor_name][j]
                            x_values = list(range(len(data)))
                            pen = pg.mkPen(color=colors[j], width=2)
                            self.curves[curve_name] = self.group_plots["IMU"].plot(
                                x_values, data, pen=pen, name=f"IMU{imu_id} {components[j]}")

    def find_sensor_item_by_base_name(self, base_name):
        """Finds a sensor item in the tree by its base name."""
        # Determine sensor type from base name
        sensor_type = None
        if base_name.startswith("EMG"):
            sensor_type = "EMG Data"
        elif base_name.startswith("IMU"):
            sensor_type = "IMU Data"
        elif base_name.startswith("pMMG"):
            sensor_type = "pMMG Data"
        else:
            return None
            
        # Find the sensor group
        group_item = None
        for i in range(self.connected_systems.topLevelItemCount()):
            item = self.connected_systems.topLevelItem(i)
            if item.text(0) == sensor_type:
                group_item = item
                break
                
        if not group_item:
            return None
            
        # Find the sensor item within the group
        for i in range(group_item.childCount()):
            item = group_item.child(i)
            item_text = item.text(0)
            if item_text.startswith(base_name):
                return item
                
        return None

    def add_sensor_curve_to_group_plot(self, sensor_name_full, sensor_type):
        """Adds a sensor curve to a group plot."""
        if sensor_type not in self.group_plots:
            return False
            
        # Extract base name
        parts = sensor_name_full.split()
        sensor_name_base = parts[0]
        
        # Add to group data if not already there
        if sensor_type not in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_type] = {}
            
        # Check if we're dealing with IMU data (quaternions)
        if sensor_name_base.startswith("IMU"):
            # For IMU, we need to handle 4 components
            sensor_id = int(sensor_name_base[3:])
            
            # Find the data for this IMU
            imu_ids = self.backend.sensor_config.get('imu_ids', [])
            if sensor_id in imu_ids:
                idx = imu_ids.index(sensor_id)
                if idx < len(self.backend.recorded_data["IMU"]) and self.backend.recorded_data["IMU"][idx]:
                    # Create the data arrays if they don't exist
                    if sensor_name_base not in self.backend.group_plot_data[sensor_type]:
                        self.backend.group_plot_data[sensor_type][sensor_name_base] = [[] for _ in range(4)]
                    
                    # Copy the data for each component
                    for i in range(4):
                        self.backend.group_plot_data[sensor_type][sensor_name_base][i] = [q[i] for q in self.backend.recorded_data["IMU"][idx]]
                    
                    # Plot each component
                    components = ['w', 'x', 'y', 'z']
                    colors = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
                    
                    for i in range(4):
                        curve_name = f"{sensor_name_base}_{components[i]}"
                        x_values = list(range(len(self.backend.group_plot_data[sensor_type][sensor_name_base][i])))
                        pen = pg.mkPen(color=colors[i], width=2)
                        self.curves[curve_name] = self.group_plots[sensor_type].plot(
                            x_values, self.backend.group_plot_data[sensor_type][sensor_name_base][i], 
                            pen=pen, name=f"{sensor_name_base} {components[i]}")
        else:
            # For EMG and pMMG, we have a single value per time point
            if sensor_name_base not in self.backend.group_plot_data[sensor_type]:
                self.backend.group_plot_data[sensor_type][sensor_name_base] = []
                
            # Extract sensor ID and find the correct data
            if sensor_name_base.startswith("EMG"):
                sensor_id = int(sensor_name_base[3:])
                sensor_ids = self.backend.sensor_config.get('emg_ids', [])
            elif sensor_name_base.startswith("pMMG"):
                sensor_id = int(sensor_name_base[4:])
                sensor_ids = self.backend.sensor_config.get('pmmg_ids', [])
            else:
                return False
                
            if sensor_id in sensor_ids:
                idx = sensor_ids.index(sensor_id)
                if idx < len(self.backend.recorded_data[sensor_type]) and self.backend.recorded_data[sensor_type][idx]:
                    # Copy the data
                    self.backend.group_plot_data[sensor_type][sensor_name_base] = self.backend.recorded_data[sensor_type][idx]
                    
                    # Add the curve to the plot
                    x_values = list(range(len(self.backend.group_plot_data[sensor_type][sensor_name_base])))
                    color = self._get_curve_color(idx)
                    pen = pg.mkPen(color=color, width=2)
                    self.curves[sensor_name_base] = self.group_plots[sensor_type].plot(
                        x_values, self.backend.group_plot_data[sensor_type][sensor_name_base], 
                        pen=pen, name=sensor_name_base)
        
        return True

    def remove_sensor_curve_from_group_plot(self, sensor_name_full, sensor_type):
        """Removes a sensor curve from a group plot."""
        if sensor_type not in self.group_plots:
            return False
            
        # Extract base name
        parts = sensor_name_full.split()
        sensor_name_base = parts[0]
        
        # Check if we're dealing with IMU data (quaternions)
        if sensor_name_base.startswith("IMU"):
            # For IMU, we need to handle 4 components
            components = ['w', 'x', 'y', 'z']
            for comp in components:
                curve_name = f"{sensor_name_base}_{comp}"
                if curve_name in self.curves:
                    self.group_plots[sensor_type].removeItem(self.curves[curve_name])
                    del self.curves[curve_name]
        else:
            # For EMG and pMMG
            if sensor_name_base in self.curves:
                self.group_plots[sensor_type].removeItem(self.curves[sensor_name_base])
                del self.curves[sensor_name_base]
        
        # Remove from group data
        if sensor_type in self.backend.group_plot_data and sensor_name_base in self.backend.group_plot_data[sensor_type]:
            del self.backend.group_plot_data[sensor_type][sensor_name_base]
        
        return True

    def clear_all_plots(self):
        """Clears all plots."""
        # Clear individual plots
        for plot_widget in self.plots.values():
            plot_widget.clear()
            self.middle_layout.removeWidget(plot_widget)
            plot_widget.deleteLater()
        self.plots.clear()
        self.highlighted_sensors.clear()
        
        # Clear group plots
        for sensor_type, plot_widget in self.group_plots.items():
            plot_widget.clear()
        
        # Clear curves
        self.curves.clear()
        
        # Clear backend data
        self.backend.plot_data.clear()
        self.backend.group_plot_data.clear()

    def _get_curve_color(self, index):
        """Returns a color for a curve based on its index."""
        colors = [
            (0, 255, 255),    # Cyan
            (255, 0, 255),    # Magenta
            (255, 255, 0),    # Yellow
            (0, 255, 0),      # Green
            (255, 0, 0),      # Red
            (0, 0, 255),      # Blue
            (255, 128, 0),    # Orange
            (128, 0, 255),    # Purple
            (0, 255, 128),    # Mint
            (255, 255, 255),  # White
        ]
        return colors[index % len(colors)]
