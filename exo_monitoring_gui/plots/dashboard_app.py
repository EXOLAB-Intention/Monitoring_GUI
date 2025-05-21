'''
Regler le probleme des capteur IMU qui ne saffiche pas dans le 2D Plot apres avoir appuyé sur record stop et en etant dans le mode plot par groupe de capteur
'''
import sys
import os
import numpy as np # Gardé pour np.zeros, np.roll
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox, 
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer # QThread, pyqtSignal sont dans le back
from PyQt5.QtGui import QColor, QBrush # QCursor n'est plus utilisé directement ici
import pyqtgraph as pg

# Ajouter le chemin du répertoire parent et du dossier back
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'back')))

from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog
# Importer la logique depuis le fichier back
from .back.dashboard_app_back import DashboardAppBack # EthernetServerThread, ClientInitThread ne sont plus utilisés directement ici


class DashboardApp(QMainWindow):
    def __init__(self):
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

        self.backend = DashboardAppBack(self)

        self.init_ui()
        self.backend.load_mappings()
        
        self.main_bar_re = self.some_method()
        self.main_bar_re._create_menubar()
    
    def some_method(self):
        from utils.Menu_bar import MainBar
        return MainBar(self)
    
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

        sensors = ["EMG Data", "IMU Data", "pMMG Data"]
        for sensor_group in sensors:
            group_item = QTreeWidgetItem([sensor_group])
            self.connected_systems.addTopLevelItem(group_item)
            num_sensors = 6 if sensor_group == "IMU Data" else 8
            for i_sensor_init in range(1, num_sensors + 1):
                sensor_item = QTreeWidgetItem([f"{sensor_group[:-5]}{i_sensor_init}"])
                sensor_item.setForeground(0, QBrush(QColor("gray")))
                sensor_item.setHidden(False)
                group_item.addChild(sensor_item)
            group_item.setExpanded(True)

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
        right_panel.addWidget(self.config_button)
        self.default_config_button = QPushButton("Set Up Default Assignments")
        # Styles des boutons (chaînes multilignes échappées)
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
        for i_group_item in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_group_item)
            sensor_type_prefix = group_item.text(0).split()[0][:-5]
            num_sensors_in_group = 6 if sensor_type_prefix == "IMU" else 8
            for j_sensor_item in range(group_item.childCount()):
                sensor_item = group_item.child(j_sensor_item)
                sensor_item.setText(0, f"{sensor_type_prefix}{j_sensor_item+1}")
                sensor_item.setForeground(0, QBrush(QColor("gray")))
                sensor_item.setHidden(False)

    def update_sensor_tree_from_config(self, sensor_config):
        if not sensor_config: return

        for i_group_idx in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_group_idx)
            for j_sensor_idx in range(group_item.childCount()):
                group_item.child(j_sensor_idx).setHidden(True)

        emg_group_item = self.find_sensor_group_item("EMG Data")
        if emg_group_item:
            num_emg_configured = len(sensor_config.get('emg_ids', []))
            for idx in range(min(num_emg_configured, emg_group_item.childCount())):
                sensor_id = sensor_config['emg_ids'][idx]
                sensor_item = emg_group_item.child(idx)
                sensor_item.setText(0, f"EMG{sensor_id}")
                sensor_item.setForeground(0, QBrush(QColor("green")))
                sensor_item.setHidden(False)

        imu_group_item = self.find_sensor_group_item("IMU Data")
        if imu_group_item:
            num_imu_configured = len(sensor_config.get('imu_ids', []))
            while imu_group_item.childCount() < num_imu_configured:
                 QTreeWidgetItem(imu_group_item)
            for idx in range(imu_group_item.childCount()):
                imu_group_item.child(idx).setHidden(True)
            for idx in range(num_imu_configured):
                sensor_id = sensor_config['imu_ids'][idx]
                sensor_item = imu_group_item.child(idx)
                sensor_item.setText(0, f"IMU{sensor_id}")
                sensor_item.setForeground(0, QBrush(QColor("green")))
                sensor_item.setHidden(False)

        pmmg_group_item = self.find_sensor_group_item("pMMG Data")
        if pmmg_group_item:
            num_pmmg_configured = len(sensor_config.get('pmmg_ids', []))
            for idx in range(min(num_pmmg_configured, pmmg_group_item.childCount())):
                sensor_id = sensor_config['pmmg_ids'][idx]
                sensor_item = pmmg_group_item.child(idx)
                sensor_item.setText(0, f"pMMG{sensor_id}")
                sensor_item.setForeground(0, QBrush(QColor("green")))
                sensor_item.setHidden(False)
        
        self.refresh_sensor_tree_with_mappings(
            self.backend.emg_mappings, 
            self.backend.pmmg_mappings
        )
        if self.group_sensor_mode.isChecked() and not self.group_plots:
            self.create_group_plots()

    def find_sensor_group_item(self, group_name):
        for i_find_group in range(self.connected_systems.topLevelItemCount()):
            item = self.connected_systems.topLevelItem(i_find_group)
            if item.text(0) == group_name: return item
        return None

    def create_group_plots(self):
        if not self.group_plots:
            if self.backend.sensor_config and self.backend.sensor_config.get('emg_ids'):
                plot_widget_emg = pg.PlotWidget(title="EMG Group")
                plot_widget_emg.setBackground('#1e1e1e')
                plot_widget_emg.getAxis('left').setTextPen('white')
                plot_widget_emg.getAxis('bottom').setTextPen('white')
                plot_widget_emg.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_emg.setTitle("EMG Group", color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget_emg)
                self.group_plots["EMG"] = plot_widget_emg
                self.backend.group_plot_data["EMG"] = {}

            if self.backend.sensor_config and self.backend.sensor_config.get('pmmg_ids'):
                plot_widget_pmmg = pg.PlotWidget(title="pMMG Group")
                plot_widget_pmmg.setBackground('#1e1e1e')
                plot_widget_pmmg.getAxis('left').setTextPen('white')
                plot_widget_pmmg.getAxis('bottom').setTextPen('white')
                plot_widget_pmmg.showGrid(x=True, y=True, alpha=0.3)
                plot_widget_pmmg.setTitle("pMMG Group", color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget_pmmg)
                self.group_plots["pMMG"] = plot_widget_pmmg
                self.backend.group_plot_data["pMMG"] = {}

    def on_sensor_clicked(self, item_clicked, column):
        if item_clicked.childCount() > 0: return
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
        recorded_data = self.backend.recorded_data
        
        # Check if specific sensor type has any data
        has_data = False
        sensor_prefix_short = sensor_name_base[:3] # EMG, IMU
        sensor_prefix_long = sensor_name_base[:4] # pMMG
        if sensor_prefix_short in recorded_data and recorded_data[sensor_prefix_short] and recorded_data[sensor_prefix_short][0]:
            has_data = True
        elif sensor_prefix_long in recorded_data and recorded_data[sensor_prefix_long] and recorded_data[sensor_prefix_long][0]:
            has_data = True

        if not has_data:
            QMessageBox.information(self, "No Data", f"No recorded data available for {sensor_name_base}.")
            return

        if self.group_sensor_mode.isChecked() and not sensor_name_base.startswith("IMU"):
            sensor_group_type = "EMG" if sensor_name_base.startswith("EMG") else "pMMG"
            if sensor_group_type not in self.group_plots: self.create_group_plots()
            plot_widget = self.group_plots.get(sensor_group_type)
            if not plot_widget: return

            is_already_plotted = any(hasattr(p_item, 'name') and p_item.name() == sensor_name_full for p_item in plot_widget.listDataItems())
            if is_already_plotted: return

            sensor_id_str = ''.join(filter(str.isdigit, sensor_name_base))
            if not sensor_id_str: return
            sensor_idx = int(sensor_id_str) - 1

            data_array_key = "EMG" if sensor_group_type == "EMG" else "pMMG"
            if sensor_idx < len(recorded_data[data_array_key]):
                data_to_plot = recorded_data[data_array_key][sensor_idx]
                if data_to_plot:
                    color_idx = sensor_idx % 8
                    plot_widget.plot(data_to_plot, pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w'][color_idx], width=2), name=sensor_name_full)
            if plot_widget.legend is None: plot_widget.addLegend()
            self.highlight_sensor_item(sensor_name_base)
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

            sensor_id_str = ''.join(filter(str.isdigit, sensor_name_base))
            if not sensor_id_str: return
            sensor_idx = int(sensor_id_str) - 1

            if sensor_name_base.startswith("EMG") and sensor_idx < len(recorded_data["EMG"]):
                if recorded_data["EMG"][sensor_idx]: plot_widget.plot(recorded_data["EMG"][sensor_idx], pen=pg.mkPen('b', width=2))
            elif sensor_name_base.startswith("pMMG") and sensor_idx < len(recorded_data["pMMG"]):
                if recorded_data["pMMG"][sensor_idx]: plot_widget.plot(recorded_data["pMMG"][sensor_idx], pen=pg.mkPen('b', width=2))
            elif sensor_name_base.startswith("IMU") and sensor_idx < len(recorded_data["IMU"]):
                quaternion_data = recorded_data["IMU"][sensor_idx]
                if quaternion_data:
                    for i_quat, axis_label in enumerate(['w', 'x', 'y', 'z']):
                        plot_widget.plot([q[i_quat] for q in quaternion_data], pen=pg.mkPen(['r', 'g', 'b', 'y'][i_quat], width=2), name=axis_label)
                    if plot_widget.legend is None: plot_widget.addLegend()
            self.highlight_sensor_item(sensor_name_base)

    def create_individual_plot(self, sensor_name_full, sensor_name_base, is_group_mode_imu=False):
        if sensor_name_base in self.plots: return
        plot_widget = pg.PlotWidget(title=sensor_name_full)
        plot_widget.setBackground('#1e1e1e'); plot_widget.getAxis('left').setTextPen('white'); plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3); plot_widget.setTitle(sensor_name_full, color='white', size='14pt')
        self.middle_layout.addWidget(plot_widget)
        self.plots[sensor_name_base] = plot_widget
        
        if sensor_name_base.startswith("IMU"):
            for axis_l in ['w', 'x', 'y', 'z']:
                self.backend.plot_data[f"{sensor_name_base}_{axis_l}"] = np.zeros(100)
        else:
            self.backend.plot_data[sensor_name_base] = np.zeros(100)
        self.highlight_sensor_item(sensor_name_base)
        if is_group_mode_imu: self.highlighted_sensors.add(sensor_name_base)

    def add_sensor_curve_to_group_plot(self, sensor_name_full, sensor_group_type):
        if sensor_group_type not in self.group_plots:
            self.create_group_plots()
            if sensor_group_type not in self.group_plots: return

        if sensor_group_type not in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_group_type] = {}
        self.backend.group_plot_data[sensor_group_type][sensor_name_full] = np.zeros(100)
        self.highlight_sensor_item(sensor_name_full.split()[0])

    def remove_sensor_plot(self, sensor_name_base):
        if sensor_name_base in self.plots:
            plot_widget = self.plots.pop(sensor_name_base)
            plot_widget.setParent(None); plot_widget.deleteLater()
            if sensor_name_base.startswith("IMU"):
                for axis_l_rem in ['w', 'x', 'y', 'z']:
                    self.backend.plot_data.pop(f"{sensor_name_base}_{axis_l_rem}", None)
            else:
                self.backend.plot_data.pop(sensor_name_base, None)
            self.unhighlight_sensor_item(sensor_name_base)

    def remove_sensor_curve_from_group_plot(self, sensor_name_full, sensor_group_type):
        if sensor_group_type in self.group_plots and sensor_group_type in self.backend.group_plot_data:
            self.backend.group_plot_data[sensor_group_type].pop(sensor_name_full, None)
            self.unhighlight_sensor_item(sensor_name_full.split()[0])

    def highlight_sensor_item(self, sensor_name_base):
        for i_hl_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_hl_group)
            for j_hl_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_hl_sensor)
                if sensor_item.text(0).startswith(sensor_name_base):
                    sensor_item.setBackground(0, QBrush(QColor("lightblue")))
                    self.highlighted_sensors.add(sensor_name_base)

    def unhighlight_sensor_item(self, sensor_name_base):
        for i_uhl_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_uhl_group)
            for j_uhl_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_uhl_sensor)
                if sensor_item.text(0).startswith(sensor_name_base):
                    sensor_item.setBackground(0, QBrush(QColor("white")))
                    self.highlighted_sensors.discard(sensor_name_base)

    def update_live_plots(self, packet):
        if not self.backend.recording or not self.backend.sensor_config: return

        for sensor_name_base, plot_widget in self.plots.items():
            sensor_type = ''.join(filter(str.isalpha, sensor_name_base))
            sensor_id_str = ''.join(filter(str.isdigit, sensor_name_base))
            if not sensor_id_str: continue
            sensor_id = int(sensor_id_str)

            cfg = self.backend.sensor_config
            if sensor_type == "EMG" and sensor_id in cfg.get('emg_ids', []):
                data_idx = cfg['emg_ids'].index(sensor_id)
                if data_idx < len(packet.get('emg',[])):
                    val = packet['emg'][data_idx]
                    p_data = self.backend.plot_data.get(sensor_name_base)
                    if p_data is not None:
                        p_data = np.roll(p_data, -1); p_data[-1] = val
                        self.backend.plot_data[sensor_name_base] = p_data
                        plot_widget.plot(p_data, clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_type == "pMMG" and sensor_id in cfg.get('pmmg_ids', []):
                data_idx = cfg['pmmg_ids'].index(sensor_id)
                if data_idx < len(packet.get('pmmg',[])):
                    val = packet['pmmg'][data_idx]
                    p_data = self.backend.plot_data.get(sensor_name_base)
                    if p_data is not None:
                        p_data = np.roll(p_data, -1); p_data[-1] = val
                        self.backend.plot_data[sensor_name_base] = p_data
                        plot_widget.plot(p_data, clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_type == "IMU" and sensor_id in cfg.get('imu_ids', []):
                data_idx = cfg['imu_ids'].index(sensor_id)
                if data_idx < len(packet.get('imu',[])):
                    quat = packet['imu'][data_idx]
                    if self.backend._is_valid_quaternion(quat):
                        plot_widget.clear()
                        for i_ax, ax_lab in enumerate(['w', 'x', 'y', 'z']):
                            key = f"{sensor_name_base}_{ax_lab}"
                            ax_data = self.backend.plot_data.get(key)
                            if ax_data is not None:
                                ax_data = np.roll(ax_data, -1); ax_data[-1] = quat[i_ax]
                                self.backend.plot_data[key] = ax_data
                                plot_widget.plot(ax_data, pen=pg.mkPen(['r', 'g', 'b', 'y'][i_ax], width=2), name=ax_lab)
                        if plot_widget.legend is None: plot_widget.addLegend()
        
        if self.group_sensor_mode.isChecked():
            for group_type, plot_widget in self.group_plots.items():
                plot_widget.clear()
                if group_type in self.backend.group_plot_data:
                    cfg = self.backend.sensor_config
                    colors = ['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'w']
                    for s_name_full, live_data_arr in self.backend.group_plot_data[group_type].items():
                        s_base = s_name_full.split()[0]
                        s_type = ''.join(filter(str.isalpha, s_base))
                        s_id_str = ''.join(filter(str.isdigit, s_base))
                        if not s_id_str: continue
                        s_id = int(s_id_str)
                        val_plot = None
                        id_list_key, packet_data_key = ('emg_ids', 'emg') if s_type == "EMG" and group_type == "EMG" else (('pmmg_ids', 'pmmg') if s_type == "pMMG" and group_type == "pMMG" else (None,None))
                        if id_list_key and s_id in cfg.get(id_list_key,[]):
                            d_idx = cfg[id_list_key].index(s_id)
                            if d_idx < len(packet.get(packet_data_key,[])):
                                val_plot = packet[packet_data_key][d_idx]
                        if val_plot is not None:
                            live_data_arr = np.roll(live_data_arr, -1); live_data_arr[-1] = val_plot
                            self.backend.group_plot_data[group_type][s_name_full] = live_data_arr
                            plot_widget.plot(live_data_arr, pen=pg.mkPen(colors[(s_id -1) % 8], width=2), name=s_name_full)
                if plot_widget.legend is None and self.backend.group_plot_data.get(group_type): plot_widget.addLegend()

    def on_display_mode_changed(self, button_clicked=None):
        # button_clicked n'est pas toujours fourni, se fier à isChecked()
        is_now_single_mode = self.single_sensor_mode.isChecked()
        is_now_group_mode = self.group_sensor_mode.isChecked()

        if self.backend.recording:
            QMessageBox.warning(self, 'Warning', "You cannot change display mode while recording.")
            # Revert to previous state if a change was attempted
            if button_clicked == self.single_sensor_mode and not is_now_single_mode: # tried to switch to group
                 self.single_sensor_mode.setChecked(True)
            elif button_clicked == self.group_sensor_mode and not is_now_group_mode: # tried to switch to single
                 self.group_sensor_mode.setChecked(True)
            return

        reply = QMessageBox.question(self, 'Change Mode', "Changing display mode will clear current plots. Continue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.update_display_mode_ui()
        else:
            # Revert selection if user cancelled
            if is_now_single_mode and button_clicked == self.group_sensor_mode: # Was single, clicked group, cancelled -> stay single
                self.single_sensor_mode.setChecked(True)
            elif is_now_group_mode and button_clicked == self.single_sensor_mode: # Was group, clicked single, cancelled -> stay group
                self.group_sensor_mode.setChecked(True)

    def update_display_mode_ui(self):
        for sb_name in list(self.plots.keys()): self.remove_sensor_plot(sb_name)
        self.plots.clear()
        for grp_type in list(self.group_plots.keys()):
            plot_w = self.group_plots.pop(grp_type); plot_w.setParent(None); plot_w.deleteLater()
        self.group_plots.clear()
        if "EMG" in self.backend.group_plot_data: self.backend.group_plot_data["EMG"].clear()
        if "pMMG" in self.backend.group_plot_data: self.backend.group_plot_data["pMMG"].clear()
        for sb_name_hl in list(self.highlighted_sensors): self.unhighlight_sensor_item(sb_name_hl)
        self.highlighted_sensors.clear()
        if self.group_sensor_mode.isChecked(): self.create_group_plots()

    def show_recorded_data_on_plots(self, recorded_data):
        self.update_display_mode_ui()
        rec_data = self.backend.recorded_data # Use backend's copy
        has_any_data = False
        for sensor_key in ["EMG", "IMU", "pMMG"]:
            if rec_data.get(sensor_key) and any(rec_data[sensor_key]) and any(d for d in rec_data[sensor_key] if d):
                has_any_data = True
                break
        
        if not has_any_data:
            QMessageBox.warning(self, 'Warning', "No data was recorded.")
            self.record_button.setEnabled(True)
            if self.backend.client_socket: self.connect_button.setText("Disconnect"); self.connect_button.setEnabled(True)
            else: self.connect_button.setText("Connect"); self.connect_button.setEnabled(True)
            return

        if self.backend.sensor_config:
            cfg = self.backend.sensor_config
            for key, id_list_name in [("EMG", 'emg_ids'), ("pMMG", 'pmmg_ids'), ("IMU", 'imu_ids')]:
                for idx, s_id_val in enumerate(cfg.get(id_list_name, [])):
                    if idx < len(rec_data.get(key,[])) and rec_data[key][idx]:
                        s_base_plot = f"{key}{s_id_val}"
                        item_t = self.find_sensor_item_by_base_name(s_base_plot)
                        s_full_plot = item_t.text(0) if item_t else s_base_plot
                        self.plot_recorded_sensor_data(s_full_plot, s_base_plot)

    def find_sensor_item_by_base_name(self, sensor_name_base):
        for i_find_item_group in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i_find_item_group)
            for j_find_item_sensor in range(group_item.childCount()):
                sensor_item = group_item.child(j_find_item_sensor)
                if sensor_item.text(0).startswith(sensor_name_base): return sensor_item
        return None

    def toggle_animation(self):
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")
        anim_style_on = """QPushButton { background-color: #f44336; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #e53935; } QPushButton:pressed { background-color: #d32f2f; }"""
        anim_style_off = """QPushButton { background-color: #2196f3; border: none; border-radius: 6px; padding: 8px 16px; color: white; font-size: 14px; font-weight: 500; text-align: center; min-width: 120px; } QPushButton:hover { background-color: #1e88e5; } QPushButton:pressed { background-color: #1976d2; }"""
        self.animate_button.setStyleSheet(anim_style_on if is_walking else anim_style_off)

    def reset_model_view(self):
        start_rot = (self.model_3d_widget.model_viewer.rotation_x, self.model_3d_widget.model_viewer.rotation_y, self.model_3d_widget.model_viewer.rotation_z)
        self._anim_steps_count = 10 # Use instance var for steps
        if not hasattr(self, '_reset_view_timer_obj'): # Ensure timer is instance variable
            self._reset_view_timer_obj = QTimer(self)
            self._reset_view_timer_obj.timeout.connect(self._animation_step_exec)
        self._animation_step_counter_val = 0
        self._start_rotation_anim_val = start_rot
        if not self._reset_view_timer_obj.isActive(): self._reset_view_timer_obj.start(20)

    def _animation_step_exec(self):
        self._animation_step_counter_val +=1
        prog = self._animation_step_counter_val / self._anim_steps_count
        rx, ry, rz = self._start_rotation_anim_val
        self.model_3d_widget.model_viewer.rotation_x = rx * (1 - prog)
        self.model_3d_widget.model_viewer.rotation_y = ry * (1 - prog)
        self.model_3d_widget.model_viewer.rotation_z = rz * (1 - prog)
        self.model_3d_widget.model_viewer.update()
        if self._animation_step_counter_val >= self._anim_steps_count: self._reset_view_timer_obj.stop()

    def open_sensor_mapping_dialog(self):
        curr_maps = self.backend.get_current_mappings_for_dialog()
        dialog = SensorMappingDialog(self, curr_maps)
        dialog.mappings_updated.connect(self.backend.update_sensor_mappings)
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
        curr_maps_def = self.backend.get_current_mappings_for_dialog()
        dialog_def = SensorMappingDialog(self, curr_maps_def)
        dialog_def.mappings_updated.connect(self.backend.save_as_default_mappings)
        QMessageBox.information(self, "Default Assignments Setup", "Configure sensor mappings...\
These will be saved as default.")
        dialog_def.exec_()

    def apply_imu_mappings(self, imu_mappings_apply):
        for imu_id_apply, body_part_apply in imu_mappings_apply.items():
            self.model_3d_widget.map_imu_to_body_part(int(imu_id_apply), body_part_apply)
        self.refresh_sensor_tree_with_mappings(self.backend.emg_mappings, self.backend.pmmg_mappings)

    def closeEvent(self, event_close):
        self.backend.cleanup_on_close()
        event_close.accept()

    def toggle_motion_prediction(self):
        """Active ou désactive la prédiction intelligente des mouvements."""
        is_enabled = self.model_3d_widget.toggle_motion_prediction()
        self.motion_prediction_button.setText(
            "Disable Smart Movement" if is_enabled else "Enable Smart Movement")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    dashboard.show()
    sys.exit(app.exec_())
