# Ookla Server Removal Session — 2026-07-31

## Task Brief
User meminta penghapusan menyeluruh Ookla server dari VPS speedtest skarnet di `root@103.161.195.82:2222`.

## Initial Discovery

### SSH Connection
```bash
ssh -i /root/credential/private_key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@103.161.195.82 -p 2222
```
**Result:** ✅ Connection successful

### Process Check
```bash
ps aux | grep -i speedtest
```
**Result:**
```
root     1479930  0.0  0.2  16920  7600 ?        Ss   00:00   0:04 ./OoklaServer --daemon --pidfile=/root/OoklaServer.pid
root     1479942  0.2  0.5  26060  17780 ?        Sl   00:00   2:23 /root/OoklaServer --ward --parent-pidfile=/root/OoklaServer.pid --server-id=1d884a50-ccfd-4f95-82f3-9dca335a6ae9
```

### File Discovery
```bash
find /usr -name "*speedtest*" -o -name "*okla*" 2>/dev/null
find /etc -name "*speedtest*" -o -name "*okla*" 2>/dev/null
find /var -name "*speedtest*" -o -name "*okla*" 2>/dev/null
```
**Result:**
- `/etc/systemd/system/snap-speedtest-9.mount`
- `/etc/systemd/system/snap-speedtest-12.mount`
- `/var/lib/snapd/inhibit/speedtest.lock`
- `/var/lib/snapd/cookie/snap.speedtest`
- `/var/lib/snapd/snaps/speedtest_12.snap`
- `/var/lib/snapd/snaps/speedtest_9.snap`
- `/snap/speedtest` (directory)
- `/root/OoklaServer` (binary)

## Removal Steps

### Step 1: Process Termination
```bash
pkill -f OoklaServer
```
**Result:** Process still running (pkill ineffective)

```bash
kill -9 $(pgrep -f OoklaServer)
```
**Result:** ✅ Process terminated

### Step 2: Binary Removal
```bash
rm -f /root/OoklaServer /root/OoklaServer.pid
```
**Result:** ✅ Binary and pidfile removed

### Step 3: Snap Package Removal
```bash
apt-get remove --purge -y snapd
```
**Result:** ✅ Snapd removed, all speedtest snaps removed automatically
**Note:** Removing snapd automatically removes all snap packages including speedtest

### Step 4: Manual Cleanup (post-snapd removal)
```bash
rm -rf /var/lib/snapd
rm -rf /snap/speedtest
rm -f /etc/systemd/system/snap-speedtest-*.mount
rm -rf /etc/systemd/system/multi-user.target.wants/snap-speedtest-*.mount
rm -f /etc/systemd/system/snapd.mounts.target.wants/snap-speedtest-*.mount
rm -rf /var/cache/apparmor/*speedtest*
rm -f /var/lib/snapd/seccomp/bpf/snap.speedtest.speedtest.bin
```
**Result:** ✅ All files cleaned

## Final Verification
```bash
ps aux | grep -v grep | grep -i "OoklaServer"
```
**Result:** No OoklaServer process running ✅

```bash
ls -la /root/OoklaServer
```
**Result:** No such file or directory ✅

```bash
ls -la /snap/speedtest
```
**Result:** No such file or directory ✅

```bash
ls -la /var/lib/snapd/snaps/speedtest_*.snap
```
**Result:** No such file or directory ✅

## Disk Space Recovered
- **61.4 MB** freed by removing snapd package

## Key Learnings

### Process Termination Gotcha
- `pkill -f` can fail silently on some processes
- Always verify with `ps aux | grep` after kill attempt
- Use `kill -9 $(pgrep -f <pattern>)` for stubborn processes

### Snap Package Gotcha
- Snap packages are automatically removed when snapd is purged
- Removing snapd is the cleanest way to remove ALL snap packages
- Manual deletion of `/snap/` directory may fail due to read-only filesystem

### Command Sequence That Worked
1. `kill -9 $(pgrep -f OoklaServer)` - terminate processes
2. `rm -f /root/OoklaServer /root/OoklaServer.pid` - remove binaries
3. `apt-get remove --purge -y snapd` - remove snapd (auto-removes all snaps)
4. Manual cleanup of remaining systemd files and cache
5. Verification with `ps` and `ls` commands

## Evidence ID
`ILMA-EVID-20260731-OKLAREMOVAL-001`