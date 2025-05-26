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
        
        # Vérifier si le modèle ML existe et l'utiliser s'il est disponible
        model_path = os.path.join(script_dir, 'data', 'motion_model.pth')
        if os.path.exists(model_path):
            print(f"✅ Modèle de prédiction de mouvement trouvé: {model_path}")
            # Le modèle sera automatiquement chargé par MotionPredictorFactory
        else:
            print("⚠️  Aucun modèle ML trouvé. Utilisation du prédicteur simple.")
            # Vous pourriez ajouter un message pour suggérer d'entraîner un modèle
        
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
    """Retourne les informations de version."""
    return {
        'current': VERSION,
        'previous': PREVIOUS_VERSION,
        'full_name': f"EXO Monitoring GUI v{VERSION}"
    }

if __name__ == "__main__":
    main()
