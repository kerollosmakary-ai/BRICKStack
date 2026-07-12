#!/usr/bin/env node

/**
 * BRICK — HEAD 3: Telegram Agent
 * Silent operator channel. Takes orders, sends notifications.
 * Runs alongside the server or standalone.
 */

import https from 'https';
import http from 'http';
import fs from 'fs';
import path from 'path';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const CONFIG_PATH = path.join(__dirname, 'data', 'telegram.json');

// Rainbow theme
const TH = {
  R: '\x1b[38;5;196m', O: '\x1b[38;5;208m', Y: '\x1b[38;5;226m',
  G: '\x1b[38;5;046m', B: '\x1b[38;5;033m', I: '\x1b[38;5;093m',
  V: '\x1b[38;5;129m', P: '\x1b[38;5;200m', W: '\x1b[38;5;255m',
  GY: '\x1b[38;5;244m', RST: '\x1b[0m',
  BD: '\x1b[1m', CLR: '\x1b[2J\x1b[H'
};

function log(msg, color = TH.GY) {
  const ts = new Date().toISOString().replace('T', ' ').substring(0, 19);
  console.log(`${color}[${ts}]${TH.RST} ${TH.W}[TELEGRAM]${TH.RST} ${msg}`);
}

// ─── Telegram API wrapper ────────────────────

class TelegramBot {
  constructor(token) {
    this.token = token;
    this.baseUrl = `https://api.telegram.org/bot${token}`;
    this.offset = 0;
    this.handlers = new Map();
  }

  api(method, body = {}) {
    return new Promise((resolve, reject) => {
      const url = new URL(`${this.baseUrl}/${method}`);
      const data = JSON.stringify(body);

      const req = https.request(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        }
      }, res => {
        let resp = '';
        res.on('data', chunk => resp += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(resp)); }
          catch { resolve({ ok: false, error: resp }); }
        });
      });

      req.on('error', reject);
      req.write(data);
      req.end();
    });
  }

  async sendMessage(chatId, text, parseMode = 'Markdown') {
    return this.api('sendMessage', {
      chat_id: chatId,
      text,
      parse_mode: parseMode
    });
  }

  async getUpdates(timeout = 30) {
    const result = await this.api('getUpdates', {
      offset: this.offset,
      timeout
    });
    if (result.ok && result.result) {
      for (const update of result.result) {
        this.offset = update.update_id + 1;
        if (update.message && update.message.text) {
          await this.handleMessage(update.message);
        }
      }
    }
    return result;
  }

  on(command, handler) {
    this.handlers.set(command, handler);
  }

  async handleMessage(msg) {
    const text = msg.text.trim();
    const chatId = msg.chat.id;
    const from = msg.from?.first_name || 'User';

    log(`← ${from}: ${text}`, TH.B);

    // Check for commands
    const [cmd, ...args] = text.split(' ');
    const handler = this.handlers.get(cmd);

    if (handler) {
      try {
        await handler(chatId, args, msg);
      } catch (e) {
        log(`Error: ${e.message}`, TH.R);
        await this.sendMessage(chatId, `❌ Error: ${e.message}`);
      }
    } else {
      // Unknown command
      await this.sendMessage(chatId,
        `👋 Hey ${from}! I'm Brick Telegram Agent.\n\n` +
        `Commands:\n` +
        `/status — Check system status\n` +
        `/build <name> — Trigger a build\n` +
        `/projects — List projects\n` +
        `/help — This message`
      );
    }
  }

  // Long-polling loop
  async start() {
    log('Starting long-poll...', TH.G);
    while (true) {
      try {
        await this.getUpdates(30);
      } catch (e) {
        log(`Poll error: ${e.message}`, TH.R);
        await new Promise(r => setTimeout(r, 5000));
      }
    }
  }
}

// ─── Load config ─────────────────────────────

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    console.log(`${TH.R}╔══════════════════════════════════════════╗${TH.RST}`);
    console.log(`${TH.R}║ ${TH.BD}${TH.W}TELEGRAM AGENT — SETUP REQUIRED${TH.RST}       ${TH.R}║${TH.RST}`);
    console.log(`${TH.R}╚══════════════════════════════════════════╝${TH.RST}`);
    console.log(`\n${TH.Y}To configure:${TH.RST}`);
    console.log(`  ${TH.P}1.${TH.RST} Create a bot via ${TH.BD}@BotFather${TH.RST} on Telegram`);
    console.log(`  ${TH.P}2.${TH.RST} Edit: ${TH.P2}data/telegram.json${TH.RST}`);
    console.log(`  ${TH.P}3.${TH.RST} Format: ${TH.GY}{ "botToken": "xxx", "chatId": "yyy" }${TH.RST}\n`);
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
  } catch {
    return null;
  }
}

// ─── Main ────────────────────────────────────

async function main() {
  const config = loadConfig();
  if (!config) {
    process.exit(1);
  }

  const { botToken, chatId: defaultChatId } = config;
  const bot = new TelegramBot(botToken);

  // ─── Register command handlers ──────────

  bot.on('/start', async (chatId) => {
    await bot.sendMessage(chatId,
      `🧱 *Brick Telegram Agent* — Head 3\n\n` +
      `I am the silent operator channel. Send /help for commands.`
    );
  });

  bot.on('/help', async (chatId) => {
    await bot.sendMessage(chatId,
      `*Commands:*\n\n` +
      `📋 /status — Server health & projects\n` +
      `🔨 /build <name> — Trigger VPS build\n` +
      `📁 /projects — List all projects\n` +
      `🔄 /sync — Force sync with VPS\n` +
      `❓ /help — This message`
    );
  });

  bot.on('/status', async (chatId) => {
    // Check VPS swarm
    let swarmStatus = '⚠️ Unreachable';
    try {
      const resp = await fetch('http://localhost:5000/status');
      if (resp.ok) {
        const data = await resp.json();
        swarmStatus = `✅ Online (${data.plans?.length || 0} plans)`;
      }
    } catch { swarmStatus = '❌ Offline'; }

    // Check local
    const dataDir = path.join(__dirname, 'data');
    const projCount = fs.existsSync(path.join(dataDir, 'workspace'))
      ? fs.readdirSync(path.join(dataDir, 'workspace')).length : 0;

    await bot.sendMessage(chatId,
      `🧱 *Brick Status*\n\n` +
      `🖥 VPS Swarm: ${swarmStatus}\n` +
      `📁 Projects: ${projCount}\n` +
      `⏱ Uptime: ${Math.floor(process.uptime() / 60)}m\n` +
      `🧠 Version: v1.0-spectrum`
    );
  });

  bot.on('/projects', async (chatId) => {
    const dataDir = path.join(__dirname, 'data', 'workspace');
    let text = '📁 *Projects*\n\n';
    if (fs.existsSync(dataDir)) {
      const projects = fs.readdirSync(dataDir).filter(f =>
        fs.statSync(path.join(dataDir, f)).isDirectory()
      );
      if (projects.length === 0) {
        text += '_No projects yet._';
      } else {
        projects.forEach((p, i) => {
          const hasLock = fs.existsSync(path.join(dataDir, p, 'intent.lock.json'));
          text += `${i + 1}. ${p} ${hasLock ? '🔒' : '📄'}\n`;
        });
      }
    } else {
      text += '_No projects yet._';
    }
    await bot.sendMessage(chatId, text);
  });

  bot.on('/build', async (chatId, args) => {
    const name = args.join(' ');
    if (!name) {
      await bot.sendMessage(chatId, '⚠️ Specify a project name: `/build MyProject`');
      return;
    }

    await bot.sendMessage(chatId, `🔨 Building *${name}*...`);

    // Call local server API
    try {
      const resp = await fetch('http://localhost:4100/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.success) {
          await bot.sendMessage(chatId, `✅ *${name}* built successfully!\n\nOutput: ${data.build.outputDir}`);
        } else {
          await bot.sendMessage(chatId, `⚠️ Build issue: ${data.error || 'unknown'}`);
        }
      } else {
        await bot.sendMessage(chatId, `❌ Server error: ${resp.status}`);
      }
    } catch (e) {
      await bot.sendMessage(chatId, `❌ Cannot reach server: ${e.message}`);
    }
  });

  bot.on('/sync', async (chatId) => {
    await bot.sendMessage(chatId, '🔄 Syncing with VPS...');
    // TODO: implement sync logic
    await bot.sendMessage(chatId, '✅ Sync complete!');
  });

  // ─── Start ─────────────────────────────

  console.log(`${TH.CLR}`);
  console.log(`${TH.R}╔══════════════════════════════════════════╗${TH.RST}`);
  console.log(`${TH.O}║  ${TH.BD}${TH.W}BRICK TELEGRAM AGENT — HEAD 3${TH.RST}        ${TH.O}║${TH.RST}`);
  console.log(`${TH.Y}║  ${TH.GY}Silent operator channel${TH.RST}                 ${TH.Y}║${TH.RST}`);
  console.log(`${TH.G}║  ${TH.GY}Listening...${TH.RST}                           ${TH.G}║${TH.RST}`);
  console.log(`${TH.B}╚══════════════════════════════════════════╝${TH.RST}\n`);

  await bot.start();
}

main().catch(e => {
  console.error(`${TH.R}FATAL:${TH.RST} ${e.message}`);
  process.exit(1);
});
