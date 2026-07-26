#!/usr/bin/env python3
"""
ILMA Memory Persistence - Durable storage with versioning and backup.

This module provides persistent memory storage with automatic versioning,
checkpointing, and recovery capabilities.

Features:
- Automatic versioning of memory states
- Checkpoint creation and recovery
- Atomic write operations
- Integrity verification
- Backup rotation

Usage:
    python ilma_memory_persistence.py --checkpoint
    python ilma_memory_persistence.py --restore
    python ilma_memory_persistence.py --verify

Author: ILMA Memory Category
Date: 2026-05-09
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/root/.hermes/profiles/ilma/logs/memory_persistence.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
MEMORY_DIR = Path('/root/.hermes/profiles/ilma/memories')
PERSISTENCE_DIR = MEMORY_DIR / 'persistence'
CHECKPOINT_DIR = PERSISTENCE_DIR / 'checkpoints'
BACKUP_DIR = PERSISTENCE_DIR / 'backups'
STATE_FILE = MEMORY_DIR / 'state.json'
METADATA_FILE = PERSISTENCE_DIR / 'metadata.json'

MAX_CHECKPOINTS = 10
MAX_BACKUPS = 5
CHECKPOINT_INTERVAL = 300  # 5 minutes


@dataclass
class MemoryCheckpoint:
    """A checkpoint of memory state."""
    version: str
    timestamp: datetime
    entry_count: int
    checksum: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'timestamp': self.timestamp.isoformat(),
            'entry_count': self.entry_count,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryCheckpoint':
        return cls(
            version=data['version'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            entry_count=data['entry_count'],
            checksum=data['checksum'],
            size_bytes=data['size_bytes'],
            metadata=data.get('metadata', {})
        )


@dataclass
class PersistenceMetadata:
    """Metadata for persistence system."""
    last_checkpoint: Optional[datetime] = None
    last_backup: Optional[datetime] = None
    total_checkpoints: int = 0
    total_backups: int = 0
    current_version: str = "1.0.0"
    state_checksum: str = ""
    entries_since_checkpoint: int = 0

    def to_dict(self) -> dict:
        return {
            'last_checkpoint': self.last_checkpoint.isoformat() if self.last_checkpoint else None,
            'last_backup': self.last_backup.isoformat() if self.last_backup else None,
            'total_checkpoints': self.total_checkpoints,
            'total_backups': self.total_backups,
            'current_version': self.current_version,
            'state_checksum': self.state_checksum,
            'entries_since_checkpoint': self.entries_since_checkpoint
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PersistenceMetadata':
        return cls(
            last_checkpoint=datetime.fromisoformat(data['last_checkpoint']) if data.get('last_checkpoint') else None,
            last_backup=datetime.fromisoformat(data['last_backup']) if data.get('last_backup') else None,
            total_checkpoints=data.get('total_checkpoints', 0),
            total_backups=data.get('total_backups', 0),
            current_version=data.get('current_version', '1.0.0'),
            state_checksum=data.get('state_checksum', ''),
            entries_since_checkpoint=data.get('entries_since_checkpoint', 0)
        )


class MemoryPersistence:
    """
    ILMA Memory Persistence with versioning and recovery.
    Provides durable storage with automatic checkpointing.
    """

    def __init__(self):
        self.memory_dir = MEMORY_DIR
        self.persistence_dir = PERSISTENCE_DIR
        self.checkpoint_dir = CHECKPOINT_DIR
        self.backup_dir = BACKUP_DIR
        self.state_file = STATE_FILE
        self.metadata_file = METADATA_FILE

        self._ensure_directories()
        self.metadata = self._load_metadata()
        logger.info("MemoryPersistence initialized")

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        for directory in [self.persistence_dir, self.checkpoint_dir, self.backup_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> PersistenceMetadata:
        """Load or create persistence metadata."""
        if self.metadata_file.exists():
            try:
                data = json.loads(self.metadata_file.read_text())
                return PersistenceMetadata.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")

        return PersistenceMetadata()

    def _save_metadata(self) -> None:
        """Save persistence metadata."""
        try:
            self.metadata_file.write_text(json.dumps(self.metadata.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            raise

    def _compute_checksum(self, data: bytes) -> str:
        """Compute checksum for data integrity."""
        return hashlib.sha256(data).hexdigest()

    def _load_state(self) -> dict[str, Any]:
        """Load current memory state."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return {'entries': {}}
        return {'entries': {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save memory state atomically."""
        temp_file = self.state_file.with_suffix('.tmp')

        try:
            temp_file.write_text(json.dumps(state, indent=2))
            temp_file.rename(self.state_file)
            logger.debug(f"State saved: {len(state.get('entries', {}))} entries")
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def checkpoint(self, force: bool = False) -> Optional[str]:
        """
        Create a checkpoint of current memory state.

        Args:
            force: Force checkpoint even if interval not reached

        Returns:
            Checkpoint version string or None
        """
        now = datetime.now()

        if not force:
            if self.metadata.last_checkpoint:
                elapsed = (now - self.metadata.last_checkpoint).total_seconds()
                if elapsed < CHECKPOINT_INTERVAL and self.metadata.entries_since_checkpoint < 100:
                    logger.debug(f"Checkpoint skipped, interval: {elapsed:.0f}s")
                    return None

        state = self._load_state()
        state_bytes = json.dumps(state, sort_keys=True).encode('utf-8')
        checksum = self._compute_checksum(state_bytes)

        version = f"cp_{now.strftime('%Y%m%d_%H%M%S')}_{checksum[:8]}"
        checkpoint_data = {
            'version': version,
            'timestamp': now.isoformat(),
            'state': state,
            'checksum': checksum,
            'size_bytes': len(state_bytes)
        }

        checkpoint_file = self.checkpoint_dir / f"{version}.json"
        compressed_file = self.checkpoint_dir / f"{version}.json.zlib"

        try:
            # Save checkpoint
            checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))

            # Create compressed backup
            compressed = zlib.compress(checkpoint_file.read_bytes())
            compressed_file.write_bytes(compressed)

            # Update metadata
            self.metadata.last_checkpoint = now
            self.metadata.total_checkpoints += 1
            self.metadata.entries_since_checkpoint = 0
            self.metadata.state_checksum = checksum
            self._save_metadata()

            # Cleanup old checkpoints
            self._cleanup_checkpoints()

            logger.info(f"Checkpoint created: {version}")
            return version

        except Exception as e:
            logger.error(f"Checkpoint failed: {e}")
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            if compressed_file.exists():
                compressed_file.unlink()
            return None

    def _cleanup_checkpoints(self) -> None:
        """Remove old checkpoints beyond MAX_CHECKPOINTS."""
        checkpoints = sorted(self.checkpoint_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)

        for cp in checkpoints[MAX_CHECKPOINTS:]:
            compressed = Path(str(cp) + '.zlib')
            if compressed.exists():
                compressed.unlink()
            cp.unlink()
            logger.debug(f"Removed old checkpoint: {cp.name}")

    def _cleanup_backups(self) -> None:
        """Remove old backups beyond MAX_BACKUPS."""
        backups = sorted(self.backup_dir.glob('*.json.zlib'), key=lambda p: p.stat().st_mtime, reverse=True)

        for backup in backups[MAX_BACKUPS:]:
            backup.unlink()
            logger.debug(f"Removed old backup: {backup.name}")

    def restore(self, version: Optional[str] = None) -> bool:
        """
        Restore memory from checkpoint.

        Args:
            version: Specific version to restore, or latest

        Returns:
            True if restoration successful
        """
        if version:
            checkpoint_file = self.checkpoint_dir / f"{version}.json"
            if not checkpoint_file.exists():
                checkpoint_file = self.checkpoint_dir / f"{version}.json.zlib"
                if checkpoint_file.exists():
                    try:
                        compressed = checkpoint_file.read_bytes()
                        data = json.loads(zlib.decompress(compressed).decode('utf-8'))
                        state = data['state']
                    except Exception as e:
                        logger.error(f"Failed to decompress checkpoint: {e}")
                        return False
                else:
                    logger.error(f"Checkpoint not found: {version}")
                    return False
            else:
                try:
                    data = json.loads(checkpoint_file.read_text())
                    state = data['state']
                except Exception as e:
                    logger.error(f"Failed to load checkpoint: {e}")
                    return False
        else:
            # Get latest checkpoint
            checkpoints = sorted(self.checkpoint_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
            if not checkpoints:
                logger.warning("No checkpoints found")
                return False

            try:
                data = json.loads(checkpoints[0].read_text())
                state = data['state']
            except Exception as e:
                logger.error(f"Failed to load latest checkpoint: {e}")
                return False

        # Create backup before restore
        self.backup()

        # Restore state
        self._save_state(state)

        logger.info(f"Restored from checkpoint: {data.get('version', 'unknown')}")
        return True

    def backup(self) -> Optional[str]:
        """
        Create a backup of current state.

        Returns:
            Backup version string or None
        """
        now = datetime.now()
        state = self._load_state()
        state_bytes = json.dumps(state, sort_keys=True).encode('utf-8')
        checksum = self._compute_checksum(state_bytes)

        version = f"backup_{now.strftime('%Y%m%d_%H%M%S')}_{checksum[:8]}"
        backup_file = self.backup_dir / f"{version}.json.zlib"

        try:
            compressed = zlib.compress(state_bytes)
            backup_file.write_bytes(compressed)

            self.metadata.last_backup = now
            self.metadata.total_backups += 1
            self._save_metadata()

            self._cleanup_backups()

            logger.info(f"Backup created: {version}")
            return version

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    def verify(self) -> dict[str, Any]:
        """
        Verify integrity of current state and checkpoints.

        Returns:
            Verification results
        """
        results = {
            'ok': True,
            'state_checksum': '',
            'checkpoints_valid': [],
            'checkpoints_invalid': [],
            'errors': []
        }

        # Verify current state
        state = self._load_state()
        state_bytes = json.dumps(state, sort_keys=True).encode('utf-8')
        checksum = self._compute_checksum(state_bytes)
        results['state_checksum'] = checksum

        if self.metadata.state_checksum and checksum != self.metadata.state_checksum:
            results['errors'].append(f"State checksum mismatch: expected {self.metadata.state_checksum}, got {checksum}")
            results['ok'] = False

        # Verify checkpoints
        for cp_file in self.checkpoint_dir.glob('*.json'):
            try:
                data = json.loads(cp_file.read_text())
                stored_checksum = data.get('checksum', '')
                cp_state_bytes = json.dumps(data.get('state', {}), sort_keys=True).encode('utf-8')
                computed = self._compute_checksum(cp_state_bytes)

                if stored_checksum == computed:
                    results['checkpoints_valid'].append(cp_file.stem)
                else:
                    results['checkpoints_invalid'].append(cp_file.stem)
                    results['errors'].append(f"Checkpoint corrupted: {cp_file.stem}")
                    results['ok'] = False
            except Exception as e:
                results['checkpoints_invalid'].append(cp_file.stem)
                results['errors'].append(f"Checkpoint read error {cp_file.stem}: {e}")
                results['ok'] = False

        # Verify compressed checkpoints
        for cp_file in self.checkpoint_dir.glob('*.json.zlib'):
            try:
                compressed = cp_file.read_bytes()
                decompressed = zlib.decompress(compressed)
                data = json.loads(decompressed.decode('utf-8'))
                stored_checksum = data.get('checksum', '')
                cp_state_bytes = json.dumps(data.get('state', {}), sort_keys=True).encode('utf-8')
                computed = self._compute_checksum(cp_state_bytes)

                if stored_checksum == computed:
                    results['checkpoints_valid'].append(cp_file.stem)
                else:
                    results['checkpoints_invalid'].append(cp_file.stem)
                    results['errors'].append(f"Compressed checkpoint corrupted: {cp_file.stem}")
                    results['ok'] = False
            except Exception as e:
                results['checkpoints_invalid'].append(cp_file.stem)
                results['errors'].append(f"Compressed checkpoint error {cp_file.stem}: {e}")
                results['ok'] = False

        return results

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all available checkpoints."""
        checkpoints = []

        for cp_file in sorted(self.checkpoint_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(cp_file.read_text())
                checkpoints.append({
                    'file': cp_file.name,
                    'version': data.get('version', ''),
                    'timestamp': data.get('timestamp', ''),
                    'entry_count': data.get('state', {}).get('entries', {}).__len__(),
                    'size_bytes': cp_file.stat().st_size,
                    'checksum': data.get('checksum', '')[:16]
                })
            except Exception as e:
                logger.warning(f"Failed to read checkpoint {cp_file}: {e}")

        return checkpoints

    def get_metadata(self) -> dict[str, Any]:
        """Get persistence metadata."""
        return self.metadata.to_dict()

    def health_check(self) -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "ok": True,
            "module": "memory_persistence",
            "persistence_dir": str(self.persistence_dir),
            "last_checkpoint": self.metadata.last_checkpoint.isoformat() if self.metadata.last_checkpoint else None,
            "last_backup": self.metadata.last_backup.isoformat() if self.metadata.last_backup else None,
            "total_checkpoints": self.metadata.total_checkpoints,
            "total_backups": self.metadata.total_backups,
            "checkpoints_available": len(list(self.checkpoint_dir.glob('*.json'))) + len(list(self.checkpoint_dir.glob('*.json.zlib')))
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='ILMA Memory Persistence - Durable storage with versioning',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--checkpoint', '-c', action='store_true', help='Create a checkpoint')
    parser.add_argument('--force-checkpoint', '-f', action='store_true', help='Force checkpoint creation')
    parser.add_argument('--restore', '-r', type=str, nargs='?', const='latest', help='Restore from checkpoint')
    parser.add_argument('--backup', '-b', action='store_true', help='Create a backup')
    parser.add_argument('--verify', '-v', action='store_true', help='Verify integrity')
    parser.add_argument('--list', '-l', action='store_true', help='List checkpoints')
    parser.add_argument('--stats', '-s', action='store_true', help='Show persistence stats')
    parser.add_argument('--health', action='store_true', help='Health check')

    args = parser.parse_args()

    try:
        persistence = MemoryPersistence()

        if args.checkpoint or args.force_checkpoint:
            version = persistence.checkpoint(force=args.force_checkpoint)
            if version:
                print(f"[OK] Checkpoint created: {version}")
            else:
                print("[INFO] Checkpoint skipped (interval not reached)")

        elif args.restore is not None:
            version = None if args.restore == 'latest' else args.restore
            if persistence.restore(version):
                print(f"[OK] Restored from checkpoint")
            else:
                print("[ERROR] Restore failed")
                sys.exit(1)

        elif args.backup:
            version = persistence.backup()
            if version:
                print(f"[OK] Backup created: {version}")
            else:
                print("[ERROR] Backup failed")
                sys.exit(1)

        elif args.verify:
            results = persistence.verify()
            print(f"\n[Verification] {'PASSED' if results['ok'] else 'FAILED'}")
            print(f"  State checksum: {results['state_checksum'][:16]}...")
            print(f"  Valid checkpoints: {len(results['checkpoints_valid'])}")
            print(f"  Invalid checkpoints: {len(results['checkpoints_invalid'])}")
            if results['errors']:
                print("  Errors:")
                for err in results['errors']:
                    print(f"    - {err}")

        elif args.list:
            checkpoints = persistence.list_checkpoints()
            print(f"\n[Checkpoints] {len(checkpoints)} available:")
            for cp in checkpoints[:10]:
                print(f"  {cp['version']} - {cp['timestamp']} ({cp['entry_count']} entries, {cp['size_bytes']} bytes)")

        elif args.stats:
            meta = persistence.get_metadata()
            print("\n[Persistence Statistics]")
            print(f"  Last checkpoint: {meta.get('last_checkpoint', 'never')}")
            print(f"  Last backup: {meta.get('last_backup', 'never')}")
            print(f"  Total checkpoints: {meta.get('total_checkpoints', 0)}")
            print(f"  Total backups: {meta.get('total_backups', 0)}")
            print(f"  State checksum: {meta.get('state_checksum', 'unknown')[:16]}...")

        elif args.health:
            health = persistence.health_check()
            print(f"\n[Health] {health}")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()