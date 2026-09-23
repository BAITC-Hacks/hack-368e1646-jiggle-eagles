import {initialize, t, number, date, timestamp, setLocale, currentLocale} from './i18n.js';
const $ = (id) => document.getElementById(id);
// SVG fills inherit theme variables: recoloring never rerenders or resets the graph.
const palette = Array.from({length: 8}, (_, index) => `var(--cluster-${index})`);
const roleColors = Object.fromEntries(['consolidator', 'transit', 'distributor', 'terminal', 'coordinator', 'peripheral']
  .map(role => [role, `var(--role-${role})`]));
const score = (n) => number(n, {minimumFractionDigits: 3, maximumFractionDigits: 3});
const role = (value) => t(`role.${value}`);
let overview = null;
let analysisStatus = null;
let historyData = null;
let openingAnalysis = false;
let editingAnalysis = null;
let savingDetails = false;
const messages = new Map();
let current = null;
let activeRevision = null;
let graphRequest = null;
let camera = {scale: 1, x: 0, y: 0};
let drag = null;
let request = null;

// The URL is the source of truth; route changes preserve an already loaded graph.
let routeVersion = 0;
let routeTask = Promise.resolve();
let pendingUpload = false;
const routeId = () => location.pathname.match(/^\/analyses\/(startup|[0-9a-f]{32})$/)?.[1] || null;
function showView(focus = false) {
  const id = routeId();
  $('analysis-home').hidden = Boolean(id);
  $('results').hidden = !id;
  $('results-workspace').hidden = !id || activeRevision !== id || !overview;
  $('show-analyses').setAttribute('aria-pressed', String(!id));
  $('show-results').setAttribute('aria-pressed', String(Boolean(id)));
  const selected = historyData?.analyses.find(entry => entry.id === id);
  document.title = `${selected ? analysisName(selected) : t(id ? 'history.results' : 'home.title')} · Money Graph`;
  if (focus) {
    (id ? $('back-analyses') : $('show-analyses')).focus({preventScroll: true});
    window.scrollTo({top: 0, behavior: 'instant'});
  }
}
function navigate(id = null) {
  const path = id ? `/analyses/${encodeURIComponent(id)}` : '/analyses';
  if (location.pathname !== path) history.pushState(null, '', path);
  return renderRoute(true);
}
function renderRoute(focus = false) {
  const version = ++routeVersion;
  const id = routeId();
  $('error').hidden = true;
  showView(focus);
  if (!id) return Promise.resolve();
  if (activeRevision !== id || !overview) {
    showMessage('summary', {key: 'summary.loading'});
    $('selected-analysis').textContent = '';
  }
  // Serialize opens so fast Back/Forward cannot publish saved runs out of order.
  routeTask = routeTask.then(async () => {
    if (version !== routeVersion) return;
    openingAnalysis = true;
    uploadBusy(true);
    try {
      if (activeRevision !== id || !overview) {
        if (analysisStatus?.revision !== id) {
          const response = await fetch(`/api/analyses/${encodeURIComponent(id)}/open`, {method: 'POST'});
          const status = await response.json();
          if (!response.ok) throw new ApiError(status, response.status);
          analysisStatus = status;
          renderStatus();
        }
        await loadOverview(id);
      }
      if (version === routeVersion) {
        messages.delete('summary');
        renderOverview();
        showView();
      }
    } catch (error) {
      if (version === routeVersion) {
        showMessage('summary', {key: 'summary.unavailable'});
        showError('error', error);
      }
    } finally {
      openingAnalysis = false;
      uploadBusy(analysisStatus && ['receiving', 'validating', 'analyzing', 'exporting'].includes(analysisStatus.state));
    }
  });
  return routeTask;
}
$('show-analyses').addEventListener('click', () => navigate());
$('back-analyses').addEventListener('click', () => navigate());
$('show-results').addEventListener('click', () => navigate(activeRevision || analysisStatus?.revision));
window.addEventListener('popstate', () => renderRoute(true));

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
  $('rule').textContent = t(a.role === 'transit' && !a.temporal ? 'rule.transitLegacy' : `rule.${a.role}`);
  // Keep the canonical English export evidence; other views use the same measured fields.
  $('evidence').textContent = currentLocale() === 'en' ? a.evidence : t('evidence.summary', {
    role: role(a.role), incoming: number(a.in_deg), outgoing: number(a.out_deg),
    inKzt: number(a.in_kzt), outKzt: number(a.out_kzt), caveat: t(warningKey)});
  let patterns = $('patterns');
  if (!patterns) {
    patterns = element('section');
    patterns.id = 'patterns';
    $('evidence').after(patterns);
  }
  patterns.replaceChildren(element('h3', t('pattern.title')));
  // Saved runs created before these features retain their original schema.
  if (a.patterns === undefined) {
    patterns.append(element('p', t('pattern.unavailable'), 'muted'));
  } else {
    const patternList = element('ul');
    for (const part of a.patterns) {
      const params = Object.fromEntries(Object.entries(part.params).map(([key, value]) =>
        [key, key === 'share' ? number(value, {style: 'percent', maximumFractionDigits: 1}) : number(value)]));
      const item = element('li', t(part.key, params));
      item.dataset.pattern = part.key;
      patternList.append(item);
    }
    patterns.append(a.patterns.length ? patternList : element('p', t('pattern.none')),
      element('p', t('pattern.caveat'), 'muted'));
  }
  let temporal = $('temporal');
  if (!temporal) {
    temporal = element('section');
    temporal.id = 'temporal';
    patterns.after(temporal);
  }
  const tf = a.temporal;
  temporal.replaceChildren(element('h3', t('temporal.title')));
  if (tf === undefined) {
    temporal.append(element('p', t('temporal.unavailable'), 'muted'));
  } else {
    temporal.append(
      element('p', t('temporal.matched', {
        amount: number(tf.matched_kzt), day1: number(tf.matched_day1_kzt), day2: number(tf.matched_day2_kzt),
        share: tf.matched_in_share === null ? t('scoring.undefined') : number(tf.matched_in_share, {style: 'percent', maximumFractionDigits: 1})})),
      element('p', t('temporal.sameDay', {amount: number(tf.same_day_overlap_kzt)})),
      element('p', t('temporal.caveat'), 'muted'));
    if (tf.end_window_incoming_kzt > 0) temporal.append(element('p', t('temporal.endWindow', {amount: number(tf.end_window_incoming_kzt)}), 'warning'));
    const details = element('details');
    details.append(element('summary', t('temporal.details')));
    const allocations = element('ul');
    for (const match of tf.matches) allocations.append(element('li', t('temporal.match', {
      incoming: date(match.in_date), outgoing: date(match.out_date), amount: number(match.amount_kzt), days: number(match.lag_days)})));
    for (const overlap of tf.same_day) allocations.append(element('li', t('temporal.overlap', {
      date: date(overlap.date), amount: number(overlap.amount_kzt)})));
    details.append(allocations);
    temporal.append(details);
  }
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
  arrow.append(svg('path', {d: 'M0 0 L8 4 L0 8 Z', fill: 'var(--graph-edge)'}));
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
    if (node.gid === center.gid) group.append(svg('circle', {cx: point.x, cy: point.y, r: 29,
      fill: 'none', stroke: 'var(--brand)', 'stroke-width': 2, class: 'selection-ring'}));
    group.append(svg('circle', {cx: point.x, cy: point.y, r: node.gid === center.gid ? 22 : 15, fill: color(node), stroke: node.boundary ? 'var(--boundary)' : 'var(--surface)', 'stroke-width': 3, 'stroke-dasharray': node.boundary ? '4 3' : 'none'}));
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
  if (!overview || (routeId() && routeId() !== activeRevision)) return;
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
async function loadOverview(id) {
  if (request) request.abort();
  if (graphRequest) graphRequest.abort();
  const data = await get('/api/overview');
  if (data.revision !== id) throw new ApiError({error_message: {key: 'error.stale'}}, 409);
  current = null;
  $('account-area').hidden = true;
  overview = data;
  activeRevision = data.revision;
  for (const link of document.querySelectorAll('.downloads a')) {
    const url = new URL(link.href);
    url.searchParams.set('revision', id);
    link.href = url.href;
  }
  $('show-results').disabled = false;
  messages.delete('summary');
  messages.delete('queue-count');
  renderOverview();
  renderHistory();
  if (data.top.length) await inspect(data.top[0].gid);
}
function renderHistory() {
  if (!historyData) return;
  const entries = historyData.analyses;
  $('history-count').textContent = t('history.count', {count: number(entries.length)});
  $('history-warning').hidden = !historyData.unavailable_count;
  $('history-warning').textContent = t('history.unavailable', {count: number(historyData.unavailable_count)});
  const selected = entries.find(entry => entry.id === (routeId() || activeRevision || analysisStatus?.revision));
  $('selected-analysis').textContent = selected ? analysisName(selected) : '';
  showView();
  if (!entries.length) {
    const empty = element('div', undefined, 'history-empty');
    empty.append(element('strong', t('history.empty')), element('p', t('history.emptyHelp'), 'muted'));
    $('history-list').replaceChildren(empty);
    return;
  }
  $('history-list').replaceChildren(...entries.map(entry => {
    const active = entry.id === (activeRevision || analysisStatus?.revision);
    const row = element('article', undefined, 'history-row' + (active ? ' active' : ''));
    row.dataset.analysisId = entry.id;
    const info = element('div', undefined, 'history-info');
    info.append(element('h3', analysisName(entry)));
    if (entry.description) info.append(element('p', entry.description, 'history-description'));
    if (entry.title) info.append(element('p', timestamp(entry.started_utc), 'muted'));
    info.append(element('p', t('history.stats', {
      nodes: number(entry.profile.nodes), edges: number(entry.profile.edges),
      transactions: number(entry.profile.transactions), seconds: number(entry.elapsed_seconds)
    }), 'muted'), element('p', t('history.id', {id: entry.id}), 'history-id'));
    const tags = element('div', undefined, 'history-tags');
    if (active) tags.append(element('span', t('history.current'), 'history-tag'));
    if (entry.duplicate_of) tags.append(element('span', t('history.duplicate'), 'history-tag'));
    info.append(tags);
    const button = element('button', t(active ? 'history.viewing' : 'history.open'));
    button.type = 'button';
    button.disabled = openingAnalysis || $('upload-form').getAttribute('aria-busy') === 'true';
    button.addEventListener('click', () => navigate(entry.id));
    const actions = element('div', undefined, 'history-actions');
    const edit = element('button', t('details.edit'), 'secondary edit-details');
    edit.type = 'button';
    edit.addEventListener('click', () => editAnalysis(entry));
    actions.append(edit, button);
    row.append(info, actions);
    return row;
  }));
}
function analysisName(entry) {
  return entry.title || t(entry.id === 'startup' ? 'history.startup' : 'history.analysis', {date: timestamp(entry.started_utc)});
}
function editAnalysis(entry) {
  editingAnalysis = entry.id;
  $('details-title').value = analysisName(entry);
  $('details-description').value = entry.description || '';
  $('details-error').hidden = true;
  $('details-dialog').showModal();
  $('details-title').focus();
  $('details-title').select();
}
$('details-cancel').addEventListener('click', () => $('details-dialog').close());
$('details-dialog').addEventListener('cancel', event => {
  if (savingDetails) event.preventDefault();
});
$('details-dialog').addEventListener('close', () => { editingAnalysis = null; });
$('details-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (savingDetails || !editingAnalysis) return;
  const id = editingAnalysis;
  const details = {title: $('details-title').value.trim(), description: $('details-description').value.trim()};
  if (!details.title || [...details.title].length > 120) {
    showMessage('details-error', {key: 'error.detailsTitle'});
    $('details-error').hidden = false;
    $('details-title').focus();
    return;
  }
  savingDetails = true;
  $('details-form').setAttribute('aria-busy', 'true');
  for (const input of $('details-form').elements) input.disabled = true;
  $('details-error').hidden = true;
  try {
    const response = await fetch(`/api/analyses/${encodeURIComponent(id)}/details`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(details)
    });
    const saved = await response.json();
    if (!response.ok) throw new ApiError(saved, response.status);
    historyData.analyses = historyData.analyses.map(entry => entry.id === id ? {...entry, ...saved} : entry);
    $('details-dialog').close();
    renderHistory();
    document.querySelector(`[data-analysis-id="${id}"] .edit-details`)?.focus();
  } catch (error) {
    showError('details-error', error);
  } finally {
    savingDetails = false;
    $('details-form').setAttribute('aria-busy', 'false');
    for (const input of $('details-form').elements) input.disabled = false;
  }
});
async function loadHistory() {
  try {
    historyData = await get('/api/analyses');
    $('history-error').hidden = true;
    renderHistory();
  } catch (error) {
    showError('history-error', error);
  }
}
function renderStatus() {
  if (!analysisStatus) return;
  const status = analysisStatus;
  $('analysis-status').dataset.state = status.state;
  const description = status.state === 'failed' ?
    `${t(status.error_message?.key || 'error.analysis', status.error_message?.params)} ${t('status.preserved')}` : t('status.' + status.state);
  $('analysis-status').textContent = `${t('state.' + status.state)}: ${description}` +
    (status.elapsed_seconds !== undefined ? ' ' + t('status.elapsed', {seconds: number(status.elapsed_seconds)}) : '') +
    (status.run_directory ? ' ' + t('status.saved', {path: status.run_directory}) : '');
}
let statusTimer = null;
function uploadBusy(busy) {
  busy = Boolean(busy || openingAnalysis);
  $('upload-form').setAttribute('aria-busy', String(busy));
  for (const input of $('upload-form').elements) input.disabled = busy;
  renderHistory();
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
    $('show-results').disabled = !(activeRevision || status.revision);
    if (!busy) await loadHistory();
    if (pendingUpload && !busy) {
      pendingUpload = false;
      if (status.state === 'succeeded' && status.revision) await navigate(status.revision);
    }
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
    pendingUpload = true;
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
    $('upload-' + name).closest('.file-field').classList.toggle('has-file', Boolean($('upload-' + name).files.length));
  }
}
function renderLanguage() {
  $('language').value = currentLocale();
  $('observation-period').textContent = `${date('2026-07-01')} – ${date('2026-07-31')}`;
  renderFiles();
  renderOverview();
  renderStatus();
  renderHistory();
  for (const [id, part] of messages) showMessage(id, part);
  if (current && !$('account-area').hidden) renderAccount();
  showView();
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
    if (location.pathname === '/') history.replaceState(null, '', '/analyses');
    await renderRoute();
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
