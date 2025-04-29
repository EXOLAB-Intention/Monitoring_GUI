from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
import sys
from ui.main_window import MainApp


def launch():
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
    
