# macOS Bluetooth Setup Script

# This script helps set up Bluetooth permissions for DeezChat on macOS

set -e

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo "\033[${color}m${message}\033[0m"
}

print_success() {
    print_status "32" "✅ $1"
}

print_info() {
    print_status "34" "ℹ️  $1"
}

print_warning() {
    print_status "33" "⚠️  $1"
}

print_error() {
    print_status "31" "❌ $1"
}

print_header() {
    echo ""
    print_status "35" "🍏  $1"
    echo "========================================"
}

print_header "macOS Bluetooth Setup for DeezChat"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is for macOS only"
    echo "Detected OS: $OSTYPE"
    exit 1
fi

print_info "macOS system detected"

# Check if System Preferences app exists
if command -v osascript >/dev/null; then
    print_info "Checking System Preferences availability..."
    if osascript -e 'tell application "System Preferences" to get name' 2>/dev/null | grep -q "System Preferences"; then
        print_success "System Preferences is available"
    else
        print_warning "System Preferences not accessible via AppleScript"
    fi
else
    print_warning "osascript not available"
fi

# Check if Bluetooth exists
if system_profiler SPBluetoothDataType 2>/dev/null | grep -q "Bluetooth"; then
    print_success "Bluetooth hardware detected"
else
    print_error "No Bluetooth hardware found"
    print_warning "DeezChat may not function properly without Bluetooth"
fi

# Check BlueZ availability (for Linux systems that might run this)
if command -v bluetoothctl >/dev/null 2>/dev/null; then
    if bluetoothctl --version >/dev/null 2>&1 | grep -q "BlueZ"; then
        print_info "BlueZ is available (for future Linux support)"
    fi
fi

# Open System Preferences to Bluetooth section
print_info "Opening System Preferences to Bluetooth settings..."

try_open_preferences() {
    # Try different methods to open System Preferences
    if command -v osascript >/dev/null 2>&1; then
        # Method 1: AppleScript
        osascript -e 'tell application "System Preferences" to activate paneid "com.apple.preference.security" &>/dev/null' && \
        osascript -e 'tell application "System Preferences" to set current pane to pane "com.apple.preference.security"' &>/dev/null
        return 0
    elif command -v open >/dev/null 2>&1; then
        # Method 2: open command
        open "x-apple.systempreferences:com.apple.preference.security" 2>/dev/null
        return 0
    fi
    return 1
}

# Try to open preferences
if try_open_preferences; then
    print_success "System Preferences opened successfully"
    print_info "Please follow these steps:"
    echo ""
    echo "📍  Navigate to Security & Privacy section"
    echo "🔍  Select 'Privacy' tab"
    echo "📡  Scroll down to 'Bluetooth' section"
    echo "🔘  Check the following boxes:"
    echo "   ☑  Bluetooth Sharing"
    echo "   ☑  Allow Bluetooth devices to connect to this computer"
    echo ""
    print_warning "You may need to enter your password to make these changes"
else
    print_error "Could not open System Preferences automatically"
    print_info "Please manually:"
    echo "  1. Open System Preferences"
    echo "  2. Go to Security & Privacy"
    echo "  3. Select 'Privacy' tab" 
    echo "  4. Scroll to 'Bluetooth' section"
    echo "  5. Enable Bluetooth Sharing and device connection"
fi

# Provide instructions for BitChat specifically
print_header "BitChat-Specific Bluetooth Setup"

print_info "For optimal BitChat connectivity with DeezChat:"
echo ""
echo "🔧  Bluetooth Configuration:"
echo "   ☑  Enable Bluetooth (if not already enabled)"
echo "   ☑  Turn on 'Discoverable' mode"
echo "   ☑  Allow nearby devices to discover this computer"
echo ""
echo "📱  BitChat App Setup:"
echo "   1. Open your BitChat app on iOS/Android"
echo "   2. Enable Bluetooth on your mobile device"
echo "   3. Make sure BitChat has Bluetooth permissions"
echo "   4. Put devices within 10-20 feet (3-6 meters)"
echo ""
echo "🔍  Troubleshooting:"
echo "   • If devices don't discover each other, restart Bluetooth on both"
echo "   • Clear Bluetooth cache if needed"
echo "   • Try moving devices closer together initially"
echo "   • Ensure no other Bluetooth devices are interfering"
echo ""

# Check if we can verify permissions were granted
sleep 2

print_header "Bluetooth Permission Verification"

# Check if Bluetooth is enabled (basic check)
if command -v defaults >/dev/null 2>/dev/null; then
    bluetooth_state=$(defaults read com.apple.Bluetooth 2>/dev/null | grep -c "BluetoothEnabled" || echo "0")
    if [[ "$bluetooth_state" == "1" ]]; then
        print_success "Bluetooth appears to be enabled"
    else
        print_warning "Bluetooth may not be enabled in System Preferences"
    fi
else
    print_info "Could not verify Bluetooth status automatically"
fi

# Check for Bluetooth discovery permissions
if command -v defaults >/dev/null 2>/dev/null; then
    discovery_state=$(defaults read com.apple.Bluetooth 2>/dev/null | grep -c "Discoverable" || echo "0")
    if [[ "$discovery_state" == "1" ]]; then
        print_success "Bluetooth discovery appears to be enabled"
    else
        print_info "Bluetooth discovery may need to be enabled in System Preferences"
    fi
else
    print_info "Could not verify discovery status automatically"
fi

print_header "Next Steps for DeezChat"

print_info "🚀  Start the Electron DeezChat application:"
echo "     - Click 'Start DeezChat' button in the app"
echo "     - The app will automatically request Bluetooth permissions if needed"
echo ""
print_info "📡  The app will:"
echo "     • Scan for BitChat peers using Bluetooth LE"
echo "     • Display discovered peers with their fingerprints"
echo "     • Show connection status"
echo "     • Provide terminal-style chat interface"
echo ""
print_info "🔐  Security Features:"
echo "     • Uses Noise Protocol encryption (same as BitChat iOS/Android)"
echo "     • End-to-end encryption for private messages"
echo "     • No phone numbers or accounts required"
echo "     • Works entirely offline within Bluetooth range"
echo ""

print_success "macOS Bluetooth setup completed!"
echo ""
print_info "🌐  For technical support or updates:"
echo "     • GitHub: https://github.com/deezchat/deezchat"
echo "     • Issues: https://github.com/deezchat/deezchat/issues"
echo ""
print_status "32" "📱 DeezChat + BitChat: Decentralized Bluetooth Mesh Chat"