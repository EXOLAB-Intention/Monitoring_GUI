
def _apply_styles(self):
    """Apply CSS styles to the application"""
    self.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #f0f0f0;
        }
        QMenuBar {
            background-color: #ffffff;
            border-bottom: 1px solid #dddddd;
        }
        QMenu {
            background-color: white;
            border: 1px solid #cccccc;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 20px;
            background-color: transparent;
        }
        QMenu::item:selected {
            background-color: #dceaff;
            color: black;
        }
        QMenu::separator {
            height: 1px;
            background: #dddddd;
            margin: 5px 15px;
        }
        QPushButton {
            background-color: #f5f5f5;
            border: 1px solid #dddddd;
            border-radius: 3px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #e5e5e5;
        }
        QPushButton:pressed {
            background-color: #d0d0d0;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 3px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #3399ff;
            width: 10px;
        }
    """)