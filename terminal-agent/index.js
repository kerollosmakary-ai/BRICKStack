#!/usr/bin/env node

/**
 * BRICK — 3-Head Product
 * HEAD 1: Terminal Agent (Mobile/Termux)
 * UI/UX v1: Spectrum rainbow on black/white, terminal grok-style
 */

// ═══════════════════════════════════════════════
// THEME — Spectrum Rainbow on Black/White
// ═══════════════════════════════════════════════

const TH = {
  // Rainbow spectrum (ROYGBIV)
  R:   '\x1b[38;5;196m',  // Red
  O:   '\x1b[38;5;208m',  // Orange
  Y:   '\x1b[38;5;226m',  // Yellow
  G:   '\x1b[38;5;046m',  // Green
  B:   '\x1b[38;5;033m',  // Blue
  I:   '\x1b[38;5;093m',  // Indigo
  V:   '\x1b[38;5;129m',  // Violet
  // Spectrum gradients
  P1:  '\x1b[38;5;200m',  // Pink
  P2:  '\x1b[38;5;051m',  // Cyan
  P3:  '\x1b[38;5;220m',  // Gold
  // Base
  W:   '\x1b[38;5;255m',  // White
  B0:  '\x1b[38;5;232m',  // Black (near)
  GY:  '\x1b[38;5;244m',  // Gray
  DGY: '\x1b[38;5;236m',  // Dark gray
  // Effects
  BD:  '\x1b[1m',         // Bold
  IT:  '\x1b[3m',         // Italic
  UL:  '\x1b[4m',         // Underline
  BL:  '\x1b[5m',         // Blink
  RV:  '\x1b[7m',         // Reverse
  // BG colors
  BGR: '\x1b[48;5;196m',  // BG Red
  BGG: '\x1b[48;5;046m',  // BG Green
  BGB: '\x1b[48;5;033m',  // BG Blue
  BGY: '\x1b[48;5;226m',  // BG Yellow
  BGD: '\x1b[48;5;236m',  // BG Dark
  BGW: '\x1b[48;5;255m',  // BG White
  RST: '\x1b[0m',         // Reset
  CLR: '\x1b[2J\x1b[H',   // Clear screen
};

// ═══════════════════════════════════════════════
// CORE
// ═══════════════════════════════════════════════

import fs from 'fs';
import path from 'path';
import { createInterface } from 'readline';
import { execSync, exec } from 'child_process';

const BRICK_VERSION = 'v1.0-spectrum';
const HOME = process.env.HOME || '/root';
const BRICK_DIR = process.env.BHOME || path.join(HOME, 'BrickIDE');
const CONFIG_DIR = path.join(BRICK_DIR, '.system', 'config');
const WORKSPACE_DIR = path.join(BRICK_DIR, 'workspace');
const EXPORTS_DIR = path.join(BRICK_DIR, 'exports');
const BACKUPS_DIR = path.join(BRICK_DIR, 'backups');
const AGENT_DIR = path.join(BRICK_DIR, '.system', 'agent');

// VPS connection
let VPS_HOST = 'http://161.97.64.179:5000';

// ═══════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════

function rainbow(text, offset = 0) {
  const colors = [TH.R, TH.O, TH.Y, TH.G, TH.B, TH.I, TH.V, TH.P1, TH.P2];
  return [...text].map((c, i) => {
    if (c === ' ') return ' ';
    return colors[(i + offset) % colors.length] + c + TH.RST;
  }).join('');
}

function gradient(text, start, end) {
  // simple gradient between two colors
  const colors = [start, TH.P3, TH.Y, TH.G, TH.P2, TH.B, end];
  return [...text].map((c, i) => {
    if (c === ' ') return ' ';
    return colors[i % colors.length] + c + TH.RST;
  }).join('');
}

function box(title, content, color = TH.B) {
  const line = '═'.repeat(Math.min(50, title.length + 6));
  const pad = ' '.repeat(Math.max(0, 50 - title.length - 4));
  console.log(`\n${color}╔${line}╗${TH.RST}`);
  console.log(`${color}║ ${TH.BD}${rainbow(title)}${' '.repeat(Math.max(0, 48 - title.length))}${color}║${TH.RST}`);
  console.log(`${color}╚${line}╝${TH.RST}`);
  if (content) console.log(content);
}

function header(text) {
  console.log(`\n${TH.BD}${TH.W}┌─ ${rainbow(text)} ${TH.GY}${'─'.repeat(Math.max(0, 40 - text.length))}${TH.RST}`);
}

function success(text) {
  console.log(` ${TH.G}✔${TH.RST} ${TH.W}${text}${TH.RST}`);
}

function info(text) {
  console.log(` ${TH.B}ℹ${TH.RST} ${TH.GY}${text}${TH.RST}`);
}

function warn(text) {
  console.log(` ${TH.Y}⚠${TH.RST} ${TH.W}${text}${TH.RST}`);
}

function error(text) {
  console.log(` ${TH.R}✘${TH.RST} ${TH.O}${text}${TH.RST}`);
}

function divider() {
  console.log(` ${TH.DGY}${'─'.repeat(50)}${TH.RST}`);
}

function rainbowBar() {
  const bar = '█'.repeat(52);
  const colors = [TH.R, TH.O, TH.Y, TH.G, TH.B, TH.I, TH.V];
  let out = ' ';
  for (let i = 0; i < bar.length; i++) {
    out += colors[i % colors.length] + bar[i] + TH.RST;
  }
  console.log(out);
}

// ═══════════════════════════════════════════════
// INPUT
// ═══════════════════════════════════════════════

const rl = createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: true
});

function ask(query) {
  return new Promise(resolve => {
    rl.question(` ${TH.P3}▶${TH.RST} ${TH.BD}${TH.W}${query}${TH.RST} `, answer => {
      resolve(answer.trim());
    });
  });
}

function pressEnter() {
  return new Promise(resolve => {
    rl.question(` ${TH.GY}Press ENTER to continue...${TH.RST}`, () => resolve());
  });
}

// ═══════════════════════════════════════════════
// FILE SYSTEM
// ═══════════════════════════════════════════════

function ensureDirs() {
  [CONFIG_DIR, WORKSPACE_DIR, EXPORTS_DIR, BACKUPS_DIR, AGENT_DIR].forEach(d => {
    fs.mkdirSync(d, { recursive: true });
  });
}

function loadConfig() {
  const cfgPath = path.join(CONFIG_DIR, 'brick.json');
  if (fs.existsSync(cfgPath)) {
    try {
      return JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));
    } catch { return {}; }
  }
  return { version: BRICK_VERSION, setup: false };
}

function saveConfig(cfg) {
  fs.writeFileSync(path.join(CONFIG_DIR, 'brick.json'), JSON.stringify(cfg, null, 2));
}

// ═══════════════════════════════════════════════
// STAGE 1: CONCEPT
// ═══════════════════════════════════════════════

async function stageConcept() {
  header('STAGE 1 — CONCEPT');
  divider();
  console.log(` ${TH.IT}${TH.GY}Describe your idea in plain words. No code needed.${TH.RST}\n`);

  const name = await ask('Project name:');
  if (!name) { warn('Cancelled.'); return; }

  const purpose = await ask('What is it for?');
  const audience = await ask('Who is it for?');
  const vibe = await ask('Vibe/Style (e.g. modern, warm, dark, playful):');

  const project = {
    name,
    purpose,
    audience,
    vibe,
    stage: 'concept',
    created: new Date().toISOString(),
  };

  const projDir = path.join(WORKSPACE_DIR, name);
  fs.mkdirSync(projDir, { recursive: true });
  fs.writeFileSync(path.join(projDir, 'concept.json'), JSON.stringify(project, null, 2));

  success(`Project "${rainbow(name)}" saved!`);
  info(`Location: BrickIDE/workspace/${name}/`);
  divider();

  console.log(`\n ${rainbow('✦')} ${TH.W}Similar projects: property listings, business pages, mobile directories${TH.RST}\n`);
  info(`Next: ${TH.P3}bricks lock${TH.RST} — to lock your design choices`);

  return project;
}

// ═══════════════════════════════════════════════
// STAGE 2: LOCK
// ═══════════════════════════════════════════════

async function stageLock() {
  header('STAGE 2 — LOCK INTENT');

  // List available projects
  const projects = fs.existsSync(WORKSPACE_DIR)
    ? fs.readdirSync(WORKSPACE_DIR).filter(f => {
        try { return fs.statSync(path.join(WORKSPACE_DIR, f)).isDirectory(); } catch { return false; }
      })
    : [];

  if (projects.length === 0) {
    warn('No projects found. Run bricks concept first.');
    return;
  }

  divider();
  console.log(` ${TH.GY}Projects:${TH.RST}`);
  projects.forEach((p, i) => {
    console.log(`   ${rainbow('✦')} ${TH.W}${i + 1}. ${p}${TH.RST}`);
  });
  divider();

  const name = await ask('Project name to lock:');
  const projDir = path.join(WORKSPACE_DIR, name);
  if (!fs.existsSync(projDir)) {
    error(`Project "${name}" not found.`);
    return;
  }

  const shape = await ask('Shape style [square/rounded/pill]:');
  const palette = await ask('Colors/palette:');
  const fontSize = await ask('Body font size [14/15/16]:');
  const goal = await ask('Main goal/purpose:');

  const lock = {
    project: name,
    shape,
    palette,
    fontSize: parseInt(fontSize) || 15,
    goal,
    marketAligned: true,
    lockedAt: Date.now(),
    stage: 'locked'
  };

  fs.writeFileSync(path.join(projDir, 'intent.lock.json'), JSON.stringify(lock, null, 2));
  success(`Design locked for "${rainbow(name)}"`);
  info(`Next: ${TH.P3}bricks build${TH.RST} — to generate output`);

  return lock;
}

// ═══════════════════════════════════════════════
// STAGE 3: BUILD
// ═══════════════════════════════════════════════

async function stageBuild() {
  header('STAGE 3 — BUILD');

  const projects = fs.existsSync(WORKSPACE_DIR)
    ? fs.readdirSync(WORKSPACE_DIR).filter(f => {
        try { return fs.statSync(path.join(WORKSPACE_DIR, f)).isDirectory(); } catch { return false; }
      })
    : [];

  if (projects.length === 0) {
    warn('No projects found.');
    return;
  }

  divider();
  projects.forEach((p, i) => {
    const hasLock = fs.existsSync(path.join(WORKSPACE_DIR, p, 'intent.lock.json'));
    const status = hasLock ? `${TH.G}● locked${TH.RST}` : `${TH.GY}○ concept only${TH.RST}`;
    console.log(`   ${rainbow('✦')} ${TH.W}${i + 1}. ${p}${TH.RST} — ${status}`);
  });
  divider();

  const name = await ask('Project name to build:');
  const projDir = path.join(WORKSPACE_DIR, name);
  if (!fs.existsSync(projDir)) {
    error(`Project "${name}" not found.`);
    return;
  }

  const lockPath = path.join(projDir, 'intent.lock.json');
  if (!fs.existsSync(lockPath)) {
    error(`No locked design — run bricks lock first.`);
    return;
  }

  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf-8'));

  console.log(`\n ${TH.P2}⟐${TH.RST} ${TH.IT}Building exactly to your design...${TH.RST}\n`);

  // Generate output
  const exportDir = path.join(EXPORTS_DIR, name);
  fs.mkdirSync(exportDir, { recursive: true });

  // Copy lock as spec
  fs.copyFileSync(lockPath, path.join(exportDir, 'spec.json'));

  // Generate README
  const readme = `# ${name}

Built by Brick Agent v1.0

## Design
- Shape: ${lock.shape}
- Palette: ${lock.palette}
- Font Size: ${lock.fontSize}
- Goal: ${lock.goal}

## Files
- spec.json — full design specification
- (more files coming in future builds)

Built: ${new Date().toISOString()}
`;
  fs.writeFileSync(path.join(exportDir, 'README.md'), readme);

  // Try VPS deploy if available
  let vpsResult = null;
  if (VPS_HOST) {
    try {
      info('Sending to VPS swarm for analysis...');
      const resp = await fetch(`${VPS_HOST}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: `Build ${name}: ${lock.palette} ${lock.shape} design for ${lock.goal}`,
          context: lock
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        vpsResult = data;
        success('VPS swarm analyzed and returned plan!');
      } else {
        warn('VPS swarm responded but with error');
      }
    } catch (e) {
      info(`VPS not reachable: ${e.message}`);
    }
  }

  const result = {
    project: name,
    builtAt: new Date().toISOString(),
    files: ['spec.json', 'README.md'],
    vpsPlan: vpsResult || null
  };
  fs.writeFileSync(path.join(exportDir, 'build.json'), JSON.stringify(result, null, 2));

  success(`Build complete!`);
  console.log(` ${TH.G}┌${TH.RST}`);
  console.log(` ${TH.G}├${TH.RST} ${TH.W}Output:${TH.RST} ${TH.P2}BrickIDE/exports/${name}/${TH.RST}`);
  console.log(` ${TH.G}├${TH.RST} ${TH.W}Files:${TH.RST} spec.json, README.md${TH.RST}`);
  if (vpsResult) {
    console.log(` ${TH.G}├${TH.RST} ${TH.W}VPS Plan ID:${TH.RST} ${vpsResult.planId || 'N/A'} ${TH.RST}`);
  }
  console.log(` ${TH.G}└${TH.RST}`);

  return result;
}

// ═══════════════════════════════════════════════
// TELEGRAM INTEGRATION HOOKS
// ═══════════════════════════════════════════════

async function telegramSetup() {
  header('TELEGRAM AGENT — HEAD 3');

  console.log(` ${TH.GY}The Telegram agent allows you to:${TH.RST}`);
  console.log(`   ${rainbow('•')} Receive build notifications`);
  console.log(`   ${rainbow('•')} Send commands from anywhere`);
  console.log(`   ${rainbow('•')} Monitor swarm status`);
  divider();

  const token = await ask('Telegram Bot Token (from @BotFather):');
  const chatId = await ask('Your Telegram Chat ID:');

  if (token && chatId) {
    const cfg = loadConfig();
    cfg.telegram = { token, chatId };
    saveConfig(cfg);

    // Store for telegram.js
    const tgCfg = { botToken: token, chatId };
    fs.writeFileSync(path.join(CONFIG_DIR, 'telegram.json'), JSON.stringify(tgCfg, null, 2));

    success('Telegram agent configured!');
    info(`Run: ${TH.P3}node telegram.js${TH.RST} to start the bot`);
  } else {
    warn('Skipped — you can configure later in .system/config/telegram.json');
  }
}

// ═══════════════════════════════════════════════
// VPS SYNC
// ═══════════════════════════════════════════════

async function vpsSync() {
  header('VPS SYNC — HEAD 2');

  const host = await ask('VPS Swarm URL [http://161.97.64.179:5000]:');
  VPS_HOST = host || VPS_HOST;

  try {
    info(`Connecting to ${VPS_HOST}...`);
    const resp = await fetch(`${VPS_HOST}/status`);
    if (resp.ok) {
      const data = await resp.json();
      success('Connected to VPS swarm!');
      console.log(`\n${JSON.stringify(data, null, 2).substring(0, 500)}`);
    } else {
      warn(`Status returned ${resp.status}`);
    }
  } catch (e) {
    error(`Cannot reach VPS: ${e.message}`);
    info('The local agent works fully offline too.');
  }

  const cfg = loadConfig();
  cfg.vpsHost = VPS_HOST;
  saveConfig(cfg);
}

// ═══════════════════════════════════════════════
// BACKUP
// ═══════════════════════════════════════════════

async function doBackup() {
  header('BACKUP');
  const ts = Date.now();
  const backupFile = path.join(BACKUPS_DIR, `brick-${ts}.tar.gz`);
  try {
    execSync(`tar -czf "${backupFile}" -C "${BRICK_DIR}" .`, { stdio: 'ignore' });
    const stats = fs.statSync(backupFile);
    success(`Backup saved!`);
    console.log(` ${TH.GY}File: BrickIDE/backups/brick-${ts}.tar.gz${TH.RST}`);
    console.log(` ${TH.GY}Size: ${(stats.size / 1024).toFixed(1)} KB${TH.RST}`);
  } catch (e) {
    error(`Backup failed: ${e.message}`);
  }
}

// ═══════════════════════════════════════════════
// SYSTEM INFO
// ═══════════════════════════════════════════════

function showInfo() {
  header('SYSTEM INFO');
  console.log(` ${TH.W}Version:${TH.RST}     ${rainbow(BRICK_VERSION)}`);
  console.log(` ${TH.W}Home:${TH.RST}       ${TH.P2}${BRICK_DIR}${TH.RST}`);
  console.log(` ${TH.W}Workspace:${TH.RST}   ${TH.B}${WORKSPACE_DIR}${TH.RST}`);
  console.log(` ${TH.W}VPS Host:${TH.RST}    ${VPS_HOST}`);
  console.log(` ${TH.W}Node:${TH.RST}        ${process.version}`);
  console.log(` ${TH.W}Platform:${TH.RST}    ${process.platform}`);

  divider();
  // Count projects
  const projCount = fs.existsSync(WORKSPACE_DIR)
    ? fs.readdirSync(WORKSPACE_DIR).filter(f => {
        try { return fs.statSync(path.join(WORKSPACE_DIR, f)).isDirectory(); } catch { return false; }
      }).length
    : 0;
  console.log(` ${rainbow('✦')} ${TH.W}Projects:${TH.RST} ${projCount}`);
  console.log(` ${rainbow('✦')} ${TH.W}Disk:${TH.RST}    ${(fs.statSync('/').size / 1073741824).toFixed(1)} GB total`);
}

// ═══════════════════════════════════════════════
// MAIN MENU
// ═══════════════════════════════════════════════

function showBanner() {
  console.log(TH.CLR);
  rainbowBar();
  console.log(` ${TH.BD}${TH.W}   ██████  ██████  ██  ██████  ██   ██ ██████  ${TH.RST}`);
  console.log(` ${TH.BD}${TH.W}   ██   ██ ██   ██ ██ ██      ██  ██  ██   ██ ${TH.RST}`);
  console.log(` ${TH.BD}${TH.W}   ██████  ██████  ██ ██      █████   ██████  ${TH.RST}`);
  console.log(` ${TH.BD}${TH.W}   ██   ██ ██   ██ ██ ██      ██  ██  ██   ██ ${TH.RST}`);
  console.log(` ${TH.BD}${TH.W}   ██████  ██   ██ ██  ██████ ██   ██ ██   ██ ${TH.RST}`);
  rainbowBar();
  console.log(` ${TH.GY}   ${TH.BD}${TH.P3}3-HEAD PRODUCT${TH.RST}${TH.GY} · Terminal · Server · Telegram${TH.RST}`);
  console.log(` ${TH.GY}   ${BRICK_VERSION}${TH.RST}`);
  rainbowBar();
}

function showMenu() {
  console.log(`\n`);
  console.log(`   ${rainbow('✦')} ${TH.BD}${TH.W}STAGE PIPELINE${TH.RST}`);
  console.log(`   ${TH.GY}  ──────────────────────────────────────${TH.RST}`);
  console.log(`   ${TH.R} 1${TH.RST}  concept     ${TH.GY}Describe your idea in plain words${TH.RST}`);
  console.log(`   ${TH.O} 2${TH.RST}  lock        ${TH.GY}Lock your design choices${TH.RST}`);
  console.log(`   ${TH.Y} 3${TH.RST}  build       ${TH.GY}Generate output + deploy to VPS${TH.RST}`);
  console.log(`\n`);
  console.log(`   ${rainbow('✦')} ${TH.BD}${TH.W}HEADS MANAGEMENT${TH.RST}`);
  console.log(`   ${TH.GY}  ──────────────────────────────────────${TH.RST}`);
  console.log(`   ${TH.B} t${TH.RST}  telegram    ${TH.GY}Configure Telegram bot (Head 3)${TH.RST}`);
  console.log(`   ${TH.V} v${TH.RST}  vps-sync    ${TH.GY}Connect to VPS swarm (Head 2)${TH.RST}`);
  console.log(`\n`);
  console.log(`   ${rainbow('✦')} ${TH.BD}${TH.W}SYSTEM${TH.RST}`);
  console.log(`   ${TH.GY}  ──────────────────────────────────────${TH.RST}`);
  console.log(`   ${TH.P1} b${TH.RST}  backup      ${TH.GY}Backup all data${TH.RST}`);
  console.log(`   ${TH.P2} i${TH.RST}  info        ${TH.GY}System information${TH.RST}`);
  console.log(`   ${TH.P3} q${TH.RST}  quit        ${TH.GY}Exit${TH.RST}`);
  rainbowBar();
}

// ═══════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════

async function init() {
  ensureDirs();

  const cfg = loadConfig();
  if (cfg.vpsHost) VPS_HOST = cfg.vpsHost;

  if (!cfg.setup) {
    showBanner();
    console.log(`\n ${TH.Y}⟐${TH.RST} ${TH.W}Welcome! Let's set up your environment.${TH.RST}\n`);

    const vpsHost = await ask('VPS swarm URL [http://161.97.64.179:5000]:');
    if (vpsHost) VPS_HOST = vpsHost;

    cfg.setup = true;
    cfg.vpsHost = VPS_HOST;
    saveConfig(cfg);
    success('Setup complete!');
  }
}

async function main() {
  await init();

  let running = true;
  while (running) {
    showBanner();
    showMenu();
    divider();

    const cmd = await ask('Command');

    switch (cmd.toLowerCase()) {
      case '1': case 'concept': await stageConcept(); break;
      case '2': case 'lock': await stageLock(); break;
      case '3': case 'build': await stageBuild(); break;
      case 't': case 'telegram': await telegramSetup(); break;
      case 'v': case 'vps-sync': await vpsSync(); break;
      case 'b': case 'backup': await doBackup(); break;
      case 'i': case 'info': showInfo(); break;
      case 'q': case 'quit': running = false; console.log(`\n ${rainbow('✦')} ${TH.W}See you, builder.${TH.RST}\n`); break;
      default:
        warn(`Unknown command: "${cmd}"`);
        info('Try: concept, lock, build, telegram, vps-sync');
    }

    if (running && cmd.toLowerCase() !== 'q') {
      await pressEnter();
    }
  }

  rl.close();
}

// Handle SIGINT gracefully
process.on('SIGINT', () => {
  console.log(`\n\n ${rainbow('✦')} ${TH.W}Shutting down gracefully...${TH.RST}\n`);
  rl.close();
  process.exit(0);
});

main().catch(err => {
  console.error(`${TH.R}Fatal:${TH.RST} ${err.message}`);
  rl.close();
  process.exit(1);
});
