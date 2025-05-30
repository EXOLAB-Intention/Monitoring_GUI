import traceback
import sys
import os

# Assurez-vous que le répertoire principal est dans le chemin Python
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(script_dir)

def main():
    try:
        print("Starting application...")
        
        # Améliorer la gestion des erreurs OpenGL
        from PyQt5.QtCore import qInstallMessageHandler, QtDebugMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg
        
        def message_handler(mode, context, message):
            # Ne pas afficher les messages OpenGL de routine pour réduire le spam de console
            if "OpenGL" in message:
                # Enregistrer uniquement les messages critiques d'OpenGL
                if "error" in message.lower() or "failed" in message.lower():
                    print(f"OpenGL Error: {message}")
                return  # Supprimer la plupart des messages OpenGL
                
            # Supprimer plusieurs types de messages Windows qui peuvent causer du spam
            if "QWindowsGLContext::swapBuffers" in message:
                return
            if "QOpenGLContext" in message and "destroyed" in message:
                return
            if "QObject" in message and "destroyed" in message:
                return
            
            # Afficher les autres messages importants
            if mode == QtCriticalMsg or mode == QtFatalMsg:
                print(f"Critical: {message}")
            elif mode == QtWarningMsg and "QFont" not in message:  # Ignorer les avertissements de police
                print(f"Warning: {message}")
                
        qInstallMessageHandler(message_handler)
        
        # Check if ML model exists and use it if available
        model_path = os.path.join(script_dir, 'data', 'motion_model.pth')
        if os.path.exists(model_path):
            print(f"Motion prediction model found: {model_path}")
            # The model will be automatically loaded by MotionPredictorFactory
        else:
            print("No ML model found. Using simple predictor.")
            # You could add a message suggesting to train a model
        
        # Ajouter une configuration OpenGL pour améliorer la performance
        from PyQt5.QtGui import QSurfaceFormat
        
        # Configuration globale OpenGL
        surface_format = QSurfaceFormat()
        surface_format.setRenderableType(QSurfaceFormat.OpenGL)
        surface_format.setDepthBufferSize(24)
        surface_format.setStencilBufferSize(8)
        surface_format.setSamples(4)  # Antialiasing (peut être réduit pour plus de performance)
        surface_format.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
        QSurfaceFormat.setDefaultFormat(surface_format)
        
        # Ajouter une vérification des dépendances essentielles
        required_packages = ['PyQt5', 'numpy', 'OpenGL', 'pyqtgraph']
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                print(f"ERROR: Required package '{package}' is not installed.")
                return
        
        from app import launch
        print("Imported launch function")
        launch()
        print("Application launched")
    except Exception as e:
        print(f"ERROR: Failed to start application: {str(e)}")
        print(traceback.format_exc())
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
