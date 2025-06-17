import os
import argparse
import shutil
from datetime import datetime

def backup_and_clean(backup=True, delete=False):
    """Backup and/or delete training files."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_dir = os.path.join(base_dir, 'machinelearning')
    json_dir = os.path.join(base_dir, 'data', 'recordings')
    
    # Create an archive folder if necessary
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(base_dir, 'data', 'archives', f'backup_{timestamp}')
        os.makedirs(backup_dir, exist_ok=True)
        print(f"Creating archive folder: {backup_dir}")
        
        # Copy CSV files
        if os.path.exists(csv_dir):
            csv_backup = os.path.join(backup_dir, 'csv')
            os.makedirs(csv_backup, exist_ok=True)
            for f in os.listdir(csv_dir):
                if f.endswith('.csv'):
                    shutil.copy2(os.path.join(csv_dir, f), os.path.join(csv_backup, f))
                    print(f"  Backed up: {f}")
        
        # Copy JSON files
        if os.path.exists(json_dir):
            json_backup = os.path.join(backup_dir, 'json')
            os.makedirs(json_backup, exist_ok=True)
            for f in os.listdir(json_dir):
                if f.endswith('.json'):
                    shutil.copy2(os.path.join(json_dir, f), os.path.join(json_backup, f))
                    print(f"  Backed up: {f}")
    
    # Delete files
    if delete:
        print("\nDeleting training files:")
        
        # Delete CSV files
        if os.path.exists(csv_dir):
            for f in os.listdir(csv_dir):
                if f.endswith('.csv'):
                    os.remove(os.path.join(csv_dir, f))
                    print(f"  Deleted: {os.path.join(csv_dir, f)}")
        
        # Delete JSON files
        if os.path.exists(json_dir):
            for f in os.listdir(json_dir):
                if f.endswith('.json'):
                    os.remove(os.path.join(json_dir, f))
                    print(f"  Deleted: {os.path.join(json_dir, f)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleans up training files")
    parser.add_argument('--no-backup', action='store_true', help="Do not backup files")
    parser.add_argument('--delete', action='store_true', help="Delete files")
    
    args = parser.parse_args()
    
    backup_and_clean(backup=not args.no_backup, delete=args.delete)
