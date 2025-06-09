import sys
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QApplication, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont, QIcon

class CalibrationGuideDialog(QDialog):
    """Dialog to guide users through the T-pose calibration process."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("T-Pose Calibration Guide")
        self.setMinimumSize(600, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Title
        title = QLabel("How to Perform T-Pose Calibration")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Explanation
        explanation = QLabel(
            "T-pose calibration is essential for the 3D model to correctly interpret IMU data.\n"
            "Without calibration, the model may not move correctly or may show incorrect postures."
        )
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        layout.addWidget(explanation)
        
        # Instruction frame
        instruction_frame = QFrame()
        instruction_frame.setFrameShape(QFrame.StyledPanel)
        instruction_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f7ff;
                border-radius: 10px;
                border: 1px solid #ccddf5;
                padding: 15px;
            }
        """)
        
        instruction_layout = QVBoxLayout(instruction_frame)
        
        # Steps
        steps = [
            "1. Make sure all IMU sensors are properly attached and mapped to body parts",
            "2. Stand in a T-pose position: arms straight out to the sides, palms down",
            "3. Keep your back straight and look forward",
            "4. Press the 'T-pose Calibration' button in the main window",
            "5. Remain still in the T-pose position for 3 seconds while calibration completes",
            "6. When calibration is complete, you can move normally"
        ]
        
        for step in steps:
            step_label = QLabel(step)
            step_label.setFont(QFont("Arial", 11))
            step_label.setWordWrap(True)
            instruction_layout.addWidget(step_label)
        
        layout.addWidget(instruction_frame)
        
        # Important notes
        notes = QLabel(
            "Important Notes:\n"
            "• You must calibrate each time you connect sensors\n"
            "• If movement looks incorrect, try resetting and calibrating again\n"
            "• The T-pose is the reference position - all movements are relative to this"
        )
        notes.setStyleSheet("color: #d32f2f; font-weight: bold;")
        notes.setWordWrap(True)
        layout.addWidget(notes)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.dont_show_again_btn = QPushButton("Don't Show Again")
        self.dont_show_again_btn.clicked.connect(self.save_preference)
        
        self.ok_button = QPushButton("OK, I Understand")
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.ok_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.dont_show_again_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_preference(self):
        """Save user preference to not show this dialog again."""
        try:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            config_path = os.path.join(config_dir, 'user_preferences.txt')
            with open(config_path, 'a') as f:
                f.write("hide_calibration_guide=True\n")
                
            self.accept()
        except Exception as e:
            print(f"Error saving preference: {e}")
            self.accept()  # Close anyway

def should_show_guide():
    """Check if the calibration guide should be shown."""
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'config', 
            'user_preferences.txt'
        )
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                if "hide_calibration_guide=True" in content:
                    return False
        return True
    except:
        return True  # Show by default if there's any error

if __name__ == "__main__":
    # For testing
    app = QApplication(sys.argv)
    dialog = CalibrationGuideDialog()
    dialog.exec_()
