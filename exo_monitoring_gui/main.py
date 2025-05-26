import traceback
import sys
import os

# Assurez-vous que le répertoire principal est dans le chemin Python
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(script_dir)

def main():
    try:
        print("Starting application...")
        
        # Vérifier si le modèle ML existe et l'utiliser s'il est disponible
        model_path = os.path.join(script_dir, 'data', 'motion_model.pth')
        if os.path.exists(model_path):
            print(f"Modèle de prédiction de mouvement trouvé: {model_path}")
            # Le modèle sera automatiquement chargé par MotionPredictorFactory
        else:
            print("Aucun modèle ML trouvé. Utilisation du prédicteur simple.")
            # Vous pourriez ajouter un message pour suggérer d'entraîner un modèle
        
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
