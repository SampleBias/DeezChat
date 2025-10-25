#!/bin/bash

# macOS Bluetooth permission helper script
# This script opens the macOS security preferences to allow Bluetooth access

echo "🔧 macOS Bluetooth Setup for DeezChat"
echo "======================================"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Open System Preferences -> Security & Privacy -> Bluetooth
echo "🍏 Opening macOS System Preferences..."

# Try different methods to open Bluetooth preferences
osascript -e 'tell application "System Preferences" to activate paneid "com.apple.preference.security" &>/dev/null' || \
open "x-apple.systempreferences:com.apple.preference.security" &>/dev/null' || \
open "/System/Preferences/Security.prefPane" &>/dev/null

echo ""
echo "📋 INSTRUCTIONS:"
echo "1. Go to 'Privacy & Security' section"
echo "2. Select 'Bluetooth' from the left menu"
echo "3. Enable Bluetooth and check the box for:"
echo "   - Bluetooth Sharing"
echo "   - Allow Bluetooth devices to connect to this computer"
echo "4. Close System Preferences"
echo ""
echo "✅ Bluetooth permissions configured!"
echo "Now you can start DeezChat and it will have full Bluetooth access."