#!/usr/bin/env node

/**
 * BRICK — HEAD 2: Server Agent
 * Deployed to Coolify on VPS. Serves the terminal agent over HTTP.
 * Same pipeline, supercharged with VPS resources.
 */

import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = process.env.PORT || 4100;
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const VPS_HOST = process.env.VPS_HOST || 'http://localhost:5000';

// Ensure data directory
fs.mkdirSync(path.join(DATA_DIR, 'workspace'), { recursive: true });
fs.mkdirSync(path.join(DATA_DIR, 'exports'), { recursive: true });
fs.mkdirSync(path.join(DATA_DIR, 'builds'), { recursive: true });

// Rainbow spectrum theme (ANSI for logs)
const TH = {
  R: '\x1b[38;5;196m', O: '\x1b[38;5;208m', Y: '\x1b[38;5;226m',
  G: '\x1b[38;5;046m', B: '\x1b[38;5;033m', I: '\x1b[38;5;093m',
  V: '\x1b[38;5;129m', W: '\x1b[38;5;255m', GY: '\x1b[38;5;244m',
  RST: '\x1b[0m'
};

function log(prefix, msg, color = TH.GY) {
  const ts = new Date().toISOString().replace('T', ' ').substring(0, 19);
  console.log(`${color}[${ts}]${TH.RST} ${TH.W}[${prefix}]${TH.RST} ${msg}`);
}

function rainbow(text) {
  const colors = [TH.R, TH.O, TH.Y, TH.G, TH.B, TH.I, TH.V];
  return [...text].map((c, i) => c === ' ' ? ' ' : colors[i % colors.length] + c + TH.RST).join('');
}

// ─── API Handlers ────────────────────────────

const routes = {
  'GET /': (req, res) => {
    serveJSON(res, {
      name: 'Brick Server Agent',
      version: 'v1.0-spectrum',
      heads: ['terminal', 'server', 'telegram'],
      status: 'running',
      uptime: process.uptime()
    });
  },

  'GET /status': (req, res) => {
    serveJSON(res, {
      status: 'healthy',
      uptime: process.uptime(),
      projects: getProjectList(),
      memory: process.memoryUsage(),
      version: 'v1.0-spectrum'
    });
  },

  'POST /concept': async (req, res) => {
    const body = await readBody(req);
    const { name, purpose, audience, vibe } = body;

    if (!name) { serveJSON(res, { error: 'name required' }, 400); return; }

    const project = {
      name, purpose, audience, vibe,
      stage: 'concept',
      created: new Date().toISOString()
    };

    const projDir = path.join(DATA_DIR, 'workspace', name);
    fs.mkdirSync(projDir, { recursive: true });
    fs.writeFileSync(path.join(projDir, 'concept.json'), JSON.stringify(project, null, 2));

    log('CONCEPT', rainbow(name), TH.B);
    serveJSON(res, { success: true, project });
  },

  'POST /lock': async (req, res) => {
    const body = await readBody(req);
    const projDir = path.join(DATA_DIR, 'workspace', body.name);

    if (!fs.existsSync(projDir)) {
      serveJSON(res, { error: 'project not found' }, 404);
      return;
    }

    const lock = {
      project: body.name,
      shape: body.shape || 'rounded',
      palette: body.palette || 'dark',
      fontSize: body.fontSize || 15,
      goal: body.goal || '',
      marketAligned: true,
      lockedAt: Date.now(),
      stage: 'locked'
    };

    fs.writeFileSync(path.join(projDir, 'intent.lock.json'), JSON.stringify(lock, null, 2));
    log('LOCK', rainbow(body.name), TH.O);
    serveJSON(res, { success: true, lock });
  },

  'POST /build': async (req, res) => {
    const body = await readBody(req);
    const projDir = path.join(DATA_DIR, 'workspace', body.name);
    const lockPath = path.join(projDir, 'intent.lock.json');

    if (!fs.existsSync(lockPath)) {
      serveJSON(res, { error: 'no locked design found' }, 400);
      return;
    }

    const lock = JSON.parse(fs.readFileSync(lockPath, 'utf-8'));
    const exportDir = path.join(DATA_DIR, 'exports', body.name);
    fs.mkdirSync(exportDir, { recursive: true });

    // Try to call VPS swarm
    let vpsResult = null;
    try {
      log('BUILD', `Sending "${body.name}" to swarm...`, TH.Y);
      const swarmResp = await fetch(`${VPS_HOST}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: `Build ${body.name}: ${lock.palette} ${lock.shape} for ${lock.goal}`,
          context: lock
        })
      });
      if (swarmResp.ok) vpsResult = await swarmResp.json();
    } catch (e) {
      log('BUILD', `Swarm not reachable: ${e.message}`, TH.R);
    }

    const buildResult = {
      project: body.name,
      builtAt: new Date().toISOString(),
      spec: lock,
      vpsPlan: vpsResult,
      outputDir: exportDir
    };

    fs.writeFileSync(path.join(exportDir, 'build.json'), JSON.stringify(buildResult, null, 2));
    fs.writeFileSync(path.join(exportDir, 'spec.json'), JSON.stringify(lock, null, 2));

    log('BUILD', `${rainbow(body.name)} complete!`, TH.G);
    serveJSON(res, { success: true, build: buildResult });
  },

  'GET /projects': (req, res) => {
    serveJSON(res, { projects: getProjectList() });
  },

  'GET /projects/:name': (req, res, params) => {
    const projDir = path.join(DATA_DIR, 'workspace', params.name);
    if (!fs.existsSync(projDir)) {
      serveJSON(res, { error: 'not found' }, 404);
      return;
    }
    const files = fs.readdirSync(projDir);
    const data = {};
    files.forEach(f => {
      if (f.endsWith('.json')) {
        data[f] = JSON.parse(fs.readFileSync(path.join(projDir, f), 'utf-8'));
      }
    });
    serveJSON(res, { project: params.name, files: data });
  }
};

// ─── HTTP Server ────────────────────────────

function serveJSON(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  });
  res.end(JSON.stringify(data, null, 2));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try { resolve(JSON.parse(body)); }
      catch { resolve({}); }
    });
    req.on('error', reject);
  });
}

function getProjectList() {
  try {
    return fs.readdirSync(path.join(DATA_DIR, 'workspace'))
      .filter(f => fs.statSync(path.join(DATA_DIR, 'workspace', f)).isDirectory())
      .map(name => {
        const stage = fs.existsSync(path.join(DATA_DIR, 'workspace', name, 'intent.lock.json'))
          ? 'locked' : 'concept';
        return { name, stage };
      });
  } catch { return []; }
}

// ─── Router ──────────────────────────────────

function parsePath(url) {
  const [route, query] = url.split('?');
  return { route: route.replace(/\/+$/, '') || '/', query };
}

function matchRoute(method, pathname) {
  for (const [pattern, handler] of Object.entries(routes)) {
    const [pMethod, pPath] = pattern.split(' ');
    if (pMethod !== method) continue;

    const pParts = pPath.split('/');
    const uParts = pathname.split('/');
    if (pParts.length !== uParts.length) continue;

    const params = {};
    let match = true;
    for (let i = 0; i < pParts.length; i++) {
      if (pParts[i].startsWith(':')) {
        params[pParts[i].slice(1)] = uParts[i];
      } else if (pParts[i] !== uParts[i]) {
        match = false;
        break;
      }
    }
    if (match) return { handler, params };
  }
  return null;
}

const server = http.createServer(async (req, res) => {
  const { route: pathname } = parsePath(req.url);

  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    });
    res.end();
    return;
  }

  const matched = matchRoute(req.method, pathname);
  if (matched) {
    try {
      await matched.handler(req, res, matched.params);
    } catch (e) {
      log('ERROR', e.message, TH.R);
      serveJSON(res, { error: e.message }, 500);
    }
  } else {
    // Try static files from a public directory
    const publicDir = path.join(__dirname, 'public');
    const filePath = path.join(publicDir, pathname === '/' ? 'index.html' : pathname);
    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath);
      const mime = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.svg': 'image/svg+xml'
      };
      res.writeHead(200, { 'Content-Type': mime[ext] || 'text/plain' });
      res.end(fs.readFileSync(filePath));
    } else {
      serveJSON(res, { error: 'not found', path: pathname }, 404);
    }
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n${TH.R}╔══════════════════════════════════════════╗${TH.RST}`);
  console.log(`${TH.O}║  ${TH.BD}${TH.W}BRICK SERVER AGENT — HEAD 2${TH.RST}          ${TH.O}║${TH.RST}`);
  console.log(`${TH.Y}║  ${TH.GY}Running on port ${TH.P3}${PORT}${TH.RST}${TH.GY}               ${TH.Y}║${TH.RST}`);
  console.log(`${TH.G}║  ${TH.GY}API: ${TH.B}http://0.0.0.0:${PORT}/${TH.RST}          ${TH.G}║${TH.RST}`);
  console.log(`${TH.B}║  ${TH.GY}Data: ${TH.P2}${DATA_DIR}${TH.RST}         ${TH.B}║${TH.RST}`);
  console.log(`${TH.I}╚══════════════════════════════════════════╝${TH.RST}\n`);
});
