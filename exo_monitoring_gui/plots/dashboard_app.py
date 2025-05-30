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
    def __init__(self, subject_file=None):
        super().__init__()
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
        
        # Désactiver "Refresh Connected System" lors de la déconnexion
        if hasattr(self, 'main_bar_re') and self.main_bar_re is not None:
            if hasattr(self.main_bar_re, 'set_refresh_connected_system_enabled'):
                try:
                    self.main_bar_re.set_refresh_connected_system_enabled(False)
                except Exception as e:
                    print(f"Error calling set_refresh_connected_system_enabled on disconnect: {e}")

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
                    # Activer seulement "Refresh Connected System" lors de la connexion
                    self.main_bar_re.set_refresh_connected_system_enabled(True)
                except Exception as e:
                    print(f"Error calling set_refresh_connected_system_enabled on connection: {e}")
        
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
                self.calibration_start_button.setText("Calibration échouée ❌")
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

    def find_sensor_item_by_base_name(self, sensor_name_base):
        """Trouve l'élément capteur dans l'arborescence par son nom de base."""
        for i_find_item_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_find_item_group)
            for j_find_item_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_find_item_sensor)
                if sensor_item.text(0).startswith(sensor_name_base): return sensor_item
        return None

    def update_live_plots(self, packet):
        """Met à jour les graphiques en temps réel avec les nouvelles données,
        en remplaçant clear()/plot() par setData() pour réduire l'overhead Qt."""
        # EMG individuel
        if 'emg' in packet and packet['emg']:
            for i, emg_value in enumerate(packet['emg']):
                sensor_name = (f"EMG{self.backend.sensor_config['emg_ids'][i]}"
                               if i < len(self.backend.sensor_config.get('emg_ids', []))
                               else f"EMG{i+1}")
                if sensor_name in self.curves:
                    self.backend.plot_data[sensor_name] = np.roll(self.backend.plot_data[sensor_name], -1)
                    self.backend.plot_data[sensor_name][-1] = emg_value
                    self.curves[sensor_name].setData(self.backend.plot_data[sensor_name])

        # EMG groupe
        if 'emg' in packet and packet['emg'] and "EMG" in self.group_plots:
            group_plot_widget_emg = self.group_plots["EMG"]
            legend_needs_update_emg = False
            for i, emg_value in enumerate(packet['emg']):
                sensor_name_full = (f"EMG{self.backend.sensor_config['emg_ids'][i]}"
                                    if i < len(self.backend.sensor_config.get('emg_ids', []))
                                    else f"EMG{i+1}")
                item = self.find_sensor_item_by_base_name(sensor_name_full.split()[0])
                display_name_emg = item.text(0) if item else sensor_name_full # Utiliser le nom de l'arbre avec mapping
                
                gp_emg = self.backend.group_plot_data.get("EMG", {})
                if display_name_emg in gp_emg:
                    gp_emg[display_name_emg] = np.roll(gp_emg[display_name_emg], -1)
                    gp_emg[display_name_emg][-1] = emg_value
                    if display_name_emg in self.group_curves:
                        self.group_curves[display_name_emg].setData(gp_emg[display_name_emg])
                # else: # La courbe n'existe pas encore, elle sera créée par _replot_sorted_curves_in_group_plot
                    # # Si on vient de l'ajouter via on_sensor_clicked, _replot a déjà été appelé.
                    # # Si c'est la première donnée pour un capteur non explicitement ajouté, on pourrait avoir besoin de la créer ici.
                    # # Pour l'instant, on suppose que les capteurs sont ajoutés via clic ou auto-display après enregistrement.
                    # # Pour garantir l'ordre, il vaut mieux appeler _replot_sorted_curves_in_group_plot
                    # # si une nouvelle courbe doit être ajoutée dynamiquement ici, mais cela peut être coûteux.
                    # # La logique actuelle dans add_sensor_curve_to_group_plot gère l'ajout et le tri.
                    pass # Logique de création de courbe déplacée vers _replot_sorted_curves_in_group_plot

        # pMMG individuel
        if 'pmmg' in packet and packet['pmmg']:
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_name = (f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}"
                               if i < len(self.backend.sensor_config.get('pmmg_ids', []))
                               else f"pMMG{i+1}")
                if sensor_name in self.curves:
                    self.backend.plot_data[sensor_name] = np.roll(self.backend.plot_data[sensor_name], -1)
                    self.backend.plot_data[sensor_name][-1] = pmmg_value
                    self.curves[sensor_name].setData(self.backend.plot_data[sensor_name])

        # pMMG groupe
        if 'pmmg' in packet and packet['pmmg'] and "pMMG" in self.group_plots:
            group_plot_widget_pmmg = self.group_plots["pMMG"]
            legend_needs_update_pmmg = False
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_name_full = (f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}"
                                    if i < len(self.backend.sensor_config.get('pmmg_ids', []))
                                    else f"pMMG{i+1}")
                item = self.find_sensor_item_by_base_name(sensor_name_full.split()[0])
                display_name_pmmg = item.text(0) if item else sensor_name_full

                gp_pmmg = self.backend.group_plot_data.get("pMMG", {})
                if display_name_pmmg in gp_pmmg:
                    gp_pmmg[display_name_pmmg] = np.roll(gp_pmmg[display_name_pmmg], -1)
                    gp_pmmg[display_name_pmmg][-1] = pmmg_value
                    if display_name_pmmg in self.group_curves:
                        self.group_curves[display_name_pmmg].setData(gp_pmmg[display_name_pmmg])
                # else:
                    pass # Logique de création de courbe déplacée

        # IMU individuel (4 composantes)
        if 'imu' in packet and packet['imu']:
            for i, quaternion in enumerate(packet['imu']):
                sensor_name = (f"IMU{self.backend.sensor_config['imu_ids'][i]}"
                               if i < len(self.backend.sensor_config.get('imu_ids', []))
                               else f"IMU{i+1}")
                for j, axis_label in enumerate(['w', 'x', 'y', 'z']):
                    key = f"{sensor_name}_{axis_label}"
                    if key in self.curves:
                        self.backend.plot_data[key] = np.roll(self.backend.plot_data[key], -1)
                        self.backend.plot_data[key][-1] = quaternion[j]
                        self.curves[key].setData(self.backend.plot_data[key])

        # IMU groupe
        if 'imu' in packet and packet['imu'] and "IMU" in self.group_plots:
            group_plot_widget_imu = self.group_plots["IMU"]
            legend_needs_update_imu = False
            for i, quaternion in enumerate(packet['imu']):
                sensor_name_base = (f"IMU{self.backend.sensor_config['imu_ids'][i]}"
                                   if i < len(self.backend.sensor_config.get('imu_ids', []))
                                   else f"IMU{i+1}")
                item = self.find_sensor_item_by_base_name(sensor_name_base)
                sensor_name_full_imu = item.text(0) if item else sensor_name_base

                gp_imu = self.backend.group_plot_data.get("IMU", {})
                for j, axis_label in enumerate(['w', 'x', 'y', 'z']):
                    curve_name_imu = f"{sensor_name_full_imu}_{axis_label}"
                    if curve_name_imu in gp_imu:
                        gp_imu[curve_name_imu] = np.roll(gp_imu[curve_name_imu], -1)
                        gp_imu[curve_name_imu][-1] = quaternion[j]
                        if curve_name_imu in self.group_curves:
                            self.group_curves[curve_name_imu].setData(gp_imu[curve_name_imu])
                    # else:
                        pass # Logique de création de courbe déplacée

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
    
    def plot_recorded_sensor_data(self, sensor_name_full, sensor_name_base):
        """Displays recorded data for a specific sensor."""
        recorded_data = self.backend.recorded_data
        
        # Extraire l'ID du capteur
        sensor_id_str = ''.join(filter(str.isdigit, sensor_name_base))
        if not sensor_id_str:
            return
        sensor_id = int(sensor_id_str)
        
        # Déterminer le type de capteur et trouver l'index correct dans recorded_data
        has_data = False
        data_array_key = None
        sensor_idx = -1
        
        if sensor_name_base.startswith("EMG"):
            data_array_key = "EMG"
            if self.backend.sensor_config and 'emg_ids' in self.backend.sensor_config:
                emg_ids = self.backend.sensor_config['emg_ids']
                if sensor_id in emg_ids:
                    sensor_idx = emg_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("EMG", [])) and 
                               recorded_data["EMG"][sensor_idx])
        elif sensor_name_base.startswith("pMMG"):
            data_array_key = "pMMG"
            if self.backend.sensor_config and 'pmmg_ids' in self.backend.sensor_config:
                pmmg_ids = self.backend.sensor_config['pmmg_ids']
                if sensor_id in pmmg_ids:
                    sensor_idx = pmmg_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("pMMG", [])) and 
                               recorded_data["pMMG"][sensor_idx])
        elif sensor_name_base.startswith("IMU"):
            data_array_key = "IMU"
            if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config:
                imu_ids = self.backend.sensor_config['imu_ids']
                if sensor_id in imu_ids:
                    sensor_idx = imu_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("IMU", [])) and 
                               recorded_data["IMU"][sensor_idx])

        if not has_data or sensor_idx == -1:
            QMessageBox.information(self, "No data", f"No recorded data available for {sensor_name_base}.")
            return

        # Mode groupe: afficher dans les graphiques de groupe
        if self.group_sensor_mode.isChecked():
            sensor_group_type = data_array_key
            
            if sensor_group_type not in self.group_plots:
                self.create_group_plots()
            
            plot_widget = self.group_plots.get(sensor_group_type)
            if not plot_widget:
                return

            if sensor_name_base.startswith("IMU"):
                for axis_label in ['w', 'x', 'y', 'z']:
                    curve_name = f"{sensor_name_full}_{axis_label}"
                    if curve_name in self.group_curves:
                        plot_widget.removeItem(self.group_curves[curve_name])
                        del self.group_curves[curve_name]
            else:
                if sensor_name_full in self.group_curves:
                    plot_widget.removeItem(self.group_curves[sensor_name_full])
                    del self.group_curves[sensor_name_full]

            data_to_plot = recorded_data[data_array_key][sensor_idx]
            if data_to_plot:
                if sensor_name_base.startswith("IMU"):
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        color = ['r', 'g', 'b', 'y'][i_quat]
                        curve_name = f"{sensor_name_full}_{axis_label}"
                        curve = plot_widget.plot(quat_data, pen=pg.mkPen(color, width=2), name=curve_name)
                        self.group_curves[curve_name] = curve
                        if "IMU" not in self.backend.group_plot_data:
                            self.backend.group_plot_data["IMU"] = {}
                        self.backend.group_plot_data["IMU"][curve_name] = np.zeros(100)
                else:
                    color_idx = sensor_idx % 8
                    curve = plot_widget.plot(data_to_plot, pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][color_idx], width=2), name=sensor_name_full)
                    self.group_curves[sensor_name_full] = curve
                    if sensor_group_type not in self.backend.group_plot_data:
                        self.backend.group_plot_data[sensor_group_type] = {}
                    self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
                
                self.highlight_sensor_item(sensor_name_base)
                self._replot_sorted_curves_in_group_plot(sensor_group_type)
        
        # Mode individuel: créer un graphique individuel
        else:
            new_plot_key = self.get_sensor_sort_key(sensor_name_base)
            plot_widget_to_use = None

            if sensor_name_base in self.plots:
                plot_widget_to_use = self.plots[sensor_name_base]
                plot_widget_to_use.clear()
                for key in list(self.curves.keys()):
                    if key.startswith(sensor_name_base):
                        del self.curves[key]
            else:
                plot_widget_to_use = pg.PlotWidget(title=sensor_name_full)
                plot_widget_to_use.setBackground('#1e1e1e')
                plot_widget_to_use.getAxis('left').setTextPen('white')
                plot_widget_to_use.getAxis('bottom').setTextPen('white')
                plot_widget_to_use.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_to_use.setTitle(sensor_name_full, color='white', size='14pt')
                plot_widget_to_use.setProperty("sensor_base_name", sensor_name_base)

                # Insérer le widget dans l'ordre
                insert_index = 0
                for i in range(self.middle_layout.count()):
                    widget = self.middle_layout.itemAt(i).widget()
                    if widget and hasattr(widget, 'property') and widget.property("sensor_base_name"):
                        existing_widget_key = self.get_sensor_sort_key(widget.property("sensor_base_name"))
                        if new_plot_key < existing_widget_key:
                            break
                    insert_index += 1
                self.middle_layout.insertWidget(insert_index, plot_widget_to_use)
                self.plots[sensor_name_base] = plot_widget_to_use

            data_to_plot = recorded_data[data_array_key][sensor_idx]
            if data_to_plot:
                if sensor_name_base.startswith("IMU"):
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        curve = plot_widget_to_use.plot(quat_data, pen=pg.mkPen(['r', 'g', 'b', 'y'][i_quat], width=2), name=axis_label)
                        self.curves[f"{sensor_name_base}_{axis_label}"] = curve
                else:
                    curve = plot_widget_to_use.plot(data_to_plot, pen=pg.mkPen('b', width=2))
                    self.curves[sensor_name_base] = curve
                
                self.highlight_sensor_item(sensor_name_base)

    def create_individual_plot(self, sensor_name_full, sensor_name_base, is_group_mode_imu=False):
        """Crée un graphique individuel pour un capteur, inséré dans l'ordre."""
        if sensor_name_base in self.plots:
            return
            
        plot_widget = pg.PlotWidget(title=sensor_name_full)
        plot_widget.setBackground('#1e1e1e')
        plot_widget.getAxis('left').setTextPen('white')
        plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
        plot_widget.setProperty("sensor_base_name", sensor_name_base)

        # Déterminer l'index d'insertion basé sur la clé de tri
        new_plot_key = self.get_sensor_sort_key(sensor_name_base)
        insert_index = 0
        for i in range(self.middle_layout.count()):
            widget = self.middle_layout.itemAt(i).widget()
            # S'assurer que c'est bien un PlotWidget géré par nous et qu'il a la propriété
            if widget and hasattr(widget, 'property') and widget.property("sensor_base_name") and isinstance(widget, pg.PlotWidget):
                existing_widget_key = self.get_sensor_sort_key(widget.property("sensor_base_name"))
                if new_plot_key < existing_widget_key:
                    break
            insert_index += 1
        
        self.middle_layout.insertWidget(insert_index, plot_widget)
        self.plots[sensor_name_base] = plot_widget

        if sensor_name_base.startswith("IMU"):
            for j, axis_l in enumerate(['w', 'x', 'y', 'z']):
                key = f"{sensor_name_base}_{axis_l}"
                self.backend.plot_data[key] = np.zeros(100)
                curve = plot_widget.plot(self.backend.plot_data[key], pen=pg.mkPen(['r', 'g', 'b', 'y'][j], width=2), name=axis_l)
                self.curves[key] = curve
        else:
            self.backend.plot_data[sensor_name_base] = np.zeros(100)
            curve = plot_widget.plot(self.backend.plot_data[sensor_name_base], pen=pg.mkPen('b', width=2))
            self.curves[sensor_name_base] = curve

        self.highlight_sensor_item(sensor_name_base)
        if is_group_mode_imu:
            self.highlighted_sensors.add(sensor_name_base)

    def add_sensor_curve_to_group_plot(self, sensor_name_full, sensor_group_type):
        """Ajoute une courbe pour un capteur spécifique à un graphique de groupe."""
        if sensor_group_type not in self.group_plots:
            self.create_group_plots()
            if sensor_group_type not in self.group_plots: # Re-check after creation attempt
                return

        if sensor_group_type not in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_group_type] = {}
            
        sensor_base_name_add = sensor_name_full.split()[0]
        if sensor_base_name_add.startswith("IMU"):
            # Si une courbe IMU existe déjà pour ce capteur, ne rien faire (les 4 composantes sont gérées ensemble)
            if any(key.startswith(sensor_name_full) for key in self.backend.group_plot_data.get(sensor_group_type, {})):
                return
            for axis_label in ['w', 'x', 'y', 'z']:
                curve_name = f"{sensor_name_full}_{axis_label}" # Utiliser sensor_name_full pour la clé
                self.backend.group_plot_data[sensor_group_type][curve_name] = np.zeros(100)
        else:
            # Si la courbe existe déjà, ne rien faire
            if sensor_name_full in self.backend.group_plot_data.get(sensor_group_type, {}):
                return
            self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
            
        self.highlight_sensor_item(sensor_base_name_add)
        self._replot_sorted_curves_in_group_plot(sensor_group_type)

    def remove_sensor_plot(self, sensor_name_base_remove):
        """Supprime un graphique individuel pour un capteur."""
        if sensor_name_base_remove in self.plots:
            plot_widget_rem = self.plots.pop(sensor_name_base_remove)
            # Parcourir le layout pour trouver et supprimer le widget
            for i in range(self.middle_layout.count()):
                item = self.middle_layout.itemAt(i)
                if item and item.widget() == plot_widget_rem:
                    self.middle_layout.takeAt(i) # Retirer l'item du layout
                    plot_widget_rem.setParent(None)
                    plot_widget_rem.deleteLater()
                    break # Sortir de la boucle une fois trouvé et supprimé
            
            # Nettoyer les courbes associées dans self.curves et self.backend.plot_data
            keys_to_delete_from_curves = [k for k in self.curves if k.startswith(sensor_name_base_remove)]
            for key_del_curve in keys_to_delete_from_curves:
                # Pas besoin de .clear() sur la courbe, elle sera supprimée avec le widget
                del self.curves[key_del_curve]

            keys_to_delete_from_plot_data = [k for k in self.backend.plot_data if k.startswith(sensor_name_base_remove)]
            for key_del_plot in keys_to_delete_from_plot_data:
                del self.backend.plot_data[key_del_plot]
            
            self.unhighlight_sensor_item(sensor_name_base_remove)

    def remove_sensor_curve_from_group_plot(self, sensor_name_full_rem, sensor_group_type_rem):
        """Supprime les courbes d'un capteur spécifique d'un graphique de groupe."""
        removed_something = False
        if sensor_group_type_rem in self.group_plots and sensor_group_type_rem in self.backend.group_plot_data:
            sensor_base_name_rem = sensor_name_full_rem.split()[0]
            if sensor_base_name_rem.startswith("IMU"):
                # Supprimer les 4 composantes pour IMU
                keys_to_delete_imu = [k for k in self.backend.group_plot_data[sensor_group_type_rem] if k.startswith(sensor_name_full_rem)]
                for key_del_imu in keys_to_delete_imu:
                    if key_del_imu in self.backend.group_plot_data[sensor_group_type_rem]:
                        del self.backend.group_plot_data[sensor_group_type_rem][key_del_imu]
                        removed_something = True
                    # Pas besoin de supprimer de self.group_curves ici, _replot_sorted_curves_in_group_plot s'en chargera
            else:
                # Supprimer la courbe unique pour EMG/pMMG
                if sensor_name_full_rem in self.backend.group_plot_data[sensor_group_type_rem]:
                    del self.backend.group_plot_data[sensor_group_type_rem][sensor_name_full_rem]
                    removed_something = True
                # Pas besoin de supprimer de self.group_curves ici
            
            if removed_something:
                self.unhighlight_sensor_item(sensor_base_name_rem)
                self._replot_sorted_curves_in_group_plot(sensor_group_type_rem)

    def highlight_sensor_item(self, sensor_name_base):
        """Met en évidence un élément capteur dans l'arborescence."""
        for i_hl_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_hl_group)
            for j_hl_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_hl_sensor)
                if sensor_item.text(0).startswith(sensor_name_base):
                    sensor_item.setBackground(0, QBrush(QColor("lightblue")))
                    self.highlighted_sensors.add(sensor_name_base)

    def unhighlight_sensor_item(self, sensor_name_base):
        """Supprime la mise en évidence d'un élément capteur dans l'arborescence."""
        for i_uhl_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_uhl_group)
            for j_uhl_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_uhl_sensor)
                if sensor_item.text(0).startswith(sensor_name_base):
                    sensor_item.setBackground(0, QBrush(QColor("white")))
                    self.highlighted_sensors.discard(sensor_name_base)

    def clear_all_plots(self):
        """Nettoie tous les graphiques existants pour préparer un nouveau trial."""
        # Nettoyer les graphiques individuels
        for plot_widget in self.plots.values():
            plot_widget.setParent(None)
            plot_widget.deleteLater()
        self.plots.clear()
        
        # Nettoyer les graphiques de groupe
        for group_plot_widget in self.group_plots.values():
            group_plot_widget.setParent(None)
            group_plot_widget.deleteLater()
        self.group_plots.clear()
        
        # Nettoyer les dictionnaires de courbes ajoutés pour l'optimisation
        self.curves.clear()
        self.group_curves.clear()
        
        
        # Réinitialiser les ensembles de capteurs mis en évidence
        self.highlighted_sensors.clear()
        
        # Nettoyer les couleurs de mise en évidence dans l'arbre des capteurs
        for i_clear_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_clear_group)
            for j_clear_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_clear_sensor)
                sensor_item.setBackground(0, QBrush(QColor("white")))

    def reset_record_button_for_new_trial(self):
        """Remet le bouton Record à l'état initial pour permettre un nouveau trial."""
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

    def clear_plots_from_menu(self):
        """Méthode appelée par le menu Edit > Clear plots."""
        if hasattr(self.backend, 'clear_plots_only'):
            self.backend.clear_plots_only()
            # Remettre le bouton Record à l'état initial
            self.reset_record_button_for_new_trial()
            # Message moins intrusif dans la status bar
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("Plots cleared - Ready for new trial", 5000)  # 5 secondes
        else:
            # Fallback si la méthode backend n'existe pas
            print("[WARNING] backend.clear_plots_only() not found, using fallback")
            self.clear_all_plots()
            self.reset_record_button_for_new_trial()
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("Plots cleared - Ready for new trial", 5000)
    
    def prepare_for_new_trial(self):
        """Prépare l'interface pour un nouveau trial."""
        self.clear_all_plots()
        # Le bouton record sera réactivé par le backend

    def _is_sensor_already_displayed(self, sensor_base):
        # ...
        pass  # Placeholder if the function was removed. If it exists, the new method goes after its end.

    def get_sensor_sort_key(self, name_for_sort):
        """Génère une clé de tri pour les noms de capteurs ou de courbes.
        Ordre: Type (EMG, pMMG, IMU), puis ID du capteur, puis composante IMU (w,x,y,z).
        """
        type_code = 99  # Default for unknown
        sensor_id = -1
        component_code = -1  # Default for non-component or whole sensor

        # Extrait la partie de base du nom, ex: "EMG25" de "EMG25 (Biceps L)"
        # ou "IMU1_w" de "IMU1 (Head)_w"
        base_name_part = name_for_sort.split(' ')[0]

        if base_name_part.startswith("EMG"):
            type_code = 0
            s_id_str = ''.join(filter(str.isdigit, base_name_part))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    pass # Garder sensor_id = -1 si pas un nombre valide
        elif base_name_part.startswith("pMMG"):
            type_code = 1
            s_id_str = ''.join(filter(str.isdigit, base_name_part))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    pass
        elif base_name_part.startswith("IMU"):
            type_code = 2
            # Extrait l'ID de l'IMU, ex: "IMU1" de "IMU1" ou "IMU1_w"
            imu_id_part_for_id = base_name_part.split('_')[0]
            s_id_str = ''.join(filter(str.isdigit, imu_id_part_for_id))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    pass

            # Vérifie la composante IMU si présente (ex: _w)
            if '_' in base_name_part:
                component_char = base_name_part.split('_')[-1]
                # Gérer les cas comme "w (Head)" -> "w"
                component_char_actual = component_char.split('(')[0].strip()
                component_map = {'w': 0, 'x': 1, 'y': 2, 'z': 3}
                if component_char_actual in component_map:
                    component_code = component_map[component_char_actual]
        
        return (type_code, sensor_id, component_code)

    def _replot_sorted_curves_in_group_plot(self, sensor_group_type):
        """Efface et redessine toutes les courbes actives dans un graphique de groupe, dans l'ordre trié."""
        if sensor_group_type not in self.group_plots or sensor_group_type not in self.backend.group_plot_data:
            return

        plot_widget = self.group_plots[sensor_group_type]
        plot_widget.clear() # Effacer toutes les courbes existantes du widget
        self.group_curves.clear() # Effacer toutes les références de courbes pour ce groupe (et potentiellement d'autres)
        # Il faut être plus spécifique pour ne pas effacer les courbes d'autres groupes si group_curves est global.
        # Pour l'instant, on assume que group_curves est nettoyé globalement avant de redessiner un groupe.
        # Idéalement, group_curves devrait être un dict de dicts: self.group_curves[sensor_group_type][curve_name]
        # Ou nettoyer sélectivement:
        keys_to_remove_from_group_curves = [k for k in self.group_curves if self.get_sensor_sort_key(k)[0] == self.get_sensor_sort_key(sensor_group_type + "1")[0]] # Compare type code
        for key_to_remove in keys_to_remove_from_group_curves:
            del self.group_curves[key_to_remove]


        # Obtenir les données à tracer pour ce groupe
        curves_data_to_plot = self.backend.group_plot_data.get(sensor_group_type, {})
        if not curves_data_to_plot:
            plot_widget.addLegend().clear() # Effacer la légende si plus de courbes
            return

        # Trier les noms des courbes (clés du dictionnaire)
        # Pour les IMU, nous voulons trier par ID de capteur puis par composante (w,x,y,z)
        # Pour EMG/pMMG, trier par ID de capteur.
        # Le nom complet (ex: "EMG25 (Biceps)" ou "IMU1 (Head)_w") est utilisé pour le tri.
        sorted_curve_names = sorted(curves_data_to_plot.keys(), key=self.get_sensor_sort_key)

        legend = plot_widget.addLegend()
        if legend: # S'assurer que la légende existe
             legend.clear() # Nettoyer les anciens items de la légende

        for curve_name_sorted in sorted_curve_names:
            data_array = curves_data_to_plot[curve_name_sorted]
            sensor_base_name_sorted = curve_name_sorted.split(' ')[0].split('_')[0] # ex: EMG25, IMU1
            sensor_id_str_sorted = ''.join(filter(str.isdigit, sensor_base_name_sorted))
            sensor_idx_sorted = int(sensor_id_str_sorted) if sensor_id_str_sorted else 0 # Fallback, devrait toujours avoir un ID

            pen = None
            if curve_name_sorted.startswith("IMU"):
                # Les courbes IMU sont nommées comme "IMU1 (Head)_w"
                component = curve_name_sorted.split('_')[-1].split('(')[0].strip()
                colors = {'w': 'r', 'x': 'g', 'y': 'b', 'z': 'c'} # Ajuster les couleurs si besoin
                pen = pg.mkPen(colors.get(component, 'w'), width=2) # 'w' par défaut si comp inconnu
            else: # EMG ou pMMG
                # Utiliser l'ID du capteur pour un schéma de couleurs cohérent
                # Les noms sont comme "EMG25 (Biceps L)"
                color_palette = ['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'pink']
                color_idx_sorted = sensor_idx_sorted % len(color_palette)
                pen = pg.mkPen(color_palette[color_idx_sorted], width=2)
            
            if pen:
                # Utiliser curve_name_sorted pour le nom dans la légende (le nom complet avec mapping)
                curve_item = plot_widget.plot(data_array, pen=pen, name=curve_name_sorted)
                self.group_curves[curve_name_sorted] = curve_item
            else:
                print(f"[WARNING] Could not determine pen for {curve_name_sorted}")

        # S'assurer que la légende est bien visible après avoir ajouté des items.
        # Parfois, elle peut être masquée ou vide.
        if plot_widget.legend:
            plot_widget.legend.setVisible(True) 

    def start_tpose_calibration(self):
        """Démarre la calibration T-pose."""
        # Vérifier si des capteurs sont connectés
        if not self.backend.sensor_config or not self.backend.sensor_config.get('imu_ids'):
            QMessageBox.warning(self, "Calibration impossible", 
                           "Aucun capteur IMU n'est connecté.\n"
                           "Veuillez d'abord connecter des IMUs.")
            return False
            
        # Vérifier si des IMUs sont mappés
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

    def stop_tpose_calibration(self):
        """Arrête la calibration T-pose."""
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
                self.calibration_start_button.setText("Calibration échouée ❌")
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
