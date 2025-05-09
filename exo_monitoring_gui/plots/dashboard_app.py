import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QMenuBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush

class DashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Monitoring Software")
        self.showFullScreen()  # Lancer en plein écran
        self.setStyleSheet("background-color: white; color: black;")

        self.init_ui()

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
        title_layout.addWidget(QLabel("Connected Systems"))
        title_layout.addStretch()
        title_layout.addWidget(QLabel("Graphics / Visual Zone"))
        title_layout.addStretch()
        title_layout.addWidget(QLabel("3D Perspective"))
        main_layout.addLayout(title_layout)

        # Main content layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Connected Systems Panel (gauche)
        self.connected_systems = QTreeWidget()
        self.connected_systems.setHeaderHidden(True)
        self.connected_systems.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                font-size: 14px;
            }
        """)

        # Organisation des capteurs par sous-groupes
        sensors = ["EMG Data", "IMU Data", "pMMG Data"]
        for sensor_group in sensors:
            group_item = QTreeWidgetItem([sensor_group])
            self.connected_systems.addTopLevelItem(group_item)
            for i in range(1, 9):
                sensor_item = QTreeWidgetItem([f"{sensor_group[:-5]}{i}"])
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté
                group_item.addChild(sensor_item)

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

        # Graphics / Visual Zone (centre)
        self.middle_placeholder = QLabel("GRAPHICS / VISUAL ZONE")
        self.middle_placeholder.setAlignment(Qt.AlignCenter)
        self.middle_placeholder.setStyleSheet("border: 2px dashed gray; font-size: 16px; padding: 50px;")
        middle_panel = QVBoxLayout()
        middle_panel.addWidget(self.middle_placeholder)

        # 3D Perspective (droite)
        right_panel = QVBoxLayout()
        label_3d = QLabel("3D Perspective")
        label_3d.setAlignment(Qt.AlignCenter)
        label_3d.setStyleSheet("background-color: #f0f0f0; padding: 30px; border: 1px solid #ccc;")
        right_panel.addWidget(label_3d)

        # Buttons under 3D Perspective
        for name in ["Kinematic Model", "Matched Part", "Matched Sensors"]:
            btn = QPushButton(name)
            btn.setEnabled(False)
            btn.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
            right_panel.addWidget(btn)

        # Ajout des panneaux gauche / centre / droite
        content_layout.addLayout(left_panel, 2)
        content_layout.addLayout(middle_panel, 5)
        content_layout.addLayout(right_panel, 3)

        # Footer
        footer_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.record_button = QPushButton("Record Start")
        self.record_button.clicked.connect(self.show_sensors)

        for btn in (self.connect_button, self.record_button):
            btn.setStyleSheet("font-size: 14px; padding: 8px 20px;")
            footer_layout.addWidget(btn)

        main_layout.addLayout(footer_layout)

    def show_sensors(self):
        # Logique pour afficher les capteurs
        pass
