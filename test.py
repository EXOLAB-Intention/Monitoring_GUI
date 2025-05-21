from PyQt5.QtWidgets import QApplication, QLabel
import sys, os

os.environ["QT_OPENGL"] = "software"  # optionnel, au cas où ton GPU bloque

app = QApplication(sys.argv)
label = QLabel("Coucou VS Code")
label.show()
sys.exit(app.exec_())
