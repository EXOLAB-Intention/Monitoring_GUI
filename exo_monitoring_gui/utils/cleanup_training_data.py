import os
import argparse
import shutil
from datetime import datetime

def backup_and_clean(backup=True, delete=False):
    """Sauvegarde et/ou supprime les fichiers d'entraînement."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_dir = os.path.join(base_dir, 'machinelearning')
    json_dir = os.path.join(base_dir, 'data', 'recordings')
    
    # Créer un dossier d'archive si nécessaire
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(base_dir, 'data', 'archives', f'backup_{timestamp}')
        os.makedirs(backup_dir, exist_ok=True)
        print(f"Création du dossier d'archive: {backup_dir}")
        
        # Copier les CSV
        if os.path.exists(csv_dir):
            csv_backup = os.path.join(backup_dir, 'csv')
            os.makedirs(csv_backup, exist_ok=True)
            for f in os.listdir(csv_dir):
                if f.endswith('.csv'):
                    shutil.copy2(os.path.join(csv_dir, f), os.path.join(csv_backup, f))
                    print(f"  Sauvegardé: {f}")
        
        # Copier les JSON
        if os.path.exists(json_dir):
            json_backup = os.path.join(backup_dir, 'json')
            os.makedirs(json_backup, exist_ok=True)
            for f in os.listdir(json_dir):
                if f.endswith('.json'):
                    shutil.copy2(os.path.join(json_dir, f), os.path.join(json_backup, f))
                    print(f"  Sauvegardé: {f}")
    
    # Supprimer les fichiers
    if delete:
        print("\nSuppression des fichiers d'entraînement:")
        
        # Supprimer les CSV
        if os.path.exists(csv_dir):
            for f in os.listdir(csv_dir):
                if f.endswith('.csv'):
                    os.remove(os.path.join(csv_dir, f))
                    print(f"  Supprimé: {os.path.join(csv_dir, f)}")
        
        # Supprimer les JSON
        if os.path.exists(json_dir):
            for f in os.listdir(json_dir):
                if f.endswith('.json'):
                    os.remove(os.path.join(json_dir, f))
                    print(f"  Supprimé: {os.path.join(json_dir, f)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nettoie les fichiers d'entraînement")
    parser.add_argument('--no-backup', action='store_true', help="Ne pas sauvegarder les fichiers")
    parser.add_argument('--delete', action='store_true', help="Supprimer les fichiers")
    
    args = parser.parse_args()
    
    backup_and_clean(backup=not args.no_backup, delete=args.delete)
