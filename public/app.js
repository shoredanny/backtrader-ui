/* global CodeMirror, LightweightCharts */
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const NEW_STRATEGY_TEMPLATE = `import backtrader as bt


class MyStrategy(bt.Strategy):
    '''Describe the idea behind the strategy here.'''
    params = dict(
        period=20,
        printlog=False,
    )

    def __init__(self):
        self.sma = bt.ind.SMA(self.data.close, period=self.p.period)

    def log(self, txt):
        if self.p.printlog:
            print('%s  %s' % (self.data.datetime.date(0).isoformat(), txt))

    def notify_order(self, order):
        if order.status == order.Completed:
            side = 'BUY' if order.isbuy() else 'SELL'
            self.log('%s @ %.2f size %s' % (side, order.executed.price, order.executed.size))

    def next(self):
        if not self.position:
            if self.data.close[0] > self.sma[0]:
                self.buy()
        elif self.data.close[0] < self.sma[0]:
            self.close()
`;

const SERIES_COLORS = ['#f0b429', '#b388ff', '#4dd0e1', '#ff8a65', '#aed581', '#f06292', '#90caf9', '#ffd54f'];

// ------------------------------------------------------------------ state
const state = {
  strategies: [],
  current: null,        // name of strategy open in the editor
  savedCode: '',
  inspectCache: {},     // name -> inspect result
  feeds: [],
  feedType: 'file',
  feedId: null,
  formStrategy: null,   // strategy whose defaults the backtest form shows
  charts: [],
  lastResult: null,
};

// ------------------------------------------------------------------ utils
async function api(url, opts = {}) {
  const init = { ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || 'POST';
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(opts.json);
  }
  const res = await fetch(url, init);
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}

let toastTimer;
function toast(msg, isError = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('error', isError);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), isError ? 6000 : 2500);
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fmtNum(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtPct(v, d = 2) { return v === null || v === undefined ? '—' : `${fmtNum(v, d)}%`; }
function signCls(v) { return v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }
function fmtTime(t, intraday) {
  if (!t) return '—';
  const iso = new Date(t * 1000).toISOString();
  return intraday ? iso.slice(0, 16).replace('T', ' ') : iso.slice(0, 10);
}
function relTime(ms) {
  const s = (Date.now() - ms) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(ms).toLocaleDateString();
}

function confirmBox(text) {
  const dlg = $('#confirmDialog');
  $('#confirmText').textContent = text;
  dlg.returnValue = '';
  dlg.showModal();
  return new Promise((resolve) => dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true }));
}

function askName(title, initial = '', hint = '') {
  const dlg = $('#nameDialog');
  $('#nameDialogTitle').textContent = title;
  $('#nameHint').textContent = hint;
  const input = $('#nameInput');
  input.value = initial;
  dlg.returnValue = '';
  dlg.showModal();
  input.select();
  return new Promise((resolve) => dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok' ? input.value.trim() : null), { once: true }));
}
$('#nameCancel').addEventListener('click', () => $('#nameDialog').close(''));

// ------------------------------------------------------------------ views
function showView(name) {
  $$('#mainTabs button').forEach((b) => b.classList.toggle('active', b.dataset.view === name));
  $$('main.view').forEach((v) => (v.hidden = v.id !== `view-${name}`));
  if (name === 'strategies') editor.refresh();
  if (name === 'backtest') syncBacktestStrategies();
  if (name === 'history') loadRuns();
}
$('#mainTabs').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-view]');
  if (b) showView(b.dataset.view);
});

// ================================================================ STRATEGIES
const editor = CodeMirror.fromTextArea($('#codeEditor'), {
  mode: 'python',
  theme: 'material-darker',
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  matchBrackets: true,
  readOnly: 'nocursor',
  extraKeys: {
    Tab: (cm) => (cm.somethingSelected() ? cm.indentSelection('add') : cm.replaceSelection('    ', 'end')),
    'Shift-Tab': (cm) => cm.indentSelection('subtract'),
    'Ctrl-S': () => saveStrategy(),
    'Cmd-S': () => saveStrategy(),
  },
});
editor.on('change', () => updateDirty());

function isDirty() { return state.current && editor.getValue() !== state.savedCode; }
function updateDirty() { $('#dirtyMark').hidden = !isDirty(); }

async function loadStrategies() {
  state.strategies = await api('/api/strategies');
  renderStrategyList();
}

// Folders the user opened in the tree (remembered per browser)
function loadPref(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function savePref(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}
const expanded = new Set(loadPref('expandedFolders', []));

const folderOf = (name) => (name.includes('/') ? name.slice(0, name.lastIndexOf('/')) : '');
const baseOf = (name) => name.slice(name.lastIndexOf('/') + 1);

function renderStrategyList() {
  const q = $('#strategyFilter').value.trim().toLowerCase();
  const match = (s) => !q || s.name.toLowerCase().includes(q)
    || s.classes.some((c) => c.toLowerCase().includes(q)) || (s.summary || '').toLowerCase().includes(q);
  const groups = new Map();
  state.strategies.filter(match).forEach((s) => {
    const folder = folderOf(s.name);
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder).push(s);
  });
  const fileLi = (s, nested) => {
    const helper = s.ok && !s.classes.length;
    const title = !s.ok ? 'Failed to load: open it to see the error'
      : helper ? 'Helper module imported by other strategies (no strategy class)'
        : `${s.classes.join(', ')}${s.summary ? ` — ${s.summary}` : ''}`;
    return `<li data-name="${esc(s.name)}" title="${esc(title)}"
      class="file${nested ? ' nested' : ''}${helper ? ' helper' : ''}${s.name === state.current ? ' active' : ''}">
      <span>${esc(baseOf(s.name))}.py${s.ok ? '' : ' <span class="err">●</span>'}</span>
      <span class="time">${relTime(s.modified)}</span></li>`;
  };
  let html = (groups.get('') || []).map((s) => fileLi(s, false)).join('');
  [...groups.keys()].filter(Boolean).sort().forEach((folder) => {
    const open = !!q || expanded.has(folder) || (state.current || '').startsWith(`${folder}/`);
    html += `<li class="folder${open ? ' open' : ''}" data-folder="${esc(folder)}">
      <span class="caret">▸</span>${esc(folder)}<span class="count">${groups.get(folder).length}</span></li>`;
    if (open) html += groups.get(folder).map((s) => fileLi(s, true)).join('');
  });
  $('#strategyList').innerHTML = html || '<li class="muted">No strategies</li>';
}
$('#strategyFilter').addEventListener('input', renderStrategyList);

$('#strategyList').addEventListener('click', async (e) => {
  const folder = e.target.closest('li[data-folder]');
  if (folder) {
    const f = folder.dataset.folder;
    if (folder.classList.contains('open')) expanded.delete(f); else expanded.add(f);
    savePref('expandedFolders', [...expanded]);
    renderStrategyList();
    return;
  }
  const li = e.target.closest('li[data-name]');
  if (!li || li.dataset.name === state.current) return;
  if (isDirty() && !(await confirmBox(`Discard unsaved changes to ${state.current}.py?`))) return;
  openStrategy(li.dataset.name);
});

async function openStrategy(name) {
  try {
    const s = await api(`/api/strategies/${encodeURIComponent(name)}`);
    state.current = name;
    state.savedCode = s.code;
    editor.setOption('readOnly', false);
    editor.setValue(s.code);
    editor.clearHistory();
    $('#editorName').textContent = `${name}.py`;
    ['#btnSave', '#btnRename', '#btnDuplicate', '#btnDelete', '#btnToBacktest'].forEach((id) => ($(id).disabled = false));
    state.inspectCache[name] = s;
    renderInspect(s);
    renderStrategyList();
    updateDirty();
  } catch (err) {
    toast(err.message, true);
  }
}

function fmtValue(v) {
  return typeof v === 'string' ? v : JSON.stringify(v);
}
const pill = (k, v) => `<span class="pill">${esc(k)} = <b>${esc(fmtValue(v))}</b></span>`;

function renderInspect(info) {
  const p = $('#inspectPanel');
  if (!info.ok) {
    p.innerHTML = `<h3 style="margin-bottom:8px">Strategy failed to load</h3><pre class="err">${esc(info.error)}</pre>`;
    return;
  }
  const parts = [];
  if (info.doc) parts.push(`<p class="moddoc">${esc(info.doc)}</p>`);
  if (!info.classes.length) {
    parts.push('<p class="muted">No <code>bt.Strategy</code> subclass in this file (a helper module imported by other strategies).</p>');
  }
  info.classes.forEach((c) => parts.push(`
    <div class="cls">
      <h3>class ${esc(c.name)}</h3>
      ${c.doc ? `<div class="doc">${esc(c.doc)}</div>` : ''}
      <div>${c.params.map((pr) => pill(pr.name, pr.default)).join('') || '<span class="muted">No params</span>'}</div>
    </div>`));
  if (info.options?.length) {
    parts.push(`<h4>Sample options</h4><div>${info.options.map((o) => pill(o.name, o.default)).join('')}</div>`);
  }
  const d = info.defaults || {};
  if (Object.keys(d).length) {
    parts.push(`<h4>Backtest defaults</h4><div>${Object.entries(d).map(([k, v]) => pill(k, v)).join('')}</div>`);
  }
  p.innerHTML = parts.join('');
}

async function saveStrategy() {
  if (!state.current) return;
  const code = editor.getValue();
  try {
    const info = await api(`/api/strategies/${encodeURIComponent(state.current)}`, { method: 'PUT', json: { code } });
    state.savedCode = code;
    state.inspectCache[state.current] = { ...info, code };
    renderInspect(info);
    updateDirty();
    await loadStrategies();
    toast(info.ok ? `Saved ${state.current}.py` : 'Saved, but the strategy has errors', !info.ok);
  } catch (err) {
    toast(err.message, true);
  }
}
$('#btnSave').addEventListener('click', saveStrategy);

async function createStrategy(name, code) {
  const info = await api(`/api/strategies/${encodeURIComponent(name)}`, { method: 'PUT', json: { code, create: true } });
  await loadStrategies();
  await openStrategy(name);
  return info;
}

$('#btnNewStrategy').addEventListener('click', async () => {
  if (isDirty() && !(await confirmBox(`Discard unsaved changes to ${state.current}.py?`))) return;
  const folder = state.current ? folderOf(state.current) : '';
  const name = await askName('New strategy', folder ? `${folder}/my_strategy` : 'my_strategy',
    'Saved as strategies/<name>.py (use "/" for a folder) and pre-filled with a template.');
  if (!name) return;
  try { await createStrategy(name, NEW_STRATEGY_TEMPLATE); } catch (err) { toast(err.message, true); }
});

$('#btnDuplicate').addEventListener('click', async () => {
  const name = await askName('Duplicate strategy', `${state.current}_copy`);
  if (!name) return;
  try { await createStrategy(name, editor.getValue()); } catch (err) { toast(err.message, true); }
});

$('#btnRename').addEventListener('click', async () => {
  if (isDirty()) await saveStrategy();
  const name = await askName('Rename strategy', state.current);
  if (!name || name === state.current) return;
  try {
    await api(`/api/strategies/${encodeURIComponent(state.current)}/rename`, { json: { to: name } });
    delete state.inspectCache[state.current];
    await loadStrategies();
    await openStrategy(name);
  } catch (err) { toast(err.message, true); }
});

$('#btnDelete').addEventListener('click', async () => {
  if (!(await confirmBox(`Delete ${state.current}.py? This cannot be undone.`))) return;
  try {
    await api(`/api/strategies/${encodeURIComponent(state.current)}`, { method: 'DELETE' });
    delete state.inspectCache[state.current];
    state.current = null;
    state.savedCode = '';
    editor.setValue('');
    editor.setOption('readOnly', 'nocursor');
    $('#editorName').textContent = '—';
    ['#btnSave', '#btnRename', '#btnDuplicate', '#btnDelete', '#btnToBacktest'].forEach((id) => ($(id).disabled = true));
    $('#inspectPanel').innerHTML = '<p class="muted">Select or create a strategy.</p>';
    await loadStrategies();
    updateDirty();
  } catch (err) { toast(err.message, true); }
});

$('#btnToBacktest').addEventListener('click', async () => {
  if (isDirty()) await saveStrategy();
  $('#fStrategy').dataset.want = state.current;
  showView('backtest');
});

window.addEventListener('beforeunload', (e) => {
  if (isDirty()) { e.preventDefault(); e.returnValue = ''; }
});

// ================================================================ BACKTEST FORM
async function syncBacktestStrategies() {
  const sel = $('#fStrategy');
  const want = sel.dataset.want || sel.value || state.current;
  delete sel.dataset.want;
  // helper modules (no strategy class) cannot be run
  const runnable = state.strategies.filter((s) => !s.ok || s.classes.length);
  const opt = (s) => `<option value="${esc(s.name)}">${esc(baseOf(s.name))}.py${s.classes.length > 1 ? ` (${s.classes.length} classes)` : ''}</option>`;
  const groups = new Map();
  runnable.forEach((s) => {
    const f = folderOf(s.name);
    if (!groups.has(f)) groups.set(f, []);
    groups.get(f).push(s);
  });
  sel.innerHTML = (groups.get('') || []).map(opt).join('')
    + [...groups.keys()].filter(Boolean).sort()
      .map((f) => `<optgroup label="${esc(f)}">${groups.get(f).map(opt).join('')}</optgroup>`).join('');
  if (want && runnable.some((s) => s.name === want)) sel.value = want;
  await onStrategyChange();
}

async function getInspect(name, fresh = false) {
  if (!fresh && state.inspectCache[name]) return state.inspectCache[name];
  const s = await api(`/api/strategies/${encodeURIComponent(name)}`);
  state.inspectCache[name] = s;
  return s;
}

// Render the strategy section of the form. Choosing another strategy applies
// its DEFAULTS; re-rendering the same one keeps what the user typed;
// opts.values (from a saved run) wins over both.
async function onStrategyChange(opts = {}) {
  const name = $('#fStrategy').value;
  const paramsBox = $('#fParams');
  const docEl = $('#fStrategyDoc');
  if (!name) {
    paramsBox.innerHTML = '<p class="hint">Create a strategy first.</p>';
    return;
  }
  const kept = name === state.formStrategy && !opts.values
    ? { cls: $('#fClass').value, params: collectFields('#fParams'), options: collectFields('#fOptions') }
    : null;
  paramsBox.innerHTML = '<p class="hint">Loading…</p>';
  try {
    const info = await getInspect(name, true);
    state.formStrategy = name;
    docEl.textContent = (info.doc || '').split(/\n\s*\n/)[0];
    docEl.hidden = !info.doc;
    if (!info.ok) {
      $('#fClassWrap').hidden = true;
      $('#fOptionsWrap').hidden = true;
      paramsBox.innerHTML = '<p class="hint neg">This strategy has errors. Fix it in the Strategies tab.</p>';
      return;
    }
    const d = info.defaults || {};
    const v = opts.values || kept || { cls: d.strategy, params: d.params || {}, options: {} };
    const classSel = $('#fClass');
    classSel.innerHTML = info.classes.map((c) => `<option>${esc(c.name)}</option>`).join('');
    if (info.classes.some((c) => c.name === v.cls)) classSel.value = v.cls;
    $('#fClassWrap').hidden = info.classes.length < 2;
    renderParams(v.params);
    renderOptions(v.options);
    if (!opts.values && !kept) applyFormDefaults(d);
  } catch (err) {
    paramsBox.innerHTML = `<p class="hint neg">${esc(err.message)}</p>`;
  }
}
$('#fStrategy').addEventListener('change', () => onStrategyChange());
$('#fClass').addEventListener('change', () => {
  renderParams(state.inspectCache[$('#fStrategy').value]?.defaults?.params || {});
});

function currentInfo() {
  const info = state.inspectCache[$('#fStrategy').value];
  return info?.ok ? info : null;
}

function currentClass() {
  const info = currentInfo();
  if (!info) return null;
  return info.classes.find((c) => c.name === $('#fClass').value) || info.classes[0];
}

// One form field for a param/option described by the runner
function fieldHtml(f, value, choices) {
  const name = esc(f.name);
  const v = value === undefined ? f.default : value;
  const shown = v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
  const list = choices?.[f.name];
  if (list) {
    const vals = list.map(String);
    if (!vals.includes(shown)) vals.unshift(shown);
    return `<label>${name}<select data-field="${name}">${vals.map((c) =>
      `<option value="${esc(c)}"${c === shown ? ' selected' : ''}>${esc(c === '' ? '(none)' : c)}</option>`).join('')}</select></label>`;
  }
  if (f.type === 'bool') {
    return `<label class="check"><input type="checkbox" data-field="${name}"${v === true || v === 'true' ? ' checked' : ''}> ${name}</label>`;
  }
  if (f.type === 'int' || f.type === 'float') {
    return `<label>${name}<input data-field="${name}" type="number" step="${f.type === 'int' ? 1 : 'any'}" value="${esc(shown)}"></label>`;
  }
  const extra = f.type === 'expr' ? ' class="expr" title="Python expression (bt, datetime and the module names are available)"'
    : f.type === 'none' ? ' placeholder="None"' : '';
  return `<label>${name}<input data-field="${name}" type="text"${extra} value="${esc(shown)}"></label>`;
}

function renderParams(values = {}) {
  const cls = currentClass();
  const box = $('#fParams');
  if (!cls) { box.innerHTML = ''; return; }
  if (!cls.params.length) { box.innerHTML = '<p class="hint">No parameters.</p>'; return; }
  const choices = currentInfo()?.choices || {};
  box.innerHTML = cls.params.map((p) => fieldHtml(p, values[p.name], choices)).join('');
}

function renderOptions(values = {}) {
  const info = currentInfo();
  const options = info?.options || [];
  $('#fOptionsWrap').hidden = !options.length;
  $('#fOptions').innerHTML = options.map((o) => fieldHtml(o, values[o.name], info.choices || {})).join('');
}

function collectFields(sel) {
  const out = {};
  $$(`${sel} [data-field]`).forEach((el) => {
    out[el.dataset.field] = el.type === 'checkbox' ? el.checked : el.value;
  });
  return out;
}

// Apply a strategy's DEFAULTS (feed, dates, broker, sizer) to the form
function applyFormDefaults(d) {
  if (!d || !Object.keys(d).length) return;
  if (d.feed) {
    if (d.feed.startsWith('yahoo:')) {
      const [, ticker, interval] = d.feed.split(':');
      setFeedType('yahoo');
      $('#fTicker').value = ticker;
      $('#fInterval').value = interval || '1d';
    } else {
      const f = state.feeds.find((x) => x.file === d.feed && x.usable);
      if (f) {
        setFeedType('file');
        $('#feedFilter').value = '';
        selectFeed(f.id, false);
        $('.feed-item.active')?.scrollIntoView({ block: 'nearest' });
      }
    }
  }
  if ('fromdate' in d) $('#fFrom').value = d.fromdate || '';
  if ('todate' in d) $('#fTo').value = d.todate || '';
  if (d.cash !== undefined) $('#fCash').value = d.cash;
  if (d.commission !== undefined) $('#fComm').value = d.commission;
  if (d.slippage !== undefined) $('#fSlip').value = d.slippage;
  if (d.coc !== undefined) $('#fCoc').checked = !!d.coc;
  if (d.sizer) {
    $('#fSizer').value = d.sizer.type === 'percent' ? 'percent' : 'fixed';
    $('#fSizerLabel').textContent = $('#fSizer').value === 'percent' ? 'Percent' : 'Units';
    $('#fSizerVal').value = d.sizer.value;
  }
}

// ---- data feeds
function setFeedType(type) {
  state.feedType = type;
  $$('#feedType button').forEach((b) => b.classList.toggle('active', b.dataset.type === type));
  $$('[data-feed]').forEach((el) => (el.hidden = el.dataset.feed !== type));
}
$('#feedType').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-type]');
  if (b) setFeedType(b.dataset.type);
});

async function loadFeeds() {
  state.feeds = await api('/api/feeds');
  renderFeeds();
}

function renderFeeds() {
  const q = $('#feedFilter').value.toLowerCase();
  const list = state.feeds.filter((f) => f.file.toLowerCase().includes(q));
  let lastSource = null;
  $('#feedList').innerHTML = list.map((f) => {
    const head = f.source !== lastSource ? `<div class="feed-item" style="cursor:default;background:var(--bg)"><span class="meta">${esc(f.source)}</span></div>` : '';
    lastSource = f.source;
    return `${head}<div class="feed-item ${f.usable ? '' : 'disabled'} ${f.id === state.feedId ? 'active' : ''}" data-id="${esc(f.id)}"
        title="${f.usable ? esc(f.columns.join(', ')) : 'Not an OHLC file: ' + esc(f.columns.join(', '))}">
      <div class="fn"><span>${esc(f.file)}</span>${f.id.startsWith('uploads/') ? `<button type="button" class="del" data-del="${esc(f.file)}" title="Delete upload">✕</button>` : ''}</div>
      <div class="meta">${f.usable ? `${esc(f.first)} → ${esc(f.last)} · ${f.rows.toLocaleString()} bars${f.intraday ? ' · intraday' : ''}` : 'not OHLC data'}</div>
    </div>`;
  }).join('') || '<div class="feed-item meta">No files</div>';
}
$('#feedFilter').addEventListener('input', renderFeeds);

function toDateInput(s) {
  const m = String(s || '').match(/(\d{4})-?(\d{2})-?(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : '';
}

function selectFeed(id, setDates = true) {
  const f = state.feeds.find((x) => x.id === id);
  if (!f || !f.usable) return;
  state.feedId = id;
  if (setDates) {
    $('#fFrom').value = toDateInput(f.first);
    $('#fTo').value = toDateInput(f.last);
  }
  renderFeeds();
}

$('#feedList').addEventListener('click', async (e) => {
  const del = e.target.closest('[data-del]');
  if (del) {
    e.stopPropagation();
    if (!(await confirmBox(`Delete uploaded file ${del.dataset.del}?`))) return;
    try {
      await api(`/api/feeds/uploads/${encodeURIComponent(del.dataset.del)}`, { method: 'DELETE' });
      if (state.feedId === `uploads/${del.dataset.del}`) state.feedId = null;
      await loadFeeds();
    } catch (err) { toast(err.message, true); }
    return;
  }
  const item = e.target.closest('.feed-item[data-id]');
  if (item) selectFeed(item.dataset.id);
});

$('#fUpload').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const info = await api(`/api/feeds/upload?name=${encodeURIComponent(file.name)}`, {
      method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text,
    });
    await loadFeeds();
    setFeedType('file');
    selectFeed(info.id);
    toast(`Uploaded ${info.file} (${info.rows} bars)`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    e.target.value = '';
  }
});

// ---- sizer
$('#fSizer').addEventListener('change', () => {
  const pct = $('#fSizer').value === 'percent';
  $('#fSizerLabel').textContent = pct ? 'Percent' : 'Units';
  $('#fSizerVal').value = pct ? 95 : 100;
});

// ---- run
function buildRequest() {
  const feed = state.feedType === 'yahoo'
    ? { type: 'yahoo', ticker: $('#fTicker').value.trim(), interval: $('#fInterval').value }
    : { type: 'file', id: state.feedId };
  return {
    strategy: $('#fStrategy').value,
    strategyClass: currentClass()?.name,
    params: collectFields('#fParams'),
    options: collectFields('#fOptions'),
    feed,
    fromdate: $('#fFrom').value || null,
    todate: $('#fTo').value || null,
    cash: Number($('#fCash').value),
    commission: Number($('#fComm').value),
    slippage: Number($('#fSlip').value),
    coc: $('#fCoc').checked,
    sizer: { type: $('#fSizer').value, value: Number($('#fSizerVal').value) },
  };
}

$('#btForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const req = buildRequest();
  if (!req.strategy) return toast('Choose a strategy', true);
  if (req.feed.type === 'file' && !req.feed.id) return toast('Choose a data feed', true);
  if (req.feed.type === 'yahoo' && !req.feed.ticker) return toast('Enter a ticker', true);
  if (state.feedType === 'upload') return toast('Upload a CSV first, or pick a local file', true);

  const btn = $('#btnRun');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Running…';
  try {
    const result = await api('/api/backtest', { json: req });
    renderResult(result);
    if (!result.ok) toast('Backtest failed', true);
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run backtest';
  }
});

// ================================================================ RESULTS
function clearCharts() {
  state.charts.forEach((c) => c.remove());
  state.charts = [];
  $('#subCharts').innerHTML = '';
}

function makeChart(el, intraday) {
  const chart = LightweightCharts.createChart(el, {
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#8a93a6', fontSize: 11 },
    grid: { vertLines: { color: '#1d222c' }, horzLines: { color: '#1d222c' } },
    rightPriceScale: { borderColor: '#272d39', minimumWidth: 80 },
    timeScale: { borderColor: '#272d39', timeVisible: intraday, secondsVisible: false, minBarSpacing: 0.02 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });
  state.charts.push(chart);
  return chart;
}

// Keep the time axes of all charts scrolled/zoomed together
function syncCharts() {
  let syncing = false;
  state.charts.forEach((src) => {
    src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (syncing || !range) return;
      syncing = true;
      state.charts.forEach((dst) => dst !== src && dst.timeScale().setVisibleLogicalRange(range));
      syncing = false;
    });
  });
}

// Pad an indicator line to the full bar timeline so logical indexes line up
function padToBars(bars, data) {
  const byTime = new Map(data.map((d) => [d.time, d.value]));
  return bars.map((b) => (byTime.has(b.time) ? { time: b.time, value: byTime.get(b.time) } : { time: b.time }));
}

function metricTile(k, v, sub = '', cls = '') {
  return `<div class="metric"><div class="k">${k}</div><div class="v ${cls}">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`;
}

function renderResult(r) {
  state.lastResult = r;
  $('#resultsEmpty').hidden = true;
  $('#resultsBody').hidden = false;
  const req = r.request || {};
  const paramsTxt = Object.entries(r.params || req.params || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
  $('#rTitle').textContent = `${r.strategy || req.strategyClass || req.strategy}${paramsTxt ? ` (${paramsTxt})` : ''}`;
  const optsTxt = Object.entries(r.options || {}).map(([k, v]) => `${k}=${fmtValue(v)}`).join(', ');
  $('#rSub').textContent = [req.strategy && `${req.strategy}.py`, req.feedLabel,
    [req.fromdate, req.todate].filter(Boolean).join(' → '),
    r.createdAt && new Date(r.createdAt).toLocaleString(), optsTxt && `options: ${optsTxt}`].filter(Boolean).join(' · ');

  clearCharts();
  const err = $('#rError');
  if (!r.ok) {
    err.hidden = false;
    err.textContent = r.error;
    $('#rMetrics').innerHTML = '';
    $$('.chart-card, .card', $('#resultsBody')).forEach((c) => (c.hidden = true));
    if (r.log) {
      $('.card', $('#resultsBody')).hidden = false;
      $('#rLog').textContent = r.log;
      showDetailTab('log');
    }
    return;
  }
  err.hidden = true;
  $$('.chart-card, .card', $('#resultsBody')).forEach((c) => (c.hidden = false));

  const m = r.metrics;
  $('#rMetrics').innerHTML = [
    metricTile('Final value', fmtNum(m.finalValue), `start ${fmtNum(m.startCash, 0)}`),
    metricTile('Total return', fmtPct(m.totalReturnPct), `P&L ${fmtNum(m.pnl)}`, signCls(m.totalReturnPct)),
    metricTile('Buy & hold', fmtPct(m.buyHoldReturnPct), 'same period', signCls(m.buyHoldReturnPct)),
    metricTile('Annual return', fmtPct(m.annualReturnPct), 'normalized', signCls(m.annualReturnPct)),
    metricTile('Sharpe', fmtNum(m.sharpe), 'annualized, rf=0'),
    metricTile('Max drawdown', fmtPct(m.maxDrawdownPct), `${m.maxDrawdownLen ?? '—'} bars`, m.maxDrawdownPct ? 'neg' : ''),
    metricTile('Trades', `${m.trades}`, `${m.won} won · ${m.lost} lost${m.openTrades ? ` · ${m.openTrades} open` : ''}`),
    metricTile('Win rate', fmtPct(m.winRatePct, 1), `avg win ${fmtNum(m.avgWin)} / loss ${fmtNum(m.avgLoss)}`),
    metricTile('SQN', fmtNum(m.sqn), `${m.bars} bars · ${fmtNum(m.elapsedSec, 2)}s`),
  ].join('');

  const intraday = r.bars.length > 1 && r.bars.some((b) => b.time % 86400 !== 0);

  // ---- price chart
  const price = makeChart($('#priceChart'), intraday);
  const candles = price.addCandlestickSeries({
    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350',
  });
  // bars without prices (e.g. filler bars with NaN) become whitespace
  const priced = (b) => [b.open, b.high, b.low, b.close].every((x) => x !== null && x !== undefined);
  candles.setData(r.bars.map((b) => (priced(b)
    ? { time: b.time, open: b.open, high: b.high, low: b.low, close: b.close } : { time: b.time })));
  if (r.bars.some((b) => b.volume > 0)) {
    const vol = price.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false });
    price.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vol.setData(r.bars.map((b) => (b.volume === null ? { time: b.time }
      : { time: b.time, value: b.volume, color: b.close >= b.open ? 'rgba(38,166,154,.35)' : 'rgba(239,83,80,.35)' })));
  }

  // markers only for orders on the charted (first) data
  const markers = r.orders.filter((o) => ['Completed', 'Partial'].includes(o.status) && o.main !== false).map((o) => ({
    time: o.time,
    position: o.side === 'BUY' ? 'belowBar' : 'aboveBar',
    color: o.side === 'BUY' ? '#26a69a' : '#ef5350',
    shape: o.side === 'BUY' ? 'arrowUp' : 'arrowDown',
    text: `${o.side === 'BUY' ? 'B' : 'S'} ${fmtNum(o.price)}`,
  })).sort((a, b) => a.time - b.time);
  if (markers.length > 40) markers.forEach((mk) => delete mk.text);  // too dense to label
  candles.setMarkers(markers);

  // ---- indicators
  let colorIdx = 0;
  const legend = [];
  r.indicators.forEach((ind) => {
    let chart = price;
    if (!ind.overlay) {
      const card = document.createElement('div');
      card.className = 'chart-card';
      const kind = ind.kind ? `<span class="muted">${ind.kind}</span> ` : '';
      card.innerHTML = `<div class="chart-title">${kind}${esc(ind.name)} <span class="legend"></span></div><div class="chart sub"></div>`;
      $('#subCharts').appendChild(card);
      chart = makeChart($('.chart', card), intraday);
      ind._legend = $('.legend', card);
    }
    ind.lines.forEach((ln) => {
      const color = SERIES_COLORS[colorIdx++ % SERIES_COLORS.length];
      // sparse lines (e.g. observers marking events) are drawn as dots
      const s = chart.addLineSeries({
        color, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        ...(ln.sparse ? { lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 3 } : {}),
      });
      s.setData(padToBars(r.bars, ln.data));
      const text = ind.overlay ? (ind.lines.length > 1 ? `${ind.name} ${ln.name}` : ind.name) : ln.name;
      const label = `<span><i style="background:${color}"></i>${esc(text)}</span>`;
      if (ind.overlay) legend.push(label);
      else ind._legend.insertAdjacentHTML('beforeend', label);
    });
  });
  $('#priceLegend').innerHTML = legend.join('');

  // ---- equity chart
  const eq = makeChart($('#equityChart'), intraday);
  const bench = eq.addLineSeries({ color: '#9aa3b5', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
  bench.setData(r.benchmark);
  const eqSeries = eq.addAreaSeries({ lineColor: '#4f8cff', topColor: 'rgba(79,140,255,.25)', bottomColor: 'rgba(79,140,255,0)', lineWidth: 2, priceLineVisible: false });
  eqSeries.setData(r.equity.map((e) => ({ time: e.time, value: e.value })));

  // fit after layout: the charts get their real width only once visible
  // (autoSize applies it via ResizeObserver, after the next frame)
  setTimeout(() => {
    state.charts.forEach((c) => c.timeScale().fitContent());
    syncCharts();
  }, 80);

  // ---- tables
  renderTrades(r, intraday);
  renderOrders(r, intraday);
  renderAnalyzers(r);
  $('#rLog').textContent = r.log ? r.log + (r.logTruncated ? '\n… (truncated)' : '') : '(no output — use print() in your strategy to log here)';
  showDetailTab('trades');
}

const multiData = (r) => [...r.orders, ...r.trades].some((x) => x.data && x.data !== r.mainData);

function renderTrades(r, intraday) {
  const md = multiData(r);
  const rows = r.trades.map((t, i) => `
    <tr class="click" data-from="${t.opened || ''}" data-to="${t.closed || ''}">
      <td>${i + 1}</td>${md ? `<td class="l">${esc(t.data)}</td>` : ''}<td class="l">${t.direction || ''}</td>
      <td class="l">${fmtTime(t.opened, intraday)}</td><td class="l">${t.closed ? fmtTime(t.closed, intraday) : '<span class="muted">open</span>'}</td>
      <td>${t.bars ?? '—'}</td><td>${fmtNum(t.size, 0)}</td><td>${fmtNum(t.price)}</td>
      <td class="${signCls(t.pnl)}">${fmtNum(t.pnl)}</td><td class="${signCls(t.pnlcomm)}">${fmtNum(t.pnlcomm)}</td>
    </tr>`).join('');
  $('[data-tabpane=trades]').innerHTML = r.trades.length ? `
    <table><thead><tr><th>#</th>${md ? '<th class="l">Data</th>' : ''}<th class="l">Dir</th><th class="l">Opened</th><th class="l">Closed</th><th>Bars</th>
    <th>Size</th><th>Entry</th><th>P&amp;L</th><th>P&amp;L net</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="hint">Click a trade to zoom the charts to it.</p>`
    : '<p class="muted">No trades were made.</p>';
}

function renderOrders(r, intraday) {
  const md = multiData(r);
  const rows = r.orders.map((o) => `
    <tr><td>${o.ref}</td>${md ? `<td class="l">${esc(o.data)}</td>` : ''}<td class="l ${o.side === 'BUY' ? 'pos' : 'neg'}">${o.side}</td><td class="l">${esc(o.type)}</td>
      <td class="l">${esc(o.status)}</td><td class="l">${fmtTime(o.created, intraday)}</td><td class="l">${fmtTime(o.time, intraday)}</td>
      <td>${fmtNum(o.size, 0)}</td><td>${fmtNum(o.price)}</td><td>${fmtNum(o.value)}</td><td>${fmtNum(o.comm)}</td></tr>`).join('');
  $('[data-tabpane=orders]').innerHTML = r.orders.length ? `
    <table><thead><tr><th>Ref</th>${md ? '<th class="l">Data</th>' : ''}<th class="l">Side</th><th class="l">Type</th><th class="l">Status</th><th class="l">Created</th>
    <th class="l">Executed</th><th>Size</th><th>Price</th><th>Value</th><th>Comm</th></tr></thead><tbody>${rows}</tbody></table>`
    : '<p class="muted">No orders.</p>';
}

// Analyzers added by the strategy file (the metric tiles use the UI's own)
function renderAnalyzers(r) {
  const list = r.analyzers || [];
  $('#tabAnalyzers').textContent = list.length ? `Analyzers (${list.length})` : 'Analyzers';
  $('[data-tabpane=analyzers]').innerHTML = list.length
    ? list.map((a) => `<div class="an-block"><h4>${esc(a.name)} <span>${esc(a.type)}</span></h4>
        <pre class="json">${esc(JSON.stringify(a.analysis, null, 2))}</pre></div>`).join('')
    : '<p class="muted">This strategy file adds no analyzers (the figures above come from the built-in ones).</p>';
}

$('[data-tabpane=trades]').addEventListener('click', (e) => {
  const tr = e.target.closest('tr[data-from]');
  if (!tr || !state.lastResult) return;
  const bars = state.lastResult.bars;
  const from = Number(tr.dataset.from);
  const to = Number(tr.dataset.to) || bars[bars.length - 1].time;
  const i0 = bars.findIndex((b) => b.time >= from);
  let i1 = bars.findIndex((b) => b.time >= to);
  if (i1 < 0) i1 = bars.length - 1;
  const pad = Math.max(10, Math.round((i1 - i0) * 0.6));
  state.charts[0]?.timeScale().setVisibleLogicalRange({ from: i0 - pad, to: i1 + pad });
  $('#priceChart').scrollIntoView({ behavior: 'smooth', block: 'center' });
});

function showDetailTab(tab) {
  $$('#detailTabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  $$('[data-tabpane]').forEach((p) => (p.hidden = p.dataset.tabpane !== tab));
}
$('#detailTabs').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-tab]');
  if (b) showDetailTab(b.dataset.tab);
});

// ================================================================ HISTORY
async function loadRuns() {
  const box = $('#runsTable');
  try {
    const runs = await api('/api/runs');
    if (!runs.length) { box.innerHTML = '<p class="muted" style="padding:0 14px">No backtests yet.</p>'; return; }
    box.innerHTML = `<table><thead><tr>
      <th class="l">When</th><th class="l">Strategy</th><th class="l">Params</th><th class="l">Data</th><th class="l">Range</th>
      <th>Return</th><th>Buy &amp; hold</th><th>Sharpe</th><th>Max DD</th><th>Trades</th><th>Win %</th><th></th></tr></thead><tbody>
      ${runs.map((r) => `<tr class="click" data-id="${esc(r.id)}">
        <td class="l">${new Date(r.createdAt).toLocaleString()}</td>
        <td class="l">${esc(r.strategyClass)} <span class="muted">${esc(r.strategy)}.py</span></td>
        <td class="l muted">${esc(Object.entries(r.params || {}).map(([k, v]) => `${k}=${v}`).join(', ')).slice(0, 60)}</td>
        <td class="l">${esc(r.feed)}</td>
        <td class="l">${esc([r.fromdate, r.todate].filter(Boolean).join(' → ') || 'all')}</td>
        <td class="${signCls(r.metrics.totalReturnPct)}">${fmtPct(r.metrics.totalReturnPct)}</td>
        <td class="${signCls(r.metrics.buyHoldReturnPct)}">${fmtPct(r.metrics.buyHoldReturnPct)}</td>
        <td>${fmtNum(r.metrics.sharpe)}</td><td>${fmtPct(r.metrics.maxDrawdownPct)}</td>
        <td>${r.metrics.trades}</td><td>${fmtPct(r.metrics.winRatePct, 1)}</td>
        <td><button class="btn small" data-act="load">Load settings</button>
            <button class="btn small danger" data-act="del">✕</button></td></tr>`).join('')}
      </tbody></table>`;
  } catch (err) {
    box.innerHTML = `<pre class="err">${esc(err.message)}</pre>`;
  }
}
$('#btnRefreshRuns').addEventListener('click', loadRuns);

$('#runsTable').addEventListener('click', async (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (!tr) return;
  const id = tr.dataset.id;
  const act = e.target.closest('button')?.dataset.act;
  try {
    if (act === 'del') {
      if (!(await confirmBox('Delete this backtest run?'))) return;
      await api(`/api/runs/${id}`, { method: 'DELETE' });
      return loadRuns();
    }
    const run = await api(`/api/runs/${id}`);
    showView('backtest');
    if (act === 'load') await applyRequest(run.request);
    renderResult(run);
  } catch (err) { toast(err.message, true); }
});

// Fill the backtest form from a saved run's request
async function applyRequest(req) {
  if (!state.strategies.some((s) => s.name === req.strategy)) {
    toast(`Strategy ${req.strategy}.py no longer exists`, true);
    return;
  }
  $('#fStrategy').value = req.strategy;
  await onStrategyChange({ values: { cls: req.strategyClass, params: req.params || {}, options: req.options || {} } });
  if (req.feed?.type === 'yahoo') {
    setFeedType('yahoo');
    $('#fTicker').value = req.feed.ticker;
    $('#fInterval').value = req.feed.interval || '1d';
  } else if (req.feed?.id) {
    setFeedType('file');
    selectFeed(req.feed.id, false);
  }
  $('#fFrom').value = req.fromdate || '';
  $('#fTo').value = req.todate || '';
  $('#fCash').value = req.cash;
  $('#fComm').value = req.commission;
  $('#fSlip').value = req.slippage || 0;
  $('#fCoc').checked = !!req.coc;
  $('#fSizer').value = req.sizer?.type || 'percent';
  $('#fSizerLabel').textContent = $('#fSizer').value === 'percent' ? 'Percent' : 'Units';
  $('#fSizerVal').value = req.sizer?.value ?? 95;
}

// ================================================================ INIT
(async function init() {
  try {
    const cfg = await api('/api/config');
    $('#envInfo').textContent = `backtrader: ${cfg.btRoot}`;
    $('#envInfo').title = `python: ${cfg.python}`;
    await Promise.all([loadStrategies(), loadFeeds()]);
    const first = state.strategies.find((x) => !x.name.includes('/')) || state.strategies[0];
    if (first) openStrategy(first.name);
    const def = state.feeds.find((f) => f.file === 'orcl-1995-2014.txt') || state.feeds.find((f) => f.usable);
    if (def) {
      selectFeed(def.id);
      if (def.file === 'orcl-1995-2014.txt') { $('#fFrom').value = '2005-01-01'; $('#fTo').value = '2014-12-31'; }
    }
  } catch (err) {
    toast(err.message, true);
  }
})();
