import { app, BrowserWindow, Menu, shell } from 'electron';
import { fileURLToPath } from 'url';
import path from 'path';
import { spawn } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = process.env.ELECTRON_DEV === 'true';
let mainWindow = null;
let apiProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 600,
    backgroundColor: '#050810',
    title: 'DragonScope',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5174');
    mainWindow.webContents.openDevTools();
  } else {
    // Production: API server serves the built app
    mainWindow.loadURL('http://localhost:3456');
  }

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startApiServer() {
  if (isDev) return; // In dev mode, API server is started separately by concurrently

  const serverPath = path.join(__dirname, '..', 'server', 'apiServer.js');
  apiProcess = spawn(process.execPath, [serverPath], {
    cwd: path.join(__dirname, '..', 'server'),
    stdio: 'pipe',
    env: { ...process.env, NODE_ENV: 'production' },
  });

  apiProcess.stdout?.on('data', (data) => {
    console.log(`[API] ${data.toString().trim()}`);
  });

  apiProcess.stderr?.on('data', (data) => {
    console.error(`[API] ${data.toString().trim()}`);
  });

  apiProcess.on('error', (err) => {
    console.error('Failed to start API server:', err.message);
  });
}

function killApiServer() {
  if (apiProcess && !apiProcess.killed) {
    apiProcess.kill('SIGTERM');
    apiProcess = null;
  }
}

function buildMenu() {
  const template = [
    {
      label: 'DragonScope',
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        { role: 'front' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'DragonScope on GitHub',
          click: () => shell.openExternal('https://github.com'),
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(() => {
  startApiServer();
  buildMenu();

  // Small delay in production to let API server start
  if (isDev) {
    createWindow();
  } else {
    setTimeout(createWindow, 1500);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killApiServer();
});
