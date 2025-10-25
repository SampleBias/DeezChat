#!/usr/bin/env node

const https = require('https');

async function checkPythonAndDeezChat() {
    console.log('🔍 Checking Python and DeezChat installation...');
    
    try {
        const { execSync } = require('child_process');
        
        // Check Python version
        const pythonVersion = execSync('python3 --version || python --version', { 
            encoding: 'utf8',
            timeout: 5000
        }).stdout.trim();
        
        console.log(`🐍 Found: ${pythonVersion}`);
        
        // Check if DeezChat is importable
        const deezchatCheck = execSync('python3 -c "import deezchat; print(\'DEEZCHAT_OK\')" || python -c "import deezchat; print(\'DEEZCHAT_OK\')"', {
            encoding: 'utf8',
            timeout: 5000,
            cwd: path.join(__dirname, '..')
        }).stdout.trim();
        
        if (deezchatCheck === 'DEEZCHAT_OK') {
            console.log('✅ DeezChat module is importable');
            return true;
        } else {
            console.log('❌ DeezChat module not found or not importable');
            return false;
        }
        
    } catch (error) {
        console.error('❌ Python/DeezChat check failed:', error.message);
        return false;
    }
}

async function installDependencies() {
    console.log('📦 Installing Python dependencies...');
    
    try {
        const { execSync } = require('child_process');
        
        // Upgrade pip
        console.log('🔄 Upgrading pip...');
        execSync('python3 -m pip install --upgrade pip', { 
            stdio: 'inherit',
            timeout: 60000,
            cwd: path.join(__dirname, '..')
        });
        
        // Install DeezChat in development mode
        console.log('🔧 Installing DeezChat in development mode...');
        execSync('python3 -m pip install -e .', {
            stdio: 'inherit',
            timeout: 120000,
            cwd: path.join(__dirname, '..')
        });
        
        console.log('✅ Dependencies installed successfully');
        return true;
        
    } catch (error) {
        console.error('❌ Installation failed:', error.message);
        return false;
    }
}

function createPythonLauncher() {
    const platform = process.platform;
    const pythonPath = platform === 'win32' ? 'python' : 'python3';
    
    console.log(`🚀 Creating Python launcher for ${platform}...`);
    
    // For Windows, create a batch file
    if (platform === 'win32') {
        const { writeFileSync } = require('fs');
        const { join } = require('path');
        
        const launcherPath = join(__dirname, 'deezchat-launch.bat');
        const launcherContent = `@echo off
cd /d "%~dp0"
${pythonPath} -m deezchat %*
pause
`;
        
        writeFileSync(launcherPath, launcherContent);
        console.log(`✅ Created launcher: ${launcherPath}`);
    }
    
    // For macOS/Linux, create a shell script
    else {
        const { writeFileSync } = require('fs');
        const { join } = require('path');
        const { execSync } = require('child_process');
        
        // Make executable
        const launcherPath = join(__dirname, 'deezchat-launch.sh');
        const launcherContent = `#!/bin/bash
cd "$(dirname "$0")/.."
${pythonPath} -m deezchat "$@"
`;
        
        writeFileSync(launcherPath, launcherContent);
        execSync(`chmod +x "${launcherPath}"`);
        
        console.log(`✅ Created launcher: ${launcherPath}`);
    }
}

async function main() {
    console.log('🚀 DeezChat Electron Setup Tool');
    console.log('========================================');
    
    const args = process.argv.slice(2);
    const command = args[0] || 'check';
    
    switch (command) {
        case 'check':
            const isReady = await checkPythonAndDeezChat();
            process.exit(isReady ? 0 : 1);
            break;
            
        case 'install':
            const success = await installDependencies();
            process.exit(success ? 0 : 1);
            break;
            
        case 'setup':
            console.log('🔧 Complete setup: check, install, launcher');
            
            const isReady = await checkPythonAndDeezChat();
            if (!isReady) {
                console.log('⚠️  Dependencies not ready, installing...');
                const installed = await installDependencies();
                if (!installed) {
                    console.error('❌ Setup failed');
                    process.exit(1);
                }
            }
            
            createPythonLauncher();
            console.log('✅ Setup complete!');
            process.exit(0);
            break;
            
        default:
            console.log('Usage:');
            console.log('  node setup.js check     - Check Python and DeezChat');
            console.log('  node setup.js install   - Install DeezChat dependencies');
            console.log('  node setup.js setup     - Complete setup (check + install + launcher)');
            console.log('');
            console.log('  This tool sets up the Python backend for the Electron app.');
            process.exit(1);
    }
}

if (require.main === module) {
    main();
}