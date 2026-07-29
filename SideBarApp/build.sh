#!/bin/bash

# Exit on error
set -e

APP_NAME="SideBarApp"
APP_BUNDLE="$APP_NAME.app"
MACOS_DIR="$APP_BUNDLE/Contents/MacOS"
RESOURCES_DIR="$APP_BUNDLE/Contents/Resources"

echo "Building executable..."
swift build -c release

echo "Creating App Bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

echo "Copying executable..."
cp ".build/release/$APP_NAME" "$MACOS_DIR/"

echo "Creating Info.plist..."
cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.sidebay.sidebarapp</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/> <!-- Make it a background/menu bar app so no dock icon -->
    <key>NSScreenCaptureUsageDescription</key>
    <string>This app needs screen capture access to record the screen.</string>
</dict>
</plist>
EOF

echo "App Bundle created at $APP_BUNDLE"
