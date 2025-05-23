'''
Fix the issue where IMU sensors do not appear in the 2D Plot after pressing record stop and being in the plot mode by sensor group.
'''
import sys
import os
import numpy as np # Kept for np.zeros, np.roll
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox, 
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea
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
from dashboard_app_back import DashboardAppBack # Changé d'import relatif à absolu


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
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        right_panel.addWidget(self.animate_button)
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_model_view)
        right_panel.addWidget(self.reset_view_button)
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.setStyleSheet("font-size: 14px; padding: 8px 20px;")
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        self.config_button.setEnabled(False)  # Disable the button by default
        right_panel.addWidget(self.config_button)
        self.default_config_button = QPushButton("Set Up Default Assignments")
        # Button styles (multi-line escaped strings)
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
        
        # Add a button for smart movement
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
        """)
        self.motion_prediction_button.clicked.connect(self.toggle_motion_prediction)
        right_panel.addWidget(self.motion_prediction_button)

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
        QTimer.singleShot(100, lambda: self.open_sensor_mapping_dialog(available_sensors))

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
                self.middle_layout.addWidget(plot_widget_imu)
                self.group_plots["IMU"] = plot_widget_imu
                self.backend.group_plot_data["IMU"] = {}

    def open_sensor_mapping_dialog(self, available_sensors=None):
        # Check if sensors are connected
        if not self.backend.sensor_config:
            QMessageBox.warning(self, "No Sensors", "Please connect sensors before configuring the mapping.")
            return
        
        # Si ce n'est pas la première fois, charger les mappages existants
        curr_maps = self.backend.get_current_mappings_for_dialog()
        
        # Créer et afficher la boîte de dialogue
        dialog = SensorMappingDialog(self, curr_maps, available_sensors)
        dialog.mappings_updated.connect(self.backend.update_sensor_mappings)
        
        # Déplacer la fenêtre de dialogue au premier plan et la mettre en évidence
        dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        dialog.activateWindow()
        dialog.raise_()
        
        # Exécuter la boîte de dialogue de façon modale
        dialog.exec_()

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
        self.backend.cleanup_on_close()
        event_close.accept()

    def toggle_motion_prediction(self):
        """Enable or disable smart movement prediction."""
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
        """Affiche les données enregistrées sur les graphiques."""
        rec_data = self.backend.recorded_data # Use backend's copy
        has_any_data = False
        for sensor_key in ["EMG", "IMU", "pMMG"]:
            if rec_data.get(sensor_key) and any(rec_data[sensor_key]) and any(d for d in rec_data[sensor_key] if d):
                has_any_data = True
                break
        
        if not has_any_data:
            QMessageBox.warning(self, 'Warning', "Aucune donnée n'a été enregistrée.")
            self.record_button.setEnabled(True)
            if self.backend.client_socket: 
                self.connect_button.setText("Disconnect")
                self.connect_button.setEnabled(True)
            else: 
                self.connect_button.setText("Connect")
                self.connect_button.setEnabled(True)
            return

        if self.group_sensor_mode.isChecked():
            self.create_group_plots()
        
        # Afficher automatiquement tous les capteurs avec des données
        self.auto_display_all_sensors_with_data()

    def auto_display_all_sensors_with_data(self):
        """Affiche automatiquement tous les capteurs qui ont des données enregistrées."""
        rec_data = self.backend.recorded_data
        
        # Vérifier si on a une configuration de capteurs
        if not self.backend.sensor_config:
            print("[WARNING] Aucune configuration de capteurs disponible")
            return
        
        print(f"[DEBUG] Configuration disponible: EMG_IDs={self.backend.sensor_config.get('emg_ids')}, "
              f"IMU_IDs={self.backend.sensor_config.get('imu_ids')}, "
              f"pMMG_IDs={self.backend.sensor_config.get('pmmg_ids')}")
        
        # Parcourir les données EMG
        if rec_data.get("EMG") and self.backend.sensor_config.get('emg_ids'):
            emg_ids = self.backend.sensor_config['emg_ids']
            print(f"[DEBUG] Traitement des données EMG pour les IDs: {emg_ids}")
            for idx, data in enumerate(rec_data["EMG"]):
                if data and idx < len(emg_ids):  # Si il y a des données pour ce capteur
                    emg_id = emg_ids[idx]  # Utiliser le vrai ID depuis la config
                    sensor_base = f"EMG{emg_id}"
                    print(f"[DEBUG] Affichage EMG - Index: {idx}, ID: {emg_id}, Capteur: {sensor_base}, Données: {len(data)} points")
                    # Trouver l'élément dans l'arbre des capteurs
                    item = self.find_sensor_item_by_base_name(sensor_base)
                    sensor_full = item.text(0) if item else sensor_base
                    
                    # Vérifier si déjà affiché pour éviter les duplications
                    if not self._is_sensor_already_displayed(sensor_base):
                        self.plot_recorded_sensor_data(sensor_full, sensor_base)
                    else:
                        print(f"[DEBUG] {sensor_base} déjà affiché, ignoré")
        
        # Parcourir les données pMMG
        if rec_data.get("pMMG") and self.backend.sensor_config.get('pmmg_ids'):
            pmmg_ids = self.backend.sensor_config['pmmg_ids']
            print(f"[DEBUG] Traitement des données pMMG pour les IDs: {pmmg_ids}")
            for idx, data in enumerate(rec_data["pMMG"]):
                if data and idx < len(pmmg_ids):  # Si il y a des données pour ce capteur
                    pmmg_id = pmmg_ids[idx]  # Utiliser le vrai ID depuis la config
                    sensor_base = f"pMMG{pmmg_id}"
                    print(f"[DEBUG] Affichage pMMG - Index: {idx}, ID: {pmmg_id}, Capteur: {sensor_base}, Données: {len(data)} points")
                    # Trouver l'élément dans l'arbre des capteurs
                    item = self.find_sensor_item_by_base_name(sensor_base)
                    sensor_full = item.text(0) if item else sensor_base
                    
                    # Vérifier si déjà affiché pour éviter les duplications
                    if not self._is_sensor_already_displayed(sensor_base):
                        self.plot_recorded_sensor_data(sensor_full, sensor_base)
                    else:
                        print(f"[DEBUG] {sensor_base} déjà affiché, ignoré")
        
        # Parcourir les données IMU
        if rec_data.get("IMU") and self.backend.sensor_config.get('imu_ids'):
            imu_ids = self.backend.sensor_config['imu_ids']
            print(f"[DEBUG] Traitement des données IMU pour les IDs: {imu_ids}")
            for idx, data in enumerate(rec_data["IMU"]):
                if data and idx < len(imu_ids):  # Si il y a des données pour ce capteur
                    imu_id = imu_ids[idx]  # Utiliser le vrai ID depuis la config
                    sensor_base = f"IMU{imu_id}"
                    print(f"[DEBUG] Affichage IMU - Index: {idx}, ID: {imu_id}, Capteur: {sensor_base}, Données: {len(data)} points")
                    # Trouver l'élément dans l'arbre des capteurs
                    item = self.find_sensor_item_by_base_name(sensor_base)
                    sensor_full = item.text(0) if item else sensor_base
                    
                    # Vérifier si déjà affiché pour éviter les duplications
                    if not self._is_sensor_already_displayed(sensor_base):
                        self.plot_recorded_sensor_data(sensor_full, sensor_base)
                    else:
                        print(f"[DEBUG] {sensor_base} déjà affiché, ignoré")

    def _is_sensor_already_displayed(self, sensor_base):
        """Vérifie si un capteur est déjà affiché pour éviter les duplications."""
        # Mode individuel: vérifier si le capteur a déjà un graphique
        if self.single_sensor_mode.isChecked():
            return sensor_base in self.plots
        
        # Mode groupe: vérifier si le capteur est déjà tracé dans un graphique de groupe
        elif self.group_sensor_mode.isChecked():
            if sensor_base.startswith("EMG"):
                sensor_group_type = "EMG"
            elif sensor_base.startswith("pMMG"):
                sensor_group_type = "pMMG"
            elif sensor_base.startswith("IMU"):
                sensor_group_type = "IMU"
            else:
                return False
                
            # Vérifier dans le graphique de groupe correspondant
            if sensor_group_type in self.group_plots:
                plot_widget = self.group_plots[sensor_group_type]
                # Chercher si une courbe avec ce nom existe déjà
                for plot_item in plot_widget.listDataItems():
                    if hasattr(plot_item, 'name') and plot_item.name():
                        if plot_item.name().startswith(sensor_base):
                            return True
        
        return False

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
        en remplaçant clear()/plot() par setData() pour réduire l’overhead Qt."""
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
            for i, emg_value in enumerate(packet['emg']):
                sensor_name_full = (f"EMG{self.backend.sensor_config['emg_ids'][i]}"
                                    if i < len(self.backend.sensor_config.get('emg_ids', []))
                                    else f"EMG{i+1}")
                gp = self.backend.group_plot_data.get("EMG", {})
                if sensor_name_full in gp:
                    gp[sensor_name_full] = np.roll(gp[sensor_name_full], -1)
                    gp[sensor_name_full][-1] = emg_value
                    if sensor_name_full in self.group_curves:
                        self.group_curves[sensor_name_full].setData(gp[sensor_name_full])
                    else:
                        color_idx = (int(''.join(filter(str.isdigit, sensor_name_full))) % 8
                                     if ''.join(filter(str.isdigit, sensor_name_full)) else 0)
                        pen = pg.mkPen(
                            ['r','g','b','y','c','m','orange','w'][color_idx],
                            width=2
                        )
                        c = self.group_plots["EMG"].plot(gp[sensor_name_full], pen=pen, name=sensor_name_full)
                        self.group_curves[sensor_name_full] = c
                        try:
                            self.group_plots["EMG"].addLegend()
                        except Exception:
                            pass

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
            for i, pmmg_value in enumerate(packet['pmmg']):
                sensor_name_full = (f"pMMG{self.backend.sensor_config['pmmg_ids'][i]}"
                                    if i < len(self.backend.sensor_config.get('pmmg_ids', []))
                                    else f"pMMG{i+1}")
                gp = self.backend.group_plot_data.get("pMMG", {})
                if sensor_name_full in gp:
                    gp[sensor_name_full] = np.roll(gp[sensor_name_full], -1)
                    gp[sensor_name_full][-1] = pmmg_value
                    if sensor_name_full in self.group_curves:
                        self.group_curves[sensor_name_full].setData(gp[sensor_name_full])
                    else:
                        color_idx = (int(''.join(filter(str.isdigit, sensor_name_full))) % 8
                                     if ''.join(filter(str.isdigit, sensor_name_full)) else 0)
                        pen = pg.mkPen(
                            ['r','g','b','y','c','m','orange','w'][color_idx],
                            width=2
                        )
                        c = self.group_plots["pMMG"].plot(gp[sensor_name_full], pen=pen, name=sensor_name_full)
                        self.group_curves[sensor_name_full] = c
                        try:
                            self.group_plots["pMMG"].addLegend()
                        except Exception:
                            pass

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

    def on_sensor_clicked(self, item_clicked, column):
        """Gère le clic sur un capteur dans l'arborescence."""
        if item_clicked.childCount() > 0:
            # C'est un groupe, pas un capteur
            return
            
        if item_clicked.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Erreur", "Le capteur n'est pas connecté. Veuillez d'abord connecter le capteur.")
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
        """Affiche les données enregistrées pour un capteur spécifique."""
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
            # Trouver l'index de ce capteur dans la configuration EMG
            if self.backend.sensor_config and 'emg_ids' in self.backend.sensor_config:
                emg_ids = self.backend.sensor_config['emg_ids']
                if sensor_id in emg_ids:
                    sensor_idx = emg_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("EMG", [])) and 
                               recorded_data["EMG"][sensor_idx])
        elif sensor_name_base.startswith("pMMG"):
            data_array_key = "pMMG"
            # Trouver l'index de ce capteur dans la configuration pMMG
            if self.backend.sensor_config and 'pmmg_ids' in self.backend.sensor_config:
                pmmg_ids = self.backend.sensor_config['pmmg_ids']
                if sensor_id in pmmg_ids:
                    sensor_idx = pmmg_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("pMMG", [])) and 
                               recorded_data["pMMG"][sensor_idx])
        elif sensor_name_base.startswith("IMU"):
            data_array_key = "IMU"
            # Trouver l'index de ce capteur dans la configuration IMU
            if self.backend.sensor_config and 'imu_ids' in self.backend.sensor_config:
                imu_ids = self.backend.sensor_config['imu_ids']
                if sensor_id in imu_ids:
                    sensor_idx = imu_ids.index(sensor_id)
                    has_data = (sensor_idx < len(recorded_data.get("IMU", [])) and 
                               recorded_data["IMU"][sensor_idx])

        if not has_data or sensor_idx == -1:
            QMessageBox.information(self, "Aucune donnée", f"Aucune donnée enregistrée disponible pour {sensor_name_base}.")
            return

        # Mode groupe: afficher dans les graphiques de groupe
        if self.group_sensor_mode.isChecked():
            sensor_group_type = data_array_key
            
            # S'assurer que le graphique de groupe existe
            if sensor_group_type not in self.group_plots:
                self.create_group_plots()
            
            plot_widget = self.group_plots.get(sensor_group_type)
            if not plot_widget:
                return

            # Vérifier si déjà tracé
            is_already_plotted = any(hasattr(p_item, 'name') and p_item.name() == sensor_name_full 
                                   for p_item in plot_widget.listDataItems())
            if is_already_plotted:
                return

            # Tracer les données
            data_to_plot = recorded_data[data_array_key][sensor_idx]
            if data_to_plot:
                if sensor_name_base.startswith("IMU"):
                    # Pour les IMUs, tracer les 4 composantes du quaternion
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        color = ['r', 'g', 'b', 'y'][i_quat]
                        plot_widget.plot(quat_data, pen=pg.mkPen(color, width=2), 
                                       name=f"{sensor_name_full}_{axis_label}")
                else:
                    # Pour EMG et pMMG, tracer directement les données
                    color_idx = sensor_idx % 8
                    plot_widget.plot(data_to_plot, 
                                   pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][color_idx], width=2), 
                                   name=sensor_name_full)
                
                self.highlight_sensor_item(sensor_name_base)
        
        # Mode individuel: créer un graphique individuel
        else:
            if sensor_name_base in self.plots:
                plot_widget = self.plots[sensor_name_base]
                plot_widget.clear()
            else:
                plot_widget = pg.PlotWidget(title=sensor_name_full)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget)
                self.plots[sensor_name_base] = plot_widget

            # Tracer les données
            data_to_plot = recorded_data[data_array_key][sensor_idx]
            if data_to_plot:
                if sensor_name_base.startswith("IMU"):
                    # Pour les IMUs, tracer les 4 composantes du quaternion
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        quat_data = [q[i_quat] for q in data_to_plot]
                        plot_widget.plot(quat_data, pen=pg.mkPen(['r', 'g', 'b', 'y'][i_quat], width=2), 
                                       name=axis_label)
                else:
                    # Pour EMG et pMMG, tracer directement les données
                    plot_widget.plot(data_to_plot, pen=pg.mkPen('b', width=2))
                
                self.highlight_sensor_item(sensor_name_base)

    def create_individual_plot(self, sensor_name_full, sensor_name_base, is_group_mode_imu=False):
        """Crée un graphique individuel pour un capteur, crée une seule fois le PlotCurveItem."""
        if sensor_name_base in self.plots:
            return
        plot_widget = pg.PlotWidget(title=sensor_name_full)
        plot_widget.setBackground('#1e1e1e')
        plot_widget.getAxis('left').setTextPen('white')
        plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
        self.middle_layout.addWidget(plot_widget)
        self.plots[sensor_name_base] = plot_widget

        if sensor_name_base.startswith("IMU"):
            for j, axis_l in enumerate(['w', 'x', 'y', 'z']):
                key = f"{sensor_name_base}_{axis_l}"
                self.backend.plot_data[key] = np.zeros(100)
                curve = plot_widget.plot(
                    self.backend.plot_data[key],
                    pen=pg.mkPen(['r', 'g', 'b', 'y'][j], width=2),
                    name=axis_l
                )
                self.curves[key] = curve
        else:
            self.backend.plot_data[sensor_name_base] = np.zeros(100)
            curve = plot_widget.plot(
                self.backend.plot_data[sensor_name_base],
                pen=pg.mkPen('b', width=2)
            )
            self.curves[sensor_name_base] = curve

        self.highlight_sensor_item(sensor_name_base)
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
        self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
        self.highlight_sensor_item(sensor_name_full.split()[0])

    def remove_sensor_plot(self, sensor_name_base):
        """Supprime un graphique individuel pour un capteur."""
        if sensor_name_base in self.plots:
            plot_widget = self.plots.pop(sensor_name_base)
            plot_widget.setParent(None)
            plot_widget.deleteLater()
            if sensor_name_base.startswith("IMU"):
                for axis_l_rem in ['w', 'x', 'y', 'z']:
                    self.backend.plot_data.pop(f"{sensor_name_base}_{axis_l_rem}", None)
            else:
                self.backend.plot_data.pop(sensor_name_base, None)
            self.unhighlight_sensor_item(sensor_name_base)
        for key in list(self.curves):
            if key.startswith(sensor_name_base):
                self.curves.pop(key).clear()

    def remove_sensor_curve_from_group_plot(self, sensor_name_full, sensor_group_type):
        """Supprime une courbe d'un capteur spécifique d'un graphique de groupe."""
        if sensor_group_type in self.group_plots and sensor_group_type in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_group_type].pop(sensor_name_full, None)
            self.unhighlight_sensor_item(sensor_name_full.split()[0])
        if sensor_name_full in self.group_curves:
            self.group_curves.pop(sensor_name_full).clear()

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    
    dashboard.show()
    sys.exit(app.exec_())
