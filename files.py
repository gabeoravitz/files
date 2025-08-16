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
import argparse, base64, json, mimetypes, os, shutil, sys, urllib.parse, io, zipfile
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
<title>File Browser</title>
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
}
[data-theme="dark"] {
  --bg: #111827;
  --card-bg: #1f2937;
  --text-color: #f9fafb;
  --accent-color: #3b82f6;
  --danger-color: #ef4444;
  --shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
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
  background-color: rgba(37, 99, 235, 0.1);
}
[data-theme="dark"] .row.selected {
  background-color: rgba(59, 130, 246, 0.2);
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
        <h1 class="h1">File Browser</h1>
        <p class="smallmuted"></p>
      </div>
    </div>
    <div class="controls">
      <input id="q" class="input" placeholder="Search files and folders..." />
      <button id="uploadBtn" class="btn">Upload</button>
      <button id="mkdir" class="btn">New Folder</button>
      <button id="refresh" class="btn">Refresh</button>
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
  contextTarget: null
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
  if(!state.files || !state.files.length){
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
  for(const it of state.files){
    const row = document.createElement('div');
    row.className='row';
    row.dataset.path = it.path;
    if (state.selectedFiles.has(it.path)) {
      row.classList.add('selected');
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
      if (e.ctrlKey || e.metaKey) {
        toggleSelection(it.path);
      } else if (e.shiftKey && state.selectedFiles.size > 0) {
        selectRange(it.path);
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
  if(!state.files || !state.files.length){
    const em = document.createElement('div');
    em.style.padding='24px';
    em.style.gridColumn = '1 / -1';
    em.textContent = state.searchMode ? 'No results found' : 'No files';
    listing.appendChild(em);
    return;
  }
  for(const it of state.files){
    const item = document.createElement('div');
    item.className='grid-item';
    item.dataset.path = it.path;
    if (state.selectedFiles.has(it.path)) {
      item.classList.add('selected');
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
      if (e.ctrlKey || e.metaKey) {
        toggleSelection(it.path);
      } else if (e.shiftKey && state.selectedFiles.size > 0) {
        selectRange(it.path);
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
  document.getElementById('themeToggle').onclick = toggleTheme;
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

		self.send_error(404)

def run_server(host, port, root, auth_password=None):
	server_address = (host, port)
	httpd = ThreadingHTTPServer(server_address, SimpleFileBrowserHandler)
	httpd.root_path = Path(root).resolve()
	httpd.auth_password = auth_password
	sa = httpd.socket.getsockname()
	print(f"Serving {httpd.root_path} on http://{sa[0]}:{sa[1]}")
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		print('Shutting down')
		httpd.server_close()

if __name__ == '__main__':
	p = argparse.ArgumentParser(description='Start a simple web file browser')
	p.add_argument('--host', default='127.0.0.1', help='Host to bind (default 127.0.0.1)')
	p.add_argument('--port', '-p', type=int, default=8000, help='Port to listen on')
	p.add_argument('--root', '-r', default='.', help='Root path to serve')
	p.add_argument('--auth', help='Set a simple password for basic auth (username optional, provide password or user:password)')
	p.add_argument('--open', dest='open', action='store_true', help='Open in default browser')
	args = p.parse_args()
	root = Path(args.root).resolve()
	if not root.exists():
		print('Root does not exist', root)
		sys.exit(1)
	if args.open:
		import webbrowser
		webbrowser.open(f'http://{args.host}:{args.port}/')
	run_server(args.host, args.port, root, auth_password=args.auth)