'use strict';

const express = require('express');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawn } = require('child_process');
const crypto = require('crypto');

const ROOT = __dirname;
const BT_ROOT = path.resolve(process.env.BT_ROOT || path.join(ROOT, '..', 'backtrader'));
const PYTHON = process.env.PYTHON || path.join(BT_ROOT, 'env', 'bin', 'python');
const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || '127.0.0.1';

const STRAT_DIR = path.join(ROOT, 'strategies');
const UPLOAD_DIR = path.join(ROOT, 'data', 'uploads');
const RUNS_DIR = path.join(ROOT, 'runs');
const RUNNER = path.join(ROOT, 'python', 'bt_runner.py');
const RUN_TIMEOUT_MS = 5 * 60 * 1000;

// Data feed sources: the backtrader sample datas plus user uploads
const FEED_SOURCES = [
  { id: 'samples', label: 'backtrader/datas', dir: path.join(BT_ROOT, 'datas') },
  { id: 'uploads', label: 'Uploads', dir: UPLOAD_DIR },
];

for (const d of [STRAT_DIR, UPLOAD_DIR, RUNS_DIR]) fs.mkdirSync(d, { recursive: true });

// MySQL feed (security_data database): settings from mysql.config.json,
// overridable with MYSQL_* environment variables
function loadMysqlConfig() {
  let cfg = {};
  const file = path.join(ROOT, 'mysql.config.json');
  if (fs.existsSync(file)) {
    try {
      cfg = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (e) {
      console.warn(`Ignoring invalid ${file}: ${e.message}`);
    }
  }
  const env = process.env;
  const merged = {
    host: env.MYSQL_HOST || cfg.host || 'localhost',
    port: String(env.MYSQL_PORT || cfg.port || 3306),
    user: env.MYSQL_USER || cfg.user || '',
    password: env.MYSQL_PASSWORD ?? cfg.password ?? '',
    database: env.MYSQL_DATABASE || cfg.database || 'security_data',
  };
  return merged.user ? merged : null;
}
const MYSQL = loadMysqlConfig();
const MYSQL_ENV = MYSQL ? {
  MYSQL_HOST: MYSQL.host,
  MYSQL_PORT: MYSQL.port,
  MYSQL_USER: MYSQL.user,
  MYSQL_PASSWORD: MYSQL.password,
  MYSQL_DATABASE: MYSQL.database,
} : {};

const app = express();
app.use(express.json({ limit: '5mb' }));
app.use(express.static(path.join(ROOT, 'public')));
app.use('/vendor/lwc', express.static(path.join(ROOT, 'node_modules', 'lightweight-charts', 'dist')));
app.use('/vendor/cm', express.static(path.join(ROOT, 'node_modules', 'codemirror')));

// ---------------------------------------------------------------- helpers
// Strategy names are paths relative to strategies/ without ".py", e.g.
// "bracket/bracket" or "sma_cross". Each segment: letters, digits, _ . -
const SAFE_SEGMENT = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$/;
const SAFE_FILE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

function httpError(status, message) {
  const e = new Error(message);
  e.status = status;
  return e;
}

function strategyPath(name) {
  const segs = String(name || '').split('/');
  if (segs.length > 4 || !segs.every((s) => SAFE_SEGMENT.test(s) && !s.includes('..'))) {
    throw httpError(400, 'Invalid strategy name: use letters, digits, _ - . and "/" for folders');
  }
  return path.join(STRAT_DIR, ...segs) + '.py';
}

function runPython(args, input, timeoutMs = RUN_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, [RUNNER, ...args], {
      cwd: ROOT,
      env: { ...process.env, ...MYSQL_ENV, BT_ROOT, MPLBACKEND: 'Agg', PYTHONUNBUFFERED: '1' },
    });
    let out = '';
    let err = '';
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      reject(httpError(504, `Backtest timed out after ${timeoutMs / 1000}s`));
    }, timeoutMs);
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => {
      clearTimeout(timer);
      reject(httpError(500, `Cannot start Python (${PYTHON}): ${e.message}`));
    });
    child.on('close', () => {
      clearTimeout(timer);
      try {
        resolve(JSON.parse(out));
      } catch {
        reject(httpError(500, `Runner produced invalid output.\n${err.slice(-4000) || out.slice(-4000)}`));
      }
    });
    if (input !== undefined) child.stdin.end(JSON.stringify(input));
    else child.stdin.end();
  });
}

const wrap = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

// Read the header and first/last rows of a CSV to describe it in the UI
async function describeFeed(source, file) {
  const full = path.join(source.dir, file);
  const text = await fsp.readFile(full, 'utf8');
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  const header = (lines[0] || '').split(',').map((h) => h.trim());
  const lower = header.map((h) => h.toLowerCase());
  const hasOHLC = ['open', 'high', 'low', 'close'].every((c) => lower.includes(c));
  const hasDate = lower.includes('date') || lower.includes('datetime');
  // some backtrader sample files carry an unlabeled time column after Date
  const row1 = (lines[1] || '').split(',');
  const hiddenTime = row1.length === header.length + 1 && /:/.test(row1[1] || '');
  const hasTime = lower.includes('time') || hiddenTime;
  const firstCell = (l) => (l || '').split(',').slice(0, hasTime ? 2 : 1).join(' ');
  return {
    id: `${source.id}/${file}`,
    source: source.label,
    file,
    columns: header,
    rows: Math.max(lines.length - 1, 0),
    first: firstCell(lines[1]),
    last: firstCell(lines[lines.length - 1]),
    intraday: hasTime || lower.includes('datetime'),
    usable: hasOHLC && hasDate,
  };
}

function resolveFeedPath(id) {
  const [sourceId, ...rest] = String(id || '').split('/');
  const file = rest.join('/');
  const source = FEED_SOURCES.find((s) => s.id === sourceId);
  if (!source || !SAFE_FILE.test(file)) throw httpError(400, 'Unknown data feed');
  const full = path.join(source.dir, file);
  if (!fs.existsSync(full)) throw httpError(404, 'Data feed file not found');
  return full;
}

// ------------------------------------------------------------ strategies
// Inspection results cached per file and mtime (inspecting imports Python)
const inspectCache = new Map();

async function walkStrategies(dir = STRAT_DIR, prefix = '') {
  const out = [];
  for (const ent of await fsp.readdir(dir, { withFileTypes: true })) {
    if (ent.name.startsWith('.') || ent.name === '__pycache__') continue;
    const rel = prefix ? `${prefix}/${ent.name}` : ent.name;
    if (ent.isDirectory()) out.push(...(await walkStrategies(path.join(dir, ent.name), rel)));
    else if (ent.name.endsWith('.py')) out.push(rel.slice(0, -3));
  }
  return out;
}

async function inspectMany(names) {
  const entries = await Promise.all(names.map(async (name) => {
    const p = strategyPath(name);
    return { name, p, mtime: (await fsp.stat(p)).mtimeMs };
  }));
  const stale = entries.filter((e) => inspectCache.get(e.p)?.mtime !== e.mtime);
  // inspect in chunks so one bad import cannot take the whole list down
  for (let i = 0; i < stale.length; i += 40) {
    const chunk = stale.slice(i, i + 40);
    const out = await runPython(['inspect', ...chunk.map((e) => e.p)], undefined, 120000);
    for (const e of chunk) inspectCache.set(e.p, { mtime: e.mtime, info: out.results[e.p] });
  }
  return entries.map((e) => ({ ...e, info: inspectCache.get(e.p).info }));
}

app.get('/api/strategies', wrap(async (req, res) => {
  const names = (await walkStrategies()).sort();
  const list = await inspectMany(names);
  res.json(list.map(({ name, mtime, info }) => ({
    name,
    modified: mtime,
    ok: info.ok,
    classes: info.ok ? info.classes.map((c) => c.name) : [],
    summary: info.ok ? (info.doc || info.classes[0]?.doc || '').split(/\n\s*\n/)[0].replace(/\s+/g, ' ') : 'Error loading file',
  })));
}));

app.get('/api/strategies/:name', wrap(async (req, res) => {
  const p = strategyPath(req.params.name);
  if (!fs.existsSync(p)) throw httpError(404, 'Strategy not found');
  const code = await fsp.readFile(p, 'utf8');
  const [{ info }] = await inspectMany([req.params.name]);
  res.json({ name: req.params.name, code, ...info });
}));

// Create (fails if it exists and create is set) or update a strategy file
app.put('/api/strategies/:name', wrap(async (req, res) => {
  const p = strategyPath(req.params.name);
  const { code, create } = req.body || {};
  if (typeof code !== 'string') throw httpError(400, 'Missing code');
  if (create && fs.existsSync(p)) throw httpError(409, 'A strategy with that name already exists');
  await fsp.mkdir(path.dirname(p), { recursive: true });
  await fsp.writeFile(p, code);
  const [{ info }] = await inspectMany([req.params.name]);
  res.json({ name: req.params.name, ...info });
}));

// Remove folders left empty after a rename/delete (never strategies/ itself)
async function pruneEmptyDirs(dir) {
  while (dir.startsWith(STRAT_DIR + path.sep)) {
    const left = (await fsp.readdir(dir)).filter((f) => f !== '__pycache__');
    if (left.length) return;
    await fsp.rm(dir, { recursive: true, force: true });
    dir = path.dirname(dir);
  }
}

app.post('/api/strategies/:name/rename', wrap(async (req, res) => {
  const from = strategyPath(req.params.name);
  const to = strategyPath(String(req.body?.to || ''));
  if (!fs.existsSync(from)) throw httpError(404, 'Strategy not found');
  if (fs.existsSync(to)) throw httpError(409, 'Target name already exists');
  await fsp.mkdir(path.dirname(to), { recursive: true });
  await fsp.rename(from, to);
  await pruneEmptyDirs(path.dirname(from));
  res.json({ ok: true });
}));

app.delete('/api/strategies/:name', wrap(async (req, res) => {
  const p = strategyPath(req.params.name);
  if (!fs.existsSync(p)) throw httpError(404, 'Strategy not found');
  await fsp.unlink(p);
  inspectCache.delete(p);
  await pruneEmptyDirs(path.dirname(p));
  res.json({ ok: true });
}));

// ------------------------------------------------------------ data feeds
app.get('/api/feeds', wrap(async (req, res) => {
  const out = [];
  for (const source of FEED_SOURCES) {
    if (!fs.existsSync(source.dir)) continue;
    const files = (await fsp.readdir(source.dir)).filter((f) => SAFE_FILE.test(f) && /\.(csv|txt)$/i.test(f)).sort();
    for (const f of files) {
      try {
        out.push(await describeFeed(source, f));
      } catch { /* unreadable file, skip */ }
    }
  }
  res.json(out);
}));

app.post('/api/feeds/upload', express.text({ type: '*/*', limit: '100mb' }), wrap(async (req, res) => {
  const name = String(req.query.name || '').replace(/[^A-Za-z0-9._-]/g, '_').replace(/^[._-]+/, '');
  if (!SAFE_FILE.test(name) || !/\.(csv|txt)$/i.test(name)) throw httpError(400, 'File must be a .csv or .txt');
  if (typeof req.body !== 'string' || !req.body.trim()) throw httpError(400, 'Empty file');
  await fsp.writeFile(path.join(UPLOAD_DIR, name), req.body);
  const info = await describeFeed(FEED_SOURCES[1], name);
  if (!info.usable) {
    await fsp.unlink(path.join(UPLOAD_DIR, name));
    throw httpError(400, 'CSV needs a Date (or Datetime) column and Open, High, Low, Close columns');
  }
  res.json(info);
}));

// Securities available in the MySQL database (cached: the query scans the
// whole price table)
let mysqlCache = null;
app.get('/api/mysql/securities', wrap(async (req, res) => {
  if (!MYSQL) return res.json({ ok: false, configured: false, error: 'MySQL is not configured (mysql.config.json)' });
  if (!mysqlCache || req.query.refresh || Date.now() - mysqlCache.at > 5 * 60 * 1000) {
    const out = await runPython(['mysql-list'], undefined, 60000);
    if (!out.ok) return res.json({ ...out, configured: true });
    mysqlCache = { at: Date.now(), data: out };
  }
  res.json({ ...mysqlCache.data, configured: true, database: `${MYSQL.user}@${MYSQL.host}/${MYSQL.database}` });
}));

app.delete('/api/feeds/uploads/:file', wrap(async (req, res) => {
  const full = resolveFeedPath(`uploads/${req.params.file}`);
  await fsp.unlink(full);
  res.json({ ok: true });
}));

// ------------------------------------------------------------ backtests
app.post('/api/backtest', wrap(async (req, res) => {
  const b = req.body || {};
  const stratFile = strategyPath(String(b.strategy || ''));
  if (!fs.existsSync(stratFile)) throw httpError(404, 'Strategy not found');

  let feed;
  let feedLabel;
  let feedName;
  if (b.feed?.type === 'mysql') {
    if (!MYSQL) throw httpError(400, 'MySQL is not configured (mysql.config.json)');
    const ticker = String(b.feed.ticker || '').trim().toUpperCase();
    if (!/^[A-Z0-9.^=\-]{1,20}$/.test(ticker)) throw httpError(400, 'Invalid ticker');
    const adjusted = b.feed.adjusted !== false;
    feed = { type: 'mysql', ticker, adjusted };
    feedLabel = `MySQL: ${ticker}${adjusted ? ' (adjusted)' : ''}`;
    feedName = ticker;
  } else if (b.feed?.type === 'yahoo') {
    const ticker = String(b.feed.ticker || '').trim().toUpperCase();
    if (!/^[A-Z0-9.^=\-]{1,20}$/.test(ticker)) throw httpError(400, 'Invalid ticker');
    const interval = ['1d', '1wk', '1mo', '1h'].includes(b.feed.interval) ? b.feed.interval : '1d';
    feed = { type: 'yahoo', ticker, interval };
    feedLabel = `Yahoo: ${ticker} (${interval})`;
    feedName = ticker;
  } else {
    feed = { type: 'file', path: resolveFeedPath(b.feed?.id) };
    feedLabel = b.feed.id;
    feedName = path.basename(feed.path).replace(/\.[^.]+$/, '');
  }

  const cfg = {
    strategyFile: stratFile,
    strategyClass: b.strategyClass || null,
    params: b.params || {},
    options: b.options || {},
    feed,
    feedName,
    fromdate: b.fromdate || null,
    todate: b.todate || null,
    cash: b.cash,
    commission: b.commission,
    slippage: b.slippage,
    coc: !!b.coc,
    sizer: b.sizer,
  };

  const result = await runPython(['run'], cfg);
  const id = new Date().toISOString().replace(/[:.]/g, '-') + '_' + crypto.randomBytes(3).toString('hex');
  const record = {
    id,
    createdAt: new Date().toISOString(),
    request: { ...b, feedLabel },
    ...result,
  };
  if (result.ok) await fsp.writeFile(path.join(RUNS_DIR, id + '.json'), JSON.stringify(record));
  res.json(record);
}));

app.get('/api/runs', wrap(async (req, res) => {
  const files = (await fsp.readdir(RUNS_DIR)).filter((f) => f.endsWith('.json')).sort().reverse();
  const list = [];
  for (const f of files) {
    try {
      const r = JSON.parse(await fsp.readFile(path.join(RUNS_DIR, f), 'utf8'));
      list.push({
        id: r.id,
        createdAt: r.createdAt,
        strategy: r.request.strategy,
        strategyClass: r.strategy,
        params: r.params,
        feed: r.request.feedLabel,
        fromdate: r.request.fromdate,
        todate: r.request.todate,
        metrics: r.metrics,
      });
    } catch { /* corrupt run file, skip */ }
  }
  res.json(list);
}));

function runPath(id) {
  if (!/^[A-Za-z0-9_-]+$/.test(id)) throw httpError(400, 'Bad run id');
  const p = path.join(RUNS_DIR, id + '.json');
  if (!fs.existsSync(p)) throw httpError(404, 'Run not found');
  return p;
}

app.get('/api/runs/:id', wrap(async (req, res) => {
  res.type('json').send(await fsp.readFile(runPath(req.params.id), 'utf8'));
}));

app.delete('/api/runs/:id', wrap(async (req, res) => {
  await fsp.unlink(runPath(req.params.id));
  res.json({ ok: true });
}));

app.get('/api/config', (req, res) => res.json({ btRoot: BT_ROOT, python: PYTHON }));

app.use((err, req, res, next) => {
  const status = err.status || 500;
  if (status >= 500) console.error(err);
  res.status(status).json({ ok: false, error: err.message });
});

app.listen(PORT, HOST, () => {
  console.log(`Backtrader UI running at http://${HOST}:${PORT}`);
  console.log(`  backtrader: ${BT_ROOT}`);
  console.log(`  python:     ${PYTHON}`);
  if (!fs.existsSync(PYTHON)) console.warn('  WARNING: python not found; set the PYTHON env variable');
});
