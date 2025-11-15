#!/bin/bash
# Script to properly upgrade docker-compose from v1 to v2
# Run this with: bash UPGRADE_DOCKER_COMPOSE.sh

set -e

echo "======================================================================"
echo "Docker Compose v1 to v2 Upgrade Script"
echo "======================================================================"
echo ""

# Step 1: Check current versions
echo "Step 1: Checking current docker-compose versions..."
echo ""

# Check all possible locations
echo "Locations where docker-compose might be installed:"
for location in /usr/local/bin/docker-compose /usr/bin/docker-compose ~/.local/bin/docker-compose; do
    if [ -f "$location" ]; then
        echo "  ✓ Found at: $location ($(file $location))"
    fi
done
echo ""

# Check PATH
echo "Current docker-compose in PATH:"
which docker-compose 2>/dev/null || echo "  ! Not found in PATH"
docker-compose --version 2>/dev/null || echo "  ! Version check failed"
echo ""

# Step 2: Remove old versions
echo "Step 2: Removing old docker-compose v1 installations..."
echo ""

# Remove from apt
echo "  - Removing docker-compose package..."
sudo apt-get remove -y docker-compose 2>/dev/null || echo "    (not installed via apt)"

# Remove from all known locations
for location in /usr/local/bin/docker-compose /usr/bin/docker-compose ~/.local/bin/docker-compose; do
    if [ -f "$location" ]; then
        echo "  - Removing $location..."
        sudo rm -f "$location"
    fi
done

# Clear any cached versions
echo "  - Clearing cache..."
sudo rm -f /usr/local/bin/docker-compose-*

echo ""

# Step 3: Download and install Docker Compose v2
echo "Step 3: Installing Docker Compose v2..."
echo ""

# Create directory if needed
sudo mkdir -p /usr/local/bin

# Download latest version
echo "  - Downloading latest Docker Compose v2..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make it executable
echo "  - Making executable..."
sudo chmod +x /usr/local/bin/docker-compose

echo ""

# Step 4: Verify installation
echo "Step 4: Verifying installation..."
echo ""

# Check if it's in PATH
if command -v docker-compose &> /dev/null; then
    echo "  ✓ docker-compose found in PATH"
else
    echo "  ! docker-compose NOT in PATH"
    echo "    Adding /usr/local/bin to PATH..."
    export PATH="/usr/local/bin:$PATH"
fi

# Check version
VERSION=$(docker-compose --version)
echo "  ✓ Version: $VERSION"

if [[ $VERSION == *"v2"* ]]; then
    echo ""
    echo "======================================================================"
    echo "✓ SUCCESS! Docker Compose v2 is installed"
    echo "======================================================================"
    echo ""
    echo "Next steps:"
    echo "  1. Navigate to deployment directory:"
    echo "     cd ~/project/ayna-pod-recommender/deployment/docker"
    echo ""
    echo "  2. Clean up old containers:"
    echo "     sudo docker-compose down -v"
    echo ""
    echo "  3. Start the application:"
    echo "     sudo docker-compose up -d"
    echo ""
    echo "  4. Check status:"
    echo "     sudo docker-compose ps"
    echo ""
else
    echo ""
    echo "======================================================================"
    echo "⚠ WARNING: Still seeing old version"
    echo "======================================================================"
    echo ""
    echo "The system may have a cached old version. Try:"
    echo "  1. Close and reopen terminal"
    echo "  2. Run: hash -r"
    echo "  3. Run: docker-compose --version"
    echo ""
    echo "Or explicitly use: /usr/local/bin/docker-compose --version"
    echo ""
fi
