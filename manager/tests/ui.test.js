// Playwright checks for Subreal Manager against the bundled recording. Run: node manager/tests/ui.test.js
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..');
const types = {'.html':'text/html','.json':'application/json','.js':'text/javascript','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'};
const srv = http.createServer((q, r) => { const f = path.join(root, decodeURIComponent(q.url.split('?')[0].replace(/^\/$/, '/index.html')));
  if (!f.startsWith(root) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
  r.writeHead(200, {'Content-Type': types[path.extname(f)] || 'text/plain'}); r.end(fs.readFileSync(f)); });
const out = process.env.SHOTS || path.join(root, 'tests', 'shots');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  await new Promise(r => srv.listen(0, r)); const base = 'http://127.0.0.1:' + srv.address().port + '/';
  fs.mkdirSync(out, {recursive: true});
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport: {width: 1360, height: 900}});
  const p = await ctx.newPage(); const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); }); p.on('pageerror', e => errs.push(String(e)));
  let posted = 0; p.on('request', q => { if (q.method() !== 'GET') posted++; });
  await p.goto(base); await p.waitForSelector('.off-okfilm');
  const mast = await p.locator('.mast').innerText();
  ok(['SUBREAL MANAGER 2027', 'Logos & Agape', 'ACTUALIZATIONS', 'Agile Management (Vertical/Archaeological Thinking)'].every(x => mast.toUpperCase().includes(x.toUpperCase())), 'masthead has the four lines');
  ok((await p.locator('#modebadge').innerText()).includes('KAYIT'), 'mode badge says recording, not live');
  const before = await p.evaluate(() => JSON.stringify(S.snap.tasks.map(t => [t.task_id, t.state, t.version, t.due])));
  for (let i = 0; i < 8; i++) { await p.keyboard.press('Space'); await p.waitForTimeout(60); }
  const after = await p.evaluate(() => JSON.stringify(S.snap.tasks.map(t => [t.task_id, t.state, t.version, t.due])));
  ok(before === after, 'Space x8 changed no task state, version or date');
  ok(posted === 0, 'Space sent no command');
  await p.goto(base + '#inbox'); await p.waitForSelector('pre.art');
  ok((await p.locator('pre.art').innerText()).length > 500, 'inbox shows a real artifact body');
  ok(await p.locator('text=sağlayıcı').first().isVisible(), 'run provenance (provider/model) is shown');
  await p.screenshot({path: path.join(out, 'inbox-desktop.png')});
  await p.locator('[data-act="decide"][data-d="accept"]').first().click();
  const ob = await p.evaluate(() => JSON.parse(localStorage.getItem('srm:outbox')));
  ok(ob.length === 1 && ob[0].cmd.action === 'approval.decide' && /^[0-9a-f]{64}$/.test(ob[0].cmd.params.artifact_sha256) && Number.isInteger(ob[0].cmd.expected_version), 'accept without a core becomes an unsent command bound to sha + version');
  ok(await p.evaluate(() => S.snap.tasks.every(t => t.state !== 'accepted')), 'task is NOT shown as accepted');
  ok(await p.evaluate(() => xp()) === 0, 'XP stays 0 until the core records an acceptance');
  await p.goto(base + '#isler'); await p.fill('#j-title', 'Test kurgu işi'); await p.fill('#j-due', '2027-01-15'); await p.click('#jobForm button[type=submit]');
  ok(await p.locator('.st.unsent').count() === 2, 'intake job is queued as "gönderilmedi"');
  const cmds = await p.evaluate(() => JSON.parse(localStorage.getItem('srm:outbox')).map(o => o.cmd));
  fs.writeFileSync(path.join(out, 'outbox.json'), JSON.stringify(cmds));
  // rehearsal isolation
  await p.goto(base + '#yonetim'); await p.click('[data-act="enter-sim"]'); await p.waitForSelector('.modebadge.sim');
  await p.keyboard.press('Space'); await p.keyboard.press('Space');
  ok(await p.evaluate(() => S.snap.simulation === true && S.snap.tasks.every(t => t.title.startsWith('[PROVA]'))), 'rehearsal uses only synthetic, labelled tasks');
  ok(await p.evaluate(() => xp()) === 0, 'rehearsal acceptances give no XP');
  await p.click('[data-act="exit-sim"]'); await p.waitForFunction(() => S.mode === 'fixture' && S.snap.simulation === false && S.snap.tasks.length === 3);
  ok(await p.evaluate(() => S.snap.simulation === false && S.snap.tasks.length === 3), 'leaving rehearsal restores the recording untouched');
  // agenda + ink
  await p.goto(base + '#ajanda'); await p.waitForSelector('#ink');
  const box = await p.locator('#ink').boundingBox();
  await p.mouse.move(box.x + 30, box.y + 30); await p.mouse.down(); await p.mouse.move(box.x + 200, box.y + 120, {steps: 8}); await p.mouse.up();
  const key = await p.evaluate(() => Object.keys(localStorage).find(k => k.startsWith('srm:ink:')));
  ok(!!key, 'ink stroke is saved for the day');
  await p.reload(); await p.waitForSelector('#ink');
  ok(await p.evaluate(k => !!localStorage.getItem(k), key), 'ink survives reload');
  await p.screenshot({path: path.join(out, 'ajanda-desktop.png')});
  // stale core
  await p.goto(base + '#portal'); await p.click('#modeBtn'); await p.fill('#c-url', 'http://127.0.0.1:9'); await p.fill('#c-token', 'x'); await p.click('#connForm button[type=submit]');
  await p.waitForSelector('.modebadge.stale');
  ok((await p.locator('#banner').innerText()).includes('ulaşılamıyor'), 'unreachable core shows a stale banner');
  ok(await p.evaluate(() => S.snap.tasks.length === 3), 'last known state is kept, nothing invented');
  // all screens render; no date before the plan start in planning cards
  for (const v of ['portal','inbox','isler','kadro','operasyon','transfer','antrenman','ajanda','yonetim']) { await p.goto(base + '#' + v); await p.waitForTimeout(80); ok((await p.locator('#view').innerText()).length > 40, 'screen renders: ' + v); }
  ok(await p.evaluate(() => MILESTONES.every(m => addDays(PLAN_START, m[0]-1) >= '2026-11-17') && addDays(PLAN_START, 89) === '2027-02-14'), 'plan dates start 17.11.2026 and end 14.02.2027');
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no horizontal page scroll (desktop)');
  await p.goto(base + '#portal'); await p.screenshot({path: path.join(out, 'portal-desktop-dark.png')});
  ok(errs.filter(e => !/127\.0\.0\.1:9|ERR_CONNECTION|Failed to load resource/.test(e)).length === 0, 'no console errors: ' + errs.slice(0, 3).join(' | '));
  // phone
  const ph = await b.newContext({viewport: {width: 412, height: 915}, deviceScaleFactor: 2});
  const q = await ph.newPage(); await q.goto(base + '#portal'); await q.waitForSelector('.off-okfilm');
  ok(await q.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no horizontal page scroll (phone)');
  ok(await q.locator('#devam2').isVisible(), 'phone has the Devam button in the thumb zone');
  await q.screenshot({path: path.join(out, 'portal-phone-light.png')});
  await q.goto(base + '#ajanda'); await q.waitForSelector('#ink'); await q.screenshot({path: path.join(out, 'ajanda-phone-light.png')});
  await b.close(); srv.close(); console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})();
