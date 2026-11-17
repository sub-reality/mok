// End-to-end: Subreal Manager <-> a real core API on a temporary store. Run: node manager/tests/live.test.js
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const http = require('http'), fs = require('fs'), os = require('os'), path = require('path');
const root = path.join(__dirname, '..'), core = path.join(root, '..', 'core');
const data = fs.mkdtempSync(path.join(os.tmpdir(), 'offices-e2e-'));
const env = {...process.env, OFFICES_DATA: data, OFFICES_API_TOKEN: 'e2e-token'};
const cli = (...a) => JSON.parse(execFileSync('python3', ['-m', 'offices', ...a], {cwd: core, env}).toString());
const types = {'.html':'text/html','.json':'application/json','.js':'text/javascript','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'};
const srv = http.createServer((q, r) => { const f = path.join(root, q.url.split('?')[0].replace(/^\/$/, '/index.html'));
  if (!fs.existsSync(f)) { r.writeHead(404); return r.end(); } r.writeHead(200, {'Content-Type': types[path.extname(f)] || 'text/plain'}); r.end(fs.readFileSync(f)); });
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  await new Promise(r => srv.listen(0, r)); const origin = 'http://127.0.0.1:' + srv.address().port;
  cli('packet', 'okfilm', 'samples/okfilm/demo-brief');
  const api = spawn('python3', ['-m', 'offices', 'serve', '--port', '8791', '--origin', origin], {cwd: core, env});
  await new Promise(r => setTimeout(r, 1200));
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1300, height: 900}});
  await p.goto(origin + '/#portal'); await p.click('#modeBtn'); await p.fill('#c-url', 'http://127.0.0.1:8791'); await p.fill('#c-token', 'e2e-token'); await p.click('#connForm button[type=submit]');
  await p.waitForFunction(() => S.mode === 'live' && !S.stale && S.snap.tasks.length === 0);
  ok((await p.locator('#modebadge').innerText()).includes('CANLI'), 'manager connects to the live core');
  await p.goto(origin + '/#isler'); // hash change keeps the in-memory session
  await p.fill('#j-title', 'E2E kurgu işi'); await p.fill('#j-due', '2027-01-20'); await p.click('#jobForm button[type=submit]');
  await p.waitForFunction(() => S.snap.tasks.length === 1);
  const t = cli('snapshot').tasks[0];
  ok(t.title === 'E2E kurgu işi' && t.state === 'draft' && t.due === '2027-01-20', 'job entered in the manager exists in the core as a draft task');
  cli('queue', t.task_id);
  const run = cli('run', t.task_id, '--provider', 'mock');          // the manager cannot do this; the CLI can
  await p.evaluate(() => reload()); await p.waitForFunction(() => S.snap.tasks[0].state === 'awaiting_review');
  ok(true, 'manager shows awaiting_review after a run started from the CLI');
  await p.goto(origin + '/#inbox'); await p.waitForSelector('[data-act="decide"][data-d="accept"]');
  fs.appendFileSync(path.join(data, 'okfilm', 'artifacts', t.task_id, 'production-plan.md'), '\nchanged after review');
  await p.click('[data-act="decide"][data-d="accept"]'); await p.waitForTimeout(700);
  ok(cli('snapshot').tasks[0].state === 'awaiting_review', 'core rejects acceptance of an artifact that changed after review');
  ok(await p.evaluate(() => xp()) === 0, 'no XP for a rejected acceptance');
  api.kill(); await new Promise(r => setTimeout(r, 400));
  await p.evaluate(() => reload()); await p.waitForSelector('.modebadge.stale');
  ok(await p.evaluate(() => S.snap.tasks[0].state === 'awaiting_review'), 'core stopped: manager shows stale, keeps last known state');
  ok(cli('snapshot').tasks.length === 1, 'core record is intact and usable from the CLI with the manager irrelevant');
  await b.close(); srv.close(); fs.rmSync(data, {recursive: true, force: true});
  console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
