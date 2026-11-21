---
name: ilma-service-removal
description: Comprehensive service removal workflow for application servers (Ookla, Speedtest, etc.) - stop processes, remove binaries, clean snap packages, remove systemd services, and verify complete removal.
tags: [system-administration, service-removal, cleanup, ookla, speedtest]
created: 2026-07-31
updated: 2026-07-31
---

# ILMA Service Removal — Application Server Cleanup

## Purpose
Menghapus menyeluruh service aplikasi seperti Ookla Server, Speedtest, atau layanan serupa dari sistem Linux. Memastikan semua komponen (binary, konfigurasi, snap packages, systemd units, lock files) telah dihapus secara komprehensif.

## When to Use
- User meminta "penghapusan menyeluruh Ookla server"
- User meminta "remove service completely"
- User membutuhkan cleanup penuh layanan aplikasi
- Service sudah tidak diperlukan atau perlu diganti

## Signal Patterns
- "hapus Ookla server"
- "remove speedtest"
- "delete service completely"
- "uninstall application server"
- "cleanup service files"

## 8-Step Removal Pipeline

### Step 1: Process Termination
Stop proses daemon dengan cara yang aman:

```bash
# Force kill proses (gunakan kill -9 jika pkill tidak efektif)
pkill -f <process_name>
# Jika masih berjalan:
kill -9 $(pgrep -f <process_name>)
sleep 2

# Verifikasi proses telah berhenti
ps aux | grep -v grep | grep -i <process_name> || echo "Process stopped"
```

**⚠️ PENTING:** `pkill` tidak selalu efektif. Gunakan `kill -9` jika proses tetap berjalan.

### Step 2: Binary and File Removal
Hapus file binary utama dan file konfigurasi:

```bash
# Remove main binary
rm -f /path/to/service_binary
rm -f /path/to/service.pid

# Remove configuration directories
rm -rf /etc/service_name
rm -rf /var/lib/service_name
```

### Step 3: Snap Package Removal (Jika ada)
Hapus snap packages yang terkait:

```bash
# Cek snap yang terinstal
snap list | grep -i <service_name>

# Hapus snap beserta semua revisions
snap remove <service_name> --revision=all

# Jika snap tidak bisa dihapus via snap command:
rm -rf /snap/<service_name>
rm -f /var/lib/snapd/snaps/<service_name>_*.snap
```

**⚠️ GOTCHA:** File di `/snap/` mungkin read-only. Gunakan `snap remove` terlebih dahulu, atau hapus via `apt purge snapd` jika diperlukan.

### Step 4: Systemd Service Removal
Hapus unit systemd yang terkait:

```bash
# Stop dan disable service
systemctl stop <service_name>
systemctl disable <service_name>

# Remove mount files (snap services)
rm -f /etc/systemd/system/snap-<service_name>-*.mount
rm -f /etc/systemd/system/multi-user.target.wants/snap-<service_name>-*.mount

# Reload systemd daemon
systemctl daemon-reload
```

### Step 5: Cache and Lock File Cleanup
Bersihkan semua file cache dan lock:

```bash
# Remove lock files
rm -f /var/lib/snapd/inhibit/<service_name>.lock
rm -f /var/lib/snapd/cookie/<service_name>

# Remove apparmor profiles
rm -rf /var/cache/apparmor/*<service_name>*

# Remove seccomp profiles
rm -f /var/lib/snapd/seccomp/bpf/<service_name>*.bin
```

### Step 6: Package Manager Cleanup
Jika service terinstal via package manager:

```bash
# Debian/Ubuntu
apt-get remove --purge -y <package_name>
apt-get autoremove -y
apt-get autoclean

# RHEL/CentOS
yum remove -y <package_name>
yum autoremove -y
```

### Step 7: Verification
Verifikasi kehilangan total:

```bash
# Check processes
ps aux | grep -v grep | grep -i <service_name> || echo "✓ No processes"

# Check files
ls -la /path/to/service_binary 2>/dev/null || echo "✓ Binary removed"
ls -la /snap/<service_name> 2>/dev/null || echo "✓ Snap directory removed"
ls -la /var/lib/snapd/snaps/<service_name>_*.snap 2>/dev/null || echo "✓ Snap files removed"
ls -la /etc/systemd/system/snap-<service_name>-*.mount 2>/dev/null || echo "✓ Systemd mount files removed"
```

### Step 8: Disk Space Recovery
Hitung ruang disk yang dilepaskan:

```bash
# Show disk usage before/after
df -h /
du -sh /path/to/service_directory 2>/dev/null || echo "0"
```

## Common Patterns & Pitfalls

### Ookla Server Specific (Verified 2026-07-31)
```bash
# Binary location
/root/OoklaServer

# Process names
OoklaServer --daemon
OoklaServer --ward

# Paths to remove
rm -f /root/OoklaServer /root/OoklaServer.pid
rm -rf /snap/speedtest
rm -f /var/lib/snapd/snaps/speedtest_*.snap
rm -f /etc/systemd/system/snap-speedtest-*.mount
rm -rf /var/lib/snapd
```

### Snap Package Gotcha
- Snap packages cannot be deleted manually from `/snap/` while mounted
- Use `snap remove <package>` first, then manual cleanup if needed
- Removing `snapd` package automatically removes all snaps

### Process Termination Gotcha
- `pkill -f` sometimes fails silently
- Always verify with `ps aux | grep <process>` after kill attempt
- Use `kill -9 $(pgrep -f <pattern>)` for stubborn processes

## CLI Commands

```bash
# Full removal with verification
python3 ilma_service_removal.py --service ookla --verify

# Dry-run (show what would be removed)
python3 ilma_service_removal.py --service ookla --dry-run

# List all service files (discovery mode)
python3 ilma_service_removal.py --service ookla --discover
```

## Support Files
- `references/ookla-removal-2026-07-31.md` — detailed session transcript with exact commands and outputs
- `scripts/ilma_service_removal.py` — automated Python script for service removal with discover/verify/dry-run modes

## Usage
```bash
# Full removal with verification
python3 scripts/ilma_service_removal.py --service ookla --binary /root/OoklaServer

# Dry-run (show what would be removed)
python3 scripts/ilma_service_removal.py --service ookla --discover

# Verify mode only
python3 scripts/ilma_service_removal.py --service ookla --verify
```