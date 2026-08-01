#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
flatpak-builder --force-clean --user build org.sidebay.SideBay.json
flatpak-builder --user --install --force-clean build org.sidebay.SideBay.json
echo "Installed. Run: flatpak run org.sidebay.SideBay"
