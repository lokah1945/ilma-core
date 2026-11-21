# Ghidra Headless Setup (v2 — Ghidra 12.1.4 + JDK 21)

## Overview
Complete setup for Ghidra headless analysis on ILMA host. Covers version selection, JDK requirements, and common pitfalls.

## Version Requirements (Critical)

| Ghidra Version | Required JDK | `application.java.compiler` | Status |
|----------------|--------------|----------------------------|--------|
| 12.0.4 | JDK 25 (not released) | 25 | ❌ Broken — will prompt for JDK |
| **12.1.x** | **JDK 21+** | **21** | ✅ **Works with Temurin 21** |

**Key insight:** Ghidra 12.0.4 was built targeting Java 25 (future version). 12.1.x targets Java 21 LTS.

## Installation (Verified 2026-11-02)

```bash
# 1. Install Temurin JDK 21 (NOT openjdk-17)
cd /opt
wget -q https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_x64_linux_hotspot_21.0.5_11.tar.gz
tar -xzf OpenJDK21U-jdk_x64_linux_hotspot_21.0.5_11.tar.gz
ln -sfn /opt/jdk-21.0.5+11 /opt/jdk-21

# 2. Install Ghidra 12.1.4
wget -q https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip
unzip -q ghidra_12.1.4_PUBLIC_20260921.zip
ln -sfn /opt/ghidra_12.1.4_PUBLIC /opt/ghidra_current

# 3. Set as system default JDK (for REA)
update-alternatives --install /usr/bin/java java /opt/jdk-21/bin/java 2000
update-alternatives --install /usr/bin/javac javac /opt/jdk-21/bin/javac 2000
update-alternatives --set java /opt/jdk-21/bin/java
update-alternatives --set javac /opt/jdk-21/bin/javac

# 4. Set env vars
export JAVA_HOME=/opt/jdk-21
export GHIDRA_INSTALL_DIR=/opt/ghidra_current
# Add to ~/.bashrc for persistence
```

## Usage

```bash
# Test version
$GHIDRA_INSTALL_DIR/support/analyzeHeadless --version
# Output: openjdk version "21.0.5" ... Headless Analyzer Usage

# Run analysis (headless, non-interactive)
mkdir -p /tmp/ghidra_proj
$GHIDRA_INSTALL_DIR/support/analyzeHeadless /tmp/ghidra_proj test_proj -import /bin/ls -deleteProject

# With post-script
$GHIDRA_INSTALL_DIR/support/analyzeHeadless /tmp/ghidra_proj test_proj -import /bin/ls -postScript ExportJson.java
```

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Unable to prompt user for JDK path, no TTY detected` | JDK not set or wrong version | Set `JAVA_HOME=/opt/jdk-21` + use Ghidra 12.1.x |
| `WARNING: JAVA_HOME environment specifies unsupported java version` | Using JDK 17 with Ghidra 12.1+ | Use Temurin JDK 21 |
| `application.java.compiler=25` | Ghidra 12.0.4 | Upgrade to Ghidra 12.1.4 |
| `Directory not found: /tmp/ghidra_proj` | Project dir doesn't exist | `mkdir -p /tmp/ghidra_proj` first |

## For REA Integration
REA requires `GHIDRA_INSTALL_DIR` env var pointing to extracted Ghidra 12.1.x:
```bash
export GHIDRA_INSTALL_DIR=/opt/ghidra_current
rea-agents doctor --client hermes --json
# Should show ghidra: ok: true, detail: "/opt/ghidra_current"
```

## Verification Checklist
- [ ] `java --version` shows Temurin 21.0.5
- [ ] `javac --version` shows 21.0.5
- [ ] `$GHIDRA_INSTALL_DIR/support/analyzeHeadless --version` works without TTY error
- [ ] Headless analysis of `/bin/ls` completes successfully
- [ ] `rea-agents doctor` shows ghidra provider as `configured: true, available: true`

## Notes
- Do NOT use `/usr/local/bin/ghidra` wrapper — it forces `bg` mode
- Always use `$GHIDRA_INSTALL_DIR/support/analyzeHeadless` directly
- Project directory must exist before running analyzeHeadless
- `-deleteProject` flag cleans up after test runs