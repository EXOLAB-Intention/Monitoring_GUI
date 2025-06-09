import traceback
import sys
import os

# Assurez-vous que le répertoire principal est dans le chemin Python
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(script_dir)

def main():
    try:
        print("Starting application...")
        
        # Handle OpenGL errors more gracefully - prevent console spam
        # Add a filter for the "QWindowsGLContext::swapBuffers: Cannot find window" error
        from PyQt5.QtCore import qInstallMessageHandler, QtDebugMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg
        
        def message_handler(mode, context, message):
            # Log OpenGL-related messages for debugging
            if "OpenGL" in message:
                print(f"OpenGL Message: {message}")
                
            # Only suppress the specific swapBuffers message, let all other messages through
            if "QWindowsGLContext::swapBuffers: Cannot find window" in message:
                return  # Suppress this specific message
            
            if mode == QtDebugMsg:
                print(f"Debug: {message}")
            elif mode == QtWarningMsg:
                print(f"Warning: {message}")
            elif mode == QtCriticalMsg:
                print(f"Critical: {message}")
            elif mode == QtFatalMsg:
                print(f"Fatal: {message}")
        
        qInstallMessageHandler(message_handler)
        
        # Check if ML model exists and use it if available
        model_path = os.path.join(script_dir, 'data', 'motion_model.pth')
        if os.path.exists(model_path):
            print(f"Motion prediction model found: {model_path}")
            # The model will be automatically loaded by MotionPredictorFactory
        else:
            print("No ML model found. Using simple predictor.")
            # You could add a message suggesting to train a model
        
        # Ajouter une vérification des dépendances essentielles
        required_packages = ['PyQt5', 'numpy', 'OpenGL', 'pyqtgraph']
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                print(f"ERROR: Required package '{package}' is not installed.")
                return
        
        # --- Initialization order ---
        # 1. PyQt application and main window are created.
        # 2. The 3D widget (Model3DWidget) is constructed, which loads the ML model if present.
        #    (The actual loading of the predictor is done in model_3d_viewer.py)
        # 3. IMU mapping and calibration can be performed in any order after connection.
        #    - Calibration only affects IMU correction, not ML predictor.
        #    - Motion prediction (ML) is independent and can be toggled at any time.
        # 4. IMU data is displayed as soon as mapping is done and data is received.
        
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
