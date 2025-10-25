const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const https = require('https');

// Global state
let mainWindow;
let deezchatProcess;
let isScanning = false;
let foundPeers = new Map();

// BitChat service UUID
const BITCHAT_SERVICE_UUID = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';

class DeezChatManager {
    constructor() {
        this.isDeezChatRunning = false;
        this.peerCount = 0;
    }

    async startDeezChat() {
        if (this.isDeezChatRunning) {
            console.log('⚠️  DeezChat already running');
            return;
        }

        try {
            // Find Python executable
            const pythonPath = await this.findPythonPath();
            if (!pythonPath) {
                throw new Error('Python not found');
            }

            // Get the directory containing this electron app
            const appPath = path.dirname(process.execPath);
            const deezchatPath = path.join(appPath, '../deezchat');
            
            // Path to the optimized DeezChat
            const scriptPath = path.join(deezchatPath, 'main.py');
            
            if (!require('fs').existsSync(scriptPath)) {
                throw new Error(`DeezChat not found at: ${scriptPath}`);
            }

            console.log('🚀 Starting DeezChat backend...');
            console.log(`🐍 Python: ${pythonPath}`);
            console.log(`📁 Script: ${scriptPath}`);

            // Environment variables for DeezChat
            const env = {
                ...process.env,
                PYTHONPATH: path.join(deezchatPath, 'deezchat'),
                DEEZCHAT_DATA_DIR: path.join(appPath, 'data'),
                DEEZCHAT_CONFIG_DIR: path.join(appPath, 'config'),
                DEEZCHAT_LOG_DIR: path.join(appPath, 'logs')
            };

            // Start DeezChat process
            deezchatProcess = spawn(pythonPath, [
                '-m', 'deezchat', 
                '--debug'
            ], {
                cwd: deezchatPath,
                env: env,
                stdio: 'inherit',
                shell: process.platform === 'win32'
            });

            this.isDeezChatRunning = true;
            console.log('✅ DeezChat backend started successfully!');

            // Handle process events
            deezchatProcess.on('error', (error) => {
                console.error('❌ DeezChat process error:', error);
                mainWindow.webContents.send('deezchat-error', error.message);
            });

            deezchatProcess.on('exit', (code) => {
                console.log(`🔄 DeezChat process exited with code: ${code}`);
                this.isDeezChatRunning = false;
                deezchatProcess = null;
                mainWindow.webContents.send('deezchat-stopped');
            });

            deezchatProcess.stdout?.on('data', (data) => {
                this.handleDeezChatOutput(data.toString());
            });

            deezchatProcess.stderr?.on('data', (data) => {
                this.handleDeezChatOutput(data.toString(), true);
            });

        } catch (error) {
            console.error('❌ Failed to start DeezChat:', error);
            throw error;
        }
    }

    async findPythonPath() {
        const { execSync } = require('child_process');
        
        // Try different Python commands
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
                    console.log(`🐍 Found Python: ${cmd}`);
                    return cmd;
                }
            } catch (error) {
                // Command not found
            }
        }
        
        return null;
    }

    handleDeezChatOutput(data, isError = false) {
        const lines = data.split('\\n');
        
        for (const line of lines) {
            if (!line.trim()) continue;
            
            // Send to renderer for display
            if (isError) {
                mainWindow.webContents.send('deezchat-output', {
                    type: 'error',
                    text: line.trim()
                });
            } else {
                mainWindow.webContents.send('deezchat-output', {
                    type: 'info',
                    text: line.trim()
                });
                
                // Parse for BitChat peer information
                this.parseDeezChatInfo(line);
            }
        }
    }

    parseDeezChatInfo(line) {
        // Look for fingerprint
        const fpMatch = line.match(/fingerprint:\\s*([a-f0-9]+)/);
        if (fpMatch) {
            const fingerprint = fpMatch[1];
            console.log(`🔑 DeezChat fingerprint: ${fingerprint}`);
            mainWindow.webContents.send('deezchat-fingerprint', fingerprint);
        }

        // Look for peer discovery
        if (line.includes('BitChat peer found') || line.includes('📱 BitChat peer')) {
            const peerMatch = line.match(/BitChat peer found[:]\\s*(.+?)\\]/);
            if (peerMatch) {
                const peerName = peerMatch[1].trim();
                const peerId = `peer_${Date.now()}`;
                
                if (!foundPeers.has(peerId)) {
                    foundPeers.set(peerId, {
                        id: peerId,
                        name: peerName,
                        firstSeen: new Date(),
                        lastSeen: new Date()
                    });
                    
                    this.peerCount = foundPeers.size;
                    console.log(`📱 BitChat peer discovered: ${peerName}`);
                    
                    mainWindow.webContents.send('deezchat-peer-found', {
                        id: peerId,
                        name: peerName,
                        fingerprint: fingerprint,
                        count: this.peerCount
                    });
                }
            }
        }

        // Look for scanning status
        if (line.includes('Scanning for BitChat peers')) {
            console.log('📡 DeezChat scanning active');
            mainWindow.webContents.send('deezchat-scanning', true);
        }

        // Look for connection status
        if (line.includes('Connected to') || line.includes('Client started')) {
            console.log('🟢 DeezChat connected');
            mainWindow.webContents.send('deezchat-connected', true);
        }
    }

    async stopDeezChat() {
        if (deezchatProcess) {
            console.log('🛑 Stopping DeezChat...');
            deezchatProcess.kill('SIGTERM');
            
            // Wait for graceful shutdown
            await new Promise(resolve => {
                const timeout = setTimeout(() => {
                    deezchatProcess.kill('SIGKILL');
                    resolve();
                }, 5000);
                
                const checkInterval = setInterval(() => {
                    try {
                        // Check if process is still running
                        process.kill(deezchatProcess.pid, 0); // Signal 0 = no-op check
                        clearInterval(checkInterval);
                        clearTimeout(timeout);
                        resolve();
                    } catch (error) {
                        clearInterval(checkInterval);
                        clearTimeout(timeout);
                        resolve();
                    }
                }, 500);
                
                timeout.start();
            });
            
            this.isDeezChatRunning = false;
            deezchatProcess = null;
            
            // Clear discovered peers
            foundPeers.clear();
            this.peerCount = 0;
            
            console.log('✅ DeezChat stopped');
            mainWindow.webContents.send('deezchat-stopped');
        }
    }

    getPeerCount() {
        return this.peerCount;
    }

    getDiscoveredPeers() {
        return Array.from(foundPeers.values());
    }

    async checkBluetoothPermissions() {
        return new Promise((resolve) => {
            // Check platform-specific Bluetooth requirements
            if (process.platform === 'darwin') {
                // macOS: Check if Bluetooth is available
                const { execSync } = require('child_process');
                try {
                    const result = execSync('system_profiler SPBluetoothDataType', { encoding: 'utf8' });
                    if (result.stdout.includes('Bluetooth') || result.stdout.includes('BluetoothLowEnergy')) {
                        console.log('✅ macOS Bluetooth available');
                        resolve(true);
                        return;
                    }
                } catch (error) {
                    console.error('❌ macOS Bluetooth check failed:', error);
                }
            }
            
            // Linux: Check if BlueZ is running
            if (process.platform === 'linux') {
                const { execSync } = require('child_process');
                try {
                    const result = execSync('systemctl is-active bluetooth', { encoding: 'utf8' });
                    if (result.stdout.includes('active')) {
                        console.log('✅ Linux Bluetooth (BlueZ) active');
                        resolve(true);
                        return;
                    }
                } catch (error) {
                    console.error('❌ Linux Bluetooth check failed:', error);
                }
            }
            
            // Windows: Check if Bluetooth adapter is available
            if (process.platform === 'win32') {
                const { execSync } = require('child_process');
                try {
                    const result = execSync('powershell "Get-Service * | Where-Object {$_.Name -like \\"*Bluetooth*\\"} | Select-Object Name, Status"', { encoding: 'utf8' });
                    if (result.stdout.includes('Running')) {
                        console.log('✅ Windows Bluetooth service available');
                        resolve(true);
                        return;
                    }
                } catch (error) {
                    console.error('❌ Windows Bluetooth check failed:', error);
                }
            }
            
            resolve(false);
        });
    }
}

const deezchat = new DeezChatManager();

// Bluetooth permission handler
async function requestBluetoothPermissions() {
    console.log('🔍 Requesting Bluetooth permissions...');
    
    try {
        // Check Bluetooth availability first
        const hasBluetooth = await deezchat.checkBluetoothPermissions();
        
        if (!hasBluetooth) {
            console.log('⚠️  Bluetooth not available on this system');
            return false;
        }

        if (process.platform === 'darwin') {
            // macOS: Request Bluetooth permission
            await shell.execCommand('open', [
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Bluetooth'
            ]);
        } else if (process.platform === 'linux') {
            // Linux: Check if user is in bluetooth group
            const { execSync } = require('child_process');
            try {
                const result = execSync('groups', { encoding: 'utf8' });
                if (!result.stdout.includes('bluetooth')) {
                    console.log('⚠️  User not in bluetooth group. Adding user...');
                    await shell.execCommand('pkexec', ['echo', 'Please add user to bluetooth group'], { shell: true });
                } else {
                    console.log('✅ User is in bluetooth group');
                }
            } catch (error) {
                console.error('❌ Failed to check Linux user groups:', error);
            }
        } else if (process.platform === 'win32') {
            // Windows: Usually works if Bluetooth adapter exists
            console.log('✅ Windows Bluetooth should work if adapter is available');
        }
        
        return true;
    } catch (error) {
        console.error('❌ Failed to request Bluetooth permissions:', error);
        return false;
    }
}

// Start a native helper script for Bluetooth setup
async function setupNativeDependencies() {
    console.log('🔧 Setting up native dependencies...');
    
    try {
        // For macOS: Grant Bluetooth permissions
        if (process.platform === 'darwin') {
            const scriptPath = path.join(__dirname, 'setup-macos-bluetooth.sh');
            if (require('fs').existsSync(scriptPath)) {
                await shell.execCommand('bash', [scriptPath]);
            }
        }
        
        // For Linux: Install Bluetooth tools
        if (process.platform === 'linux') {
            const { execSync } = require('child_process');
            try {
                execSync('sudo apt-get update && sudo apt-get install -y bluetooth bluez', { shell: true });
                console.log('✅ Linux Bluetooth tools installed');
            } catch (error) {
                console.error('❌ Failed to install Linux Bluetooth tools:', error);
            }
        }
        
        // For Windows: Check Windows Bluetooth drivers
        if (process.platform === 'win32') {
            console.log('ℹ️  Windows Bluetooth drivers check recommended');
        }
        
    } catch (error) {
        console.error('❌ Failed to setup native dependencies:', error);
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        minWidth: 600,
        minHeight: 400,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            backgroundThrottle: 60,
            preload: path.join(__dirname, 'preload.js')
        },
        icon: path.join(__dirname, 'assets', 'icon.png'),
        show: false
    });

    // Remove menu bar on macOS
    if (process.platform === 'darwin') {
        mainWindow.setMenuBarVisibility(false);
    }

    mainWindow.loadFile('index.html');
}

// IPC handlers
ipcMain.handle('start-deezchat', async (event) => {
    console.log('🚀 Received start-deezchat request');
    
    try {
        // Check and request Bluetooth permissions first
        const hasPermissions = await deezchat.checkBluetoothPermissions();
        if (!hasPermissions) {
            mainWindow.webContents.send('bluetooth-status', 'checking');
            
            // Show permission dialog
            const result = await dialog.showMessageBox(mainWindow, {
                type: 'question',
                buttons: ['Grant Bluetooth', 'Cancel'],
                title: 'Bluetooth Access Required',
                message: 'DeezChat needs Bluetooth access to discover BitChat peers.\\n\\nWould you like to grant Bluetooth permissions now?\\n\\nIf you cancel, you can still use DeezChat but scanning may be limited.',
                defaultId: 0
            });
            
            if (result.response === 0) {
                await requestBluetoothPermissions();
                mainWindow.webContents.send('bluetooth-status', 'checking');
                
                // Wait a bit for permissions to take effect
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        }
        
        // Start DeezChat
        await deezchat.startDeezChat();
        
        mainWindow.webContents.send('deezchat-status', {
            running: deezchat.isDeezChatRunning,
            fingerprint: 'pending'
        });
        
    } catch (error) {
        console.error('❌ Failed to start DeezChat:', error);
        mainWindow.webContents.send('deezchat-error', error.message);
    }
});

ipcMain.handle('stop-deezchat', async (event) => {
    console.log('🛑 Received stop-deezchat request');
    
    try {
        await deezchat.stopDeezChat();
        
        mainWindow.webContents.send('deezchat-status', {
            running: false
            fingerprint: null
        });
        
    } catch (error) {
        console.error('❌ Failed to stop DeezChat:', error);
        mainWindow.webContents.send('deezchat-error', error.message);
    }
});

ipcMain.handle('get-peers', (event) => {
    console.log('📋 Sending peer list');
    
    const peers = deezchat.getDiscoveredPeers();
    mainWindow.webContents.send('peer-list', peers);
});

ipcMain.handle('check-bluetooth', async (event) => {
    console.log('🔍 Checking Bluetooth status...');
    
    const hasPermissions = await deezchat.checkBluetoothPermissions();
    const peerCount = deezchat.getPeerCount();
    
    mainWindow.webContents.send('bluetooth-status', {
        available: hasPermissions,
        scanning: deezchat.isDeezChatRunning,
        peerCount: peerCount
    });
});

ipcMain.handle('install-deezchat', async (event) => {
    console.log('📦 Installing DeezChat...');
    
    try {
        // Show installation dialog
        const result = await dialog.showMessageBox(mainWindow, {
            type: 'info',
            buttons: ['Install', 'Cancel'],
            title: 'Install DeezChat CLI',
            message: 'This will install the DeezChat Python client with all dependencies.\\n\\nDo you want to continue?',
            detail: 'This requires pip and Python to be available on your system.',
            defaultId: 0
        });
        
        if (result.response === 0) {
            mainWindow.webContents.send('install-status', 'installing');
            
            // For development, we can run pip install
            const { execSync } = require('child_process');
            try {
                execSync('pip install -e .', { cwd: path.join(__dirname, '..'), shell: true });
                console.log('✅ DeezChat installed successfully');
                mainWindow.webContents.send('install-status', 'completed');
            } catch (error) {
                console.error('❌ Failed to install DeezChat:', error);
                mainWindow.webContents.send('install-status', 'failed');
            }
        }
        
    } catch (error) {
        console.error('❌ Installation failed:', error);
        mainWindow.webContents.send('install-status', 'failed');
    }
});

ipcMain.handle('show-license', () => {
    dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'License',
        message: 'MIT License\\n\\nDeezChat - BitChat Python Client\\n\\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\\n\\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.',
        buttons: ['OK']
    });
});

// App events
app.whenReady(() => {
    console.log('🚀 DeezChat Electron app ready');
    
    // Auto-check DeezChat installation
    setTimeout(() => {
        checkDeezChatInstallation();
    }, 1000);
});

app.on('window-all-closed', () => {
    console.log('�AllWindows Closed');
    app.quit();
});

function checkDeezChatInstallation() {
    const { execSync } = require('child_process');
    
    try {
        // Check if Python and DeezChat dependencies are available
        const result = execSync('python -c "import deezchat; print(\'OK\')"', { 
            encoding: 'utf8', 
            timeout: 5000 
        });
        
        if (result.stdout.includes('OK')) {
            console.log('✅ DeezChat CLI installed and available');
        } else {
            console.log('⚠️  DeezChat CLI not found - installation may be required');
        }
    } catch (error) {
        console.log('❌ Could not check DeezChat installation:', error.message);
    }
}

app.on('activate', () => {
    console.log('📱 DeezChat Electron app activated');
});

async function setupAndShow() {
    console.log('🎬 Setting up and showing DeezChat...');
    
    try {
        // Setup native dependencies
        await setupNativeDependencies();
        
        // Show window
        createWindow();
        
        // Show after a short delay to ensure everything is ready
        setTimeout(() => {
            mainWindow.show();
        }, 500);
        
    } catch (error) {
        console.error('❌ Setup failed:', error);
        
        // Show anyway for user to see error
        createWindow();
        setTimeout(() => mainWindow.show(), 1000);
    }
}

// Start the application
app.whenReady().then(setupAndShow);