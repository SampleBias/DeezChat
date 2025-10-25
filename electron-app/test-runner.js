#!/usr/bin/env node

/**
 * Test Runner for DeezChat Electron Application
 * Tests UI, IPC communication, and basic functionality
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

async function runTests() {
    console.log('🧪 Starting DeezChat Electron Tests');
    console.log('================================');
    
    const testWindow = new BrowserWindow({
        width: 800,
        height: 600,
        show: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });
    
    const testResults = [];
    
    testWindow.loadFile(path.join(__dirname, 'test-runner.html'));
    
    // IPC handlers for testing
    ipcMain.handle('test-result', (event, result) => {
        testResults.push(result);
        console.log(`✅ Test: ${result.name} - ${result.status}`);
        
        if (result.error) {
            console.error(`❌ Test Failed: ${result.error}`);
        }
    });
    
    ipcMain.handle('test-complete', (event, summary) => {
        console.log('\n🧪 Test Summary');
        console.log('==================');
        console.log(`Total Tests: ${summary.total}`);
        console.log(`Passed: ${summary.passed}`);
        console.log(`Failed: ${summary.failed}`);
        console.log(`Success Rate: ${((summary.passed / summary.total) * 100).toFixed(1)}%`);
        
        // Print detailed results
        testResults.forEach(test => {
            const status = test.status === 'pass' ? '✅' : '❌';
            console.log(`${status} ${test.name}: ${test.message}`);
        });
        
        // Exit with appropriate code
        process.exit(summary.failed > 0 ? 1 : 0);
    });
    
    testWindow.once('ready', () => {
        console.log('📋 Test runner ready');
        testWindow.show();
        
        // Run initial tests
        testWindow.webContents.send('run-tests');
        
        // Auto-close after 30 seconds if not completed
        setTimeout(() => {
            console.log('⏰ Test timeout reached');
            testWindow.webContents.send('test-timeout');
        }, 30000);
    });
    
    testWindow.on('closed', () => {
        console.log('📋 Test runner closed');
        app.quit();
    });
}

if (require.main === module) {
    runTests();
}