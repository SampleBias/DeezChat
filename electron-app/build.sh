#!/bin/bash

# DeezChat Electron Build Script
# Cross-platform build automation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}🔧 DeezChat Electron Builder${NC}"
    echo "======================================"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Node.js version is suitable
check_node_version() {
    if command_exists node; then
        NODE_VERSION=$(node -v | cut -d' ' -f2 | cut -d' -f1)
        REQUIRED_VERSION="18.0.0"
        
        if [ "$(printf '%s\n' "$NODE_VERSION" "$REQUIRED_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
            print_success "Node.js found: $NODE_VERSION (>= $REQUIRED_VERSION)"
        else
            print_error "Node.js version too old: $NODE_VERSION (required >= $REQUIRED_VERSION)"
            print_info "Please upgrade Node.js from: https://nodejs.org/"
            return 1
        fi
    else
        print_error "Node.js not found"
        print_info "Please install Node.js from: https://nodejs.org/"
        return 1
    fi
    return 0
}

# Function to check if npm is available
check_npm() {
    if command_exists npm; then
        NPM_VERSION=$(npm -v | cut -d' ' -f2 | cut -d' -f1)
        print_success "npm found: $NPM_VERSION"
    else
        print_error "npm not found"
        print_info "Please install npm (comes with Node.js)"
        return 1
    fi
    return 0
}

# Function to create app icons
create_icons() {
    print_info "Creating app icons..."
    
    # Create assets directory if it doesn't exist
    mkdir -p assets
    
    # Create simple SVG icon (512x512)
    cat > assets/icon.svg << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <!-- Orange background -->
  <rect width="512" height="512" fill="#ff6b35"/>
  
  <!-- BitChat text -->
  <text x="256" y="240" font-family="Arial, sans-serif" font-size="48" font-weight="bold" text-anchor="middle" fill="white">BITCHAT</text>
  
  <!-- Bluetooth symbol -->
  <path d="M128 160c-13.3 0-24 10.7-24 24v24c0 26.7 21.3 48 48 48h80c26.7 0 48-10.7 48-24v-24c0-26.7-21.3-48-48-48zm128 48c0-13.3 0-24 10.7-24 24v24c0 26.7 21.3 48 48 48h80c26.7 0 48-10.7 48-24v-24c0-26.7-21.3-48-48-48zm64 64c0-17.7 0-32 14.3-32 32v32c0 35.3 28.7 64 64 64h80c17.7 0 32-14.3 32-32v-32c0-35.3-28.7-64-64-64z" fill="white"/>
  
  <!-- Network connections -->
  <circle cx="180" cy="280" r="8" fill="none" stroke="white" stroke-width="4"/>
  <circle cx="332" cy="280" r="8" fill="none" stroke="white" stroke-width="4"/>
  <line x1="180" y1="280" x2="332" y2="280" stroke="white" stroke-width="4"/>
  <line x1="200" y1="260" x2="312" y2="260" stroke="white" stroke-width="4"/>
  <line x1="200" y1="300" x2="312" y2="300" stroke="white" stroke-width="4"/>
</svg>
EOF

    # Create PNG versions using ImageMagick or librsvg if available
    if command_exists rsvg-convert; then
        print_info "Converting SVG to PNG..."
        rsvg-convert -w 512 -h 512 assets/icon.svg assets/icon.png
        rsvg-convert -w 256 -h 256 assets/icon.svg assets/icon-256.png
        rsvg-convert -w 128 -h 128 assets/icon.svg assets/icon-128.png
        rsvg-convert -w 64 -h 64 assets/icon.svg assets/icon-64.png
        rsvg-convert -w 32 -h 32 assets/icon.svg assets/icon-32.png
    elif command_exists convert; then
        print_info "Converting SVG to PNG using ImageMagick..."
        convert assets/icon.svg -resize 512x512 assets/icon.png
        convert assets/icon.svg -resize 256x256 assets/icon-256.png
        convert assets/icon.svg -resize 128x128 assets/icon-128.png
        convert assets/icon.svg -resize 64x64 assets/icon-64.png
        convert assets/icon.svg -resize 32x32 assets/icon-32.png
    else
        print_warning "SVG to PNG conversion tools not found"
        print_info "Please install rsvg-convert (librsvg) or ImageMagick"
    fi
    
    # Create Windows ICO
    if command_exists convert; then
        print_info "Creating Windows ICO file..."
        convert assets/icon-256.png assets/icon-256.png assets/icon-128.png assets/icon-64.png assets/icon-32.png assets/icon.ico
    else
        print_warning "ICO creation not available - please install ImageMagick"
    fi
    
    print_success "Icon files created in assets/"
}

# Function to install npm dependencies
install_dependencies() {
    print_info "Installing npm dependencies..."
    
    if npm install; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        return 1
    fi
}

# Function to build for current platform
build_current_platform() {
    PLATFORM=$(node -p "process.platform")
    print_info "Building for platform: $PLATFORM"
    
    case $PLATFORM in
        darwin)
            npm run build:mac
            ;;
        linux)
            npm run build:linux
            ;;
        win32)
            npm run build:win
            ;;
        *)
            print_error "Unsupported platform: $PLATFORM"
            return 1
            ;;
    esac
}

# Function to build for all platforms
build_all_platforms() {
    print_info "Building for all platforms..."
    
    # Build for all platforms
    npm run build:mac || print_error "macOS build failed"
    npm run build:linux || print_error "Linux build failed"
    npm run build:win || print_error "Windows build failed"
    npm run build:portable || print_error "Portable build failed"
}

# Function to clean build artifacts
clean() {
    print_info "Cleaning build artifacts..."
    
    if [ -d "dist" ]; then
        rm -rf dist
        print_success "Removed dist/"
    fi
    
    if [ -d "release" ]; then
        rm -rf release
        print_success "Removed release/"
    fi
    
    if [ -d "node_modules" ]; then
        read -p "This will remove node_modules. Are you sure? (y/N): " choice
        if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
            rm -rf node_modules
            print_success "Removed node_modules/"
        else
            print_info "Keeping node_modules"
        fi
    fi
}

# Function to run tests
run_tests() {
    print_info "Running tests..."
    
    if npm test; then
        print_success "All tests passed"
    else
        print_error "Tests failed"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "DeezChat Electron Build Script"
    echo "============================"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  setup              - Setup environment and create icons"
    echo "  deps                - Install dependencies"
    echo "  icons               - Create app icons"
    echo "  clean               - Clean build artifacts"
    echo "  build               - Build for current platform"
    echo "  build:all           - Build for all platforms"
    echo "  build:mac           - Build for macOS"
    echo "  build:linux          - Build for Linux"
    echo "  build:win            - Build for Windows"
    echo "  build:portable      - Build portable executables"
    echo "  test                - Run tests"
    echo "  dev                 - Start development server"
    echo "  dist                - Build and create distribution"
    echo "  help                - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 setup build      # Setup, create icons, and build"
    echo "  $0 clean build:all  # Clean and build for all platforms"
    echo "  $0 dev               # Start development server"
    echo ""
    echo "Environment Variables:"
    echo "  NODE_ENV=development    # Enable development mode"
    echo "  DEBUG=true              # Enable debug logging"
}

# Main script logic
main() {
    local command=${1:-"help"}
    
    print_status
    
    # Change to script directory
    cd "$(dirname "$0")"
    
    case $command in
        setup)
            create_icons
            ;;
        deps)
            install_dependencies
            ;;
        icons)
            create_icons
            ;;
        clean)
            clean
            ;;
        build)
            build_current_platform
            ;;
        build:all)
            build_all_platforms
            ;;
        build:mac)
            npm run build:mac
            ;;
        build:linux)
            npm run build:linux
            ;;
        build:win)
            npm run build:win
            ;;
        build:portable)
            npm run build:portable
            ;;
        test)
            run_tests
            ;;
        dev)
            npm run dev
            ;;
        dist)
            build_all_platforms
            ;;
        help)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"