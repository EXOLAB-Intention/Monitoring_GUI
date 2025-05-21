from PyQt5.QtWidgets import (QMainWindow, QPushButton, QLabel, QAction, QFileDialog,
                         QMessageBox, QVBoxLayout, QWidget, QProgressBar, QDialog, QTextEdit, QHBoxLayout, QStackedWidget)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
import h5py
import os
from datetime import datetime
import traceback
from UI.informations import InformationWindow
from utils.hdf5_utils import load_metadata, save_metadata
from utils.Menu_bar import MainBar
from utils.style import _apply_styles
from UI.back.main_window_back import MainAppBack

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialization of state variables
        self.current_subject_file = None
        self.current_trial_data = None
        self.modified = False
        self.plot_widgets = []  # To store references to plot widgets

        # Main window configuration
        self.stack = QStackedWidget()
        self.setWindowTitle("Data Monitoring Software")
        self.setGeometry(50, 50, 1600, 900)  # More reasonable size
        self._setup_ui()
        self.main_app_back = MainAppBack(self)

        # Create an instance of MainBar and pass self (MainApp instance)
        self.main_bar = MainBar(self)

        # Use MainBar to create the menu bar
        self.main_bar._create_menubar()

        _apply_styles(self)

        # Timer for auto-save (every 5 minutes)
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.main_app_back._autosave)
        self.autosave_timer.start(300000)  # 5 minutes in milliseconds

        # Initialize actions
        self.save_subject_action = QAction("Save Subject", self)
        self.save_subject_as_action = QAction("Save Subject As", self)
        self.show_metadata_action = QAction("Show Metadata", self)

    def _setup_ui(self):
        """Configure the main user interface"""
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create welcome screen container
        welcome_container = QWidget()
        welcome_layout = QVBoxLayout(welcome_container)
        welcome_layout.setContentsMargins(50, 50, 50, 50)
        welcome_layout.setSpacing(20)

        # Add logo (if you have one)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        try:
            logo_pixmap = QPixmap("resources/logo.png").scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            welcome_layout.addWidget(logo_label)
        except:
            # If logo image doesn't exist, use a placeholder
            logo_label.setText("💻")
            logo_label.setStyleSheet("font-size: 120px; color: #1976D2;")
            logo_label.setAlignment(Qt.AlignCenter)
            welcome_layout.addWidget(logo_label)

        # Welcome text with large scientific font
        welcome_text = QLabel("START SCREEN")
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 48px;
            font-weight: bold;
            color: #1976D2;
            letter-spacing: 4px;
            margin-top: 20px;
        """)
        welcome_layout.addWidget(welcome_text)

        # Subtitle
        subtitle_text = QLabel("Exoskeleton Monitoring System")
        subtitle_text.setAlignment(Qt.AlignCenter)
        subtitle_text.setStyleSheet("""
            font-family: 'Segoe UI Light', Arial, sans-serif;
            font-size: 24px;
            color: #455A64;
            margin-bottom: 30px;
        """)
        welcome_layout.addWidget(subtitle_text)

        # Quick action buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(20)

        new_subject_btn = QPushButton("New Subject")
        new_subject_btn.clicked.connect(lambda: self.main_bar.create_new_subject())

        load_subject_btn = QPushButton("Load Subject")
        load_subject_btn.clicked.connect(lambda: self.main_bar.load_existing_subject())

        quick_help_btn = QPushButton("Quick Help")
        quick_help_btn.clicked.connect(lambda: self.main_bar.show_about_dialog())

        button_layout.addStretch()
        button_layout.addWidget(new_subject_btn)
        button_layout.addWidget(load_subject_btn)
        button_layout.addWidget(quick_help_btn)
        button_layout.addStretch()

        welcome_layout.addWidget(button_container)
        welcome_layout.addStretch()

        # Add version and copyright
        version_label = QLabel("DATA Monitoring Software v2.5.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            color: #78909C;
        """)
        welcome_layout.addWidget(version_label)

        copyright_label = QLabel("© 2025 Advanced Exoskeleton Research Laboratory")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10px;
            color: #B0BEC5;
        """)
        welcome_layout.addWidget(copyright_label)

        # Add welcome container to main layout
        main_layout.addWidget(welcome_container)

        # Status bar to display information
        self.statusBar().showMessage("Ready")

        # Progress bar for long operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

