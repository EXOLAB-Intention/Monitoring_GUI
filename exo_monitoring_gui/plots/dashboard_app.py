import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QMenuBar, QComboBox, QMessageBox, QRadioButton, QButtonGroup, QGroupBox, QTableWidget, QTableWidgetItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush, QCursor  # QCursor should be imported from QtGui
import pyqtgraph as pg

# Add import for model_3d_viewer and mapping dialog
from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog

# Add parent directory of data_generator to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_generator.sensor_simulator import SensorSimulator

class DashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1600, 900)
        self.setMinimumSize(1400, 800)
        self.setStyleSheet("background-color: white; color: black;")

        self.simulator = SensorSimulator()

        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(40)  # Update data every 40 ms

    def init_ui(self):
        # Menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet("background-color: white; color: black;")
        file_menu = menubar.addMenu('File')
        edit_menu = menubar.addMenu('Edit')
        options_menu = menubar.addMenu('Options')

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

        # Connected Systems Panel (left)
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

        # Organize sensors by sub-groups
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
                sensor_item.setForeground(0, QBrush(QColor("gray")))  # Gray for disconnected
                sensor_item.setHidden(False)  # Displayed by default
                group_item.addChild(sensor_item)
            group_item.setExpanded(True)  # Open dropdown by default

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

        # Display mode selection
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

        # Graphics / Visual Zone (center)
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout()
        self.middle_placeholder.setLayout(self.middle_layout)
        middle_panel = QVBoxLayout()
        middle_panel.addWidget(self.middle_placeholder)

        # 3D Perspective (right)
        right_panel = QVBoxLayout()

        # 3D section title
        label_3d_title = QLabel("3D Perspective")
        label_3d_title.setAlignment(Qt.AlignCenter)
        label_3d_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_panel.addWidget(label_3d_title)

        # Replace static label with 3D widget
        self.model_3d_widget = Model3DWidget()
        right_panel.addWidget(self.model_3d_widget, stretch=3)

        # Add button to control animation
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        right_panel.addWidget(self.animate_button)

        # Add "Configure Sensor Mapping" button to bottom right
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.setStyleSheet("font-size: 14px; padding: 8px 20px;")
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        right_panel.addWidget(self.config_button)

        # Add left/center/right panels
        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(middle_panel, stretch=2)
        content_layout.addLayout(right_panel, stretch=1)

        # Footer
        footer_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.record_button = QPushButton("Record Start")
        self.record_button.clicked.connect(self.show_sensors)

        for btn in (self.connect_button, self.record_button):
            btn.setStyleSheet("font-size: 14px; padding: 8px 20px;")
            footer_layout.addWidget(btn)

        main_layout.addLayout(footer_layout)

        # Initialize graphs
        self.plots = {}
        self.plot_data = {}
        self.highlighted_sensors = set()
        self.group_plots = {}
        self.group_plot_data = {}

    def show_sensors(self):
        # Show and connect sensors
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_item.setHidden(False)
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Green for connected

        # Create group plots if mode is "Plots by sensor groups"
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()

    def create_group_plots(self):
        # Create group plots for EMG, IMU, pMMG
        for group in ["EMG", "IMU", "pMMG"]:
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
        # Update Matched Part options based on Kinematic Model selection
        self.matched_part_combo.clear()
        if text == "Upper body w/o head":
            self.matched_part_combo.addItems(["Pectorals", "Deltoid", "Biceps", "Forearm", "Trapezius", "Latissimus Dorsi"])
        elif text == "Upper body w/ head":
            self.matched_part_combo.addItems(["Head", "Pectorals", "Deltoid", "Biceps", "Forearm", "Trapezius", "Latissimus Dorsi"])
        elif text == "Lower body":
            self.matched_part_combo.addItems(["Quadriceps", "Hamstrings", "Calves", "Gluteus"])

    def update_matched_sensors(self, text):
        if not text:
            print("No matched part selected.")
            return

        self.matched_sensors_combo.clear()
        sensors = ["EMG1", "EMG2", "EMG3", "EMG4", "EMG5", "EMG6", "EMG7", "EMG8",
                   "IMU1", "IMU2", "IMU3", "IMU4", "IMU5", "IMU6", "IMU7", "IMU8",
                   "pMMG1", "pMMG2", "pMMG3", "pMMG4", "pMMG5", "pMMG6", "pMMG7", "pMMG8"]
        self.matched_sensors_combo.addItems(sensors)
        print(f"Matched sensors updated for part: {text}")

    def update_sensor_label(self, text):
        # Update sensor label with selected Matched Part
        self.selected_sensor = text

    def confirm_selection(self):
        # Confirm selection and update sensor label
        if hasattr(self, 'selected_sensor') and self.selected_sensor and self.matched_part_combo.currentText():
            for i in range(self.connected_systems.topLevelItemCount()):
                group_item = self.connected_systems.topLevelItem(i)
                for j in range(group_item.childCount()):
                    sensor_item = group_item.child(j)
                    if sensor_item.text(0).startswith(self.selected_sensor):
                        matched_part = self.matched_part_combo.currentText()
                        sensor_item.setText(0, f"{self.selected_sensor} ({matched_part})")

    def reset_sensor_mappings(self):
        """Reset sensor-joint associations to defaults."""
        default_mappings = {
            1: 'torso',
            2: 'left_elbow',
            3: 'right_elbow',
            4: 'left_knee',
            5: 'right_knee',
            6: 'head'
        }
        
        # Apply default mappings
        for imu_id, joint in default_mappings.items():
            self.model_3d_widget.map_imu_to_body_part(imu_id, joint)
            self.mapping_table.setItem(imu_id-1, 1, QTableWidgetItem(self._convert_model_part_to_ui(joint)))
        
        print("Sensor-joint associations reset")

    def on_mapping_clicked(self, item):
        """Handle click on mapping table item."""
        row = item.row()
        imu_id = row + 1  # IMU IDs start at 1
        
        # Get list of available joints
        available_joints = self.model_3d_widget.get_available_body_parts()
        
        # Create context menu with joint list
        menu = QMenu(self)
        
        for joint in available_joints:
            # Convert technical name to readable name
            ui_joint_name = self._convert_model_part_to_ui(joint)
            action = QAction(ui_joint_name, self)
            # Store data needed for mapping
            action.setData({'imu_id': imu_id, 'joint': joint})
            menu.addAction(action)
        
        # Connect triggered signal to mapping method
        menu.triggered.connect(self.map_sensor_to_joint)
        
        # Show menu at cursor position
        menu.exec_(QCursor.pos())

    def map_sensor_to_joint(self, action):
        """Map an IMU sensor to a joint."""
        data = action.data()
        imu_id = data['imu_id']
        joint = data['joint']
        
        success = self.model_3d_widget.map_imu_to_body_part(imu_id, joint)
        if success:
            # Update item in table
            self.mapping_table.setItem(imu_id-1, 1, QTableWidgetItem(self._convert_model_part_to_ui(joint)))
            print(f"IMU{imu_id} has been mapped to {joint}")
        else:
            print(f"Failed to map IMU{imu_id} to {joint}")

    def on_joint_clicked(self, joint_name):
        """Handle click on a joint in the 3D model."""
        # Create context menu to select IMU sensor to map
        menu = QMenu(self)
        menu.setWindowTitle(f"Map sensor to {self._convert_model_part_to_ui(joint_name)}")
        
        for i in range(1, 7):  # 6 IMUs
            action = QAction(f"IMU{i}", self)
            action.setData({'imu_id': i, 'joint': joint_name})
            menu.addAction(action)
        
        menu.triggered.connect(self.map_sensor_to_joint)
        menu.exec_(QCursor.pos())

    def on_sensor_clicked(self, item, column):
        # Check if sensor is connected
        if item.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Error", "The sensor is not connected. Please connect the sensor first.")
            return

        sensor_name = item.text(0).split()[0]  # Extract sensor name
        if sensor_name in self.plots or sensor_name in self.highlighted_sensors:
            # Deselect sensor
            self.remove_sensor_plot(sensor_name)
        else:
            self.plot_sensor_data(item.text(0))

    def plot_sensor_data(self, sensor_name):
        # Add sensor curve to group chart
        if self.group_sensor_mode.isChecked():
            sensor_group = sensor_name.split()[0][:-1]
            if sensor_group in self.group_plots:
                if sensor_name not in self.group_plot_data[sensor_group]:
                    self.group_plot_data[sensor_group][sensor_name] = np.zeros(100)
                    if sensor_name.startswith("IMU"):
                        for axis in ['w', 'x', 'y', 'z']:
                            self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"] = np.zeros(100)

                # Highlight selected sensor
                self.highlight_sensor(sensor_name.split()[0])
        else:
            # Create new chart for selected sensor
            plot_widget = pg.PlotWidget(title=sensor_name)
            plot_widget.setBackground('#1e1e1e')
            plot_widget.getAxis('left').setTextPen('white')
            plot_widget.getAxis('bottom').setTextPen('white')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setTitle(sensor_name, color='white', size='14pt')

            # Add chart to "2D Plots" section
            self.middle_layout.addWidget(plot_widget)

            # Store chart and data
            self.plots[sensor_name.split()[0]] = plot_widget
            self.plot_data[sensor_name.split()[0]] = np.zeros(100)

            # Highlight selected sensor
            self.highlight_sensor(sensor_name.split()[0])

    def remove_sensor_plot(self, sensor_name):
        # Remove sensor chart from "2D Plots" section
        if sensor_name in self.plots:
            plot_widget = self.plots.pop(sensor_name)
            plot_widget.setParent(None)
            plot_widget.deleteLater()

            # Remove sensor highlight
            self.unhighlight_sensor(sensor_name)
        else:
            sensor_group = sensor_name.split()[0][:-1]
            if sensor_group in self.group_plots:
                if sensor_name in self.group_plot_data[sensor_group]:
                    self.group_plot_data[sensor_group].pop(sensor_name, None)
                    if sensor_name.startswith("IMU"):
                        for axis in ['w', 'x', 'y', 'z']:
                            self.group_plot_data[sensor_group].pop(f"{sensor_name}_{axis}", None)

            # Remove sensor highlight
            self.unhighlight_sensor(sensor_name)

    def highlight_sensor(self, sensor_name):
        # Highlight selected sensor
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("lightblue")))
                    self.highlighted_sensors.add(sensor_name)

    def unhighlight_sensor(self, sensor_name):
        # Remove sensor highlight
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("white")))
                    self.highlighted_sensors.discard(sensor_name)

    def update_data(self):
        # Update chart data in real time
        packet = self.simulator.generate_packet()
        
        # Update 3D model with IMU data
        if "IMU" in packet:
            for i, quaternion in enumerate(packet["IMU"]):
                imu_id = i + 1  # IMU IDs start at 1
                if imu_id <= 6:  # We only use 6 IMUs in our mapping
                    self.model_3d_widget.apply_imu_data(imu_id, quaternion)
        
        for sensor_name, plot_widget in self.plots.items():
            if sensor_name.startswith("EMG"):
                index = int(sensor_name[3]) - 1
                self.plot_data[sensor_name] = np.roll(self.plot_data[sensor_name], -1)
                self.plot_data[sensor_name][-1] = packet["EMG"][index]
                plot_widget.plot(self.plot_data[sensor_name], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("pMMG"):
                index = int(sensor_name[4]) - 1
                self.plot_data[sensor_name] = np.roll(self.plot_data[sensor_name], -1)
                self.plot_data[sensor_name][-1] = packet["pMMG"][index]
                plot_widget.plot(self.plot_data[sensor_name], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("IMU"):
                index = int(sensor_name[3]) - 1
                quaternion = packet["IMU"][index]
                plot_widget.clear()
                for i, axis in enumerate(['w', 'x', 'y', 'z']):
                    self.plot_data[f"{sensor_name}_{axis}"] = np.roll(self.plot_data.get(f"{sensor_name}_{axis}", np.zeros(100)), -1)
                    self.plot_data[f"{sensor_name}_{axis}"][-1] = quaternion[i]
                    plot_widget.plot(self.plot_data[f"{sensor_name}_{axis}"], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)

                plot_widget.addLegend()

        for sensor_group, plot_widget in self.group_plots.items():
            plot_widget.clear()
            for sensor_name, data in self.group_plot_data[sensor_group].items():
                if sensor_name.startswith("IMU"):
                    index = int(sensor_name[3]) - 1
                    quaternion = packet["IMU"][index]
                    for i, axis in enumerate(['w', 'x', 'y', 'z']):
                        self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"] = np.roll(self.group_plot_data[sensor_group].get(f"{sensor_name}_{axis}", np.zeros(100)), -1)
                        self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"][-1] = quaternion[i]
                        plot_widget.plot(self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=f"{sensor_name}_{axis}")
                else:
                    if sensor_name.startswith("EMG"):
                        index = int(sensor_name[3]) - 1
                        self.group_plot_data[sensor_group][sensor_name] = np.roll(self.group_plot_data[sensor_group][sensor_name], -1)
                        self.group_plot_data[sensor_group][sensor_name][-1] = packet["EMG"][index]
                    elif sensor_name.startswith("pMMG"):
                        index = int(sensor_name[4]) - 1
                        self.group_plot_data[sensor_group][sensor_name] = np.roll(self.group_plot_data[sensor_group][sensor_name], -1)
                        self.group_plot_data[sensor_group][sensor_name][-1] = packet["pMMG"][index]

                    plot_widget.plot(self.group_plot_data[sensor_group][sensor_name], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'k', 'w'][int(sensor_name[-1]) - 1], width=2), name=sensor_name)

            plot_widget.addLegend()

    def update_3d_model(self, rotation_x, rotation_y, rotation_z):
        """Updates the 3D model rotation."""
        try:
            self.model_3d_widget.update_rotation(rotation_x, rotation_y, rotation_z)
        except Exception as e:
            print(f"Error updating 3D model: {e}")

    def toggle_animation(self):
        """Toggle stickman walking animation."""
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")

    def open_sensor_mapping_dialog(self):
        """Open sensor configuration dialog"""
        # Get current mappings
        current_mappings = {
            'EMG': {},  # TODO: Store EMG mappings
            'IMU': self.model_3d_widget.get_current_mappings(),
            'pMMG': {}  # TODO: Store pMMG mappings
        }
        
        dialog = SensorMappingDialog(None, current_mappings)
        dialog.exec_()

    def update_sensor_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        """Update sensor mappings after dialog closes"""
        # Update IMU mappings
        for imu_id, body_part in imu_mappings.items():
            self.model_3d_widget.map_imu_to_body_part(imu_id, body_part)
            
        # Update mapping display table
        self.mapping_table.clearContents()
        for imu_id, body_part in imu_mappings.items():
            self.mapping_table.setItem(imu_id-1, 0, QTableWidgetItem(f"IMU{imu_id}"))
            self.mapping_table.setItem(imu_id-1, 1, QTableWidgetItem(self._convert_model_part_to_ui(body_part)))
            
        print("Sensor mappings updated")
        
        # TODO: Handle EMG and pMMG mappings when implemented

    def _convert_model_part_to_ui(self, model_part):
        """Convert model part names to more readable UI names."""
        mapping = {
            'head': 'Head',
            'neck': 'Neck',
            'torso': 'Torso',
            'left_shoulder': 'Left Shoulder',
            'right_shoulder': 'Right Shoulder',
            'left_elbow': 'Left Elbow',
            'right_elbow': 'Right Elbow',
            'left_hand': 'Left Hand',
            'right_hand': 'Right Hand',
            'hip': 'Hip',
            'left_knee': 'Left Knee',
            'right_knee': 'Right Knee',
            'left_foot': 'Left Foot',
            'right_foot': 'Right Foot'
        }
        return mapping.get(model_part, model_part)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    dashboard.show()
    sys.exit(app.exec_())
