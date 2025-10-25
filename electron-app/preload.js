const { contextBridge } = require('electron');

// Expose protected APIs to renderer
contextBridge.exposeInMainWorld('ipcRenderer', {
    send: (channel, ...args) => {
        const { ipcRenderer } = require('electron');
        return ipcRenderer.send(channel, ...args);
    },
    invoke: (channel, ...args) => {
        const { ipcRenderer } = require('electron');
        return ipcRenderer.invoke(channel, ...args);
    },
    on: (channel, listener) => {
        const { ipcRenderer } = require('electron');
        return ipcRenderer.on(channel, listener);
    }
});

// Expose shell commands safely
contextBridge.exposeInMainWorld('shellAPI', {
    openExternal: (url) => {
        const { shell } = require('electron');
        shell.openExternal(url);
    },
    showItemInFolder: (fullPath) => {
        const { shell } = require('electron');
        shell.showItemInFolder(fullPath);
    },
    showMessageBox: (options) => {
        const { dialog } = require('electron');
        return dialog.showMessageBox(options);
    }
});

// Development tools
if (process.env.NODE_ENV === 'development') {
    contextBridge.exposeInMainWorld('devTools', {
        openDevTools: () => {
            const { BrowserWindow } = require('electron');
            BrowserWindow.getFocusedWindow()?.webContents.openDevTools();
        },
        reload: () => {
            const { app } = require('electron');
            app.relaunch();
            app.exit();
        }
    });
}