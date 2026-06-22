import json
import hashlib
from pathlib import Path
import os

BACKUP_DIR = Path("/root/backup/ilma_phase24_pre_patch_backups/")
TARGET_DIR = Path("/root/.hermes/profiles/ilma/")
MANIFEST_PATH = Path("/root/.hermes/profiles/ilma/rollback_manifest_final.json")

def generate_manifest():
    manifest = []
    
    if not BACKUP_DIR.exists():
        print("Backup dir missing.")
        return
        
    for backup_file in BACKUP_DIR.glob("*.py"):
        target_path = TARGET_DIR / backup_file.name
        if target_path.exists():
            c_sha = hashlib.sha256(target_path.read_bytes()).hexdigest()
            b_sha = hashlib.sha256(backup_file.read_bytes()).hexdigest()
            manifest.append({
                "file_path": str(target_path),
                "backup_path": str(backup_file),
                "current_sha256": c_sha,
                "backup_sha256": b_sha,
                "file_type": "python_script",
                "phase_changed": "Phase 24",
                "rollback_command": f"cp {str(backup_file)} {str(target_path)}",
                "post_rollback_test": "python3 -m py_compile " + str(target_path),
                "risk_of_rollback": "Low" if c_sha == b_sha else "Medium"
            })
            
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {MANIFEST_PATH}")

if __name__ == "__main__":
    generate_manifest()
