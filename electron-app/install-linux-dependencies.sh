# Install Linux dependencies for DeezChat
# Run as root or with sudo

set -e

print_status() {
    echo "📦 DeezChat Linux Dependency Installer"
    echo "======================================="
}

print_error() {
    echo "❌ ERROR: $1"
    exit 1
}

print_success() {
    echo "✅ $1"
}

print_info() {
    echo "ℹ️  $1"
}

print_status

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root or with sudo"
    echo "Usage: sudo bash install-linux-dependencies.sh"
fi

print_info "Updating package repositories..."
apt-get update

# Install Bluetooth and development tools
print_info "Installing Bluetooth development tools..."
apt-get install -y \
    bluetooth \
    bluez-tools \
    libbluetooth-dev \
    libglib2.0-dev \
    build-essential \
    pkg-config \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    udev \
    systemd

# Install additional system dependencies
print_info "Installing additional system dependencies..."
apt-get install -y \
    libusb-1.0-0-dev \
    libudev-dev \
    libffi-dev \
    libssl-dev \
    curl \
    wget \
    git

# Install Python packages
print_info "Installing Python packages..."

# Upgrade pip first
python3 -m pip install --upgrade pip

# Install core Python dependencies for DeezChat
python3 -m pip install \
    bleak>=0.20.0 \
    cryptography>=3.4.8 \
    aioconsole>=0.6.0 \
    lz4>=3.1.0 \
    pyyaml>=6.0 \
    aiosqlite>=0.17.0

# Install development dependencies
python3 -m pip install \
    pybloom-live>=4.0.0 \
    black>=22.0.0 \
    isort>=5.10.0 \
    flake8>=5.0.0 \
    pytest>=7.0.0 \
    pytest-asyncio>=0.21.0 \
    pytest-cov>=4.0.0 \
    mypy>=1.0.0

# Add current user to bluetooth group if not already member
print_info "Adding current user to bluetooth group..."
if ! groups $SUDO_USER | grep -q bluetooth; then
    usermod -aG bluetooth $SUDO_USER
    print_success "Added $SUDO_USER to bluetooth group"
else
    print_info "User $SUDO_USER is already in bluetooth group"
fi

# Create udev rules for Bluetooth device access
print_info "Creating udev rules for DeezChat..."
cat > /etc/udev/rules.d/99-deezchat-bluetooth.rules << 'EOF'
# DeezChat Bluetooth permissions
KERNEL=="hci[0-9]*", SUBSYSTEM=="bluetooth", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# Allow access to Bluetooth devices for DeezChat
SUBSYSTEM=="bluetooth", KERNEL=="rfcomm*", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# USB Bluetooth device permissions
SUBSYSTEM=="usb", ATTRS{idVendor}=="0x0a12", ATTRS{idProduct}=="0x0001", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# Generic Bluetooth adapter permissions
SUBSYSTEM=="bluetooth", ATTRS{address}=="*", MODE="0666", GROUP="bluetooth", TAG+="deezchat"

# Allow D-Bus access for Bluetooth operations
SUBSYSTEM=="d-bus", ENV{DBUS_SESSION_BUS_ADDRESS}=="*", TAG+="deezchat"
EOF

print_success "Created udev rules for DeezChat"

# Reload udev rules
udevadm control --reload-rules
print_success "Reloaded udev rules"

# Enable and start Bluetooth services
print_info "Configuring Bluetooth services..."
systemctl enable bluetooth
systemctl start bluetooth

# Check if Bluetooth services are running
if systemctl is-active --quiet bluetooth; then
    print_success "Bluetooth service is active"
else
    print_warning "Bluetooth service may not be running"
fi

# Enable and start udev
systemctl enable udev
systemctl restart udev

# Check BlueZ version
if command -v bluetoothctl >/dev/null 2>&1 | grep -q "BlueZ"; then
    bluez_version=$(bluetoothctl --version | head -1)
    print_success "BlueZ version: $bluez_version"
else
    print_warning "BlueZ command not found"
fi

# Test Bluetooth functionality
print_info "Testing Bluetooth functionality..."
if command -v bluetoothctl >/dev/null 2>&1; then
    if timeout 5 bluetoothctl list 2>/dev/null | grep -q "Controller"; then
        print_success "Bluetooth controller detected"
    else
        print_warning "No Bluetooth controller detected"
    fi
else
    print_warning "bluetoothctl command not available"
fi

# Create systemd service file for DeezChat (optional)
print_info "Creating systemd service template..."
cat > /etc/systemd/system/deezchat.service << 'EOF'
[Unit]
Description=DeezChat - BitChat Python Client
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
ExecStart=/opt/venv/bin/python -m deezchat
WorkingDirectory=/opt/deezchat
Environment=PYTHONPATH=/opt/venv/bin
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

print_success "Created systemd service template: /etc/systemd/system/deezchat.service"

# Set up virtual environment for DeezChat (optional)
print_info "Setting up Python virtual environment..."
VENV_PATH="/opt/venv"

if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
    print_success "Created virtual environment at $VENV_PATH"
else
    print_info "Virtual environment already exists at $VENV_PATH"
fi

# Install DeezChat in virtual environment
$VENV_PATH/bin/pip install --upgrade pip
$VENV_PATH/bin/pip install -e .

print_success "Installed DeezChat in virtual environment"

# Create DeezChat system user (optional)
if ! id -u deezchat &>/dev/null; then
    print_info "Creating deezchat system user..."
    useradd -r -s /bin/false deezchat
    usermod -a -G bluetooth,users deezchat
    print_success "Created deezchat system user"
else
    print_info "deezchat system user already exists"
fi

print_status
print_success "Linux dependency installation completed!"
echo ""
echo "📱 DeezChat Setup Summary:"
echo "  • Bluetooth development tools installed"
echo "  • Python dependencies installed"
echo "  • User added to bluetooth group"
echo "  • udev rules configured"
echo "  • Virtual environment created"
echo "  • Systemd service template created"
echo ""
echo "🚀 Next Steps:"
echo "  1. Reboot or log out/in to apply group changes"
echo "  2. Run the Electron DeezChat app"
echo "  3. The app will have full Bluetooth access"
echo ""
echo "🔧 Bluetooth Troubleshooting:"
echo "  • Check: systemctl status bluetooth"
echo "  • Start: sudo systemctl start bluetooth"
echo "  • List: bluetoothctl list"
echo "  • Scan: sudo bluetoothctl scan"
echo "  • Test: hciconfig -a"
echo ""
print_success "Setup completed! DeezChat is ready for Linux."