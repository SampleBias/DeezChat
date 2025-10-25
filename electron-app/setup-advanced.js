#!/usr/bin/env node

/**
 * DeezChat Setup Manager
 * Handles platform-specific setup for DeezChat Electron app
 */

const { spawn, execSync } = require('child_process');
const { existsSync } = require('fs');
const { join, dirname } = require('path');
const https = require('https');
const { createWriteStream } = require('fs');

class DeezChatSetupManager {
    constructor() {
        this.setupDir = __dirname;
        this.deezchatDir = dirname(this.setupDir);
        this.pythonPath = null;
        this.platform = process.platform;
        this.arch = process.arch;
    }

    async findPython() {
        console.log('🔍 Finding Python installation...');
        
        const pythonCommands = process.platform === 'win32' 
            ? ['python', 'python3', 'py', 'python.exe']
            : ['python3', 'python', '/usr/bin/python3', '/usr/bin/python'];
        
        for (const cmd of pythonCommands) {
            try {
                const result = execSync(`${cmd} --version`, { 
                    encoding: 'utf8', 
                    timeout: 5000 
                });
                
                if (result.stdout) {
                    this.pythonPath = cmd;
                    console.log(`✅ Found Python: ${cmd}`);
                    return true;
                }
            } catch (error) {
                // Command not found
            }
        }
        
        return false;
    }

    async installPython() {
        console.log('📦 Installing Python...');
        
        const urls = {
            'win32': {
                x64: 'https://www.python.org/ftp/python/3.12/python-3.12.1-amd64.exe',
                x32: 'https://www.python.org/ftp/python/3.12/python-3.12.1.exe'
            },
            'darwin': {
                x64: 'https://www.python.org/ftp/python/3.12/python-3.12.1-macos11.pkg',
                arm64: 'https://www.python.org/ftp/python/3.12/python-3.12.1-macos11.pkg'
            },
            'linux': {
                x64: 'https://www.python.org/ftp/python/3.12/Python-3.12.1.tgz'
            }
        };

        const os = this.platform;
        const arch = this.arch === 'arm64' ? 'arm64' : 'x64';
        
        if (!urls[os] || !urls[os][arch]) {
            throw new Error(`Unsupported platform/arch: ${os}/${arch}`);
        }

        const url = urls[os][arch];
        const filename = os === 'win32' ? 'python-installer.exe' : 'python-installer.pkg';
        const outputPath = join(this.setupDir, filename);

        console.log(`📥 Downloading Python for ${os}/${arch}...`);
        
        // Download Python
        await this.downloadFile(url, outputPath);
        
        console.log(`🚀 Installing Python...`);
        
        if (os === 'win32') {
            // Run installer silently on Windows
            await new Promise((resolve, reject) => {
                const installer = spawn(outputPath, ['/quiet', 'InstallAllUsers=0', 'PrependPath=0']);
                
                installer.on('close', (code) => {
                    if (code === 0) {
                        resolve();
                    } else {
                        reject(new Error(`Python installer failed with code: ${code}`));
                    }
                });
                
                installer.on('error', reject);
            });
        } else if (os === 'darwin') {
            // Run installer on macOS
            execSync(`open "${outputPath}"`);
        } else {
            // Extract and install on Linux
            execSync(`tar -xzf "${outputPath}" -C "${this.setupDir}"`);
            
            const pythonDir = join(this.setupDir, 'python3');
            
            // Build and install Python
            execSync(`cd "${pythonDir}" && ./configure --enable-optimizations --prefix=/opt/python3`, { stdio: 'inherit' });
            execSync(`cd "${pythonDir}" && make -j$(nproc)`, { stdio: 'inherit' });
            execSync(`sudo make altinstall`, { stdio: 'inherit' });
        }

        // Find Python after installation
        await this.findPython();
        
        return this.pythonPath !== null;
    }

    async downloadFile(url, outputPath) {
        return new Promise((resolve, reject) => {
            const file = createWriteStream(outputPath);
            
            https.get(url, (response) => {
                if (response.statusCode !== 200) {
                    reject(new Error(`HTTP ${response.statusCode}: ${url}`));
                    return;
                }
                
                response.pipe(file);
                
                file.on('finish', () => {
                    resolve();
                });
                
                file.on('error', (error) => {
                    reject(error);
                });
            }).on('error', (error) => {
                reject(error);
            });
        });
    }

    async installDeezChatDependencies() {
        if (!this.pythonPath) {
            throw new Error('Python not available');
        }

        console.log('📦 Installing DeezChat dependencies...');
        
        const pipCommand = this.platform === 'win32' ? 'pip' : 'pip3';
        const args = [
            'install', '--upgrade',
            'bleak>=0.20.0',
            'cryptography>=3.4.8',
            'aioconsole>=0.6.0',
            'lz4>=3.1.0',
            'pyyaml>=6.0',
            'aiosqlite>=0.17.0',
            'pybloom-live>=4.0.0',
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.0.0'
        ];

        return new Promise((resolve, reject) => {
            const installer = spawn(this.pythonPath, [
                '-m', 'pip'
            ].concat(args));
            
            installer.stdout.on('data', (data) => {
                process.stdout.write(data);
            });
            
            installer.stderr.on('data', (data) => {
                process.stderr.write(data);
            });
            
            installer.on('close', (code) => {
                if (code === 0) {
                    resolve();
                } else {
                    reject(new Error(`pip install failed with code: ${code}`));
                }
            });
            
            installer.on('error', (error) => {
                reject(error);
            });
        });
    }

    async createVirtualEnvironment() {
        console.log('🔧 Creating Python virtual environment...');
        
        const venvName = this.platform === 'win32' ? 'venv' : 'venv';
        const venvPath = join(this.setupDir, 'deezchat-venv');
        
        if (!existsSync(venvPath)) {
            execSync(`${this.pythonPath} -m ${venvName} ${venvPath}`, { stdio: 'inherit' });
        }
        
        return venvPath;
    }

    async setupBluetoothPlatform() {
        console.log(`🔍 Setting up Bluetooth for ${this.platform}...`);
        
        switch (this.platform) {
            case 'darwin':
                await this.setupMacOSBluetooth();
                break;
            case 'win32':
                await this.setupWindowsBluetooth();
                break;
            case 'linux':
                await this.setupLinuxBluetooth();
                break;
            default:
                console.warn(`⚠️  Unsupported platform: ${this.platform}`);
        }
    }

    async setupMacOSBluetooth() {
        console.log('🍎 macOS Bluetooth Setup...');
        
        // Check if Bluetooth is available
        try {
            const result = execSync('system_profiler SPBluetoothDataType', { encoding: 'utf8' });
            if (result.stdout.includes('Bluetooth') || result.stdout.includes('BluetoothLowEnergy')) {
                console.log('✅ macOS Bluetooth hardware detected');
            } else {
                console.warn('⚠️  No Bluetooth hardware detected via system profiler');
            }
        } catch (error) {
            console.warn('⚠️  Could not check Bluetooth availability:', error.message);
        }
        
        // Try to enable Bluetooth via system preferences
        try {
            execSync('open "x-apple.systempreferences:com.apple.preference.security"', { stdio: 'inherit' });
            console.log('🍏 Opened macOS Security & Privacy preferences');
        } catch (error) {
            console.warn('⚠️  Could not open System Preferences:', error.message);
        }
        
        // Show setup instructions
        console.log(`
📱 macOS Bluetooth Setup Instructions:
1. Go to System Preferences → Security & Privacy
2. Select "Privacy" tab
3. Choose "Bluetooth" from left menu
4. Enable:
   ☑  Bluetooth (if not already enabled)
   ☑  Allow Bluetooth devices to connect to this computer
5. Close System Preferences

🔧 For Enhanced Setup:
1. Enable "Bluetooth Sharing" for better device discovery
2. Keep devices within range (3-10 meters)
3. Restart Bluetooth if having issues

✅ Bluetooth should now be configured for DeezChat!
        `);
    }

    async setupWindowsBluetooth() {
        console.log('🪟 Windows Bluetooth Setup...');
        
        // Check if Bluetooth service is running
        try {
            const result = execSync('sc query bluetooth', { encoding: 'utf8' });
            if (result.stdout.includes('RUNNING')) {
                console.log('✅ Windows Bluetooth service is active');
            } else {
                console.warn('⚠️  Bluetooth service may not be running');
            }
        } catch (error) {
            console.warn('⚠️  Could not check Bluetooth service status:', error.message);
        }
        
        // Show setup instructions
        console.log(`
📱 Windows Bluetooth Setup Instructions:
1. Open Settings → Bluetooth & other devices
2. Ensure Bluetooth is turned ON
3. Select "More Bluetooth options"
4. Enable:
   ☑  Allow Bluetooth devices to find this PC
   ☑  Allow Bluetooth devices to connect to this PC
5. Click "Add Bluetooth or other device"

🔧 For Enhanced Setup:
1. Update Bluetooth drivers from manufacturer
2. Check Device Manager for Bluetooth adapter status
3. Restart Bluetooth service if having issues
4. Keep DeezChat in Windows Firewall exceptions

✅ Windows Bluetooth should now be configured for DeezChat!
        `);
    }

    async setupLinuxBluetooth() {
        console.log('🐧 Linux Bluetooth Setup...');
        
        // Check BlueZ installation
        try {
            const result = execSync('bluetoothctl --version', { encoding: 'utf8' });
            if (result.stdout.includes('BlueZ')) {
                console.log(`✅ BlueZ detected: ${result.stdout.split('\n')[0]}`);
            } else {
                console.warn('⚠️  BlueZ may not be properly installed');
            }
        } catch (error) {
            console.warn('⚠️  Could not check BlueZ status:', error.message);
        }
        
        // Show setup instructions
        console.log(`
📱 Linux BlueZ Setup Instructions:
1. Install BlueZ and development tools:
   sudo apt-get install bluetooth bluez-tools
   sudo apt-get install libbluetooth-dev
   sudo pacman -S bluez bluez-tools  # Arch
   sudo dnf install bluez  # Fedora

2. Check Bluetooth status:
   systemctl status bluetooth
   sudo systemctl start bluetooth
   sudo systemctl enable bluetooth

3. Add user to bluetooth group:
   sudo usermod -aG bluetooth $USER
   logout && login  # Required for group changes

4. Test Bluetooth functionality:
   bluetoothctl show
   bluetoothctl scan

🔧 For Enhanced Setup:
1. Enable bluetoothd service
2. Check if your Bluetooth adapter is supported
3. Update firmware from manufacturer website
4. Restart bluetoothd service if having issues

✅ Linux Bluetooth should now be configured for DeezChat!
        `);
        
        // Create a helper script for user
        const helperScript = `
#!/bin/bash
# Linux Bluetooth Helper for DeezChat

echo "🔍 Checking Bluetooth service..."
if systemctl is-active --quiet bluetooth; then
    echo "✅ Bluetooth service is active"
else
    echo "⚠️  Starting Bluetooth service..."
    sudo systemctl start bluetooth
fi

echo "🔍 Scanning for Bluetooth devices..."
if timeout 10 bluetoothctl scan; then
    echo "✅ Bluetooth scanning successful"
else
    echo "⚠️  Bluetooth scan failed"
fi

echo "📱 Bluetooth setup complete!"
        `;
        
        require('fs').writeFileSync(join(this.setupDir, 'setup-linux-helper.sh'), helperScript);
        execSync(`chmod +x "${join(this.setupDir, 'setup-linux-helper.sh')}"`);
    }

    async fullSetup() {
        console.log('🚀 Starting complete DeezChat setup...');
        
        try {
            // Step 1: Find or install Python
            const pythonFound = await this.findPython();
            if (!pythonFound) {
                console.log('Python not found, attempting installation...');
                const pythonInstalled = await this.installPython();
                if (!pythonInstalled) {
                    throw new Error('Failed to install Python');
                }
            }
            
            // Step 2: Create virtual environment
            await this.createVirtualEnvironment();
            
            // Step 3: Install DeezChat dependencies
            await this.installDeezChatDependencies();
            
            // Step 4: Setup Bluetooth platform-specific configurations
            await this.setupBluetoothPlatform();
            
            console.log('✅ DeezChat setup completed successfully!');
            console.log('\n📱 Next Steps:');
            console.log('1. Start the Electron DeezChat app');
            console.log('2. Grant Bluetooth permissions when prompted');
            console.log('3. Begin discovering BitChat peers');
            console.log('4. Start chatting with discovered peers');
            
        } catch (error) {
            console.error('❌ Setup failed:', error.message);
            process.exit(1);
        }
    }

    async quickSetup() {
        console.log('⚡ Running quick setup check...');
        
        await this.findPython();
        await this.setupBluetoothPlatform();
    }

    async showStatus() {
        console.log('📊 DeezChat Setup Status');
        console.log('==================');
        
        console.log(`Platform: ${this.platform} (${this.arch})`);
        console.log(`Python: ${this.pythonPath || 'Not found'}`);
        console.log(`Setup Dir: ${this.setupDir}`);
        console.log(`DeezChat Dir: ${this.deezchatDir}`);
        
        // Check Python and DeezChat
        if (this.pythonPath) {
            try {
                const pythonVersion = execSync(`${this.pythonPath} --version`, { encoding: 'utf8' });
                console.log(`Python Version: ${pythonVersion.stdout.trim()}`);
                
                const deezchatCheck = execSync(`${this.pythonPath} -c "import deezchat; print(\\"DEZCHAT_OK\\")"`, { 
                    encoding: 'utf8',
                    timeout: 5000,
                    cwd: this.deezchatDir
                });
                
                if (deezchatCheck.stdout.includes('DEEZCHAT_OK')) {
                    console.log('✅ DeezChat module: Available');
                } else {
                    console.log('⚠️  DeezChat module: Not found');
                    console.log('   Run: npm run install:backend');
                }
            } catch (error) {
                console.log(`❌ Python/DeezChat check failed: ${error.message}`);
            }
        }
    }
}

async function main() {
    const manager = new DeezChatSetupManager();
    
    const command = process.argv[2] || 'help';
    
    switch (command) {
        case 'install-python':
            await manager.installPython();
            break;
            
        case 'install-deps':
            if (await manager.findPython()) {
                await manager.installDeezChatDependencies();
            } else {
                console.error('❌ Python not found - run install-python first');
                process.exit(1);
            }
            break;
            
        case 'setup-bluetooth':
            await manager.setupBluetoothPlatform();
            break;
            
        case 'full-setup':
            await manager.fullSetup();
            break;
            
        case 'quick':
            await manager.quickSetup();
            break;
            
        case 'status':
            await manager.showStatus();
            break;
            
        case 'help':
        default:
            console.log(`
DeezChat Electron Setup Manager
================================

Usage: node setup.js <command>

Commands:
  install-python     - Install Python for current platform
  install-deps        - Install DeezChat Python dependencies
  setup-bluetooth   - Configure Bluetooth for current platform
  full-setup        - Complete setup (install all components)
  quick             - Quick setup check (find Python + check Bluetooth)
  status           - Show current setup status
  help              - Show this help

Examples:
  node setup.js full-setup     # Complete setup for first time
  node setup.js quick          # Quick status check
  node setup.js setup-bluetooth # Configure Bluetooth only

Platform Support:
  - macOS: Python installation and Bluetooth preferences setup
  - Windows: Python installer download and Bluetooth configuration
  - Linux: BlueZ setup and user group configuration

🔧 For Development:
  Run 'npm run dev' to start the Electron app in development mode

📱 For Production:
  Run 'npm run build' to create distributable packages
            `);
            break;
    }
    
    process.exit(0);
}

if (require.main === module) {
    main();
}