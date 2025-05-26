'''
Fix the issue where IMU sensors do not appear in the 2D Plot after pressing record stop and being in the plot mode by sensor group.
'''
import sys
import os
import traceback
import numpy as np  # Kept for np.zeros, np.roll
import pyqtgraph as pg  # Add missing import
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox, 
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer # QThread, pyqtSignal are in the backend
from PyQt5.QtGui import QColor, QBrush # QCursor is no longer directly used here

# Add the parent directory and backend folder to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'back')))

from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog
# Import logic from the backend file
from dashboard_app_back import DashboardAppBack  # Changed from relative import to absolute


class DashboardApp(QMainWindow):
    def __init__(self):
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
        self.current_subject_file = None
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
                self.main_bar_re.edit_Boleen(True)
        except Exception as e:
            print(f"[ERROR] Error initializing MainBar: {e}")
            import traceback
            traceback.print_exc()
            self.main_bar_re = None

        # Ajouter un timer pour surveiller la qualité du signal IMU
        self.imu_monitor_timer = QTimer()
        self.imu_monitor_timer.timeout.connect(self.check_imu_signal_quality)
        self.imu_monitor_timer.start(5000)  # Vérification toutes les 5 secondes

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
        self.model_3d_widget = Model3DWidget()
        right_panel.addWidget(self.model_3d_widget, stretch=3)
        
        # Grouper les contrôles du modèle 3D
        model_controls_group = QGroupBox("Model Controls")
        model_controls_layout = QVBoxLayout()
        
        # Ligne 1: Animation et Reset view
        animation_layout = QHBoxLayout()
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_model_view)
        animation_layout.addWidget(self.animate_button)
        animation_layout.addWidget(self.reset_view_button)
        model_controls_layout.addLayout(animation_layout)
        
        # Ligne 2: Smart Movement
        self.motion_prediction_button = QPushButton("Smart Movement: INACTIVE")
        self.motion_prediction_button.clicked.connect(self.toggle_motion_prediction)
        model_controls_layout.addWidget(self.motion_prediction_button)
        
        model_controls_group.setLayout(model_controls_layout)
        right_panel.addWidget(model_controls_group)
        
        # Grouper les contrôles de configuration des capteurs
        sensor_config_group = QGroupBox("Sensor Configuration")
        sensor_config_layout = QVBoxLayout()
        
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        self.config_button.setEnabled(False)  # Disable the button by default
        sensor_config_layout.addWidget(self.config_button)
        
        self.default_config_button = QPushButton("Set Up Default Assignments")
        self.default_config_button.clicked.connect(self.setup_default_mappings)
        sensor_config_layout.addWidget(self.default_config_button)
        
        sensor_config_group.setLayout(sensor_config_layout)
        right_panel.addWidget(sensor_config_group)

        # Grouper les outils de debug et validation
        debug_group = QGroupBox("Debug & Validation")
        debug_layout = QGridLayout()  # Utiliser une grille pour une meilleure organisation
        
        self.imu_status_button = QPushButton("IMU Status")
        self.imu_status_button.clicked.connect(self.show_imu_status)
        debug_layout.addWidget(self.imu_status_button, 0, 0)
        
        self.calibration_status_button = QPushButton("Calibration Status")
        self.calibration_status_button.clicked.connect(self.show_calibration_status)
        debug_layout.addWidget(self.calibration_status_button, 0, 1)
        
        debug_group.setLayout(debug_layout)
        right_panel.addWidget(debug_group)
        
        # Styles améliorés pour les boutons
        animate_button_style = """
            QPushButton {
                background-color: #2196f3;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                min-height: 30px;
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
                padding: 8px 12px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #8e8e8e;
            }
            QPushButton:pressed {
                background-color: #757575;
            }
        """
        
        motion_prediction_style = """
            QPushButton {
                background-color: #9C27B0;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                color: white;
                font-size: 13px;
                font-weight: 500;
                text-align: center;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #8E24AA;
            }
            QPushButton:pressed {
                background-color: #7B1FA2;
            }
        """
        
        config_button_style = """
            QPushButton {
                background-color: #ff9800;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                color: white;
                font-size: 13px;
                font-weight: 500;
                text-align: center;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #fb8c00;
            }
            QPushButton:pressed {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #d0d0d0;
                color: #888888;
            }
        """
        
        default_config_style = """
            QPushButton {
                background-color: #673AB7;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                color: white;
                font-size: 13px;
                font-weight: 500;
                text-align: center;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #5E35B1;
            }
            QPushButton:pressed {
                background-color: #512DA8;
            }
        """
        
        debug_button_style = """
            QPushButton {
                background-color: #607D8B;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
                font-size: 11px;
                font-weight: 500;
                text-align: center;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:pressed {
                background-color: #455A64;
            }
        """
        
        # Appliquer les styles
        self.animate_button.setStyleSheet(animate_button_style)
        self.reset_view_button.setStyleSheet(reset_view_button_style)
        self.motion_prediction_button.setStyleSheet(motion_prediction_style)
        self.config_button.setStyleSheet(config_button_style)
        self.default_config_button.setStyleSheet(default_config_style)
        self.imu_status_button.setStyleSheet(debug_button_style)
        self.calibration_status_button.setStyleSheet(debug_button_style)
        
        # Style pour les groupes
        group_style = """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #333;
                font-size: 12px;
            }
        """
        
        model_controls_group.setStyleSheet(group_style)
        sensor_config_group.setStyleSheet(group_style)
        debug_group.setStyleSheet(group_style)

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
        
        # Désactiver le menu Edit quand de nouveaux capteurs se connectent
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
        
        # If not the first time, load existing mappings
        curr_maps = self.backend.get_current_mappings_for_dialog()
        
        # Create and show dialog
        dialog = SensorMappingDialog(self, curr_maps, available_sensors)
        dialog.mappings_updated.connect(self.backend.update_sensor_mappings)
        
        # Move dialog to foreground and highlight it
        dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        dialog.activateWindow()
        dialog.raise_()
        
        # Execute dialog modally
        dialog.exec_()

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

    def check_imu_signal_quality(self):
        """Checks IMU signal quality periodically."""
        if hasattr(self, 'model_3d_widget') and self.backend.sensor_config:
            debug_info = self.model_3d_widget.model_viewer.get_debug_info()
            if debug_info and 'imu_ids' in self.backend.sensor_config:
                expected_imus = self.backend.sensor_config['imu_ids']
                active_imus = debug_info['active_imus']
                
                # Count disconnected IMUs
                disconnected_count = len([imu for imu in expected_imus if imu not in active_imus])
                
                if disconnected_count > 0:
                    print(f"[WARNING] {disconnected_count} IMU(s) not responding")

    def toggle_animation(self):
        """Toggles the 3D model walking animation."""
        if hasattr(self, 'model_3d_widget'):
            walking = self.model_3d_widget.toggle_animation()
            if walking:
                self.animate_button.setText("Stop Animation")
                self.animate_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 12px;
                        color: white;
                        font-size: 12px;
                        font-weight: 500;
                        text-align: center;
                        min-height: 30px;
                    }
                    QPushButton:hover {
                        background-color: #e53935;
                    }
                    QPushButton:pressed {
                        background-color: #d32f2f;
                    }
                """)
            else:
                self.animate_button.setText("Start Animation")
                self.animate_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2196f3;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 12px;
                        color: white;
                        font-size: 12px;
                        font-weight: 500;
                        text-align: center;
                        min-height: 30px;
                    }
                    QPushButton:hover {
                        background-color: #1e88e5;
                    }
                    QPushButton:pressed {
                        background-color: #1976d2;
                    }
                """)
        else:
            QMessageBox.warning(self, "Error", "3D model viewer not available")

    def reset_model_view(self):
        """Resets the 3D model view to default position."""
        if hasattr(self, 'model_3d_widget'):
            self.model_3d_widget.reset_view()
        else:
            QMessageBox.warning(self, "Error", "3D model viewer not available")

    def toggle_motion_prediction(self):
        """Toggles motion prediction on/off."""
        if hasattr(self, 'model_3d_widget'):
            prediction_active = self.model_3d_widget.toggle_motion_prediction()
            if prediction_active:
                self.motion_prediction_button.setText("Smart Movement: ACTIVE")
                self.motion_prediction_button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 16px;
                        color: white;
                        font-size: 13px;
                        font-weight: 500;
                        text-align: center;
                        min-height: 35px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #3d8b40;
                    }
                """)
            else:
                self.motion_prediction_button.setText("Smart Movement: INACTIVE")
                self.motion_prediction_button.setStyleSheet("""
                    QPushButton {
                        background-color: #9C27B0;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 16px;
                        color: white;
                        font-size: 13px;
                        font-weight: 500;
                        text-align: center;
                        min-height: 35px;
                    }
                    QPushButton:hover {
                        background-color: #8E24AA;
                    }
                    QPushButton:pressed {
                        background-color: #7B1FA2;
                    }
                """)
        else:
            QMessageBox.warning(self, "Error", "3D model viewer not available")

    def show_imu_status(self):
        """Shows detailed IMU status."""
        if not hasattr(self, 'model_3d_widget'):
            QMessageBox.warning(self, "Error", "3D model viewer not available")
            return
            
        debug_info = self.model_3d_widget.model_viewer.get_debug_info()
        if not debug_info:
            QMessageBox.information(self, "IMU Status", 
                                   "Debug mode not active.\nEnable debug mode in sensor configuration to see detailed status.")
            return
        
        status_msg = "IMU Signal Status:\n\n"
        
        if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config:
            expected_imus = self.backend.sensor_config['imu_ids']
            active_imus = debug_info['active_imus']
            
            for imu_id in expected_imus:
                if imu_id in active_imus:
                    signal_info = debug_info['signal_quality'].get(imu_id, {})
                    status = f"✅ IMU {imu_id}: ACTIVE"
                    if signal_info:
                        status += f" ({signal_info.get('data_rate', 'N/A')}Hz)"
                else:
                    status = f"❌ IMU {imu_id}: NO SIGNAL"
                status_msg += status + "\n"
        else:
            status_msg += "No IMU configuration available"
        
        QMessageBox.information(self, "IMU Status", status_msg)

    def show_calibration_status(self):
        """Shows IMU calibration status."""
        if not hasattr(self, 'model_3d_widget'):
            QMessageBox.warning(self, "Error", "3D model viewer not available")
            return
            
        debug_info = self.model_3d_widget.model_viewer.get_debug_info()
        if not debug_info:
            QMessageBox.information(self, "Calibration Status", 
                                   "Debug mode not active.\nEnable debug mode to see calibration status.")
            return
        
        cal_info = debug_info['calibration_status']
        status_msg = "IMU Calibration Status:\n\n"
        
        if cal_info['calibration_active']:
            status_msg += "🔄 Calibration in progress...\n\n"
        else:
            status_msg += "Calibration completed\n\n"
        
        if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config:
            expected_imus = self.backend.sensor_config['imu_ids']
            calibrated_imus = cal_info['calibrated_imus']
            
            for imu_id in expected_imus:
                if imu_id in calibrated_imus:
                    status_msg += f"✅ IMU {imu_id}: CALIBRATED\n"
                else:
                    status_msg += f"⚠️ IMU {imu_id}: NOT CALIBRATED\n"
        
        status_msg += "\nNote: Calibration improves tracking accuracy.\nUse 'Start IMU Calibration' in sensor configuration."
        
        QMessageBox.information(self, "Calibration Status", status_msg)

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
        """Shows recorded data on plots."""
        rec_data = self.backend.recorded_data # Use backend's copy
        has_any_data = False
        for sensor_key in ["EMG", "IMU", "pMMG"]:
            if rec_data.get(sensor_key) and any(rec_data[sensor_key]) and any(d for d in rec_data[sensor_key] if d):
                has_any_data = True
                break
        
        if not has_any_data:
            QMessageBox.warning(self, 'Warning', "No data was recorded.")
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
        
        # Check if we have sensor configuration
        if not self.backend.sensor_config:
            print("[WARNING] No sensor configuration available")
            return
        
        print(f"[DEBUG] Configuration disponible: EMG_IDs={self.backend.sensor_config.get('emg_ids')}, "
              f"IMU_IDs={self.backend.sensor_config.get('imu_ids')}, "
              f"pMMG_IDs={self.backend.sensor_config.get('pmmg_ids')}")
        
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
                if sensor_item.text(0).startswith(sensor_name_base): 
                    return sensor_item
        return None

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
                    del self.backend.group_plot_data[sensor_group_type_rem][key_del_imu]
                    removed_something = True
            else:
                # Supprimer la courbe unique pour EMG/pMMG
                if sensor_name_full_rem in self.backend.group_plot_data[sensor_group_type_rem]:
                    del self.backend.group_plot_data[sensor_group_type_rem][sensor_name_full_rem]
                    removed_something = True
            
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
                    if sensor_name_base in self.highlighted_sensors:
                        self.highlighted_sensors.remove(sensor_name_base)

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

    def get_sensor_sort_key(self, name_for_sort):
        """Generates a sort key for sensor names or curve names."""
        type_code = 99  # Default for unknown
        sensor_id = -1
        component_code = -1  # Default for non-component or whole sensor

        # Extract base name part
        base_name_part = name_for_sort.split(' ')[0]

        if base_name_part.startswith("EMG"):
            type_code = 0
            s_id_str = ''.join(filter(str.isdigit, base_name_part))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    sensor_id = -1
        elif base_name_part.startswith("pMMG"):
            type_code = 1
            s_id_str = ''.join(filter(str.isdigit, base_name_part))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    sensor_id = -1
        elif base_name_part.startswith("IMU"):
            type_code = 2
            # Extract IMU ID
            imu_id_part_for_id = base_name_part.split('_')[0]
            s_id_str = ''.join(filter(str.isdigit, imu_id_part_for_id))
            if s_id_str:
                try:
                    sensor_id = int(s_id_str)
                except ValueError:
                    sensor_id = -1

            # Check for IMU component if present
            if '_' in base_name_part:
                component_char = base_name_part.split('_')[-1]
                component_char_actual = component_char.split('(')[0].strip()
                component_map = {'w': 0, 'x': 1, 'y': 2, 'z': 3}
                if component_char_actual in component_map:
                    component_code = component_map[component_char_actual]
        
        return (type_code, sensor_id, component_code)

    def update_live_plots(self, packet):
        """Updates real-time plots with new data using setData() for better performance."""
        # EMG individual plots
        if 'emg' in packet and packet['emg']:
            for i, emg_value in enumerate(packet['emg']):
                sensor_name = (f"EMG{self.backend.sensor_config['emg_ids'][i]}"
                               if i < len(self.backend.sensor_config.get('emg_ids', []))
                               else f"EMG{i+1}")
                if sensor_name in self.curves:
                    self.backend.plot_data[sensor_name] = np.roll(self.backend.plot_data[sensor_name], -1)
                    self.backend.plot_data[sensor_name][-1] = emg_value
                    self.curves[sensor_name].setData(self.backend.plot_data[sensor_name])

        # EMG group plots
        if 'emg' in packet and packet['emg'] and "EMG" in self.group_plots:
            for i, emg_value in enumerate(packet['emg']):
                sensor_name_full = (f"EMG{self.backend.sensor_config['emg_ids'][i]}"
                                    if i < len(self.backend.sensor_config.get('emg_ids', []))
                                    else f"EMG{i+1}")
                item = self.find_sensor_item_by_base_name(sensor_name_full.split()[0])
                display_name_emg = item.text(0) if item else sensor_name_full
                
                gp_emg = self.backend.group_plot_data.get("EMG", {})
                if display_name_emg in gp_emg:
                    gp_emg[display_name_emg] = np.roll(gp_emg[display_name_emg], -1)
                    gp_emg[display_name_emg][-1] = emg_value
                    if display_name_emg in self.group_curves:
                        self.group_curves[display_name_emg].setData(gp_emg[display_name_emg])

        # pMMG individual plots
        if 'pmmg' in packet and packet['pmmg']:
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_name = (f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}"
                               if i < len(self.backend.sensor_config.get('pmmg_ids', []))
                               else f"pMMG{i+1}")
                if sensor_name in self.curves:
                    self.backend.plot_data[sensor_name] = np.roll(self.backend.plot_data[sensor_name], -1)
                    self.backend.plot_data[sensor_name][-1] = pmmg_value
                    self.curves[sensor_name].setData(self.backend.plot_data[sensor_name])

        # pMMG group plots
        if 'pmmg' in packet and packet['pmmg'] and "pMMG" in self.group_plots:
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

        # IMU individual plots (4 components)
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

        # IMU group plots
        if 'imu' in packet and packet['imu'] and "IMU" in self.group_plots:
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

    def on_sensor_clicked(self, item_clicked, column):
        """Handles click on a sensor in the tree."""
        if item_clicked.childCount() > 0:
            # It's a group, not a sensor
            return
            
        if item_clicked.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Error", "Sensor is not connected. Please connect the sensor first.")
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
        """Shows recorded data for a specific sensor."""
        recorded_data = self.backend.recorded_data
        
        # Extract sensor ID
        sensor_id_str = ''.join(filter(str.isdigit, sensor_name_base))
        if not sensor_id_str:
            return
        sensor_id = int(sensor_id_str)
        
        # Determine sensor type and find correct index in recorded_data
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
            QMessageBox.information(self, "No Data", f"No recorded data available for {sensor_name_base}.")
            return

        # Group mode: display in group plots
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
                print(f"[DEBUG] Group mode - Displaying {sensor_name_base}: {len(data_to_plot)} data points")
                if sensor_name_base.startswith("IMU"):
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        color_idx = i_quat
                        curve_name = f"{sensor_name_full}_{axis_label}"
                        curve = plot_widget.plot(quat_data, pen=pg.mkPen(['r', 'g', 'b', 'c'][color_idx], width=2), name=curve_name)
                        self.group_curves[curve_name] = curve
                else:
                    color_idx = sensor_idx % 8
                    print(f"[DEBUG]   {sensor_name_full}: {len(data_to_plot)} points")
                    curve = plot_widget.plot(data_to_plot, pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][color_idx], width=2), name=sensor_name_full)
                    self.group_curves[sensor_name_full] = curve
                    if sensor_group_type not in self.backend.group_plot_data:
                        self.backend.group_plot_data[sensor_group_type] = {}
                    self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
                
                self.highlight_sensor_item(sensor_name_base)
                self._replot_sorted_curves_in_group_plot(sensor_group_type)
        
        # Individual mode: create individual plot
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

                # Insert widget in order
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
                print(f"[DEBUG] Displaying {sensor_name_base}: {len(data_to_plot)} data points")
                if sensor_name_base.startswith("IMU"):
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        curve = plot_widget_to_use.plot(quat_data, pen=pg.mkPen(['r', 'g', 'b', 'c'][i_quat], width=2), name=axis_label)
                        key = f"{sensor_name_base}_{axis_label}"
                        self.curves[key] = curve
                else:
                    print(f"[DEBUG]   {sensor_name_base}: {len(data_to_plot)} points")
                    curve = plot_widget_to_use.plot(data_to_plot, pen=pg.mkPen('b', width=2))
                    self.curves[sensor_name_base] = curve
                
                self.highlight_sensor_item(sensor_name_base)

    def apply_imu_mappings(self, imu_mappings):
        """Apply IMU mappings to the 3D model."""
        if hasattr(self, 'model_3d_widget'):
            self.model_3d_widget.model_viewer.imu_mapping = imu_mappings.copy()

    def refresh_sensor_tree_with_mappings(self, emg_mappings, pmmg_mappings):
        """Refresh the sensor tree display with new mappings."""
        # Update sensor names in the tree with their body part mappings
        for i_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_group)
            group_name = group_item.text(0)
            
            for j_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_sensor)
                original_text = sensor_item.text(0)
                sensor_base = original_text.split(' ')[0]  # Get base name (e.g., "EMG25")
                
                # Extract sensor ID
                sensor_id_str = ''.join(filter(str.isdigit, sensor_base))
                if sensor_id_str:
                    sensor_id = int(sensor_id_str)
                    
                    # Check for mapping and update display
                    if group_name == "EMG Data" and sensor_id in emg_mappings:
                        body_part = emg_mappings[sensor_id]
                        sensor_item.setText(0, f"{sensor_base} ({body_part})")
                    elif group_name == "pMMG Data" and sensor_id in pmmg_mappings:
                        body_part = pmmg_mappings[sensor_id]
                        sensor_item.setText(0, f"{sensor_base} ({body_part})")
                    # IMU mappings are handled by the 3D model directly

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    
    dashboard.show()
    sys.exit(app.exec_())
