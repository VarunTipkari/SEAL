const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
    // Electron APIs will go here later
});