import {initialize, t, number, date, setLocale, currentLocale} from './i18n.js';
const $ = (id) => document.getElementById(id);
const palette = ['#087e8b', '#9b5bb5', '#d98839', '#527bc2', '#c95c72', '#61843b', '#b86d39', '#546e7a'];
const roleColors = {consolidator: '#087e8b', transit: '#527bc2', distributor: '#d98839', terminal: '#9b5bb5', coordinator: '#c95c72', peripheral: '#80918f'};
const score = (n) => number(n, {minimumFractionDigits: 3, maximumFractionDigits: 3});
const role = (value) => t(`role.${value}`);
let overview = null;
let analysisStatus = null;
const messages = new Map();
let current = null;
let activeRevision = null;
let graphRequest = null;
let camera = {scale: 1, x: 0, y: 0};
let drag = null;
let request = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function svg(tag, attributes = {}, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}
function accountButton(gid) {
  const button = element('button', gid);
  button.type = 'button';
  button.addEventListener('click', () => inspect(gid));
  return button;
}
class ApiError extends Error {
  constructor(data, status) {
    super(data.error || t('error.request', {status}));
    this.part = data.error_message || {key: 'error.request', params: {status}};
  }
}
function errorPart(error) {
  return error instanceof ApiError ? error.part : {key: 'error.network'};
}
function showMessage(id, part) {
  messages.set(id, part);
  const params = {...part.params};
  if (part.cause) params.message = t(part.cause.key, part.cause.params);
  $(id).textContent = t(part.key, params);
}
function showError(id, error) {
  showMessage(id, errorPart(error));
  $(id).hidden = false;
}
async function get(url, signal) {
  const response = await fetch(url, {signal});
  const data = await response.json();
  if (!response.ok) throw new ApiError(data, response.status);
  return data;
}
function metric(label, value, detail) {
  const box = element('div', undefined, 'metric');
  box.append(element('span', label), element('strong', value));
  if (detail) box.append(element('small', detail));
  return box;
}
async function inspect(gid) {
  if (request) request.abort();
  if (graphRequest) graphRequest.abort();
  const controller = new AbortController();
  request = controller;
  $('gid').value = gid;
  $('error').hidden = true;
  $('account-area').hidden = true;
  $('search-form').setAttribute('aria-busy', 'true');
  try {
    const revision = activeRevision ? `&revision=${encodeURIComponent(activeRevision)}` : '';
    const data = await get(`/api/account?gid=${encodeURIComponent(gid)}${revision}`, controller.signal);
    if (controller.signal.aborted) return;
    current = data;
    current.initialGraph = data.graph;
    $('graph-error').hidden = true;
    $('account-area').hidden = false;
    renderAccount(true);
  } catch (error) {
    if (controller.signal.aborted) return;
    showError('error', error);
  } finally {
    if (request === controller) $('search-form').setAttribute('aria-busy', 'false');
  }
}
function clusterDescription(cluster) {
  return cluster.description_parts.map(part => {
    const params = {...part.params};
    for (const [key, value] of Object.entries(params)) {
      if (typeof value === 'number') params[key] = number(value);
      if (key === 'inKzt' || key === 'outKzt') params[key] = number(Number(value), {minimumFractionDigits: 2});
    }
    if (part.key === 'cluster.roles') params.roles = Object.entries(cluster.role_counts).map(([key, count]) => `${role(key)}=${number(count)}`).join(', ');
    return t(part.key, params);
  }).join(' ');
}
function renderAccount(reset = false) {
  const data = current;
  const a = data.account;
  $('account-id').textContent = t('account.title', {gid: a.gid});
  $('role-badge').textContent = t('account.role', {role: role(a.role)});
  const warningKey = a.boundary ? 'account.boundary' : a.is_seed ? 'account.seed' : 'account.partial';
  $('account-warning').textContent = t(warningKey);
  $('metrics').replaceChildren(
    metric(t('metric.incoming'), number(a.in_kzt), t('metric.peers', {peers: number(a.in_deg), transfers: number(a.in_tx)})),
    metric(t('metric.outgoing'), number(a.out_kzt), t('metric.peers', {peers: number(a.out_deg), transfers: number(a.out_tx)})),
    metric(t('metric.confidence'), score(a.role_score), t('metric.activity', {depth: number(a.depth), days: number(a.active_days)})),
    metric(t('metric.priority'), score(a.priority_score), t('community.name', {id: a.cluster_id})));
  $('rule').textContent = t(`rule.${a.role}`);
  // Keep the canonical English export evidence; other views use the same measured fields.
  $('evidence').textContent = currentLocale() === 'en' ? a.evidence : t('evidence.summary', {
    role: role(a.role), incoming: number(a.in_deg), outgoing: number(a.out_deg),
    inKzt: number(a.in_kzt), outKzt: number(a.out_kzt), caveat: t(warningKey)});
  const scoring = $('scoring');
  scoring.replaceChildren(element('p', t('scoring.ratio', {
    ratio: a.observed_out_in_ratio === null ? t('scoring.undefined') : number(a.observed_out_in_ratio)})));
  scoring.append(element('p', t('scoring.dates', {dates: a.first_date ? `${date(a.first_date)} – ${date(a.last_date)}` : t('scoring.noTransfers')})));
  scoring.append(element('p', t('scoring.matches', {rules: a.candidates.map(c => `${role(c.role)} ${score(c.base_score)}`).join(', ')})));
  const list = element('ul');
  for (const [key, value] of Object.entries(a.priority_contributions)) {
    list.append(element('li', `${t('contribution.' + key)}: +${number(value, {minimumFractionDigits: 6, maximumFractionDigits: 6})}`));
  }
  scoring.append(element('p', t('scoring.contributions')), list);
  scoring.append(element('p', t('scoring.rules')));
  scoring.append(element('p', t('scoring.formula')));
  const rows = data.edges.map(e => {
    const row = element('tr');
    const direction = element('td');
    direction.append(accountButton(e.src), document.createTextNode(' → '), accountButton(e.dst));
    row.append(direction, element('td', number(e.sum_kzt)), element('td', number(e.n_tx)));
    return row;
  });
  $('connections').replaceChildren(...rows);
  $('connections-summary').textContent = t('graph.connections', {count: number(rows.length)});
  const cluster = data.cluster;
  $('cluster-title').textContent = t('cluster.title', {id: cluster.cluster_id, count: number(cluster.n_nodes)});
  $('cluster-description').textContent = `${clusterDescription(cluster)} ${t('cluster.totals', {seeds: number(cluster.n_seed), amount: number(cluster.sum_kzt_internal)})}`;
  $('cluster-peers').replaceChildren(...cluster.top_gids.map(accountButton));
  for (const button of document.querySelectorAll('.queue-item')) button.classList.toggle('selected', button.dataset.gid === a.gid);
  drawGraph(reset);
}
function color(node) {
  return $('color-mode').value === 'role' ? roleColors[node.role] : palette[node.cluster_id % palette.length];
}
function drawGraph(reset = false) {
  if (!current) return;
  const center = current.account;
  const neighborhood = current.graph;
  const shown = neighborhood.nodes.filter(n => n.gid !== center.gid);
  const points = new Map([[center.gid, {x: 460, y: 270}]]);
  // Small concentric rings keep nodes apart; larger bounded views fit, then zoom.
  shown.forEach((n, i) => {
    const ring = Math.floor(i / 12);
    const count = Math.min(12, shown.length - ring * 12);
    const angle = 2 * Math.PI * (i % 12) / count - Math.PI / 2;
    points.set(n.gid, {x: 460 + (270 + ring * 210) * Math.cos(angle), y: 270 + (165 + ring * 140) * Math.sin(angle)});
  });
  const graph = $('graph');
  const defs = svg('defs');
  const arrow = svg('marker', {id: 'arrow', markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto'});
  arrow.append(svg('path', {d: 'M0 0 L8 4 L0 8 Z', fill: '#78929a'}));
  defs.append(arrow);
  const viewport = svg('g', {id: 'graph-viewport'});
  graph.replaceChildren(defs, viewport);
  const links = neighborhood.edges;
  for (const e of links) {
    const a = points.get(e.src), b = points.get(e.dst);
    let d;
    if (e.src === e.dst) {
      d = `M${a.x - 12} ${a.y - 14} C${a.x - 80} ${a.y - 110},${a.x + 80} ${a.y - 110},${a.x + 14} ${a.y - 14}`;
    } else {
      const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy);
      const ux = dx / length, uy = dy / length;
      d = `M${a.x + ux * 23} ${a.y + uy * 23} Q${(a.x + b.x) / 2 - uy * 22} ${(a.y + b.y) / 2 + ux * 22},${b.x - ux * 25} ${b.y - uy * 25}`;
    }
    const edge = svg('path', {d, class: 'edge', 'marker-end': 'url(#arrow)', 'data-src': e.src, 'data-dst': e.dst});
    edge.append(svg('title', {}, t('graph.edgeTitle', {src: e.src, dst: e.dst, amount: number(e.sum_kzt), count: number(e.n_tx)})));
    viewport.append(edge);
  }
  for (const node of [center, ...shown]) {
    const point = points.get(node.gid);
    const group = svg('g', {class: 'graph-node', tabindex: '0', role: 'button', 'aria-label': t('graph.inspect', {gid: node.gid}), 'data-gid': node.gid});
    group.append(svg('title', {}, t('graph.nodeTitle', {gid: node.gid, role: role(node.role), cluster: node.cluster_id})));
    group.append(svg('circle', {cx: point.x, cy: point.y, r: node.gid === center.gid ? 22 : 15, fill: color(node), stroke: node.boundary ? '#9a771d' : '#fff', 'stroke-width': 3, 'stroke-dasharray': node.boundary ? '4 3' : 'none'}));
    group.append(svg('text', {x: point.x, y: point.y + 34, 'text-anchor': 'middle', class: 'node-label'}, node.gid));
    group.append(svg('text', {x: point.x, y: point.y + 48, 'text-anchor': 'middle', class: 'node-role'}, `${role(node.role)} · C${node.cluster_id}${node.boundary ? ' · ' + t('graph.depthFour') : ''}`));
    group.addEventListener('click', () => inspect(node.gid));
    group.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); inspect(node.gid);}});
    viewport.append(group);
  }
  const isolation = neighborhood.total_nodes === 1 ? t(links.length ? 'graph.self' : 'graph.isolated') : '';
  $('graph-caption').textContent = isolation + t('graph.caption', {
    hops: t(neighborhood.hops === 1 ? 'graph.oneHop' : 'graph.twoHops'), visible: number(neighborhood.nodes.length),
    total: number(neighborhood.total_nodes), links: number(links.length), omitted: number(neighborhood.omitted_nodes)});
  $('node-limit').textContent = t('graph.limit', {count: number(neighborhood.node_limit)});
  $('expand').disabled = neighborhood.hops === 2;
  if (reset) {
    const ring = Math.max(0, Math.ceil(shown.length / 12) - 1);
    const scale = Math.min(1, 920 / (2 * (270 + ring * 210) + 220), 560 / (2 * (165 + ring * 140) + 140));
    camera = {scale, x: 460 * (1 - scale), y: 270 * (1 - scale)};
  }
  transformGraph();
  const legend = $('legend');
  const colors = $('color-mode').value === 'role' ? Object.entries(roleColors).map(([key, fill]) => [role(key), fill]) :
    [...new Set([center, ...shown].map(n => n.cluster_id))].sort((a, b) => a - b).map(c => [t('community.name', {id: c}), palette[c % palette.length]]);
  legend.replaceChildren(...colors.map(([label, fill]) => {
    const item = element('span', undefined, 'legend-item');
    const dot = svg('svg', {viewBox: '0 0 10 10'});
    dot.append(svg('circle', {cx: 5, cy: 5, r: 4, fill}));
    item.append(dot, document.createTextNode(label));
    return item;
  }));
  legend.append(element('span', t('graph.legend')));
}
function transformGraph() {
  const viewport = $('graph-viewport');
  if (viewport) viewport.setAttribute('transform', `translate(${camera.x} ${camera.y}) scale(${camera.scale})`);
}
function zoom(factor, x = 460, y = 280) {
  const scale = Math.max(0.2, Math.min(4, camera.scale * factor));
  const ratio = scale / camera.scale;
  camera = {scale, x: x - (x - camera.x) * ratio, y: y - (y - camera.y) * ratio};
  transformGraph();
}
function graphPoint(event) {
  return new DOMPoint(event.clientX, event.clientY).matrixTransform($('graph').getScreenCTM().inverse());
}
async function expandGraph() {
  if (!current) return;
  if (graphRequest) graphRequest.abort();
  const controller = new AbortController();
  graphRequest = controller;
  const account = current;
  $('expand').disabled = true;
  $('graph-error').hidden = true;
  try {
    const graph = await get(`/api/graph?gid=${encodeURIComponent(account.account.gid)}&hops=2&revision=${encodeURIComponent(account.revision)}`, controller.signal);
    if (controller.signal.aborted || current !== account) return;
    current.graph = graph;
    drawGraph(true);
  } catch (error) {
    if (controller.signal.aborted) return;
    showError('graph-error', error);
    $('expand').disabled = false;
  }
}
$('search-form').addEventListener('submit', e => {e.preventDefault(); inspect($('gid').value.trim());});
$('color-mode').addEventListener('change', () => drawGraph());
$('expand').addEventListener('click', expandGraph);
$('reset-graph').addEventListener('click', () => {
  if (!current) return;
  if (graphRequest) graphRequest.abort();
  current.graph = current.initialGraph;
  $('graph-error').hidden = true;
  drawGraph(true);
});
$('zoom-in').addEventListener('click', () => zoom(1.25));
$('zoom-out').addEventListener('click', () => zoom(1 / 1.25));
$('graph').addEventListener('wheel', event => {
  event.preventDefault();
  const point = graphPoint(event);
  zoom(event.deltaY < 0 ? 1.15 : 1 / 1.15, point.x, point.y);
}, {passive: false});
$('graph').addEventListener('pointerdown', event => {
  if (event.button !== 0 || event.target.closest('.graph-node')) return;
  drag = {point: graphPoint(event), x: camera.x, y: camera.y};
  $('graph').setPointerCapture(event.pointerId);
});
$('graph').addEventListener('pointermove', event => {
  if (!drag) return;
  const point = graphPoint(event);
  camera.x = drag.x + point.x - drag.point.x;
  camera.y = drag.y + point.y - drag.point.y;
  transformGraph();
});
for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) $('graph').addEventListener(name, () => {drag = null;});
$('graph').addEventListener('keydown', event => {
  if (event.target !== $('graph')) return;
  const moves = {ArrowLeft: [30, 0], ArrowRight: [-30, 0], ArrowUp: [0, 30], ArrowDown: [0, -30]};
  if (moves[event.key]) {
    event.preventDefault();
    camera.x += moves[event.key][0]; camera.y += moves[event.key][1]; transformGraph();
  } else if (event.key === '+' || event.key === '-') {
    event.preventDefault(); zoom(event.key === '+' ? 1.25 : 1 / 1.25);
  }
});
function renderOverview() {
  if (!overview) return;
  const stats = [['accounts', 'nodes'], ['edges', 'edges'], ['transactions', 'transactions'], ['clusters', 'clusters'], ['isolates', 'isolates']];
  $('summary').replaceChildren(...stats.map(([key, field]) => {
    const stat = element('div', undefined, 'stat');
    stat.append(element('strong', number(overview.profile[field])), element('span', t('summary.' + key)));
    return stat;
  }));
  $('queue-count').textContent = t('queue.top', {count: number(overview.top.length)});
  $('queue').replaceChildren(...overview.top.map(n => {
    const button = accountButton(n.gid);
    button.className = 'queue-item';
    button.dataset.gid = n.gid;
    button.classList.toggle('selected', n.gid === current?.account.gid);
    const info = element('span', undefined, 'queue-info');
    info.append(element('strong', n.gid), element('span', role(n.role)));
    button.replaceChildren(element('span', number(n.rank, {minimumIntegerDigits: 2}), 'rank'), info, element('span', score(n.priority_score), 'queue-score'));
    return button;
  }));
}
async function loadOverview() {
  try {
    const data = await get('/api/overview');
    overview = data;
    activeRevision = data.revision;
    messages.delete('summary');
    messages.delete('queue-count');
    renderOverview();
    if (data.top.length) await inspect(data.top[0].gid);
  } catch (error) {
    showMessage('summary', {key: 'summary.unavailable'});
    showError('error', error);
  }
}
function renderStatus() {
  if (!analysisStatus) return;
  const status = analysisStatus;
  const description = status.state === 'failed' ?
    `${t(status.error_message?.key || 'error.analysis', status.error_message?.params)} ${t('status.preserved')}` : t('status.' + status.state);
  $('analysis-status').textContent = `${t('state.' + status.state)}: ${description}` +
    (status.elapsed_seconds !== undefined ? ' ' + t('status.elapsed', {seconds: number(status.elapsed_seconds)}) : '') +
    (status.run_directory ? ' ' + t('status.saved', {path: status.run_directory}) : '');
}
let statusTimer = null;
function uploadBusy(busy) {
  $('upload-form').setAttribute('aria-busy', String(busy));
  for (const input of $('upload-form').elements) input.disabled = busy;
}
async function pollStatus() {
  clearTimeout(statusTimer);
  try {
    const status = await get('/api/status');
    const busy = ['receiving', 'validating', 'analyzing', 'exporting'].includes(status.state);
    uploadBusy(busy);
    analysisStatus = status;
    messages.delete('analysis-status');
    renderStatus();
    $('upload-error').hidden = status.state !== 'failed';
    if (status.state === 'failed') showMessage('upload-error', status.error_message || {key: 'error.analysis'});
    if (status.revision && status.revision !== activeRevision) await loadOverview();
    if (busy) statusTimer = setTimeout(pollStatus, 400);
    return status;
  } catch (error) {
    uploadBusy(false);
    showMessage('upload-error', {key: 'error.status', cause: errorPart(error)});
    $('upload-error').hidden = false;
    return null;
  }
}
$('upload-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData($('upload-form'));
  const files = [...form.values()];
  if (files.some(file => !file.size) || files.reduce((sum, file) => sum + file.size, 0) >= 64 * 1024 * 1024) {
    showMessage('upload-error', {key: 'upload.invalid'});
    $('upload-error').hidden = false;
    return;
  }
  uploadBusy(true);
  $('upload-error').hidden = true;
  showMessage('analysis-status', {key: 'upload.pending'});
  try {
    const response = await fetch('/api/analysis', {method: 'POST', body: form});
    const data = await response.json();
    if (!response.ok) throw new ApiError(data, response.status);
    await pollStatus();
  } catch (error) {
    uploadBusy(false);
    await pollStatus();
    showError('upload-error', error);
  }
});
function renderFiles() {
  for (const name of ['nodes', 'edges', 'transactions']) {
    $('filename-' + name).textContent = $('upload-' + name).files[0]?.name || t('upload.emptyFile');
  }
}
function renderLanguage() {
  $('language').value = currentLocale();
  $('observation-period').textContent = `${date('2026-07-01')} – ${date('2026-07-31')}`;
  renderFiles();
  renderOverview();
  renderStatus();
  for (const [id, part] of messages) showMessage(id, part);
  if (current && !$('account-area').hidden) renderAccount();
}
$('language').addEventListener('change', () => {
  setLocale($('language').value);
  renderLanguage();
});
for (const name of ['nodes', 'edges', 'transactions']) $('upload-' + name).addEventListener('change', renderFiles);
(async () => {
  try {
    const unavailable = await initialize();
    for (const option of $('language').options) option.disabled = unavailable.includes(option.value);
    $('language').disabled = false;
    showMessage('summary', {key: 'summary.loading'});
    showMessage('analysis-status', {key: 'status.idle'});
    renderLanguage();
    const status = await pollStatus();
    if (status && !status.revision) {
      showMessage('summary', {key: 'summary.empty'});
      showMessage('queue-count', {key: 'queue.empty'});
    }
    if (unavailable.length) {
      showMessage('error', {key: 'error.catalog'});
      $('error').hidden = false;
    }
  } catch (error) {
    // Even a missing English catalog must leave a visible, actionable failure.
    $('error').textContent = error.message;
    $('error').hidden = false;
  }
})();
