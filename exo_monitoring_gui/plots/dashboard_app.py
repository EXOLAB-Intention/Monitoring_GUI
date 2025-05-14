import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QMenuBar, QComboBox, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush
import pyqtgraph as pg

# Ajouter le chemin du répertoire parent de data_generator au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_generator.sensor_simulator import SensorSimulator

class DashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1400, 800)
        self.setStyleSheet("background-color: white; color: black;")

        self.simulator = SensorSimulator()

        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(40)  # Mettre à jour les données toutes les 40 ms

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
        middle_panel = QVBoxLayout()
        middle_panel.addWidget(self.middle_placeholder)

        # 3D Perspective (droite)
        right_panel = QVBoxLayout()
        label_3d = QLabel("3D Perspective")
        label_3d.setAlignment(Qt.AlignCenter)
        label_3d.setStyleSheet("background-color: #f0f0f0; padding: 30px; border: 1px solid #ccc;")
        right_panel.addWidget(label_3d)

        # Kinematic Model ComboBox
        self.kinematic_model_combo = QComboBox()
        self.kinematic_model_combo.addItem("")  # Vide par défaut
        self.kinematic_model_combo.addItems(["Upper body w/o head", "Upper body w/ head", "Lower body"])
        self.kinematic_model_combo.currentTextChanged.connect(self.update_matched_part)

        # Label Kinematic Model
        kinematic_model_layout = QHBoxLayout()
        kinematic_model_layout.addWidget(QLabel("Kinematic Model:"))
        kinematic_model_layout.addWidget(self.kinematic_model_combo)
        right_panel.addLayout(kinematic_model_layout)

        # Matched Part ComboBox
        self.matched_part_combo = QComboBox()
        self.matched_part_combo.currentTextChanged.connect(self.update_matched_sensors)

        # Label Matched Part
        matched_part_layout = QHBoxLayout()
        matched_part_layout.addWidget(QLabel("Matched Part:"))
        matched_part_layout.addWidget(self.matched_part_combo)
        right_panel.addLayout(matched_part_layout)

        # Matched Sensors ComboBox
        self.matched_sensors_combo = QComboBox()
        self.matched_sensors_combo.currentTextChanged.connect(self.update_sensor_label)

        # Label Matched Sensors
        matched_sensors_layout = QHBoxLayout()
        matched_sensors_layout.addWidget(QLabel("Matched Sensors:"))
        matched_sensors_layout.addWidget(self.matched_sensors_combo)
        right_panel.addLayout(matched_sensors_layout)

        # Bouton de Confirmation
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.confirm_selection)
        right_panel.addWidget(self.confirm_button)

        # Ajout des panneaux gauche / centre / droite
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

        # Initialiser les graphiques
        self.plots = {}
        self.plot_data = {}
        self.highlighted_sensors = set()
        self.group_plots = {}
        self.group_plot_data = {}

    def show_sensors(self):
        # Afficher les capteurs et les connecter
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_item.setHidden(False)
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté

        # Créer les graphiques de groupe si le mode est "Graphiques par groupe de capteurs"
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()

    def create_group_plots(self):
        # Créer les graphiques de groupe pour EMG, IMU, pMMG
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
        # Mettre à jour les options de Matched Part en fonction de la sélection de Kinematic Model
        self.matched_part_combo.clear()
        if text == "Upper body w/o head":
            self.matched_part_combo.addItems(["pectorals_L", "Deltoid_L", "Biceps_L", "forearm_L", "dorsalis major_L", "pectorals_R", "Deltoid_R", "Biceps_R", "forearm_R",  "dorsalis major_R"])
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
        # Ajouter la courbe du capteur au graphique de groupe correspondant
        if self.group_sensor_mode.isChecked():
            sensor_group = sensor_name.split()[0][:-1]
            if sensor_group in self.group_plots:
                if sensor_name not in self.group_plot_data[sensor_group]:
                    self.group_plot_data[sensor_group][sensor_name] = np.zeros(100)
                    if sensor_name.startswith("IMU"):
                        for axis in ['w', 'x', 'y', 'z']:
                            self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"] = np.zeros(100)

                # Mettre en surbrillance le capteur sélectionné
                self.highlight_sensor(sensor_name.split()[0])
        else:
            # Créer un nouveau graphique pour le capteur sélectionné
            plot_widget = pg.PlotWidget(title=sensor_name)
            plot_widget.setBackground('#1e1e1e')
            plot_widget.getAxis('left').setTextPen('white')
            plot_widget.getAxis('bottom').setTextPen('white')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setTitle(sensor_name, color='white', size='14pt')

            # Ajouter le graphique à la section "2D Plots"
            self.middle_layout.addWidget(plot_widget)

            # Stocker le graphique et les données
            self.plots[sensor_name.split()[0]] = plot_widget
            self.plot_data[sensor_name.split()[0]] = np.zeros(100)

            # Mettre en surbrillance le capteur sélectionné
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
            sensor_group = sensor_name.split()[0][:-1]
            if sensor_group in self.group_plots:
                if sensor_name in self.group_plot_data[sensor_group]:
                    self.group_plot_data[sensor_group].pop(sensor_name, None)
                    if sensor_name.startswith("IMU"):
                        for axis in ['w', 'x', 'y', 'z']:
                            self.group_plot_data[sensor_group].pop(f"{sensor_name}_{axis}", None)

            # Retirer la surbrillance du capteur
            self.unhighlight_sensor(sensor_name)

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
        packet = self.simulator.generate_packet()
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    dashboard.show()
    sys.exit(app.exec_())
