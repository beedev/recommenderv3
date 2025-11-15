# Systemd Deployment - Changelog

## 2025-11-06 - Dynamic Path Detection

### Summary
Updated deployment scripts to automatically detect installation paths and user instead of using hardcoded values. This allows deployment to any directory on any Linux server without manual configuration.

### Breaking Changes

**⚠️ IMPORTANT**: Service template files now contain placeholders and **must not** be copied directly to `/etc/systemd/system/`. Always use the `deploy.sh` script for installation.

### Files Modified

#### 1. `deploy.sh`
**Major Changes:**
- Added automatic path detection from script location
- Added automatic user detection from `$SUDO_USER` or current user
- Added `generate_service_files()` function to dynamically create service files
- Added configuration display at script start
- Removed hardcoded user creation (now verifies existing user)
- Removed hardcoded file copying (now works in repository location)
- Updated service installation to use generated files instead of repository templates

**Key Code Changes:**
```bash
# Auto-detect installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Auto-detect user
APP_USER="${SUDO_USER:-$(whoami)}"
APP_GROUP="$APP_USER"

# Use detected repository root
INSTALL_DIR="$REPO_ROOT"
```

**New Function:**
```bash
generate_service_files() {
    # Dynamically generates service files with detected paths
    # Uses HERE documents to create files in /tmp/
    # Replaces all placeholders with actual detected values
}
```

#### 2. `esab-recommender.service`
**Changes:**
- Added header comment indicating this is a TEMPLATE file
- Replaced all hardcoded paths with placeholders:
  - `/home/azureuser/esab_recommender-bh` → `<PLACEHOLDER_BACKEND_DIR>`
  - `azureuser` → `<PLACEHOLDER_USER>`
  - `/home/azureuser/esab_recommender-bh/logs` → `<PLACEHOLDER_LOG_DIR>`

**Warning Added:**
```ini
# TEMPLATE FILE - DO NOT COPY DIRECTLY TO /etc/systemd/system/
# This file contains placeholder paths for reference only.
# The deploy.sh script will generate the actual service file with correct paths.
# Run: sudo ./deployment/systemd/deploy.sh install
```

#### 3. `esab-recommender-frontend.service`
**Changes:**
- Added header comment indicating this is a TEMPLATE file
- Replaced hardcoded paths with placeholders:
  - `/home/azureuser/esab_recommender-bh/src` → `<PLACEHOLDER_INSTALL_DIR>/src`
  - `azureuser` → `<PLACEHOLDER_USER>`

#### 4. `README.md`
**Changes:**
- Updated "Installation Location" from hardcoded path to "Auto-detected"
- Added "Path Detection" section explaining auto-detection features
- Updated "System Requirements" to reflect auto-detected user
- Completely rewrote "Automated Installation" section with dynamic path examples
- Updated "Manual Installation" section with strong warning against manual installation
- Recommended always using deploy.sh script
- Updated all example paths to use placeholders instead of hardcoded values
- Added note about dynamic service file generation

### New Files

#### 1. `MIGRATION_GUIDE.md`
Complete migration guide for existing deployments covering:
- What changed and why
- How dynamic path detection works
- Step-by-step migration instructions
- Three migration options (fresh install, update, manual regeneration)
- Comprehensive troubleshooting section
- Benefits of new approach
- Verification procedures

#### 2. `QUICK_START_AYNALINUX.md`
Server-specific quick start guide for Aynalinux deployment:
- Exact commands for your server setup
- Step-by-step deployment process
- Troubleshooting specific to your environment
- Verification checklist
- Quick reference table of file paths
- Common management commands

#### 3. `CHANGELOG.md` (this file)
Documents all changes made to the systemd deployment system.

### How It Works

#### Old Flow (Hardcoded):
1. User copies repository to `/home/azureuser/esab_recommender-bh/`
2. Service files have hardcoded paths to that location
3. Copy service files to `/etc/systemd/system/`
4. Start services

**Problem**: Only works in that exact location with that exact user.

#### New Flow (Dynamic):
1. User clones/copies repository to **any location**
2. Run `deploy.sh` from within repository
3. Script detects repository location and current user
4. Script **generates** service files with detected paths
5. Install generated service files to `/etc/systemd/system/`
6. Start services

**Benefit**: Works anywhere, with any user, no configuration needed.

### Installation Path Examples

The new system works with **any** of these paths:

```bash
/home/azureuser/esab_recommender-bh        # Old default
/home/Aynalinux/project/ayna-pod-recommender   # Your current server
/opt/esab-recommender                       # System-wide installation
/srv/applications/esab                      # Server directory
/home/john/dev/esab-recommender            # Developer machine
/var/www/esab-api                          # Web server directory
```

**No changes needed** - the script adapts to any location automatically.

### User Detection Examples

The script works with **any** user:

```bash
azureuser    # Azure VM default user
Aynalinux    # Your current user
ubuntu       # AWS EC2 default user
centos       # CentOS default user
www-data     # Web server user
esab         # Dedicated service user
```

**No configuration needed** - the script detects the user running sudo.

### Backward Compatibility

**Breaking Change**: Service template files can no longer be copied directly.

**Migration Required**: Existing deployments must:
1. Stop services
2. Remove old service files
3. Run new `deploy.sh install` to generate new service files
4. Start services

See `MIGRATION_GUIDE.md` for detailed instructions.

### Testing

Tested on:
- ✅ Ubuntu 20.04 LTS
- ✅ Ubuntu 22.04 LTS
- ✅ Multiple installation paths
- ✅ Multiple users
- ✅ Fresh installation
- ✅ Update from existing installation

### Benefits

1. **Portability**: Deploy anywhere without path configuration
2. **Flexibility**: Works with any Linux user
3. **Simplicity**: No manual service file editing required
4. **Reliability**: Eliminates path mismatch errors
5. **Maintainability**: Single source of truth (deploy.sh)
6. **Documentation**: Self-documenting (shows detected config)

### Known Issues

None identified. If you encounter issues, see:
- `MIGRATION_GUIDE.md` for troubleshooting
- `QUICK_START_AYNALINUX.md` for deployment-specific help

### Future Enhancements

Potential improvements for future versions:
- [ ] Command-line flags to override auto-detected values
- [ ] Support for custom service names
- [ ] Multi-instance deployment support
- [ ] Docker integration with dynamic paths
- [ ] Automated backup/restore of .env files
- [ ] Health check integration in deploy script
- [ ] Log rotation configuration
- [ ] Firewall rule automation

### Contributors

- Anandhan S. - Dynamic path detection implementation

### References

- Original issue: Port 8000 not listening due to hardcoded paths
- Server: Aynalinux@Aynalinux
- Date: 2025-11-06

---

## Previous Versions

### 2025-11-05 and earlier
- Used hardcoded paths (`/home/azureuser/esab_recommender-bh/`)
- Required manual path configuration for different installations
- Service files were static templates without placeholders
