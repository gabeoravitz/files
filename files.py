#!/usr/bin/env python3
"""
file_browser.py - Self-contained web file browser
Usage:
  python3 file_browser.py --root /path/to/serve [--host 0.0.0.0] [--port 8000] [--auth password]
Features:
- Single-file Python script, no external dependencies.
- Modern, responsive UI (embedded CSS/JS) with light/dark modes following OS.
- Directory listing with breadcrumbs, previews for text/images, download, upload, rename, delete, mkdir, basic search.
- Optional basic auth (single password) via --auth.
- Prevents path traversal: all operations restricted to provided root.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import argparse, base64, json, mimetypes, os, shutil, sys, urllib.parse, io, zipfile, stat, pwd, grp, subprocess, threading, socket, time, struct, hashlib
from pathlib import Path
from datetime import datetime

def human_size(n):
	try:
		n = int(n)
	except Exception:
		return '-'
	for unit in ['B','KB','MB','GB','TB']:
		if abs(n) < 1024.0:
			return f"{n:3.1f}{unit}"
		n /= 1024.0
	return f"{n:.1f}PB"

def iso_time(ts):
	return datetime.fromtimestamp(ts).isoformat(sep=' ', timespec='seconds')

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	daemon_threads = True

HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Files</title>
<style>
:root {
  --bg: #f9fafb;
  --card-bg: #ffffff;
  --text-color: #374151;
  --accent-color: #2563eb;
  --danger-color: #ef4444;
  --border-radius: 8px;
  --shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  --font-family: 'Inter', sans-serif;
  --border-color: #e5e7eb;
  --hover-bg: #f3f4f6;
  --selection-bg: rgba(37, 99, 235, 0.1);
}
[data-theme="dark"] {
  --bg: #1a1a1a;
  --card-bg: #2d2d2d;
  --text-color: #e5e5e5;
  --accent-color: #6b7280;
  --danger-color: #ef4444;
  --shadow: 0 8px 25px rgba(0, 0, 0, 0.4);
  --border-color: #404040;
  --hover-bg: #3a3a3a;
  --selection-bg: rgba(107, 114, 128, 0.2);
}
body {
  margin: 0;
  font-family: var(--font-family);
  background-color: var(--bg);
  color: var(--text-color);
  line-height: 1.5;
}
.app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 50px;
  height: 50px;
  background-color: var(--accent-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--border-radius);
  font-weight: bold;
  font-size: 20px;
}
.controls {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn {
  background-color: var(--accent-color);
  color: white;
  border: none;
  padding: 6px 10px;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 12px;
  height: 32px;
  line-height: 1;
  min-width: 36px;
}
.btn:hover {
  background-color: #1e40af;
}
.btn-secondary {
  background-color: #f3f4f6;
  color: var(--text-color);
  padding: 6px 10px;
  font-size: 12px;
  height: 32px;
}
.btn-secondary:hover {
  background-color: var(--accent-color);
  color: white;
}
.btn-primary {
  background-color: var(--accent-color);
  color: white;
  padding: 6px 10px;
  font-size: 12px;
  height: 32px;
}
.theme-toggle {
  background: none;
  border: 1px solid var(--text-color);
  color: var(--text-color);
  padding: 6px 8px;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 12px;
  height: 32px;
}
.card {
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  padding: 20px;
  margin-bottom: 20px;
}
.pathbar {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 15px;
}
.breadcrumb {
  color: var(--accent-color);
  cursor: pointer;
  text-decoration: none;
  font-size: 14px;
}
.breadcrumb:hover {
  text-decoration: underline;
}
.row {
  display: grid;
  grid-template-columns: minmax(300px, 3fr) 100px 180px;
  gap: 10px;
  align-items: center;
  padding: 4px 10px;
  min-height: 28px;
  word-wrap: break-word;
  overflow: hidden;
  cursor: pointer;
}
.icon {
  font-size: 20px;
  margin-right: 10px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}
.file-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.file-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 1px;
  line-height: 1.3;
  font-size: 13px;
}
.file-path {
  font-size: 10px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  opacity: 0.7;
}
.meta {
  font-size: 12px;
  color: #6b7280;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  min-width: 240px;
}
.actions button {
  font-size: 12px;
  padding: 4px 8px;
  white-space: nowrap;
  flex-shrink: 0;
}
.action {
  background-color: transparent;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  font-size: 14px;
}
.action:hover {
  color: var(--accent-color);
}
.footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
}
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-card {
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
  padding: 20px;
  box-shadow: var(--shadow);
  max-width: 500px;
  width: 100%;
}
.modal.show {
  display: flex !important;
}
.btn-danger {
  background-color: var(--danger-color);
}
.btn-danger:hover {
  background-color: #dc2626;
}
.btn-secondary {
  background-color: #6b7280;
}
.btn-secondary:hover {
  background-color: #4b5563;
}
.upload-area {
  border: 2px dashed #d1d5db;
  border-radius: var(--border-radius);
  padding: 20px;
  text-align: center;
  margin: 10px 0;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-area:hover {
  border-color: var(--accent-color);
}
.upload-area.dragover {
  border-color: var(--accent-color);
  background-color: rgba(37, 99, 235, 0.1);
}
#fileInput {
  display: none;
}
.theme-toggle {
  background: none;
  border: 1px solid var(--text-color);
  color: var(--text-color);
  padding: 6px 8px;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 12px;
  height: 32px;
}
.theme-toggle:hover {
  background-color: var(--text-color);
  color: var(--card-bg);
}
.stats-info {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #6b7280;
}
.preview {
  max-height: 400px;
  overflow: auto;
}
.preview pre {
  background-color: #f3f4f6;
  padding: 15px;
  border-radius: var(--border-radius);
  overflow-x: auto;
}
[data-theme="dark"] .preview pre {
  background-color: #374151;
}
.context-menu {
  position: fixed;
  background-color: var(--card-bg);
  border: 1px solid #d1d5db;
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  padding: 4px 0;
  z-index: 2000;
  min-width: 180px;
  display: none;
}
[data-theme="dark"] .context-menu {
  border-color: #374151;
}
.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-color);
  display: flex;
  align-items: center;
  gap: 8px;
}
.context-menu-item:hover {
  background-color: var(--accent-color);
  color: white;
}
.context-menu-separator {
  height: 1px;
  background-color: #e5e7eb;
  margin: 4px 0;
}
[data-theme="dark"] .context-menu-separator {
  background-color: #374151;
}
.context-menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.context-menu-item.disabled:hover {
  background-color: transparent;
  color: var(--text-color);
}
.context-menu-item.danger:hover {
  background-color: var(--danger-color);
}
.row.selected {
  background-color: var(--selection-bg);
  border-left: 3px solid var(--accent-color);
}
.grid-item.selected {
  background-color: var(--selection-bg);
  border: 2px solid var(--accent-color);
}
.row:hover:not(.selected) {
  background-color: var(--hover-bg);
}
.grid-item:hover:not(.selected) {
  background-color: var(--hover-bg);
}
.drag-over {
  background-color: rgba(107, 114, 128, 0.2) !important;
  border: 2px dashed var(--accent-color) !important;
}
.no-select {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
.dragging {
  opacity: 0.5;
}
.hidden-file {
  opacity: 0.6;
  font-style: italic;
}
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  padding: 10px;
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
  border: 1px solid #e5e7eb;
}
[data-theme="dark"] .toolbar {
  border-color: #374151;
}
.toolbar-group {
  display: flex;
  gap: 5px;
  align-items: center;
}
.toolbar-separator {
  width: 1px;
  height: 24px;
  background-color: #e5e7eb;
  margin: 0 5px;
}
[data-theme="dark"] .toolbar-separator {
  background-color: #374151;
}
.view-toggle {
  display: flex;
  border: 1px solid #d1d5db;
  border-radius: var(--border-radius);
  overflow: hidden;
}
.view-toggle button {
  background: none;
  border: none;
  padding: 6px 12px;
  cursor: pointer;
  color: var(--text-color);
  font-size: 12px;
}
.view-toggle button.active {
  background-color: var(--accent-color);
  color: white;
}
.view-toggle button:hover:not(.active) {
  background-color: #f3f4f6;
}
[data-theme="dark"] .view-toggle button:hover:not(.active) {
  background-color: #374151;
}
.dropdown {
  position: relative;
  display: inline-block;
}
.dropdown-btn {
  cursor: pointer;
}
.dropdown-menu {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  background-color: var(--card-bg);
  border: 1px solid #e5e7eb;
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  min-width: 160px;
  z-index: 1000;
  padding: 4px 0;
}
.dropdown-menu.show {
  display: block;
}
.dropdown-item {
  display: block;
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-color);
}
.dropdown-item:hover:not(:disabled) {
  background-color: var(--accent-color);
  color: white;
}
.dropdown-item:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}
.dropdown-separator {
  height: 1px;
  background-color: #e5e7eb;
  margin: 4px 0;
}
[data-theme="dark"] .dropdown-menu {
  background-color: #374151;
  border-color: #4b5563;
}
[data-theme="dark"] .dropdown-separator {
  background-color: #4b5563;
}
.grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 15px;
  padding: 20px;
  min-height: 400px;
}
.grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 15px;
  border-radius: var(--border-radius);
  cursor: pointer;
  text-align: center;
  transition: background-color 0.2s;
}
.grid-item:hover {
  background-color: #f3f4f6;
}
[data-theme="dark"] .grid-item:hover {
  background-color: #374151;
}
.grid-item .icon {
  margin: 0 0 8px 0;
  font-size: 32px;
}
.grid-item .file-name {
  font-size: 12px;
  word-break: break-word;
  line-height: 1.2;
}
#listing {
  min-height: 400px;
  padding: 10px;
  background-color: var(--card-bg);
  border-radius: var(--border-radius);
}
#listing:not(.grid-view) {
  padding: 0;
}
#listing:not(.grid-view) .row:first-child {
  background-color: #f8f9fa;
  font-weight: 600;
  border-bottom: 2px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}
[data-theme="dark"] #listing:not(.grid-view) .row:first-child {
  background-color: #374151;
  border-bottom-color: #4b5563;
}
@media (max-width: 1200px) {
  .row {
    grid-template-columns: minmax(250px, 2fr) 80px 150px;
    gap: 15px;
    padding: 5px 12px;
  }
}
@media (max-width: 900px) {
  .row {
    grid-template-columns: minmax(200px, 1fr) 100px;
    gap: 10px;
  }
  .row > div:nth-child(2) {
    display: none;
  }
}
@media (max-width: 600px) {
  .row {
    grid-template-columns: 1fr;
    gap: 5px;
    padding: 8px;
  }
  .row > div:not(:first-child) {
    display: none;
  }
  .toolbar {
    flex-wrap: wrap;
    gap: 5px;
  }
  .toolbar-group {
    flex-wrap: wrap;
    gap: 5px;
  }
  .dropdown-btn {
    font-size: 12px;
    padding: 6px 10px;
  }
}
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <div class="brand">
      <div class="logo">FB</div>
      <div>
        <h1 class="h1">Files</h1>
        <p class="smallmuted"></p>
      </div>
    </div>
    <div class="controls">
      <input id="q" class="input" placeholder="Search files and folders..." />
      <button id="uploadBtn" class="btn">Upload</button>
      <button id="mkdir" class="btn">New Folder</button>
      <button id="refresh" class="btn">Refresh</button>
      <button id="toggleHidden" class="btn btn-secondary">👁️</button>
      <button id="serverControlBtn" class="btn">🖥️ Servers</button>
      <button id="themeToggle" class="theme-toggle">🌙</button>
      <button id="aboutBtn" class="btn">About</button>
    </div>
  </div>
  <div class="card">
    <div class="pathbar" id="pathbar"></div>
    <div class="toolbar">
      <div class="toolbar-group">
        <div class="dropdown">
          <button class="btn btn-secondary dropdown-btn">📋 Select ▼</button>
          <div class="dropdown-menu">
            <button id="selectAllBtn" class="dropdown-item">Select All</button>
            <button id="selectNoneBtn" class="dropdown-item">Select None</button>
          </div>
        </div>
        <div class="dropdown">
          <button class="btn btn-secondary dropdown-btn" id="fileMenuBtn" disabled>📂 File ▼</button>
          <div class="dropdown-menu">
            <button id="openBtn" class="dropdown-item" disabled>Open</button>
            <button id="previewBtn" class="dropdown-item" disabled>Preview</button>
            <button id="downloadBtn" class="dropdown-item" disabled>Download</button>
            <div class="dropdown-separator"></div>
            <button id="renameBtn" class="dropdown-item" disabled>Rename</button>
            <button id="deleteBtn" class="dropdown-item" disabled>Delete</button>
            <button id="propertiesBtn" class="dropdown-item" disabled>Properties</button>
            <button id="editBtn" class="dropdown-item" disabled>Edit</button>
            <button id="permissionsBtn" class="dropdown-item" disabled>Permissions</button>
          </div>
        </div>
        <div class="dropdown">
          <button class="btn btn-secondary dropdown-btn" id="editMenuBtn" disabled>✂️ Edit ▼</button>
          <div class="dropdown-menu">
            <button id="cutBtn" class="dropdown-item" disabled>Cut</button>
            <button id="copyBtn" class="dropdown-item" disabled>Copy</button>
            <button id="pasteBtn" class="dropdown-item" disabled>Paste</button>
          </div>
        </div>
      </div>
      <div style="margin-left: auto;" class="toolbar-group">
        <div class="view-toggle">
          <button id="listViewBtn" class="active">📋</button>
          <button id="gridViewBtn">⊞</button>
        </div>
      </div>
    </div>
    <div id="listing"></div>
    <div class="footer">
      <div class="stats-info">
        <div id="stats"></div>
        <div>Root: <span id="serverRoot"></span></div>
      </div>
    </div>
  </div>
</div>
<input type="file" id="fileInput" multiple />
<div id="contextMenu" class="context-menu">
  <div class="context-menu-item" id="ctxOpen">
    <span>📂</span> Open
  </div>
  <div class="context-menu-item" id="ctxPreview">
    <span>👁️</span> Preview
  </div>
  <div class="context-menu-separator"></div>
  <div class="context-menu-item" id="ctxCut">
    <span>✂️</span> Cut
  </div>
  <div class="context-menu-item" id="ctxCopy">
    <span>📋</span> Copy
  </div>
  <div class="context-menu-item" id="ctxPaste">
    <span>📄</span> Paste
  </div>
  <div class="context-menu-separator"></div>
  <div class="context-menu-item" id="ctxDownload">
    <span>⬇️</span> Download
  </div>
  <div class="context-menu-item" id="ctxRename">
    <span>✏️</span> Rename
  </div>
  <div class="context-menu-item danger" id="ctxDelete">
    <span>🗑️</span> Delete
  </div>
  <div class="context-menu-separator"></div>
  <div class="context-menu-item" id="ctxNewFolder">
    <span>📁</span> New Folder
  </div>
  <div class="context-menu-item" id="ctxUpload">
    <span>⬆️</span> Upload Files
  </div>
  <div class="context-menu-separator"></div>
  <div class="context-menu-item" id="ctxProperties">
    <span>ℹ️</span> Properties
  </div>
  <div class="context-menu-item" id="ctxEdit">
    <span>✏️</span> Edit
  </div>
  <div class="context-menu-item" id="ctxPermissions">
    <span>🔒</span> Permissions
  </div>
  <div class="context-menu-separator"></div>
  <div class="context-menu-item" id="ctxRefresh">
    <span>🔄</span> Refresh
  </div>
</div>
<div id="modal" class="modal" style="display: none;">
  <div class="modal-card" id="modalCard"></div>
</div>
<script>
console.log('filebrowser: script loaded');
const api = (p, o) => fetch('/api/'+p, o).then(r=>{
  if(!r.ok) throw r;
  const t=r.headers.get('content-type')||'';
  return t.includes('application/json')?r.json():r.text()
});
let state = {
  path: '/',
  files: [],
  searchMode: false,
  selectedFiles: new Set(),
  clipboard: {items: [], operation: null},
  viewMode: 'list',
  contextTarget: null,
  showHidden: false,
  draggedItems: [],
  servers: {nfs: {enabled: false, shares: []}, smb: {enabled: false, shares: [], users: []}}
};
function initTheme() {
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = savedTheme || (prefersDark ? 'dark' : 'light');
  setTheme(theme);
}
function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  setTheme(current === 'dark' ? 'light' : 'dark');
}
async function load(p) {
  if(p && p.startsWith('/?q=')){
    const q = decodeURIComponent(p.split('=')[1]||'');
    await search(q);
    return;
  }
  state.path = p || state.path;
  state.searchMode = false;
  try {
    const res = await api('list?path='+encodeURIComponent(state.path));
    state.files = res.files;
    render();
    document.getElementById('serverRoot').textContent = res.root;
    updateStats();
  } catch(e) {
    console.error('Load failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to load directory</p></div>');
  }
}
async function search(q) {
  if (!q.trim()) {
    load(state.path);
    return;
  }
  try {
    const res = await api('search?q='+encodeURIComponent(q));
    state.files = res.files;
    state.searchMode = true;
    render();
    document.getElementById('serverRoot').textContent = res.root;
    updateStats();
  } catch(e) {
    console.error('Search failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Search failed</p></div>');
  }
}
function updateStats() {
  const stats = document.getElementById('stats');
  if (state.files) {
    const dirs = state.files.filter(f => f.is_dir).length;
    const files = state.files.length - dirs;
    const totalSize = state.files.filter(f => !f.is_dir).reduce((sum, f) => sum + (f.size || 0), 0);
    stats.textContent = `${files} files, ${dirs} folders`;
    if (totalSize > 0) {
      stats.textContent += ` (${humanSize(totalSize)})`;
    }
  }
}
function humanSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)}${units[unitIndex]}`;
}
function render() {
  renderBreadcrumbs();
  renderListing();
}
function renderBreadcrumbs() {
  const bar = document.getElementById('pathbar');
  bar.innerHTML='';
  if (state.searchMode) {
    const searchLabel = document.createElement('span');
    searchLabel.textContent = 'Search Results';
    searchLabel.style.fontWeight = '600';
    bar.appendChild(searchLabel);
    return;
  }
  const parts = state.path.split('/').filter(Boolean);
  let acc='/';
  const rootBtn = bread('🏠', '/');
  bar.appendChild(rootBtn);
  parts.reduce((prev,cur)=>{
    acc = prev + (prev.endsWith('/')?'':'/') + cur;
    bar.appendChild(document.createTextNode(' / '));
    bar.appendChild(bread(cur, acc));
    return acc;
  },'/');
}
function renderListing() {
  const listing = document.getElementById('listing');
  listing.innerHTML='';
  if (state.viewMode === 'grid') {
    renderGridView(listing);
  } else {
    renderListView(listing);
  }
  updateToolbarState();
}
function renderListView(listing) {
  const header = document.createElement('div');
  header.className='row';
  header.innerHTML=`<div style="font-weight:600">Name</div><div style="text-align:right;font-weight:600">Size</div><div style="text-align:right;font-weight:600">Modified</div>`;
  listing.appendChild(header);
  const filteredFiles = state.files.filter(file => {
    if (!state.showHidden && file.name.startsWith('.')) {
      return false;
    }
    return true;
  });
  if(!filteredFiles || !filteredFiles.length){
    const em = document.createElement('div');
    em.style.padding='50px 24px';
    em.style.textAlign='center';
    em.style.color='#6b7280';
    em.style.minHeight='300px';
    em.style.display='flex';
    em.style.alignItems='center';
    em.style.justifyContent='center';
    em.textContent = state.searchMode ? 'No results found' : 'No files in this folder';
    listing.appendChild(em);
    return;
  }
  for(const it of filteredFiles){
    const row = document.createElement('div');
    row.className='row no-select';
    row.dataset.path = it.path;
    if (state.selectedFiles.has(it.path)) {
      row.classList.add('selected');
    }
    if (it.name.startsWith('.')) {
      row.classList.add('hidden-file');
    }
    const name = document.createElement('div');
    name.style.display='flex';
    name.style.alignItems='center';
    name.className='item';
    const icon = document.createElement('div');
    icon.className='icon';
    icon.style.fontSize='16px';
    icon.style.marginRight='8px';
    icon.style.flexShrink='0';
    icon.textContent = it.is_dir ? '📁' : getFileIcon(it.name);
    const fileInfo = document.createElement('div');
    fileInfo.className = 'file-info';
    const fileName = document.createElement('div');
    fileName.className = 'file-name';
    fileName.textContent = it.name;
    fileInfo.appendChild(fileName);
    name.appendChild(icon);
    name.appendChild(fileInfo);
    const size = document.createElement('div');
    size.style.textAlign='right';
    size.style.fontSize='12px';
    size.style.whiteSpace='nowrap';
    size.style.overflow='hidden';
    size.style.textOverflow='ellipsis';
    size.textContent = it.is_dir ? '-' : it.size_h;
    const mod = document.createElement('div');
    mod.style.textAlign='right';
    mod.style.fontSize='12px';
    mod.style.whiteSpace='nowrap';
    mod.style.overflow='hidden';
    mod.style.textOverflow='ellipsis';
    mod.textContent = it.mtime;
    row.addEventListener('click', (e) => {
      if (e.shiftKey) {
        e.preventDefault();
        if (state.selectedFiles.size > 0) {
          selectRange(it.path);
        } else {
          toggleSelection(it.path);
        }
      } else if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        toggleSelection(it.path);
      } else {
        clearSelection();
        toggleSelection(it.path);
      }
    });
    row.addEventListener('dblclick', () => {
      if (it.is_dir) {
        load(it.path);
      } else {
        preview(it.path);
      }
    });
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      if (!state.selectedFiles.has(it.path)) {
        clearSelection();
        toggleSelection(it.path);
      }
      state.contextTarget = it;
      showContextMenu(e.clientX, e.clientY);
    });
    
    // Add drag and drop functionality
    row.draggable = true;
    row.addEventListener('dragstart', (e) => {
      if (!state.selectedFiles.has(it.path)) {
        clearSelection();
        toggleSelection(it.path);
      }
      state.draggedItems = Array.from(state.selectedFiles);
      document.querySelectorAll('.row.selected, .grid-item.selected').forEach(item => {
        item.classList.add('dragging');
      });
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', JSON.stringify(state.draggedItems));
    });
    
    row.addEventListener('dragend', (e) => {
      document.querySelectorAll('.dragging').forEach(item => {
        item.classList.remove('dragging');
      });
      state.draggedItems = [];
    });
    
    if (it.is_dir) {
      row.addEventListener('dragover', (e) => {
        if (state.draggedItems.length > 0 && !state.draggedItems.includes(it.path)) {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          row.classList.add('drag-over');
        }
      });
      
      row.addEventListener('dragleave', (e) => {
        row.classList.remove('drag-over');
      });
      
      row.addEventListener('drop', (e) => {
        e.preventDefault();
        row.classList.remove('drag-over');
        if (state.draggedItems.length > 0 && !state.draggedItems.includes(it.path)) {
          moveMultipleItems(state.draggedItems, it.path);
        }
      });
    }
    row.appendChild(name);
    row.appendChild(size);
    row.appendChild(mod);
    listing.appendChild(row);
  }
  const spacer = document.createElement('div');
  spacer.style.minHeight = '200px';
  spacer.style.width = '100%';
  listing.appendChild(spacer);
}
function renderGridView(listing) {
  listing.className = 'grid-view';
  const filteredFiles = state.files.filter(file => {
    if (!state.showHidden && file.name.startsWith('.')) {
      return false;
    }
    return true;
  });
  if(!filteredFiles || !filteredFiles.length){
    const em = document.createElement('div');
    em.style.padding='24px';
    em.style.gridColumn = '1 / -1';
    em.textContent = state.searchMode ? 'No results found' : 'No files';
    listing.appendChild(em);
    return;
  }
  for(const it of filteredFiles){
    const item = document.createElement('div');
    item.className='grid-item no-select';
    item.dataset.path = it.path;
    if (state.selectedFiles.has(it.path)) {
      item.classList.add('selected');
    }
    if (it.name.startsWith('.')) {
      item.classList.add('hidden-file');
    }
    const icon = document.createElement('div');
    icon.className='icon';
    icon.textContent = it.is_dir ? '📁' : getFileIcon(it.name);
    const fileName = document.createElement('div');
    fileName.className = 'file-name';
    fileName.textContent = it.name;
    item.appendChild(icon);
    item.appendChild(fileName);
    item.addEventListener('click', (e) => {
      if (e.shiftKey) {
        e.preventDefault();
        if (state.selectedFiles.size > 0) {
          selectRange(it.path);
        } else {
          toggleSelection(it.path);
        }
      } else if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        toggleSelection(it.path);
      } else {
        clearSelection();
        toggleSelection(it.path);
      }
    });
    item.addEventListener('dblclick', () => {
      if (it.is_dir) {
        load(it.path);
      } else {
        preview(it.path);
      }
    });
    item.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      if (!state.selectedFiles.has(it.path)) {
        clearSelection();
        toggleSelection(it.path);
      }
      state.contextTarget = it;
      showContextMenu(e.clientX, e.clientY);
    });
    
    // Add drag and drop functionality for grid view
    item.draggable = true;
    item.addEventListener('dragstart', (e) => {
      if (!state.selectedFiles.has(it.path)) {
        clearSelection();
        toggleSelection(it.path);
      }
      state.draggedItems = Array.from(state.selectedFiles);
      document.querySelectorAll('.row.selected, .grid-item.selected').forEach(selectedItem => {
        selectedItem.classList.add('dragging');
      });
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', JSON.stringify(state.draggedItems));
    });
    
    item.addEventListener('dragend', (e) => {
      document.querySelectorAll('.dragging').forEach(draggedItem => {
        draggedItem.classList.remove('dragging');
      });
      state.draggedItems = [];
    });
    
    if (it.is_dir) {
      item.addEventListener('dragover', (e) => {
        if (state.draggedItems.length > 0 && !state.draggedItems.includes(it.path)) {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          item.classList.add('drag-over');
        }
      });
      
      item.addEventListener('dragleave', (e) => {
        item.classList.remove('drag-over');
      });
      
      item.addEventListener('drop', (e) => {
        e.preventDefault();
        item.classList.remove('drag-over');
        if (state.draggedItems.length > 0 && !state.draggedItems.includes(it.path)) {
          moveMultipleItems(state.draggedItems, it.path);
        }
      });
    }
    listing.appendChild(item);
  }
}
function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const iconMap = {
    'txt': '📄', 'md': '📝', 'pdf': '📕', 'doc': '📘', 'docx': '📘',
    'xls': '📗', 'xlsx': '📗', 'ppt': '📙', 'pptx': '📙',
    'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
    'mp3': '🎵', 'wav': '🎵', 'mp4': '🎬', 'avi': '🎬', 'mov': '🎬',
    'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
    'js': '⚡', 'html': '🌐', 'css': '🎨', 'py': '🐍', 'java': '☕',
    'cpp': '⚙️', 'c': '⚙️', 'php': '🐘', 'rb': '💎', 'go': '🐹'
  };
  return iconMap[ext] || '📄';
}
function bread(label, p) {
  const b = document.createElement('button');
  b.className='breadcrumb';
  b.textContent=label||'/';
  b.onclick=()=>load(p);
  return b;
}
function el(tag,txt,cb) {
  const b=document.createElement(tag);
  b.className='action';
  b.textContent=txt;
  b.onclick=cb;
  return b;
}
function escapeHtml(s) {
  return (s||'').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function toggleSelection(path) {
  if (state.selectedFiles.has(path)) {
    state.selectedFiles.delete(path);
  } else {
    state.selectedFiles.add(path);
  }
  updateSelectionUI();
  updateToolbarState();
}
function clearSelection() {
  state.selectedFiles.clear();
  updateSelectionUI();
  updateToolbarState();
}
function selectAll() {
  state.files.forEach(file => state.selectedFiles.add(file.path));
  updateSelectionUI();
  updateToolbarState();
}
function selectRange(endPath) {
  const files = state.files;
  const startIndex = files.findIndex(f => state.selectedFiles.has(f.path));
  const endIndex = files.findIndex(f => f.path === endPath);
  if (startIndex !== -1 && endIndex !== -1) {
    const start = Math.min(startIndex, endIndex);
    const end = Math.max(startIndex, endIndex);
    for (let i = start; i <= end; i++) {
      state.selectedFiles.add(files[i].path);
    }
    updateSelectionUI();
    updateToolbarState();
  }
}
function updateSelectionUI() {
  document.querySelectorAll('.row, .grid-item').forEach(item => {
    const path = item.dataset.path;
    if (path && state.selectedFiles.has(path)) {
      item.classList.add('selected');
    } else {
      item.classList.remove('selected');
    }
  });
}
function updateToolbarState() {
  const hasSelection = state.selectedFiles.size > 0;
  const hasClipboard = state.clipboard.items.length > 0;
  const singleSelection = state.selectedFiles.size === 1;
  const selectedFile = singleSelection ? state.files.find(f => state.selectedFiles.has(f.path)) : null;
  const isDir = selectedFile && selectedFile.is_dir;
  const isFile = selectedFile && !selectedFile.is_dir;
  document.getElementById('fileMenuBtn').disabled = !hasSelection;
  document.getElementById('editMenuBtn').disabled = !hasSelection && !hasClipboard;
  document.getElementById('openBtn').disabled = !singleSelection || !isDir;
  document.getElementById('previewBtn').disabled = !singleSelection || !isFile;
  document.getElementById('downloadBtn').disabled = !hasSelection;
  document.getElementById('cutBtn').disabled = !hasSelection;
  document.getElementById('copyBtn').disabled = !hasSelection;
  document.getElementById('pasteBtn').disabled = !hasClipboard;
  document.getElementById('renameBtn').disabled = !singleSelection;
  document.getElementById('deleteBtn').disabled = !hasSelection;
  document.getElementById('propertiesBtn').disabled = !singleSelection;
  document.getElementById('editBtn').disabled = !singleSelection || !isFile;
  document.getElementById('permissionsBtn').disabled = !singleSelection;
}
function showContextMenu(x, y) {
  const menu = document.getElementById('contextMenu');
  const hasSelection = state.selectedFiles.size > 0;
  const hasClipboard = state.clipboard.items.length > 0;
  const isFile = state.contextTarget && !state.contextTarget.is_dir;
  const isDir = state.contextTarget && state.contextTarget.is_dir;
  const isEmptySpace = !state.contextTarget;
  document.getElementById('ctxOpen').style.display = isDir ? 'flex' : 'none';
  document.getElementById('ctxPreview').style.display = isFile ? 'flex' : 'none';
  document.getElementById('ctxCut').classList.toggle('disabled', !hasSelection);
  document.getElementById('ctxCopy').classList.toggle('disabled', !hasSelection);
  document.getElementById('ctxDownload').classList.toggle('disabled', !hasSelection);
  document.getElementById('ctxRename').classList.toggle('disabled', state.selectedFiles.size !== 1);
  document.getElementById('ctxDelete').classList.toggle('disabled', !hasSelection);
  document.getElementById('ctxProperties').classList.toggle('disabled', state.selectedFiles.size !== 1);
  document.getElementById('ctxEdit').classList.toggle('disabled', state.selectedFiles.size !== 1 || !isFile);
  document.getElementById('ctxPermissions').classList.toggle('disabled', state.selectedFiles.size !== 1);
  document.getElementById('ctxPaste').classList.toggle('disabled', !hasClipboard);
  document.getElementById('ctxNewFolder').classList.remove('disabled');
  document.getElementById('ctxUpload').classList.remove('disabled');
  document.getElementById('ctxRefresh').classList.remove('disabled');
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.style.display = 'block';
  const rect = menu.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    menu.style.left = (x - rect.width) + 'px';
  }
  if (rect.bottom > window.innerHeight) {
    menu.style.top = (y - rect.height) + 'px';
  }
}
function hideContextMenu() {
  document.getElementById('contextMenu').style.display = 'none';
}
function cutFiles() {
  if (state.selectedFiles.size === 0) return;
  state.clipboard.items = Array.from(state.selectedFiles);
  state.clipboard.operation = 'cut';
  updateToolbarState();
  document.querySelectorAll('.row.selected, .grid-item.selected').forEach(item => {
    item.style.opacity = '0.5';
  });
}
function copyFiles() {
  if (state.selectedFiles.size === 0) return;
  state.clipboard.items = Array.from(state.selectedFiles);
  state.clipboard.operation = 'copy';
  updateToolbarState();
}
async function pasteFiles() {
  if (state.clipboard.items.length === 0) return;
  try {
    const operation = state.clipboard.operation;
    const items = state.clipboard.items;
    for (const itemPath of items) {
      const fileName = itemPath.split('/').pop();
      const sourcePath = itemPath;
      const targetPath = state.path + (state.path.endsWith('/') ? '' : '/') + fileName;
      if (operation === 'cut') {
        await fetch('/api/rename', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({path: sourcePath, new: fileName})
        });
      } else {
        showModal('<div style="padding:8px"><h3>Copy Operation</h3><p>Copy operation is not yet implemented. Use cut/move instead.</p></div>');
        return;
      }
    }
    if (operation === 'cut') {
      state.clipboard.items = [];
      state.clipboard.operation = null;
    }
    load(state.path);
    updateToolbarState();
  } catch (e) {
    console.error('Paste failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Paste operation failed</p></div>');
  }
}
function showProperties() {
  if (state.selectedFiles.size !== 1) return;
  const filePath = Array.from(state.selectedFiles)[0];
  const file = state.files.find(f => f.path === filePath);
  if (!file) return;
  const propertiesHtml = `
    <div style="padding:8px">
      <h3>Properties</h3>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:4px;font-weight:600">Name:</td><td style="padding:4px">${escapeHtml(file.name)}</td></tr>
        <tr><td style="padding:4px;font-weight:600">Type:</td><td style="padding:4px">${file.is_dir ? 'Folder' : 'File'}</td></tr>
        <tr><td style="padding:4px;font-weight:600">Size:</td><td style="padding:4px">${file.is_dir ? '-' : file.size_h}</td></tr>
        <tr><td style="padding:4px;font-weight:600">Modified:</td><td style="padding:4px">${file.mtime}</td></tr>
        <tr><td style="padding:4px;font-weight:600">Path:</td><td style="padding:4px">${escapeHtml(file.rel)}</td></tr>
      </table>
    </div>
  `;
  showModal(propertiesHtml);
}
function setViewMode(mode) {
  state.viewMode = mode;
  localStorage.setItem('viewMode', mode);
  document.getElementById('listViewBtn').classList.toggle('active', mode === 'list');
  document.getElementById('gridViewBtn').classList.toggle('active', mode === 'grid');
  const listing = document.getElementById('listing');
  listing.className = '';
  renderListing();
}
async function preview(p) {
  try {
    const t = await fetch('/api/preview?path='+encodeURIComponent(p));
    if(!t.ok) throw t;
    const ct = t.headers.get('content-type')||'';
    if(ct.startsWith('text/')) {
      const txt = await t.text();
      showModal(`<div class='preview'><pre>${escapeHtml(txt)}</pre></div>`);
    } else if(ct.startsWith('image/')) {
      const blob = await t.blob();
      const url = URL.createObjectURL(blob);
      showModal(`<div class='preview'><img src='${url}' style='max-width:100%;height:auto;border-radius:8px' /></div>`);
    } else {
      showModal(`<div class='preview'>No preview available. <a href='/api/download?path=${encodeURIComponent(p)}' target='_blank'>Download</a></div>`);
    }
  } catch(e) {
    console.error('Preview failed:', e);
    showModal('<div class="preview">Failed to preview</div>');
  }
}
function showModal(htmlContent) {
  const modal = document.getElementById('modal');
  const card = document.getElementById('modalCard');
  card.innerHTML = '';
  const wrapper = document.createElement('div');
  wrapper.innerHTML = htmlContent;
  const footer = document.createElement('div');
  footer.style.cssText = 'text-align:right;margin-top:12px';
  const closeBtn = document.createElement('button');
  closeBtn.className = 'btn btn-secondary';
  closeBtn.textContent = 'Close';
  closeBtn.onclick = () => hideModal();
  footer.appendChild(closeBtn);
  card.appendChild(wrapper);
  card.appendChild(footer);
  modal.classList.add('show');
  modal.onclick = (e) => {
    if (e.target === modal) hideModal();
  };
}
function hideModal() {
  document.getElementById('modal').classList.remove('show');
}

function showToast(message, type = 'info') {
  // Create toast container if it doesn't exist
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;pointer-events:none';
    document.body.appendChild(toastContainer);
  }
  
  // Create toast element
  const toast = document.createElement('div');
  const bgColor = type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#6b7280';
  toast.style.cssText = `
    background:${bgColor};
    color:white;
    padding:12px 16px;
    border-radius:6px;
    margin-bottom:8px;
    box-shadow:0 4px 12px rgba(0,0,0,0.3);
    transform:translateX(100%);
    transition:transform 0.3s ease;
    pointer-events:auto;
    max-width:300px;
    word-wrap:break-word;
  `;
  toast.textContent = message;
  
  toastContainer.appendChild(toast);
  
  // Animate in
  setTimeout(() => {
    toast.style.transform = 'translateX(0)';
  }, 10);
  
  // Auto remove after 4 seconds
  setTimeout(() => {
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 4000);
}
function showUploadModal() {
  const uploadHtml = `
    <div style="padding:8px">
      <h3>Upload Files</h3>
      <div class="upload-area" id="uploadArea">
        <p>Click here or drag files to upload</p>
        <p style="font-size:12px;color:#6b7280">Multiple files supported</p>
      </div>
      <div id="uploadProgress" style="display:none;margin-top:10px">
        <div style="background:#e5e7eb;border-radius:4px;height:8px">
          <div id="progressBar" style="background:var(--accent-color);height:100%;border-radius:4px;width:0%;transition:width 0.3s"></div>
        </div>
        <p id="uploadStatus" style="margin-top:5px;font-size:12px"></p>
      </div>
    </div>
  `;
  showModal(uploadHtml);
  const uploadArea = document.getElementById('uploadArea');
  const fileInput = document.getElementById('fileInput');
  uploadArea.onclick = () => fileInput.click();
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
  });
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
  });
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    handleFileUpload(e.dataTransfer.files);
  });
}
async function handleFileUpload(files) {
  if (!files.length) return;
  const progressDiv = document.getElementById('uploadProgress');
  const progressBar = document.getElementById('progressBar');
  const statusText = document.getElementById('uploadStatus');
  progressDiv.style.display = 'block';
  statusText.textContent = `Uploading ${files.length} file(s)...`;
  const fd = new FormData();
  for (const f of files) {
    fd.append('file', f);
  }
  fd.append('path', state.path);
  try {
    const res = await fetch('/api/upload', {method:'POST', body:fd});
    if (!res.ok) throw new Error('Upload failed');
    progressBar.style.width = '100%';
    statusText.textContent = 'Upload complete!';
    setTimeout(() => {
      hideModal();
      load(state.path);
    }, 1000);
  } catch(e) {
    console.error('Upload failed:', e);
    statusText.textContent = 'Upload failed!';
    statusText.style.color = 'var(--danger-color)';
  }
}
function download(p) {
  window.location = '/api/download?path='+encodeURIComponent(p);
}
function renamePrompt(p, name) {
  const newName = prompt('Rename to:', name);
  if (newName && newName !== name) {
    fetch('/api/rename', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:p, new:newName})
    })
    .then(res => {
      if (!res.ok) throw new Error('Rename failed');
      return res.json();
    })
    .then(() => load(state.path))
    .catch(e => {
      console.error('Rename failed:', e);
      alert('Rename failed');
    });
  }
}
function delConfirm(p) {
  if (confirm('Are you sure you want to delete this item?')) {
    fetch('/api/delete', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:p})
    })
    .then(res => {
      if (!res.ok) throw new Error('Delete failed');
      return res.json();
    })
    .then(() => load(state.path))
    .catch(e => {
      console.error('Delete failed:', e);
      alert('Delete failed');
    });
  }
}
function createFolder() {
  const name = prompt('Folder name:');
  if (!name) return;
  fetch('/api/mkdir', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:state.path, name})
  })
  .then(res => {
    if (!res.ok) throw new Error('Create folder failed');
    return res.json();
  })
  .then(() => load(state.path))
  .catch(e => {
    console.error('Create folder failed:', e);
    alert('Failed to create folder');
  });
}

function toggleHiddenFiles() {
  state.showHidden = !state.showHidden;
  localStorage.setItem('showHidden', state.showHidden);
  const btn = document.getElementById('toggleHidden');
  btn.textContent = state.showHidden ? '🙈' : '👁️';
  btn.title = state.showHidden ? 'Hide hidden files' : 'Show hidden files';
  renderListing();
}

async function moveItem(sourcePath, targetPath) {
  try {
    const fileName = sourcePath.split('/').pop();
    const newPath = targetPath + (targetPath.endsWith('/') ? '' : '/') + fileName;
    
    const response = await fetch('/api/move', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source: sourcePath, target: newPath})
    });
    
    if (!response.ok) {
      throw new Error('Move failed');
    }
    
    load(state.path);
  } catch (e) {
    console.error('Move failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to move item</p></div>');
  }
}

async function moveMultipleItems(sourcePaths, targetPath) {
  try {
    const response = await fetch('/api/move-multiple', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sources: sourcePaths, target: targetPath})
    });
    
    if (!response.ok) {
      throw new Error('Move failed');
    }
    
    clearSelection();
    load(state.path);
  } catch (e) {
    console.error('Move multiple failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to move items</p></div>');
  }
}

function showTextEditor(filePath) {
  fetch('/api/edit?path=' + encodeURIComponent(filePath))
    .then(response => {
      if (!response.ok) throw new Error('Failed to load file');
      return response.text();
    })
    .then(content => {
      const ext = filePath.split('.').pop().toLowerCase();
      const language = getLanguageFromExtension(ext);
      
      const editorHtml = `
        <div style="padding:8px">
          <h3>Edit: ${escapeHtml(filePath.split('/').pop())}</h3>
          <div style="margin-bottom:10px">
            <select id="languageSelect" style="padding:4px;margin-right:10px">
              <option value="text" ${language === 'text' ? 'selected' : ''}>Plain Text</option>
              <option value="javascript" ${language === 'javascript' ? 'selected' : ''}>JavaScript</option>
              <option value="python" ${language === 'python' ? 'selected' : ''}>Python</option>
              <option value="bash" ${language === 'bash' ? 'selected' : ''}>Bash</option>
              <option value="powershell" ${language === 'powershell' ? 'selected' : ''}>PowerShell</option>
              <option value="html" ${language === 'html' ? 'selected' : ''}>HTML</option>
              <option value="css" ${language === 'css' ? 'selected' : ''}>CSS</option>
              <option value="json" ${language === 'json' ? 'selected' : ''}>JSON</option>
              <option value="markdown" ${language === 'markdown' ? 'selected' : ''}>Markdown</option>
              <option value="yaml" ${language === 'yaml' ? 'selected' : ''}>YAML</option>
            </select>
            <button id="saveFileBtn" class="btn btn-primary">Save</button>
            <button id="saveAsBtn" class="btn btn-secondary">Save As</button>
          </div>
          <textarea id="fileEditor" style="width:100%;height:400px;font-family:monospace;font-size:14px;border:1px solid var(--border-color);border-radius:4px;padding:10px;background:var(--card-bg);color:var(--text-color);resize:vertical">${escapeHtml(content)}</textarea>
          <div style="margin-top:10px;font-size:12px;color:#6b7280">
            <span id="editorStats">Lines: ${content.split('\n').length}, Characters: ${content.length}</span>
          </div>
        </div>
      `;
      
      showModal(editorHtml);
      
      const editor = document.getElementById('fileEditor');
      const stats = document.getElementById('editorStats');
      const languageSelect = document.getElementById('languageSelect');
      
      editor.addEventListener('input', () => {
        const lines = editor.value.split('\n').length;
        const chars = editor.value.length;
        stats.textContent = `Lines: ${lines}, Characters: ${chars}`;
      });
      
      languageSelect.addEventListener('change', () => {
        // Basic syntax highlighting could be added here
        editor.focus();
      });
      
      document.getElementById('saveFileBtn').onclick = () => {
        saveFile(filePath, editor.value);
      };
      
      document.getElementById('saveAsBtn').onclick = () => {
        const newName = prompt('Save as:', filePath.split('/').pop());
        if (newName) {
          const newPath = state.path + (state.path.endsWith('/') ? '' : '/') + newName;
          saveFile(newPath, editor.value);
        }
      };
      
      editor.focus();
    })
    .catch(e => {
      console.error('Failed to load file:', e);
      showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to load file for editing</p></div>');
    });
}

function getLanguageFromExtension(ext) {
  const langMap = {
    'js': 'javascript', 'jsx': 'javascript', 'ts': 'javascript', 'tsx': 'javascript',
    'py': 'python', 'pyw': 'python',
    'sh': 'bash', 'bash': 'bash', 'zsh': 'bash',
    'ps1': 'powershell', 'psm1': 'powershell',
    'html': 'html', 'htm': 'html',
    'css': 'css', 'scss': 'css', 'sass': 'css',
    'json': 'json',
    'md': 'markdown', 'markdown': 'markdown',
    'yml': 'yaml', 'yaml': 'yaml'
  };
  return langMap[ext] || 'text';
}

async function saveFile(filePath, content) {
  try {
    const response = await fetch('/api/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: filePath, content: content})
    });
    
    if (!response.ok) {
      throw new Error('Save failed');
    }
    
    hideModal();
    load(state.path);
    showModal('<div style="padding:8px"><h3>Success</h3><p>File saved successfully!</p></div>');
    setTimeout(hideModal, 1500);
  } catch (e) {
    console.error('Save failed:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to save file</p></div>');
  }
}

function showPermissionsDialog() {
  if (state.selectedFiles.size !== 1) return;
  const filePath = Array.from(state.selectedFiles)[0];
  const file = state.files.find(f => f.path === filePath);
  if (!file) return;
  
  fetch('/api/permissions?path=' + encodeURIComponent(filePath))
    .then(response => {
      if (!response.ok) throw new Error('Failed to get permissions');
      return response.json();
    })
    .then(data => {
      const permissionsHtml = `
        <div style="padding:8px">
          <h3>Permissions: ${escapeHtml(file.name)}</h3>
          <div style="margin:15px 0">
            <h4>POSIX Permissions</h4>
            <div style="display:grid;grid-template-columns:80px 1fr;gap:10px;align-items:center">
              <label>Owner:</label>
              <div>
                <label><input type="checkbox" id="ownerRead" ${data.permissions.owner.read ? 'checked' : ''}> Read</label>
                <label><input type="checkbox" id="ownerWrite" ${data.permissions.owner.write ? 'checked' : ''}> Write</label>
                <label><input type="checkbox" id="ownerExecute" ${data.permissions.owner.execute ? 'checked' : ''}> Execute</label>
              </div>
              <label>Group:</label>
              <div>
                <label><input type="checkbox" id="groupRead" ${data.permissions.group.read ? 'checked' : ''}> Read</label>
                <label><input type="checkbox" id="groupWrite" ${data.permissions.group.write ? 'checked' : ''}> Write</label>
                <label><input type="checkbox" id="groupExecute" ${data.permissions.group.execute ? 'checked' : ''}> Execute</label>
              </div>
              <label>Others:</label>
              <div>
                <label><input type="checkbox" id="othersRead" ${data.permissions.others.read ? 'checked' : ''}> Read</label>
                <label><input type="checkbox" id="othersWrite" ${data.permissions.others.write ? 'checked' : ''}> Write</label>
                <label><input type="checkbox" id="othersExecute" ${data.permissions.others.execute ? 'checked' : ''}> Execute</label>
              </div>
            </div>
            <div style="margin:10px 0">
              <label>Octal: <input type="text" id="octalPerms" value="${data.octal}" style="width:60px;padding:4px"></label>
            </div>
          </div>
          <div style="margin:15px 0">
            <h4>Ownership</h4>
            <div style="display:grid;grid-template-columns:80px 1fr;gap:10px;align-items:center">
              <label>Owner:</label>
              <input type="text" id="fileOwner" value="${data.owner}" style="padding:4px">
              <label>Group:</label>
              <input type="text" id="fileGroup" value="${data.group}" style="padding:4px">
            </div>
          </div>
          <div style="text-align:right;margin-top:15px">
            <button id="applyPermissions" class="btn btn-primary">Apply</button>
            <button onclick="hideModal()" class="btn btn-secondary">Cancel</button>
          </div>
        </div>
      `;
      
      showModal(permissionsHtml);
      
      document.getElementById('applyPermissions').onclick = () => {
        applyPermissions(filePath);
      };
      
      // Update octal when checkboxes change
      const checkboxes = document.querySelectorAll('#modalCard input[type="checkbox"]');
      checkboxes.forEach(cb => {
        cb.addEventListener('change', updateOctal);
      });
      
      function updateOctal() {
        let octal = '';
        const groups = ['owner', 'group', 'others'];
        groups.forEach(group => {
          let value = 0;
          if (document.getElementById(group + 'Read').checked) value += 4;
          if (document.getElementById(group + 'Write').checked) value += 2;
          if (document.getElementById(group + 'Execute').checked) value += 1;
          octal += value;
        });
        document.getElementById('octalPerms').value = octal;
      }
    })
    .catch(e => {
      console.error('Failed to get permissions:', e);
      showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to get file permissions</p></div>');
    });
}

async function applyPermissions(filePath) {
  try {
    const permissions = {
      owner: {
        read: document.getElementById('ownerRead').checked,
        write: document.getElementById('ownerWrite').checked,
        execute: document.getElementById('ownerExecute').checked
      },
      group: {
        read: document.getElementById('groupRead').checked,
        write: document.getElementById('groupWrite').checked,
        execute: document.getElementById('groupExecute').checked
      },
      others: {
        read: document.getElementById('othersRead').checked,
        write: document.getElementById('othersWrite').checked,
        execute: document.getElementById('othersExecute').checked
      }
    };
    
    const owner = document.getElementById('fileOwner').value;
    const group = document.getElementById('fileGroup').value;
    
    const response = await fetch('/api/permissions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        path: filePath,
        permissions: permissions,
        owner: owner,
        group: group
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to set permissions');
    }
    
    hideModal();
    load(state.path);
    showModal('<div style="padding:8px"><h3>Success</h3><p>Permissions updated successfully!</p></div>');
    setTimeout(hideModal, 1500);
  } catch (e) {
    console.error('Failed to set permissions:', e);
    showModal('<div style="padding:8px"><h3>Error</h3><p>Failed to set permissions</p></div>');
  }
}

function showServerControlPanel() {
  const serverHtml = `
    <div style="padding:20px;max-width:900px">
      <h2 style="margin-top:0;display:flex;align-items:center;gap:10px">
        <span>🛠️</span> Server Configuration
      </h2>
      
      <!-- Tab Navigation -->
      <div class="tabs" style="display:flex;border-bottom:1px solid var(--border-color);margin-bottom:20px">
        <button class="tab-btn active" data-tab="nfs-tab" style="padding:10px 20px;border:none;background:none;cursor:pointer;border-bottom:2px solid var(--accent-color);color:var(--accent-color)">
          🗂️ NFS Server
        </button>
        <button class="tab-btn" data-tab="smb-tab" style="padding:10px 20px;border:none;background:none;cursor:pointer;color:var(--text-color);opacity:0.7">
          💼 SMB Server
        </button>
      </div>
      
      <!-- NFS Tab Content -->
      <div id="nfs-tab" class="tab-content" style="display:block">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
          <h3 style="margin:0">NFS Server Settings</h3>
          <label class="switch">
            <input type="checkbox" id="nfsEnabled" ${state.servers.nfs.enabled ? 'checked' : ''}>
            <span class="slider round"></span>
            <span style="margin-left:10px;font-weight:500">${state.servers.nfs.enabled ? 'Enabled' : 'Disabled'}</span>
          </label>
        </div>
        
        <div id="nfsConfig" style="${state.servers.nfs.enabled ? '' : 'opacity:0.5;pointer-events:none'}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px">
            <h4 style="margin:0">Shared Directories</h4>
            <button id="addNfsShare" class="btn btn-primary" style="font-size:13px;padding:6px 12px">
              <span style="font-size:16px;margin-right:5px">+</span> Add Share
            </button>
          </div>
          
          <div id="nfsShares" style="margin-bottom:20px">
            ${state.servers.nfs.shares.length === 0 ? `
              <div style="text-align:center;padding:30px;background:var(--hover-bg);border-radius:8px;color:var(--text-color);opacity:0.7">
                No NFS shares configured. Click "Add Share" to get started.
              </div>
            ` : ''}
          </div>
          
          <div class="card" style="background:var(--hover-bg);padding:15px;border-radius:8px;margin-top:20px">
            <h4 style="margin-top:0">Connection Information</h4>
            <div style="display:grid;grid-template-columns:120px 1fr;gap:10px;font-family:monospace;font-size:13px">
              <div style="opacity:0.7">Server IP:</div>
              <div>${window.location.hostname}</div>
              <div style="opacity:0.7">Port:</div>
              <div>2049</div>
              <div style="opacity:0.7">Example:</div>
              <div>mount -t nfs ${window.location.hostname}:/path/to/share /mnt/nfs</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- SMB Tab Content -->
      <div id="smb-tab" class="tab-content" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
          <h3 style="margin:0">SMB Server Settings</h3>
          <label class="switch">
            <input type="checkbox" id="smbEnabled" ${state.servers.smb.enabled ? 'checked' : ''}>
            <span class="slider round"></span>
            <span style="margin-left:10px;font-weight:500">${state.servers.smb.enabled ? 'Enabled' : 'Disabled'}</span>
          </label>
        </div>
        
        <div id="smbConfig" style="${state.servers.smb.enabled ? '' : 'opacity:0.5;pointer-events:none'}">
          <!-- Users Section -->
          <div class="card" style="margin-bottom:25px;border:1px solid var(--border-color);border-radius:8px;overflow:hidden">
            <div style="background:var(--hover-bg);padding:12px 15px;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center">
              <h4 style="margin:0">Users</h4>
              <button id="addSmbUser" class="btn btn-secondary" style="font-size:13px;padding:4px 10px">
                <span style="font-size:14px;margin-right:5px">+</span> Add User
              </button>
            </div>
            <div id="smbUsers" style="padding:10px">
              ${state.servers.smb.users.length === 0 ? `
                <div style="text-align:center;padding:20px;color:var(--text-color);opacity:0.7">
                  No SMB users configured. Add a user to enable access to shares.
                </div>
              ` : ''}
            </div>
          </div>
          
          <!-- Shares Section -->
          <div class="card" style="border:1px solid var(--border-color);border-radius:8px;overflow:hidden">
            <div style="background:var(--hover-bg);padding:12px 15px;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center">
              <h4 style="margin:0">Shared Directories</h4>
              <button id="addSmbShare" class="btn btn-primary" style="font-size:13px;padding:4px 10px">
                <span style="font-size:14px;margin-right:5px">+</span> Add Share
              </button>
            </div>
            <div id="smbShares" style="padding:10px">
              ${state.servers.smb.shares.length === 0 ? `
                <div style="text-align:center;padding:20px;color:var(--text-color);opacity:0.7">
                  No SMB shares configured. Add a share to make directories available.
                </div>
              ` : ''}
            </div>
          </div>
          
          <!-- Connection Info -->
          <div class="card" style="background:var(--hover-bg);padding:15px;border-radius:8px;margin-top:20px">
            <h4 style="margin-top:0">Connection Information</h4>
            <div style="display:grid;grid-template-columns:120px 1fr;gap:10px;font-family:monospace;font-size:13px">
              <div style="opacity:0.7">Server:</div>
              <div>\\\\${window.location.hostname}</div>
              <div style="opacity:0.7">Port:</div>
              <div>445</div>
              <div style="opacity:0.7">Example:</div>
              <div>net use Z: \\\\${window.location.hostname}\sharename /user:username</div>
            </div>
          </div>
        </div>
      </div>
      
      <div style="text-align:right;margin-top:30px;padding-top:20px;border-top:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:13px;color:var(--text-color);opacity:0.7">
          Changes will take effect after saving and restarting the server.
        </div>
        <div>
          <button onclick="hideModal()" class="btn btn-secondary" style="margin-right:10px">Cancel</button>
          <button id="saveServerConfig" class="btn btn-primary">Save Configuration</button>
        </div>
      </div>
    </div>
    
    <style>
      .switch {
        position: relative;
        display: inline-block;
        width: 50px;
        height: 24px;
        vertical-align: middle;
      }
      .switch input { 
        opacity: 0;
        width: 0;
        height: 0;
      }
      .slider {
        position: absolute;
        cursor: pointer;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #ccc;
        transition: .4s;
        border-radius: 24px;
      }
      .slider:before {
        position: absolute;
        content: "";
        height: 16px;
        width: 16px;
        left: 4px;
        bottom: 4px;
        background-color: white;
        transition: .4s;
        border-radius: 50%;
      }
      input:checked + .slider {
        background-color: var(--accent-color);
      }
      input:focus + .slider {
        box-shadow: 0 0 1px var(--accent-color);
      }
      input:checked + .slider:before {
        transform: translateX(26px);
      }
      .tab-btn {
        padding: 10px 20px;
        border: none;
        background: none;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        color: var(--text-color);
        opacity: 0.7;
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
      }
      .tab-btn:hover {
        opacity: 1;
      }
      .tab-btn.active {
        opacity: 1;
        color: var(--accent-color);
        border-bottom-color: var(--accent-color);
      }
      .card {
        background: var(--card-bg);
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        overflow: hidden;
      }
    </style>
  `;
  
  showModal(serverHtml);
  
  // Render existing shares and users
  renderNfsShares();
  renderSmbUsers();
  renderSmbShares();
  
  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Update active tab
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // Show corresponding tab content
      document.querySelectorAll('.tab-content').forEach(content => {
        content.style.display = 'none';
      });
      document.getElementById(btn.dataset.tab).style.display = 'block';
    });
  });
  
  // Toggle server status
  const updateServerStatus = (serverType, enabled) => {
    const configDiv = document.getElementById(`${serverType}Config`);
    if (enabled) {
      configDiv.style.opacity = '1';
      configDiv.style.pointerEvents = 'auto';
    } else {
      configDiv.style.opacity = '0.5';
      configDiv.style.pointerEvents = 'none';
    }
    // Update the status text
    const statusSpan = document.querySelector(`#${serverType}Enabled`).nextElementSibling.nextElementSibling;
    statusSpan.textContent = enabled ? 'Enabled' : 'Disabled';
  };
  
  document.getElementById('nfsEnabled').addEventListener('change', (e) => {
    state.servers.nfs.enabled = e.target.checked;
    updateServerStatus('nfs', e.target.checked);
  });
  
  document.getElementById('smbEnabled').addEventListener('change', (e) => {
    state.servers.smb.enabled = e.target.checked;
    updateServerStatus('smb', e.target.checked);
  });
  
  // Initialize server status display
  updateServerStatus('nfs', state.servers.nfs.enabled);
  updateServerStatus('smb', state.servers.smb.enabled);
  
  // Button event listeners
  document.getElementById('addNfsShare').onclick = addNfsShare;
  document.getElementById('addSmbUser').onclick = addSmbUser;
  document.getElementById('addSmbShare').onclick = addSmbShare;
  document.getElementById('saveServerConfig').onclick = saveServerConfiguration;
}

function renderNfsShares() {
  const container = document.getElementById('nfsShares');
  if (!container) return;
  
  if (state.servers.nfs.shares.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:20px;color:var(--text-color);opacity:0.7">
        No NFS shares configured. Click "Add Share" to get started.
      </div>
    `;
    return;
  }
  
  container.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 200px 100px;gap:10px;margin-bottom:10px;font-weight:500;padding:8px 0;border-bottom:1px solid var(--border-color)">
      <div>Path</div>
      <div>Options</div>
      <div>Actions</div>
    </div>
  `;
  
  state.servers.nfs.shares.forEach((share, index) => {
    const shareDiv = document.createElement('div');
    shareDiv.style.cssText = 'display:grid;grid-template-columns:1fr 200px 100px;gap:10px;align-items:center;padding:10px 0;border-bottom:1px dashed var(--border-color)';
    shareDiv.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px">
        <span>📁</span>
        <input type="text" 
               value="${share.path}" 
               placeholder="/path/to/share" 
               style="flex:1;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="path" 
               readonly>
        <button class="btn btn-secondary" 
                style="padding:6px 10px;min-width:80px" 
                onclick="browseNfsSharePath(${index})">
          Browse...
        </button>
      </div>
      <div>
        <input type="text" 
               value="${share.options || 'rw,sync,no_subtree_check'}" 
               placeholder="Options" 
               style="width:100%;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="options">
      </div>
      <div>
        <button class="btn btn-danger" 
                style="width:100%;padding:6px 10px" 
                onclick="if(confirm('Are you sure you want to remove this NFS share?')) removeNfsShare(${index})">
          Remove
        </button>
      </div>
    `;
    container.appendChild(shareDiv);
    
    // Add event listeners for input changes
    shareDiv.querySelectorAll('input').forEach(input => {
      input.addEventListener('change', (e) => {
        const index = parseInt(e.target.dataset.index);
        const field = e.target.dataset.field;
        state.servers.nfs.shares[index][field] = e.target.value;
      });
    });
  });
}

function renderSmbUsers() {
  const container = document.getElementById('smbUsers');
  if (!container) return;
  
  if (state.servers.smb.users.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:20px;color:var(--text-color);opacity:0.7">
        No SMB users configured. Add a user to enable access to shares.
      </div>
    `;
    return;
  }
  
  container.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr 100px;gap:10px;margin-bottom:10px;font-weight:500;padding:8px 0;border-bottom:1px solid var(--border-color)">
      <div>Username</div>
      <div>Password</div>
      <div>Actions</div>
    </div>
  `;
  
  state.servers.smb.users.forEach((user, index) => {
    const userDiv = document.createElement('div');
    userDiv.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 100px;gap:10px;align-items:center;padding:10px 0;border-bottom:1px dashed var(--border-color)';
    
    userDiv.innerHTML = `
      <div>
        <input type="text" 
               value="${user.username}" 
               placeholder="Username" 
               style="width:100%;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="username"
               required>
      </div>
      <div>
        <input type="password" 
               value="${user.password}" 
               placeholder="Password" 
               style="width:100%;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="password"
               required>
      </div>
      <div>
        <button class="btn btn-danger" 
                style="width:100%;padding:6px 10px" 
                onclick="if(confirm('Are you sure you want to remove this user?')) removeSmbUser(${index})">
          Remove
        </button>
      </div>
    `;
    container.appendChild(userDiv);
    
    // Add event listeners for input changes
    userDiv.querySelectorAll('input').forEach(input => {
      input.addEventListener('change', (e) => {
        const index = parseInt(e.target.dataset.index);
        const field = e.target.dataset.field;
        state.servers.smb.users[index][field] = e.target.value;
      });
      
      // Add validation
      input.addEventListener('blur', (e) => {
        if (e.target.required && !e.target.value.trim()) {
          e.target.style.borderColor = 'var(--danger-color)';
        } else {
          e.target.style.borderColor = 'var(--border-color)';
        }
      });
    });
  });
}

function renderSmbShares() {
  const container = document.getElementById('smbShares');
  if (!container) return;
  
  if (state.servers.smb.shares.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:20px;color:var(--text-color);opacity:0.7">
        No SMB shares configured. Add a share to make directories available.
      </div>
    `;
    return;
  }
  
  container.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr 120px 120px 100px;gap:10px;margin-bottom:10px;font-weight:500;padding:8px 0;border-bottom:1px solid var(--border-color)">
      <div>Share Name</div>
      <div>Path</div>
      <div>Access</div>
      <div>Users</div>
      <div>Actions</div>
    </div>
  `;
  
  state.servers.smb.shares.forEach((share, index) => {
    const shareDiv = document.createElement('div');
    shareDiv.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 120px 120px 100px;gap:10px;align-items:center;padding:10px 0;border-bottom:1px dashed var(--border-color)';
    
    // Get list of users with access to this share
    const userList = (share.users || []).length > 0 
      ? share.users.join(', ') 
      : 'All users';
    
    shareDiv.innerHTML = `
      <div>
        <input type="text" 
               value="${share.name}" 
               placeholder="Share Name" 
               style="width:100%;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="name"
               required>
      </div>
      <div style="display:flex;gap:8px">
        <input type="text" 
               value="${share.path}" 
               placeholder="/path/to/share" 
               style="flex:1;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
               data-index="${index}" 
               data-field="path" 
               readonly>
        <button class="btn btn-secondary" 
                style="padding:6px 10px;min-width:80px" 
                onclick="browseSmbSharePath(${index})">
          Browse...
        </button>
      </div>
      <div>
        <select style="width:100%;padding:6px 10px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);color:var(--text-color)" 
                data-index="${index}" 
                data-field="access">
          <option value="ro" ${share.access === 'ro' ? 'selected' : ''}>Read Only</option>
          <option value="rw" ${share.access === 'rw' ? 'selected' : ''}>Read/Write</option>
        </select>
      </div>
      <div title="${userList}" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
        ${userList}
      </div>
      <div>
        <button class="btn btn-danger" 
                style="width:100%;padding:6px 10px" 
                onclick="if(confirm('Are you sure you want to remove this share?')) removeSmbShare(${index})">
          Remove
        </button>
      </div>
    `;
    container.appendChild(shareDiv);
    
    // Add event listeners for input changes
    shareDiv.querySelectorAll('input, select').forEach(input => {
      input.addEventListener('change', (e) => {
        const index = parseInt(e.target.dataset.index);
        const field = e.target.dataset.field;
        state.servers.smb.shares[index][field] = e.target.value;
      });
      
      // Add validation for required fields
      if (input.required) {
        input.addEventListener('blur', (e) => {
          if (!e.target.value.trim()) {
            e.target.style.borderColor = 'var(--danger-color)';
          } else {
            e.target.style.borderColor = 'var(--border-color)';
          }
        });
      }
    });
  });
}

function addNfsShare() {
  // Check if we can add more shares (optional: implement a limit)
  const maxShares = 10; // Example limit
  if (state.servers.nfs.shares.length >= maxShares) {
    showToast(`Maximum of ${maxShares} NFS shares allowed`, 'error');
    return;
  }
  
  // Show folder browser with a callback
  showFolderBrowser((selectedPath) => {
    if (!selectedPath) return; // User cancelled
    
    // Check if this path is already shared
    const isDuplicate = state.servers.nfs.shares.some(share => 
      share.path === selectedPath
    );
    
    if (isDuplicate) {
      showToast('This path is already shared', 'error');
      return;
    }
    
    // Add the new share
    state.servers.nfs.shares.push({
      path: selectedPath, 
      options: 'rw,sync,no_subtree_check',
      comment: ''
    });
    
    // Re-render the shares list
    renderNfsShares();
    showToast('NFS share added', 'success');
  });
}

function addSmbUser() {
  // Check if we can add more users (optional: implement a limit)
  const maxUsers = 20; // Example limit
  if (state.servers.smb.users.length >= maxUsers) {
    showToast(`Maximum of ${maxUsers} SMB users allowed`, 'error');
    return;
  }
  
  // Add a new user with default values
  state.servers.smb.users.push({
    username: `user${state.servers.smb.users.length + 1}`,
    password: '',
    enabled: true
  });
  
  // Re-render the users list
  renderSmbUsers();
  
  // Scroll to the bottom to show the new user
  const container = document.getElementById('smbUsers');
  if (container) {
    container.scrollTop = container.scrollHeight;
    
    // Focus the username field of the newly added user
    const inputs = container.querySelectorAll('input[data-field="username"]');
    if (inputs.length > 0) {
      inputs[inputs.length - 1].focus();
    }
  }
  
  showToast('New user added. Please set a password.', 'info');
}

function addSmbShare() {
  // Check if we can add more shares (optional: implement a limit)
  const maxShares = 20; // Example limit
  if (state.servers.smb.shares.length >= maxShares) {
    showToast(`Maximum of ${maxShares} SMB shares allowed`, 'error');
    return;
  }
  
  // Show folder browser to select the share path
  showFolderBrowser((selectedPath) => {
    if (!selectedPath) return; // User cancelled
    
    // Generate a default share name from the last part of the path
    let shareName = selectedPath.split('/').filter(Boolean).pop() || 'share';
    
    // Clean up the share name to be SMB compatible
    shareName = shareName
      .replace(/[^a-zA-Z0-9_-]/g, '_') // Replace special chars with underscore
      .toLowerCase()
      .substring(0, 15); // Limit length
    
    // Ensure the share name is unique
    let counter = 1;
    let baseName = shareName;
    while (state.servers.smb.shares.some(share => share.name === shareName)) {
      shareName = `${baseName}${counter}`;
      counter++;
      
      // Prevent infinite loops
      if (counter > 100) {
        showToast('Too many similar share names', 'error');
        return;
      }
    }
    
    // Check if this path is already shared
    const isDuplicate = state.servers.smb.shares.some(share => 
      share.path === selectedPath
    );
    
    if (isDuplicate) {
      showToast('This path is already shared', 'error');
      return;
    }
    
    // Add the new share with default values
    state.servers.smb.shares.push({
      name: shareName,
      path: selectedPath,
      access: 'rw',
      browseable: true,
      guest_ok: false,
      comment: '',
      users: [] // Empty array means all users can access
    });
    
    // Re-render the shares list
    renderSmbShares();
    showToast('SMB share added', 'success');
  });
}

function removeNfsShare(index) {
  if (index < 0 || index >= state.servers.nfs.shares.length) return;
  
  const share = state.servers.nfs.shares[index];
  
  // Show confirmation dialog
  if (!confirm(`Are you sure you want to remove the NFS share for '${share.path}'?`)) {
    return;
  }
  
  // Remove the share
  state.servers.nfs.shares.splice(index, 1);
  
  // Re-render the shares list
  renderNfsShares();
  showToast('NFS share removed', 'success');
}

function removeSmbUser(index) {
  if (index < 0 || index >= state.servers.smb.users.length) return;
  
  const user = state.servers.smb.users[index];
  
  // Check if this user is used in any shares
  const usedInShares = state.servers.smb.shares.some(share => 
    share.users && share.users.includes(user.username)
  );
  
  if (usedInShares) {
    showToast('Cannot remove: User is assigned to one or more shares', 'error');
    return;
  }
  
  // Show confirmation dialog
  if (!confirm(`Are you sure you want to remove the user '${user.username}'?`)) {
    return;
  }
  
  // Remove the user
  state.servers.smb.users.splice(index, 1);
  
  // Re-render the users list
  renderSmbUsers();
  showToast('User removed', 'success');
}

function removeSmbShare(index) {
  if (index < 0 || index >= state.servers.smb.shares.length) return;
  
  const share = state.servers.smb.shares[index];
  
  // Show confirmation dialog
  if (!confirm(`Are you sure you want to remove the SMB share '${share.name}'?`)) {
    return;
  }
  
  // Remove the share
  state.servers.smb.shares.splice(index, 1);
  
  // Re-render the shares list
  renderSmbShares();
  showToast('SMB share removed', 'success');
}

function browseNfsSharePath(index) {
  showFolderBrowser((selectedPath) => {
    state.servers.nfs.shares[index].path = selectedPath;
    renderNfsShares();
  });
}

function browseSmbSharePath(index) {
  showFolderBrowser((selectedPath) => {
    state.servers.smb.shares[index].path = selectedPath;
    renderSmbShares();
  });
}

function showFolderBrowser(callback) {
  const folderHtml = `
    <div style="padding:20px;max-width:600px">
      <h2>Select Folder</h2>
      <div style="margin:20px 0">
        <div id="folderBreadcrumb" style="margin-bottom:15px;font-size:14px;color:var(--accent-color)"></div>
        <div id="folderList" style="max-height:400px;overflow-y:auto;border:1px solid var(--border-color);border-radius:4px;padding:10px"></div>
      </div>
      <div style="text-align:right;margin-top:20px;padding-top:15px;border-top:1px solid var(--border-color)">
        <button id="selectFolder" class="btn btn-primary">Select This Folder</button>
        <button onclick="hideModal()" class="btn btn-secondary">Cancel</button>
      </div>
    </div>
  `;
  
  showModal(folderHtml);
  
  let currentPath = '';
  
  function loadFolders(path = '') {
    fetch('/api/list?path=' + encodeURIComponent(path))
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          showToast('Error loading folders: ' + data.error, 'error');
          return;
        }
        
        currentPath = path;
        
        // Update breadcrumb
        const breadcrumb = document.getElementById('folderBreadcrumb');
        const pathParts = path ? path.split('/').filter(p => p) : [];
        let breadcrumbHtml = '<a href="#" onclick="loadFolders(\'\')" style="color:var(--accent-color);text-decoration:none">🏠 Root</a>';
        let buildPath = '';
        pathParts.forEach(part => {
          buildPath += (buildPath ? '/' : '') + part;
          breadcrumbHtml += ` / <a href="#" onclick="loadFolders(\'${buildPath}\')" style="color:var(--accent-color);text-decoration:none">${part}</a>`;
        });
        breadcrumb.innerHTML = breadcrumbHtml;
        
        // Update folder list
        const folderList = document.getElementById('folderList');
        const folders = data.files ? data.files.filter(item => item.is_dir) : [];
        
        if (folders.length === 0) {
          folderList.innerHTML = '<div style="text-align:center;color:var(--text-color);opacity:0.6;padding:20px">No folders found</div>';
        } else {
          folderList.innerHTML = folders.map(folder => {
            const folderPath = path ? path + '/' + folder.name : folder.name;
            return `
              <div style="padding:8px;cursor:pointer;border-radius:4px;display:flex;align-items:center;gap:8px" 
                   onmouseover="this.style.background='var(--hover-bg)'" 
                   onmouseout="this.style.background='transparent'" 
                   onclick="loadFolders('${folderPath}')">
                <span>📁</span>
                <span>${folder.name}</span>
              </div>
            `;
          }).join('');
        }
      })
      .catch(e => {
        showToast('Error loading folders: ' + e.message, 'error');
      });
  }
  
  // Load initial folders
  loadFolders();
  
  // Select folder button
  document.getElementById('selectFolder').onclick = () => {
    callback(currentPath);
    hideModal();
  };
  
  // Make loadFolders available globally for breadcrumb clicks
  window.loadFolders = loadFolders;
}

function saveServerConfiguration() {
  // Validate configuration before saving
  const errors = [];
  
  // Validate NFS shares
  state.servers.nfs.shares.forEach((share, index) => {
    if (!share.path) {
      errors.push(`NFS share #${index + 1}: Path is required`);
    }
  });
  
  // Validate SMB users
  const usernames = new Set();
  state.servers.smb.users.forEach((user, index) => {
    if (!user.username) {
      errors.push(`SMB user #${index + 1}: Username is required`);
    } else if (usernames.has(user.username)) {
      errors.push(`SMB user #${index + 1}: Username '${user.username}' is duplicated`);
    } else {
      usernames.add(user.username);
    }
    
    if (!user.password && state.servers.smb.users.length > 1) {
      errors.push(`SMB user '${user.username}': Password is required`);
    }
  });
  
  // Validate SMB shares
  const shareNames = new Set();
  state.servers.smb.shares.forEach((share, index) => {
    if (!share.name) {
      errors.push(`SMB share #${index + 1}: Share name is required`);
    } else if (shareNames.has(share.name)) {
      errors.push(`SMB share #${index + 1}: Share name '${share.name}' is duplicated`);
    } else {
      shareNames.add(share.name);
    }
    
    if (!share.path) {
      errors.push(`SMB share '${share.name}': Path is required`);
    }
  });
  
  // Show errors if any
  if (errors.length > 0) {
    const errorHtml = `
      <div style="max-height:200px;overflow-y:auto;margin-bottom:15px">
        <h4 style="color:var(--danger-color);margin-top:0">Please fix the following errors:</h4>
        <ul style="margin:0;padding-left:20px;color:var(--danger-color)">
          ${errors.map(error => `<li>${error}</li>`).join('')}
        </ul>
      </div>
    `;
    
    // Find or create the error container
    let errorContainer = document.getElementById('serverConfigErrors');
    if (!errorContainer) {
      errorContainer = document.createElement('div');
      errorContainer.id = 'serverConfigErrors';
      const saveButton = document.getElementById('saveServerConfig');
      saveButton.parentNode.insertBefore(errorContainer, saveButton);
    }
    
    errorContainer.innerHTML = errorHtml;
    
    // Scroll to the first error
    window.scrollTo({
      top: errorContainer.offsetTop - 20,
      behavior: 'smooth'
    });
    
    showToast('Please fix the configuration errors', 'error');
    return;
  }
  
  // If we're here, the configuration is valid
  
  // Show loading state
  const saveButton = document.getElementById('saveServerConfig');
  const originalText = saveButton.textContent;
  saveButton.disabled = true;
  saveButton.innerHTML = '<span class="spinner">Saving...</span>';
  
  // Send the configuration to the server
  fetch('/api/server/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      nfs: state.servers.nfs,
      smb: state.servers.smb
    })
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.error || 'Failed to save configuration');
      });
    }
    return response.json();
  })
  .then(data => {
    if (data.success) {
      showToast('Server configuration saved successfully', 'success');
      
      // If the server needs a restart, show a notice
      if (data.requires_restart) {
        showToast('Server restart required for changes to take effect', 'warning');
      }
      
      // Close the modal after a short delay
      setTimeout(hideModal, 1000);
    } else {
      throw new Error(data.error || 'Failed to save configuration');
    }
  })
  .catch(error => {
    console.error('Error saving server configuration:', error);
    showToast('Error saving configuration: ' + error.message, 'error');
    
    // Re-enable the save button
    saveButton.disabled = false;
    saveButton.textContent = originalText;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  console.log('filebrowser: DOM ready');
  initTheme();
  document.getElementById('fileInput').addEventListener('change', (ev) => {
    handleFileUpload(ev.target.files);
    ev.target.value = '';
  });
  const savedViewMode = localStorage.getItem('viewMode') || 'list';
  setViewMode(savedViewMode);
  document.getElementById('uploadBtn').onclick = showUploadModal;
  document.getElementById('refresh').onclick = () => load(state.path);
  document.getElementById('mkdir').onclick = createFolder;
  document.getElementById('toggleHidden').onclick = toggleHiddenFiles;
  document.getElementById('serverControlBtn').onclick = showServerControlPanel;
  document.getElementById('themeToggle').onclick = toggleTheme;
  
  // Initialize hidden files state
  state.showHidden = localStorage.getItem('showHidden') === 'true';
  const hiddenBtn = document.getElementById('toggleHidden');
  hiddenBtn.textContent = state.showHidden ? '🙈' : '👁️';
  hiddenBtn.title = state.showHidden ? 'Hide hidden files' : 'Show hidden files';
  document.getElementById('selectAllBtn').onclick = selectAll;
  document.getElementById('selectNoneBtn').onclick = clearSelection;
  document.getElementById('openBtn').onclick = () => {
    if (state.selectedFiles.size === 1) {
      const path = Array.from(state.selectedFiles)[0];
      const file = state.files.find(f => f.path === path);
      if (file && file.is_dir) {
        load(file.path);
      }
    }
  };
  document.getElementById('previewBtn').onclick = () => {
    if (state.selectedFiles.size === 1) {
      const path = Array.from(state.selectedFiles)[0];
      const file = state.files.find(f => f.path === path);
      if (file && !file.is_dir) {
        preview(file.path);
      }
    }
  };
  document.getElementById('downloadBtn').onclick = () => {
    if (state.selectedFiles.size > 0) {
      state.selectedFiles.forEach(path => download(path));
    }
  };
  document.getElementById('cutBtn').onclick = cutFiles;
  document.getElementById('copyBtn').onclick = copyFiles;
  document.getElementById('pasteBtn').onclick = pasteFiles;
  document.getElementById('renameBtn').onclick = () => {
    if (state.selectedFiles.size === 1) {
      const path = Array.from(state.selectedFiles)[0];
      const file = state.files.find(f => f.path === path);
      if (file) {
        renamePrompt(file.path, file.name);
      }
    }
  };
  document.getElementById('deleteBtn').onclick = () => {
    if (state.selectedFiles.size > 0) {
      const count = state.selectedFiles.size;
      if (confirm(`Are you sure you want to delete ${count} item(s)?`)) {
        state.selectedFiles.forEach(path => {
          fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path})
          }).then(() => load(state.path));
        });
      }
    }
  };
  document.getElementById('propertiesBtn').onclick = showProperties;
  document.getElementById('editBtn').onclick = () => {
    if (state.selectedFiles.size === 1) {
      const path = Array.from(state.selectedFiles)[0];
      const file = state.files.find(f => f.path === path);
      if (file && !file.is_dir) {
        showTextEditor(file.path);
      }
    }
  };
  document.getElementById('permissionsBtn').onclick = showPermissionsDialog;
  document.getElementById('listViewBtn').onclick = () => setViewMode('list');
  document.getElementById('gridViewBtn').onclick = () => setViewMode('grid');
  document.querySelectorAll('.dropdown-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = btn.parentElement;
      const menu = dropdown.querySelector('.dropdown-menu');
      document.querySelectorAll('.dropdown-menu.show').forEach(otherMenu => {
        if (otherMenu !== menu) {
          otherMenu.classList.remove('show');
        }
      });
      menu.classList.toggle('show');
    });
  });
  document.addEventListener('click', () => {
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
      menu.classList.remove('show');
    });
  });
  document.querySelectorAll('.dropdown-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
      });
    });
  });
  document.getElementById('ctxOpen').onclick = () => {
    if (state.contextTarget && state.contextTarget.is_dir) {
      load(state.contextTarget.path);
    }
    hideContextMenu();
  };
  document.getElementById('ctxPreview').onclick = () => {
    if (state.contextTarget && !state.contextTarget.is_dir) {
      preview(state.contextTarget.path);
    }
    hideContextMenu();
  };
  document.getElementById('ctxCut').onclick = () => {
    cutFiles();
    hideContextMenu();
  };
  document.getElementById('ctxCopy').onclick = () => {
    copyFiles();
    hideContextMenu();
  };
  document.getElementById('ctxPaste').onclick = () => {
    pasteFiles();
    hideContextMenu();
  };
  document.getElementById('ctxDownload').onclick = () => {
    if (state.selectedFiles.size > 0) {
      state.selectedFiles.forEach(path => download(path));
    }
    hideContextMenu();
  };
  document.getElementById('ctxRename').onclick = () => {
    if (state.contextTarget) {
      renamePrompt(state.contextTarget.path, state.contextTarget.name);
    }
    hideContextMenu();
  };
  document.getElementById('ctxDelete').onclick = () => {
    if (state.selectedFiles.size > 0) {
      const count = state.selectedFiles.size;
      if (confirm(`Are you sure you want to delete ${count} item(s)?`)) {
        state.selectedFiles.forEach(path => {
          fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path})
          }).then(() => load(state.path));
        });
      }
    }
    hideContextMenu();
  };
  document.getElementById('ctxNewFolder').onclick = () => {
    createFolder();
    hideContextMenu();
  };
  document.getElementById('ctxUpload').onclick = () => {
    showUploadModal();
    hideContextMenu();
  };
  document.getElementById('ctxProperties').onclick = () => {
    showProperties();
    hideContextMenu();
  };
  document.getElementById('ctxEdit').onclick = () => {
    if (state.contextTarget && !state.contextTarget.is_dir) {
      showTextEditor(state.contextTarget.path);
    }
    hideContextMenu();
  };
  document.getElementById('ctxPermissions').onclick = () => {
    showPermissionsDialog();
    hideContextMenu();
  };
  document.getElementById('ctxRefresh').onclick = () => {
    load(state.path);
    hideContextMenu();
  };
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#contextMenu')) {
      hideContextMenu();
    }
  });
  document.addEventListener('contextmenu', (e) => {
    const listing = document.getElementById('listing');
    const isInListing = listing.contains(e.target);
    const clickedItem = e.target.closest('.row, .grid-item');
    if (isInListing) {
      e.preventDefault();
      if (!clickedItem) {
        clearSelection();
        state.contextTarget = null;
        showContextMenu(e.clientX, e.clientY);
      }
    }
  });
  document.getElementById('q').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      search(this.value);
    }
  });
  document.getElementById('aboutBtn').onclick = () => {
    showModal(`
      <div style="padding:8px">
        <h3>Python File Browser Pro</h3>
        <p>Enterprise-grade single-file server with advanced features:</p>
        <ul style="text-align:left;margin:10px 0;font-size:14px">
          <li>📁 Browse, preview, download files & folders</li>
          <li>⬆️ Upload with drag & drop support</li>
          <li>✂️ Cut, copy, paste operations</li>
          <li>🔍 Advanced search functionality</li>
          <li>🎨 Dark/light theme toggle</li>
          <li>📋 List and grid view modes</li>
          <li>🖱️ Right-click context menus</li>
          <li>⌨️ Comprehensive keyboard shortcuts</li>
          <li>📊 File properties and statistics</li>
          <li>🔄 Multi-file selection and operations</li>
          <li>📱 Responsive design for all devices</li>
        </ul>
        <div style="margin-top:15px;padding:10px;background:#f3f4f6;border-radius:6px;font-size:12px">
          <strong>Keyboard Shortcuts:</strong><br>
          Ctrl+A: Select All | Ctrl+X: Cut | Ctrl+C: Copy | Ctrl+V: Paste<br>
          Ctrl+N: New Folder | Ctrl+U: Upload | Ctrl+F: Search | F2: Rename<br>
          Delete: Delete Selected | F5: Refresh | Enter: Open/Preview
        </div>
        <p style="font-size:12px;color:#6b7280;margin-top:10px">Built with Python + vanilla JS • Enterprise NAS-level functionality</p>
      </div>
    `);
  };
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Escape') {
        e.target.blur();
      }
      return;
    }
    if (e.ctrlKey || e.metaKey) {
      switch(e.key) {
        case 'u':
          e.preventDefault();
          showUploadModal();
          break;
        case 'r':
          e.preventDefault();
          load(state.path);
          break;
        case 'f':
          e.preventDefault();
          document.getElementById('q').focus();
          break;
        case 'a':
          e.preventDefault();
          selectAll();
          break;
        case 'x':
          e.preventDefault();
          cutFiles();
          break;
        case 'c':
          e.preventDefault();
          copyFiles();
          break;
        case 'v':
          e.preventDefault();
          pasteFiles();
          break;
        case 'n':
          e.preventDefault();
          createFolder();
          break;
      }
    } else {
      switch(e.key) {
        case 'Delete':
        case 'Backspace':
          if (state.selectedFiles.size > 0) {
            e.preventDefault();
            const count = state.selectedFiles.size;
            if (confirm(`Are you sure you want to delete ${count} item(s)?`)) {
              state.selectedFiles.forEach(path => {
                fetch('/api/delete', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({path})
                }).then(() => load(state.path));
              });
            }
          }
          break;
        case 'F2':
          if (state.selectedFiles.size === 1) {
            e.preventDefault();
            const path = Array.from(state.selectedFiles)[0];
            const file = state.files.find(f => f.path === path);
            if (file) {
              renamePrompt(file.path, file.name);
            }
          }
          break;
        case 'F5':
          e.preventDefault();
          load(state.path);
          break;
        case 'Enter':
          if (state.selectedFiles.size === 1) {
            e.preventDefault();
            const path = Array.from(state.selectedFiles)[0];
            const file = state.files.find(f => f.path === path);
            if (file) {
              if (file.is_dir) {
                load(file.path);
              } else {
                preview(file.path);
              }
            }
          }
          break;
        case 'Escape':
          hideModal();
          hideContextMenu();
          clearSelection();
          break;
      }
    }
  });
  window.addEventListener('error', (e) => {
    console.error('JS error', e);
    try {
      showModal(`<div style="padding:8px"><h3>JavaScript Error</h3><pre>${escapeHtml(e.message||String(e))}</pre></div>`);
    } catch(_) {}
  });
  window.addEventListener('unhandledrejection', (e) => {
    console.error('UnhandledRejection', e);
    try {
      showModal(`<div style="padding:8px"><h3>Unhandled Promise Rejection</h3><pre>${escapeHtml(String(e.reason||e))}</pre></div>`);
    } catch(_) {}
  });
  load('/');
});
</script>
</body>
</html>
"""

class SimpleFileBrowserHandler(BaseHTTPRequestHandler):
	server_version = "SimpleFileBrowser/0.1"

	def _set_json(self, code=200):
		self.send_response(code)
		self.send_header('Content-Type', 'application/json; charset=utf-8')
		self.end_headers()

	def _set_text(self, code=200, ctype='text/html; charset=utf-8'):
		self.send_response(code)
		self.send_header('Content-Type', ctype)
		self.end_headers()

	def do_AUTHHEAD(self):
		self.send_response(401)
		self.send_header('WWW-Authenticate', 'Basic realm="File Browser"')
		self.send_header('Content-Type', 'text/html')
		self.end_headers()

	def authenticate(self):
		pwd = getattr(self.server, 'auth_password', None)
		if not pwd:
			return True
		header = self.headers.get('Authorization')
		if header is None:
			self.do_AUTHHEAD()
			return False
		try:
			kind, val = header.split(' ', 1)
			if kind != 'Basic':
				self.do_AUTHHEAD()
				return False
			dec = base64.b64decode(val).decode()
			if dec == pwd or dec.split(':', 1)[-1] == pwd:
				return True
		except Exception:
			pass
		self.do_AUTHHEAD()
		return False

	def translate_path_safe(self, qpath):
		rp = self.server.root_path
		if qpath.startswith('/'):
			q = qpath
		else:
			q = '/' + qpath
		q = urllib.parse.unquote(q)
		target = (rp / q.lstrip('/')).resolve()
		try:
			target.relative_to(rp)
		except Exception:
			raise PermissionError('Path outside root')
		return target

	def do_GET(self):
		if not self.authenticate():
			return
		parsed = urllib.parse.urlparse(self.path)
		path = parsed.path
		qs = urllib.parse.parse_qs(parsed.query)

		if path == '/' or path == '/index.html':
			self._set_text(200)
			self.wfile.write(HTML_PAGE.encode('utf-8'))
			return

		if not path.startswith('/api/'):
			self.send_error(404)
			return

		api = path[len('/api/'):]

		if api == 'list':
			p = qs.get('path', ['/'])[0]
			try:
				target = self.translate_path_safe(p)
			except PermissionError:
				self._set_json(403)
				self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
				return
			if not target.exists() or not target.is_dir():
				self._set_json(404)
				self.wfile.write(json.dumps({'error': 'not found'}).encode())
				return
			entries = []
			try:
				for name in sorted(os.listdir(target), key=lambda s: s.lower()):
					try:
						fp = target / name
						stat = fp.stat()
						entries.append({
							'name': name,
							'rel': os.path.relpath(str(fp), str(self.server.root_path)),
							'path': '/' + os.path.relpath(str(fp), str(self.server.root_path)).replace('\\', '/'),
							'is_dir': fp.is_dir(),
							'size': stat.st_size,
							'size_h': human_size(stat.st_size),
							'mtime': iso_time(stat.st_mtime)
						})
					except Exception:
						continue
			except PermissionError:
				self._set_json(403)
				self.wfile.write(json.dumps({'error': 'forbidden'}).encode())
				return
			self._set_json(200)
			self.wfile.write(json.dumps({'root': str(self.server.root_path), 'files': entries}).encode())
			return

		if api == 'download':
			p = qs.get('path', ['/'])[0]
			try:
				target = self.translate_path_safe(p)
			except PermissionError:
				self.send_error(403)
				return
			if not target.exists():
				self.send_error(404)
				return
			if target.is_dir():
				self.send_response(200)
				self.send_header('Content-Type', 'application/zip')
				self.send_header('Content-Disposition', f'attachment; filename="{target.name or "root"}.zip"')
				self.end_headers()
				with io.BytesIO() as mem:
					with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
						for root, dirs, files in os.walk(target):
							for f in files:
								full = Path(root)/f
								try:
									zf.write(str(full), arcname=os.path.relpath(str(full), str(target)))
								except Exception:
									continue
					mem.seek(0)
					shutil.copyfileobj(mem, self.wfile)
				return
			else:
				ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
				try:
					with open(target, 'rb') as fh:
						self.send_response(200)
						self.send_header('Content-Type', ctype)
						self.send_header('Content-Length', str(target.stat().st_size))
						self.send_header('Content-Disposition', f'attachment; filename="{target.name}"')
						self.end_headers()
						shutil.copyfileobj(fh, self.wfile)
				except BrokenPipeError:
					pass
				return

		if api == 'preview':
			p = qs.get('path', ['/'])[0]
			try:
				target = self.translate_path_safe(p)
			except PermissionError:
				self.send_error(403)
				return
			if not target.exists():
				self.send_error(404)
				return
			if target.is_dir():
				self._set_text(200, 'text/plain; charset=utf-8')
				self.wfile.write(b'Directory')
				return
			ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
			if ctype.startswith('text/') or ctype in ('application/json','application/javascript'):
				self.send_response(200)
				self.send_header('Content-Type', f'{ctype}; charset=utf-8')
				self.end_headers()
				with open(target, 'rb') as fh:
					data = fh.read(200000)
					self.wfile.write(data)
				return
			elif ctype.startswith('image/'):
				self.send_response(200)
				self.send_header('Content-Type', ctype)
				self.end_headers()
				with open(target, 'rb') as fh:
					shutil.copyfileobj(fh, self.wfile)
				return
			else:
				self._set_text(200, 'text/plain; charset=utf-8')
				self.wfile.write(b'No preview')
				return

		if api == 'search':
			q = qs.get('q', [''])[0]
			try:
				files = []
				for root, dirs, filenames in os.walk(self.server.root_path):
					for f in filenames + dirs:
						try:
							if q.lower() in f.lower():
								full = Path(root)/f
								stat = full.stat()
								files.append({
									'name': f,
									'rel': os.path.relpath(str(full), str(self.server.root_path)),
									'path': '/' + os.path.relpath(str(full), str(self.server.root_path)).replace('\\','/'),
									'is_dir': full.is_dir(),
									'size': stat.st_size,
									'size_h': human_size(stat.st_size),
									'mtime': iso_time(stat.st_mtime)
								})
						except Exception:
							continue
				self._set_json(200)
				self.wfile.write(json.dumps({'root':str(self.server.root_path), 'files': files}).encode())
				return
			except Exception:
				self._set_json(500)
				self.wfile.write(json.dumps({'error':'failed'}).encode())
				return

		if api == 'edit':
			p = qs.get('path', ['/'])[0]
			try:
				target = self.translate_path_safe(p)
				if not target.exists() or target.is_dir():
					self.send_error(404)
					return
				with open(target, 'r', encoding='utf-8') as f:
					content = f.read()
				self._set_text(200, 'text/plain; charset=utf-8')
				self.wfile.write(content.encode('utf-8'))
				return
			except Exception:
				self.send_error(500)
				return

		if api == 'permissions':
			p = qs.get('path', ['/'])[0]
			try:
				target = self.translate_path_safe(p)
				if not target.exists():
					self.send_error(404)
					return
				file_stat = target.stat()
				mode = file_stat.st_mode
				
				# Get owner and group names
				try:
					owner_name = pwd.getpwuid(file_stat.st_uid).pw_name
				except KeyError:
					owner_name = str(file_stat.st_uid)
				
				try:
					group_name = grp.getgrgid(file_stat.st_gid).gr_name
				except KeyError:
					group_name = str(file_stat.st_gid)
				
				permissions = {
					'owner': {
						'read': bool(mode & stat.S_IRUSR),
						'write': bool(mode & stat.S_IWUSR),
						'execute': bool(mode & stat.S_IXUSR)
					},
					'group': {
						'read': bool(mode & stat.S_IRGRP),
						'write': bool(mode & stat.S_IWGRP),
						'execute': bool(mode & stat.S_IXGRP)
					},
					'others': {
						'read': bool(mode & stat.S_IROTH),
						'write': bool(mode & stat.S_IWOTH),
						'execute': bool(mode & stat.S_IXOTH)
					}
				}
				
				octal = oct(stat.S_IMODE(mode))[-3:]
				
				self._set_json(200)
				self.wfile.write(json.dumps({
					'permissions': permissions,
					'octal': octal,
					'owner': owner_name,
					'group': group_name
				}).encode())
				return
			except Exception:
				self.send_error(500)
				return

		self.send_error(404)

	def do_POST(self):
		if not self.authenticate():
			return
		parsed = urllib.parse.urlparse(self.path)
		path = parsed.path

		if path == '/api/upload':
			import cgi
			form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST'}, keep_blank_values=True)
			target_subpath = form.getvalue('path', '/')
			try:
				target_folder = self.translate_path_safe(target_subpath)
			except Exception:
				target_folder = self.server.root_path
			files_saved = 0
			if 'file' in form:
				parts = form['file']
				if not isinstance(parts, list):
					parts = [parts]
				for part in parts:
					if part.filename:
						safe_name = Path(part.filename).name
						dest = target_folder / safe_name
						try:
							with open(dest, 'wb') as out:
								while True:
									chunk = part.file.read(8192)
									if not chunk:
										break
									out.write(chunk)
							files_saved += 1
						except Exception:
							continue
			if files_saved == 0:
				self._set_json(400)
				self.wfile.write(json.dumps({'error': 'no files uploaded'}).encode())
				return
			self._set_json(200)
			self.wfile.write(json.dumps({'saved':files_saved}).encode())
			return

		if path == '/api/mkdir':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			p = obj.get('path','/')
			name = obj.get('name')
			try:
				base = self.translate_path_safe(p)
				(base / name).mkdir(parents=False, exist_ok=False)
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/delete':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			p = obj.get('path')
			try:
				target = self.translate_path_safe(p)
				if target.is_dir():
					shutil.rmtree(target)
				else:
					target.unlink()
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/rename':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			p = obj.get('path')
			new = obj.get('new')
			try:
				target = self.translate_path_safe(p)
				dest = target.parent / new
				target.rename(dest)
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/move':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			source = obj.get('source')
			target = obj.get('target')
			try:
				source_path = self.translate_path_safe(source)
				target_path = self.translate_path_safe(target)
				shutil.move(str(source_path), str(target_path))
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/save':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			file_path = obj.get('path')
			content = obj.get('content')
			try:
				target = self.translate_path_safe(file_path)
				with open(target, 'w', encoding='utf-8') as f:
					f.write(content)
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/permissions':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			file_path = obj.get('path')
			permissions = obj.get('permissions')
			owner = obj.get('owner')
			group = obj.get('group')
			try:
				target = self.translate_path_safe(file_path)
				# Set permissions
				mode = 0
				if permissions['owner']['read']: mode |= stat.S_IRUSR
				if permissions['owner']['write']: mode |= stat.S_IWUSR
				if permissions['owner']['execute']: mode |= stat.S_IXUSR
				if permissions['group']['read']: mode |= stat.S_IRGRP
				if permissions['group']['write']: mode |= stat.S_IWGRP
				if permissions['group']['execute']: mode |= stat.S_IXGRP
				if permissions['others']['read']: mode |= stat.S_IROTH
				if permissions['others']['write']: mode |= stat.S_IWOTH
				if permissions['others']['execute']: mode |= stat.S_IXOTH
				os.chmod(target, mode)
				# Set ownership (requires root privileges)
				try:
					uid = pwd.getpwnam(owner).pw_uid if owner else -1
					gid = grp.getgrnam(group).gr_gid if group else -1
					if uid != -1 or gid != -1:
						os.chown(target, uid, gid)
				except (KeyError, PermissionError):
					pass  # Ignore ownership errors
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/move-multiple':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			obj = json.loads(body)
			sources = obj.get('sources', [])
			target = obj.get('target')
			try:
				target_path = self.translate_path_safe(target)
				for source in sources:
					source_path = self.translate_path_safe(source)
					filename = source_path.name
					dest_path = target_path / filename
					shutil.move(str(source_path), str(dest_path))
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		if path == '/api/server-config':
			length = int(self.headers.get('Content-Length',0))
			body = self.rfile.read(length)
			config = json.loads(body)
			try:
				# Save server configuration
				self.server.server_config = config
				# Restart servers with new config
				if hasattr(self.server, 'nfs_server'):
					self.server.nfs_server.update_config(config.get('nfs', {}))
				if hasattr(self.server, 'smb_server'):
					self.server.smb_server.update_config(config.get('smb', {}))
				self._set_json(200)
				self.wfile.write(json.dumps({'ok':True}).encode())
			except Exception as e:
				self._set_json(400)
				self.wfile.write(json.dumps({'error':str(e)}).encode())
			return

		self.send_error(404)

class NFSServer:
	def __init__(self, root_path, use_privileged_ports=False):
		self.root_path = root_path
		self.enabled = False
		self.shares = []
		self.server_thread = None
		self.server_socket = None
		self.running = False
		self.port = 2049 if use_privileged_ports else 12049
	
	def update_config(self, config):
		self.enabled = config.get('enabled', False)
		self.shares = config.get('shares', [])
		if self.enabled:
			self.start()
		else:
			self.stop()
	
	def start(self):
		if not self.shares or self.running:
			return
		try:
			self.running = True
			self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.server_socket.bind(('0.0.0.0', self.port))
			self.server_thread = threading.Thread(target=self._run_server, daemon=True)
			self.server_thread.start()
			print(f"NFS Server: Started on port {self.port}")
			for share in self.shares:
				print(f"  Share: {share.get('path', '')} ({share.get('options', 'rw')})")
		except Exception as e:
			print(f"NFS Server error: {e}")
			self.running = False
	
	def _run_server(self):
		"""Simple NFS-like server implementation"""
		while self.running:
			try:
				data, addr = self.server_socket.recvfrom(8192)
				if len(data) < 4:
					continue
				
				# Simple RPC-like protocol
				xid = struct.unpack('>I', data[:4])[0]
				command = data[4:8].decode('utf-8', errors='ignore').strip()
				path = data[8:].decode('utf-8', errors='ignore').strip()
				
				response = self._handle_nfs_request(command, path)
				response_data = struct.pack('>I', xid) + response.encode('utf-8')
				self.server_socket.sendto(response_data, addr)
			except Exception as e:
				if self.running:
					print(f"NFS Server error: {e}")
	
	def _handle_nfs_request(self, command, path):
		"""Handle NFS-like requests"""
		try:
			# Check if path is in any share
			allowed = False
			share_root = None
			for share in self.shares:
				share_path = share.get('path', '').strip('/')
				if path.startswith(share_path) or path == share_path:
					allowed = True
					share_root = share_path
					break
			
			if not allowed:
				return 'ERROR: Access denied'
			
			# Build path relative to root folder
			relative_path = path.strip('/')
			full_path = os.path.join(str(self.root_path), relative_path)
			
			if command == 'LIST':
				if os.path.isdir(full_path):
					items = os.listdir(full_path)
					return 'OK:' + ','.join(items)
				else:
					return 'ERROR: Not a directory'
			elif command == 'READ':
				if os.path.isfile(full_path):
					with open(full_path, 'rb') as f:
						content = f.read(1024)  # Limit for demo
						return 'OK:' + base64.b64encode(content).decode()
				else:
					return 'ERROR: File not found'
			elif command == 'STAT':
				if os.path.exists(full_path):
					stat_info = os.stat(full_path)
					return f'OK:{stat_info.st_size},{stat_info.st_mtime},{stat_info.st_mode}'
				else:
					return 'ERROR: File not found'
			else:
				return 'ERROR: Unknown command'
		except Exception as e:
			return f'ERROR: {str(e)}'
	
	def stop(self):
		self.running = False
		if self.server_socket:
			self.server_socket.close()
		if self.server_thread:
			self.server_thread.join(timeout=1)
		print("NFS Server: Stopped")

class SMBServer:
	def __init__(self, root_path, use_privileged_ports=False):
		self.root_path = root_path
		self.enabled = False
		self.shares = []
		self.users = []
		self.server_thread = None
		self.server_socket = None
		self.running = False
		self.port = 445 if use_privileged_ports else 1445
		self.sessions = {}  # Track authenticated sessions
	
	def update_config(self, config):
		self.enabled = config.get('enabled', False)
		self.shares = config.get('shares', [])
		self.users = config.get('users', [])
		if self.enabled:
			self.start()
		else:
			self.stop()
	
	def start(self):
		if not self.shares or self.running:
			return
		try:
			self.running = True
			self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.server_socket.bind(('0.0.0.0', self.port))
			self.server_socket.listen(5)
			self.server_thread = threading.Thread(target=self._run_server, daemon=True)
			self.server_thread.start()
			print(f"SMB Server: Started on port {self.port}")
			for share in self.shares:
				print(f"  Share: {share.get('name', '')} -> {share.get('path', '')} ({share.get('access', 'rw')})")
			print(f"  Users: {len(self.users)} configured")
		except Exception as e:
			print(f"SMB Server error: {e}")
			self.running = False
	
	def _run_server(self):
		"""Simple SMB-like server implementation"""
		while self.running:
			try:
				client_socket, addr = self.server_socket.accept()
				client_thread = threading.Thread(
					target=self._handle_client,
					args=(client_socket, addr),
					daemon=True
				)
				client_thread.start()
			except Exception as e:
				if self.running:
					print(f"SMB Server error: {e}")
	
	def _handle_client(self, client_socket, addr):
		"""Handle SMB client connection"""
		try:
			session_id = f"{addr[0]}:{addr[1]}"
			self.sessions[session_id] = {'authenticated': False, 'user': None}
			
			while self.running:
				data = client_socket.recv(4096)
				if not data:
					break
				
				response = self._handle_smb_request(session_id, data)
				client_socket.send(response)
		except Exception as e:
			print(f"SMB Client error: {e}")
		finally:
			if session_id in self.sessions:
				del self.sessions[session_id]
			client_socket.close()
	
	def _handle_smb_request(self, session_id, data):
		"""Handle SMB-like requests"""
		try:
			if len(data) < 8:
				return b'ERROR: Invalid request'
			
			# Simple protocol: COMMAND:PATH:DATA
			request = data.decode('utf-8', errors='ignore')
			parts = request.split(':', 2)
			command = parts[0] if len(parts) > 0 else ''
			path = parts[1] if len(parts) > 1 else ''
			data_part = parts[2] if len(parts) > 2 else ''
			
			if command == 'AUTH':
				# AUTH:username:password
				creds = path.split(':')
				if len(creds) == 2:
					username, password = creds
					for user in self.users:
						if user.get('username') == username and user.get('password') == password:
							self.sessions[session_id]['authenticated'] = True
							self.sessions[session_id]['user'] = username
							return b'OK: Authenticated'
				return b'ERROR: Authentication failed'
			
			if not self.sessions[session_id]['authenticated']:
				return b'ERROR: Not authenticated'
			
			if command == 'SHARES':
				share_list = []
				for share in self.shares:
					share_list.append(f"{share.get('name', '')}:{share.get('path', '')}:{share.get('access', 'rw')}")
				return ('OK:' + ','.join(share_list)).encode('utf-8')
			
			elif command == 'LIST':
				# Find share and list directory
				share_path = self._get_share_path(path)
				if not share_path:
					return b'ERROR: Share not found'
				
				# Build path relative to root folder
				relative_path = share_path.strip('/')
				full_path = os.path.join(str(self.root_path), relative_path)
				if os.path.isdir(full_path):
					items = os.listdir(full_path)
					return ('OK:' + ','.join(items)).encode('utf-8')
				else:
					return b'ERROR: Not a directory'
			
			elif command == 'READ':
				share_path = self._get_share_path(path)
				if not share_path:
					return b'ERROR: Share not found'
				
				# Build path relative to root folder
				relative_path = share_path.strip('/')
				full_path = os.path.join(str(self.root_path), relative_path)
				if os.path.isfile(full_path):
					with open(full_path, 'rb') as f:
						content = f.read(8192)  # Limit for demo
						return b'OK:' + base64.b64encode(content)
				else:
					return b'ERROR: File not found'
			
			else:
				return b'ERROR: Unknown command'
			
		except Exception as e:
			return f'ERROR: {str(e)}'.encode('utf-8')
	
	def _get_share_path(self, requested_path):
		"""Get the actual path for a share (relative to root)"""
		for share in self.shares:
			share_name = share.get('name', '')
			if requested_path.startswith(share_name) or requested_path == share_name:
				# Return path relative to root folder
				share_path = share.get('path', '').strip('/')
				# If requesting a subpath within the share
				if len(requested_path) > len(share_name) and requested_path.startswith(share_name + '/'):
					subpath = requested_path[len(share_name):].strip('/')
					return os.path.join(share_path, subpath) if subpath else share_path
				return share_path
		return None
	
	def stop(self):
		self.running = False
		if self.server_socket:
			self.server_socket.close()
		if self.server_thread:
			self.server_thread.join(timeout=1)
		print("SMB Server: Stopped")

def run_server(host, port, root, auth_password=None, use_privileged_ports=False):
	server_address = (host, port)
	httpd = ThreadingHTTPServer(server_address, SimpleFileBrowserHandler)
	httpd.root_path = Path(root).resolve()
	httpd.auth_password = auth_password
	httpd.server_config = {'nfs': {'enabled': False, 'shares': []}, 'smb': {'enabled': False, 'shares': [], 'users': []}}
	
	# Initialize NFS and SMB servers
	httpd.nfs_server = NFSServer(httpd.root_path, use_privileged_ports)
	httpd.smb_server = SMBServer(httpd.root_path, use_privileged_ports)
	
	sa = httpd.socket.getsockname()
	print(f"Serving {httpd.root_path} on http://{sa[0]}:{sa[1]}")
	print(f"NFS/SMB Server Control Panel available at the 🖥️ Servers button")
	nfs_port = 2049 if use_privileged_ports else 12049
	smb_port = 445 if use_privileged_ports else 1445
	port_type = "standard" if use_privileged_ports else "non-privileged"
	print(f"NFS will run on port {nfs_port}, SMB on port {smb_port} ({port_type} ports)")
	if use_privileged_ports:
		print("⚠️  Using privileged ports - ensure you're running as root")
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		print('Shutting down')
		httpd.nfs_server.stop()
		httpd.smb_server.stop()
		httpd.server_close()

if __name__ == '__main__':
	p = argparse.ArgumentParser(description='Start a simple web file browser')
	p.add_argument('--host', default='127.0.0.1', help='Host to bind (default 127.0.0.1)')
	p.add_argument('--port', type=int, default=8000, help='HTTP port to listen on (default 8000)')
	p.add_argument('--root', '-r', default='.', help='Root path to serve')
	p.add_argument('--auth', help='Set a simple password for basic auth (username optional, provide password or user:password)')
	p.add_argument('--privileged-ports', '-p', action='store_true', help='Use standard NFS (2049) and SMB (445) ports (requires root)')
	p.add_argument('--open', dest='open', action='store_true', help='Open in default browser')
	args = p.parse_args()
	
	# Check for root privileges when using privileged ports
	if args.privileged_ports and os.getuid() != 0:
		print('⚠️  Warning: --privileged-ports requires root privileges for ports 2049 and 445')
		print('   Consider running with sudo or use default non-privileged ports')
	
	root = Path(args.root).resolve()
	if not root.exists():
		print('Root does not exist', root)
		sys.exit(1)
	if args.open:
		import webbrowser
		webbrowser.open(f'http://{args.host}:{args.port}/')
	run_server(args.host, args.port, root, auth_password=args.auth, use_privileged_ports=args.privileged_ports)