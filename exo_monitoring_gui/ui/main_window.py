from PyQt5.QtWidgets import QMainWindow, QPushButton, QLabel
from ui.informations import createInformationWindow  # change le nom de la fonction si tu veux

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitoring GUI")
        self.setGeometry(0, 0, 1920, 1080)

        self.label = QLabel("PMMG Data: ", self)
        self.label.setGeometry(50, 50, 700, 50)

        button = QPushButton("Update Data", self)
        button.setGeometry(50, 150, 200, 50)
        button.clicked.connect(self.showInformationWindow)  # on passe par une méthode

    def showInformationWindow(self):
        from ui.informations import createInformationWindow
        self.info_window = createInformationWindow()  # garde une référence
        self.info_window.show()
