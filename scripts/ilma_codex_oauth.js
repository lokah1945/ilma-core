#!/usr/bin/env node
/**
 * ilma_codex_oauth.js — Step 2: OAuth URL Navigation
 * ======================================================
 * Fokus Step 2:
 *   ✅ Navigate to OpenAI Codex OAuth authorization URL
 *   ✅ Verify page loads (check for Cloudflare, login form, or error)
 *   ✅ Detect current OAuth state (which page we're on)
 *   ✅ Screenshot current state
 *   ✅ Report page elements
 *
 * Command: node ilma_codex_oauth.js step2
 */

const puppeteer = require('puppeteer-extra');
const stealth = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

const CHROME = process.env.PUPPETEER_EXECUTABLE_PATH
  || '/root/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome';

const PROFILE = process.env.BROWSER_PROFILE
  || '/root/.cache/ayda/playwright_persistent/nvidia_build/nvidia_build';

const OUT_DIR = '/tmp/codex_oauth';
fs.mkdirSync(OUT_DIR, { recursive: true });

const stealthPlugin = stealth();

// ── PKCE helpers (needed for proper OAuth URL) ─────────────────────────
const crypto = require('crypto');
const https = require('https');
const http = require('http');
const url = require('url');

function genPkce() {
  const verifier = crypto.randomBytes(64).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  const challenge = crypto.createHash('sha256')
    .update(verifier).digest('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  return { verifier, challenge };
}

function buildAuthUrl(challenge, state) {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: 'app_EMoamEEZ73f0CkXaXp7hrann',
    redirect_uri: 'http://localhost:1455/callback',
    scope: 'openid profile email offline',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
    codex_cli_simplified_flow: 'true',
    originator: 'openclaw',
  });
  return `https://auth.openai.com/oauth/authorize?${params.toString()}`;
}

function log(label, msg) {
  const ts = new Date().toISOString().substring(11, 23);
  console.log(`[${ts}] [${label}] ${msg}`);
}

// ── HTTP Callback Server ─────────────────────────────────────────────────
function startCallbackServer() {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const parsed = url.parse(req.url, true);
      if (parsed.pathname === '/callback') {
        const code = parsed.query.code;
        const state = parsed.query.state;
        const error = parsed.query.error;
        if (code) {
          log('SERVER', `✅ Callback received — code: ${code.substring(0, 20)}...`);
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end('<html><body><h1>Authorization Successful!</h1><p>Close this window.</p></body></html>');
          resolve({ code, state });
        } else if (error) {
          log('SERVER', `❌ OAuth error: ${error} — ${parsed.query.error_description || ''}`);
          res.writeHead(400, { 'Content-Type': 'text/html' });
          res.end(`<html><body><h1>Error: ${error}</h1><p>${parsed.query.error_description || ''}</p></body></html>`);
          resolve({ error, description: parsed.query.error_description });
        } else {
          res.writeHead(400);
          res.end('Missing code parameter');
          resolve(null);
        }
      } else {
        res.writeHead(404);
        res.end('Not found');
      }
    });
    server.on('error', e => {
      if (e.code === 'EADDRINUSE') {
        log('SERVER', 'Port 1455 in use — clearing and retrying...');
        server.close();
        resolve(null);
      }
    });
    server.listen(1455, '127.0.0.1', () => {
      log('SERVER', 'Callback server listening on http://127.0.0.1:1455');
      resolve(null);
    });
  });
}

// ── Page State Detector ──────────────────────────────────────────────────
async function detectPageState(page) {
  const info = {};

  info.url = page.url();
  info.title = await page.title().catch(() => '');

  // Body text (first 500 chars)
  info.bodyText = await page.evaluate(() => document.body.innerText.substring(0, 500))
    .catch(() => '');

  // All buttons
  info.buttons = await page.evaluate(() =>
    Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"]'))
      .map(b => b.innerText.trim() || b.value || b.type)
      .filter(t => t.length > 0)
  ).catch(() => []);

  // All links
  info.links = await page.evaluate(() =>
    Array.from(document.querySelectorAll('a[href]'))
      .map(a => ({ text: a.innerText.trim().substring(0, 40), href: a.href }))
      .filter(a => a.text.length > 0)
      .slice(0, 15)
  ).catch(() => []);

  // Forms
  info.forms = await page.evaluate(() =>
    Array.from(document.querySelectorAll('form')).map(f => ({
      action: f.action, method: f.method
    }))
  ).catch(() => []);

  // Inputs
  info.inputs = await page.evaluate(() =>
    Array.from(document.querySelectorAll('input'))
      .map(i => ({ type: i.type, name: i.name, placeholder: i.placeholder }))
  ).catch(() => []);

  // CSS injection detection markers
  info.hasAutomationStyles = await page.evaluate(() => {
    const el = document.querySelector('#cloudscape-internals') ||
               document.querySelector('[data-testid="challenge"]') ||
               document.querySelector('#cf-challenge') ||
               document.querySelector('.cf-error-code') ||
               document.querySelector('#challenge-form');
    return !!el;
  }).catch(() => false);

  return info;
}

// ── Step 2: OAuth Navigation ─────────────────────────────────────────────
async function step2() {
  log('CONFIG', `Chrome: ${CHROME}`);
  log('CONFIG', `Profile: ${PROFILE}`);

  // Generate PKCE
  const { verifier, challenge } = genPkce();
  const state = crypto.randomBytes(16).toString('hex');
  const AUTH_URL = buildAuthUrl(challenge, state);

  log('OAUTH', `Auth URL: ${AUTH_URL.substring(0, 100)}...`);
  log('OAUTH', `PKCE verifier: ${verifier.substring(0, 20)}... (saved to ${OUT_DIR}/pkce_verifier.txt)`);

  // Save verifier for later token exchange
  fs.writeFileSync(`${OUT_DIR}/pkce_verifier.txt`, verifier);
  fs.writeFileSync(`${OUT_DIR}/oauth_state.txt`, state);

  // Start callback server
  let callbackData = null;
  const serverPromise = startCallbackServer();
  serverPromise.then(r => { if (r) callbackData = r; });

  // Apply stealth
  puppeteer.use(stealthPlugin);

  // Launch browser
  log('LAUNCH', 'Starting Chromium...');
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: CHROME,
    userDataDir: PROFILE,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--exclude-switches=enable-automation',
      '--disable-infobars',
      '--disable-dev-shm-usage',
      '--no-first-run',
      '--disable-gpu',
    ],
  });
  log('LAUNCH', 'Browser launched');

  const page = (await browser.pages()).length > 0
    ? (await browser.pages())[0]
    : await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  // CDP session
  const cdp = await page.createCDPSession();
  await cdp.send('Network.enable');
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  log('CDP', 'CDP session active');

  // Intercept OAuth redirect URLs
  let capturedRedirect = null;
  cdp.on('Network.responseReceived', params => {
    const respUrl = params.response.url;
    const status = params.response.status;
    if (status >= 300 && status < 400 && respUrl.includes('localhost:1455')) {
      capturedRedirect = { url: respUrl, status };
      log('REDIRECT', `${status} → ${respUrl.substring(0, 120)}`);
    }
  });

  // Log all navigation requests
  const allRequests = [];
  cdp.on('Network.requestWillBeSent', params => {
    const reqUrl = params.request.url;
    if (reqUrl.includes('auth.openai') || reqUrl.includes('google') || reqUrl.includes('accounts')) {
      allRequests.push({ method: params.request.method, url: reqUrl.substring(0, 120) });
    }
  });

  // Navigate to OAuth URL
  log('NAV', 'Navigating to auth.openai.com...');
  await page.goto(AUTH_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  log('NAV', `Page loaded: ${page.url()}`);

  // Wait for dynamic content
  await new Promise(r => setTimeout(r, 5000));

  // Take screenshot
  const ssPath = `${OUT_DIR}/step2_oauth_page.png`;
  await page.screenshot({ path: ssPath, fullPage: false });
  log('SCREENSHOT', `Saved: ${ssPath}`);

  // Detect page state
  const pageInfo = await detectPageState(page);
  log('STATE', `URL: ${pageInfo.url}`);
  log('STATE', `Title: ${pageInfo.title}`);
  log('STATE', `Buttons: [${pageInfo.buttons.slice(0, 8).join(', ')}]`);
  log('STATE', `Has CF/challenge: ${pageInfo.hasAutomationStyles}`);

  if (pageInfo.bodyText) {
    log('BODY', pageInfo.bodyText.replace(/\n/g, ' | ').substring(0, 300));
  }

  log('LINKS', 'Sample links:');
  pageInfo.links.slice(0, 5).forEach(l => {
    log('LINKS', `  "${l.text}" → ${l.href.substring(0, 80)}`);
  });

  // Wait a bit more for any redirects
  await new Promise(r => setTimeout(r, 5000));

  // Check final URL
  log('FINAL', `URL: ${page.url()}`);
  log('FINAL', `Title: ${await page.title()}`);

  // Save state for next step
  fs.writeFileSync(`${OUT_DIR}/step2_state.json`, JSON.stringify({
    url: page.url(),
    title: await page.title(),
    verifier,
    state,
    pageInfo,
    timestamp: new Date().toISOString()
  }, null, 2));

  log('RESULT', '✅ Step 2 navigation complete');

  await browser.close();
}

step2().catch(e => {
  log('ERROR', e.message);
  process.exit(1);
});
