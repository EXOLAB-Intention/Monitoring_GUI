import traceback
import sys
import os

# Assurez-vous que le répertoire principal est dans le chemin Python
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(script_dir)

# Version information
VERSION = "1.0"
PREVIOUS_VERSION = "0"

def main():
    try:
        print(f"Starting EXO Monitoring GUI v{VERSION} (previous: v{PREVIOUS_VERSION})...")
        print("=" * 60)
        
        # Check if ML model exists and use it if available
        model_path = os.path.join(script_dir, 'data', 'motion_model.pth')
        if os.path.exists(model_path):
            print(f"✅ Motion prediction model found: {model_path}")
            # Model will be automatically loaded by MotionPredictorFactory
        else:
            print("⚠️  No ML model found. Using simple predictor.")
            # You could add a message to suggest training a model
        
        from app import launch
        print("📦 Imported launch function")
        print("🚀 Launching application...")
        launch()
        print("✅ Application launched successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to start application: {str(e)}")
        print("📋 Traceback:")
        print(traceback.format_exc())
        input("Press Enter to exit...")

def get_version_info():
    """Returns version information."""
    return {
        'current': VERSION,
        'previous': PREVIOUS_VERSION,
        'full_name': f"EXO Monitoring GUI v{VERSION}"
    }

if __name__ == "__main__":
    main()
