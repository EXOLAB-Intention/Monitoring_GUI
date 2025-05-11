from PyQt5.QtWidgets import QLabel, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt
import os

class ImageDropArea(QLabel):
    """Area allowing to drop or select an image"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Click or drag an image here")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            border: 2px dashed #cccccc;
            border-radius: 5px;
            padding: 10px;
            background-color: #f8f8f8;
        """)
        self.setAcceptDrops(True)
        self.image_path = None

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events for files"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                border: 2px dashed #3399ff;
                border-radius: 5px;
                padding: 10px;
                background-color: #ebf5ff;
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave events"""
        self.setStyleSheet("""
            border: 2px dashed #cccccc;
            border-radius: 5px;
            padding: 10px;
            background-color: #f8f8f8;
        """)

    def dropEvent(self, event: QDropEvent):
        """Handle drop events for image files"""
        self.setStyleSheet("""
            border: 2px dashed #cccccc;
            border-radius: 5px;
            padding: 10px;
            background-color: #f8f8f8;
        """)
        
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                self.load_image(file_path)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select an image file.")
        
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        """Handle mouse clicks to select an image file"""
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select an image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if file_path:
                self.load_image(file_path)

    def load_image(self, file_path):
        """Load and display an image from file path"""
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            # Scale image to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
            self.image_path = file_path
        else:
            self.setText("Unable to load image")
            self.image_path = None
    
    def get_image_path(self):
        """Return the path to the loaded image"""
        return self.image_path

    def resizeEvent(self, event):
        """Handle resize events to rescale the image"""
        if self.pixmap() and not self.pixmap().isNull():
            scaled_pixmap = self.pixmap().scaled(self.width(), self.height(), 
                                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        super().resizeEvent(event)
