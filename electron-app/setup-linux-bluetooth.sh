# Linux BlueZ Setup for DeezChat

# This script helps set up BlueZ (Bluetooth stack) for DeezChat on Linux

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
    print_status "35" "🔧 $1"
    echo "========================================"
}

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* && "$OSTYPE" != "linux"* ]]; then
    print_error "This script is for Linux only"
    echo "Detected OS: $OSTYPE"
    exit 1
fi

print_header "Linux BlueZ Setup for DeezChat"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root is not recommended for Bluetooth operations"
    print_info "Consider running as a regular user for better security"
fi

# Check BlueZ installation
print_info "Checking BlueZ installation..."

if command -v systemctl >/dev/null && systemctl is-active --quiet bluetooth 2>/dev/null; then
    print_success "BlueZ is active and running (systemctl)"
elif command -v service >/dev/null && service bluetooth status 2>/dev/null | grep -q "active\|running"; then
    print_success "BlueZ is active and running (service)"
elif command -v bluetoothctl >/dev/null && bluetoothctl --version >/dev/null 2>&1 | grep -q "BlueZ"; then
    print_info "BlueZ is installed but may not be running"
else
    print_error "BlueZ does not appear to be installed or running"
    print_info "Please install BlueZ:"
    echo "  Ubuntu/Debian: sudo apt-get install bluetooth bluez-tools"
    echo "  Fedora: sudo dnf install bluez bluez-tools"
    echo "  Arch: sudo pacman -S bluez"
    echo "  openSUSE: sudo zypper install bluez"
    exit 1
fi

# Check Bluetooth hardware
print_info "Checking for Bluetooth hardware..."

if lsusb 2>/dev/null | grep -iq bluetooth || \
   lsusb 2>/dev/null | grep -iq "0a12:1"; then
    print_success "Bluetooth hardware detected via USB"
elif ls /sys/class/bluetooth/ 2>/dev/null | grep -q "hci"; then
    print_success "Bluetooth hardware detected via hciX interfaces"
    bluetooth_count=$(ls /sys/class/bluetooth/ | grep -c hci)
    print_info "Found $bluetooth_count Bluetooth interfaces"
else
    print_warning "No Bluetooth hardware detected"
    print_info "This could mean:"
    echo "  • Bluetooth is disabled in BIOS/UEFI"
    echo "  • No Bluetooth adapter present"
    echo "  • Virtual environment without Bluetooth support"
    print_info "DeezChat will still run but may not discover peers"
fi

# Check user's membership in Bluetooth group
print_info "Checking user Bluetooth group membership..."

if groups $USER | grep -q bluetooth; then
    print_success "User $USER is in the bluetooth group"
else
    print_warning "User $USER is NOT in the bluetooth group"
    print_info "This will prevent Bluetooth operations"
    print_info "Solutions:"
    echo "  sudo usermod -aG bluetooth $USER    # Add user to group"
    echo "  sudo adduser $USER bluetooth        # Alternative method"
    echo "  logout && login                       # Re-login for group changes"
fi

# Check required packages
print_info "Checking for required packages..."

required_packages=("python3" "python3-pip" "python3-venv" "python3-dev" "libbluetooth-dev" "bluez-tools" "libglib2.0-dev" "pkg-config")

missing_packages=()
for package in "${required_packages[@]}"; do
    if ! dpkg -l | grep -q "ii  $package "; then
        missing_packages+=("$package")
    fi
done

if [[ ${#missing_packages[@]} -gt 0 ]]; then
    print_warning "Missing required packages: ${missing_packages[*]}"
    print_info "Install with:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install ${missing_packages[*]}"
    echo ""
    print_info "For Debian/Ubuntu systems, you may need:"
    echo "  sudo apt-get install python3-dev python3-pip"
    echo "  sudo apt-get install libbluetooth-dev libglib2.0-dev pkg-config"
    echo "  sudo apt-get install bluez-tools"
else
    print_success "All required packages are installed"
fi

# Test Bluetooth operations
print_info "Testing basic Bluetooth operations..."

if command -v bluetoothctl >/dev/null 2>&1; then
    if bluetoothctl --version >/dev/null 2>&1 | grep -q "BlueZ"; then
        print_info "Bluetooth control tool (bluetoothctl) is available"
        
        # Try to get adapter info
        if timeout 5 bluetoothctl show 2>/dev/null | grep -q "Adapter"; then
            adapter_info=$(timeout 5 bluetoothctl show | grep -A 5 "Adapter" || echo "Available")
            print_success "Bluetooth adapter information accessible"
            print_info "Adapter: $adapter_info"
        else
            print_info "Bluetooth adapter check timed out (may need to be started)"
        fi
    else
        print_warning "bluetoothctl available but may not be BlueZ compatible"
    fi
else
    print_warning "bluetoothctl not found - please install bluez-tools"
fi

# Check for device visibility settings
print_info "Checking device visibility settings..."

if command -v dbus-send >/dev/null 2>/dev/null; then
    print_success "D-Bus communication available"
else
    print_warning "D-Bus not available - may affect Bluetooth operations"
fi

# Create udev rule for DeezChat (if doesn't exist)
print_info "Creating udev rule for DeezChat..."

UDEV_RULE="/etc/udev/rules.d/99-deezchat-bluetooth.rules"
UDEV_RULE_CONTENT='# DeezChat Bluetooth permissions
# This rule ensures proper permissions for DeezChat to access Bluetooth

KERNEL=="hci[0-9]*", SUBSYSTEM=="bluetooth", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# Give Bluetooth devices proper permissions
SUBSYSTEM=="bluetooth", ATTR{address}=="*", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# Allow D-Bus access for Bluetooth operations
SUBSYSTEM=="bluetooth", KERNEL=="rfcomm", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

SUBSYSTEM=="dbus", ENV{DBUS_SESSION_BUS_ADDRESS}=="*", TAG+="deezchat"
'

if [[ ! -f "$UDEV_RULE" ]]; then
    if [[ $EUID -eq 0 ]]; then
        echo "$UDEV_RULE_CONTENT" | sudo tee "$UDEV_RULE" >/dev/null
        print_success "Created udev rule at $UDEV_RULE"
        print_info "Reloading udev rules..."
        sudo udevadm control --reload-rules
        print_success "udev rules reloaded"
    else
        print_warning "Cannot create udev rule without root privileges"
        print_info "Please run this as root or create the file manually:"
        echo "sudo tee $UDEV_RULE"
        echo "$UDEV_RULE_CONTENT"
    fi
else
    print_info "udev rule already exists at $UDEV_RULE"
fi

# Check systemd service configuration
print_info "Checking systemd Bluetooth service..."

if command -v systemctl >/dev/null; then
    if systemctl is-active --quiet bluetooth; then
        bluetooth_status=$(systemctl is-enabled bluetooth 2>/dev/null || echo "dynamic")
        print_info "Bluetooth service status: $bluetooth_status"
        
        if [[ "$bluetooth_status" == "disabled" ]]; then
            print_warning "Bluetooth service is disabled"
            print_info "Enable with: sudo systemctl enable --now bluetooth"
        fi
    else
        print_warning "Bluetooth service is not running"
        print_info "Start with: sudo systemctl start bluetooth"
    fi
else
    print_info "No systemd available (or not on this Linux distribution)"
fi

# Provide platform-specific troubleshooting
print_header "Platform-Specific Troubleshooting"

print_info "For Ubuntu/Debian:"
echo "  • Install: sudo apt-get install bluetooth bluez-tools"
echo "  • Start: sudo systemctl start bluetooth"
echo "  • Enable: sudo systemctl enable bluetooth"
echo "  • Check: bluetoothctl show"
echo ""

print_info "For Fedora/RHEL:"
echo "  • Install: sudo dnf install bluez"
echo "  • Enable and start: sudo systemctl enable --now bluetooth"
echo "  • Firewall: sudo firewall-cmd --permanent --add-service=bluetooth"
echo "  • Check: bluetoothctl show"
echo ""

print_info "For Arch Linux:"
echo "  • Install: sudo pacman -S bluez"
echo "  • Enable and start: sudo systemctl enable --now bluetooth"
echo "  • Check: bluetoothctl show"
echo ""

print_info "For openSUSE:"
echo "  • Install: sudo zypper install bluez"
echo "  • Enable and start: sudo systemctl enable --now bluetooth"
echo "  • Check: bluetoothctl show"
echo ""

print_info "For Generic Linux (without systemd):"
echo "  • Start Bluetooth: sudo service bluetooth start"
echo "  • Enable on boot: sudo chkconfig bluetooth on"
echo "  • Check: bluetoothctl show"
echo ""

print_header "Next Steps for DeezChat"

print_success "Linux BlueZ setup completed!"
echo ""
print_info "🚀  Start the Electron DeezChat application:"
echo "      ./deezchat"
echo ""
print_info "📱  The application will:"
echo "      • Check BlueZ status automatically"
echo "      • Request Bluetooth permissions if needed"
echo "      • Scan for BitChat peers using bluetoothctl"
echo "      • Display discovered peers in the UI"
echo ""
print_info "🔧  Manual troubleshooting (if needed):"
echo "      • sudo systemctl status bluetooth   # Check service status"
echo "      • sudo bluetoothctl show             # List adapters"
echo "      • sudo hciconfig -a             # List devices"
echo "      • sudo bluetoothctl scan           # Scan for devices"
echo "      • sudo rfkill unblock bluetooth     # Reset Bluetooth"
echo ""
print_success "🔒  Security Features:"
echo "      • Uses Noise Protocol encryption (same as BitChat)"
echo "      • Runs as regular user (unless sudo used)"
echo "      • No phone numbers or accounts required"
echo "      • Works entirely within local Bluetooth range"
echo ""
print_info "🌐  For help or issues:"
echo "      • GitHub: https://github.com/deezchat/deezchat/issues"
echo "      • Documentation: https://github.com/deezchat/deezchat"
echo ""
print_status "35" "🔧 BlueZ + DeezChat = Linux Bluetooth Mesh Chat"