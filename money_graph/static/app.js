import {initialize, t, number, date, timestamp, setLocale, currentLocale} from './i18n.js';
import {roleColors, shortId, initialize as initializeMap, load as loadMap, render as renderMap,
        setSelection as setMapSelection} from './map.js';
import {initialize as initializeFlows, load as loadFlows, render as renderFlows} from './flows.js';
const $ = (id) => document.getElementById(id);
// SVG fills inherit theme variables: recoloring never rerenders or resets the graph.
const palette = Array.from({length: 8}, (_, index) => `var(--cluster-${index})`);
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
let trail = [];
let clusterPalette = new Map();
function accountButton(gid) {
  const button = element('button', shortId(gid));
  button.type = 'button';
  button.title = gid;
  button.addEventListener('click', () => inspect(gid));
  return button;
}
// A visited path: clicking through the network never loses where the review started.
function renderTrail() {
  const container = $('trail');
  if (!container) return;
  if (trail.length < 2) {
    container.replaceChildren();
    container.hidden = true;
    return;
  }
  container.hidden = false;
  const visible = trail.slice(-6);
  const parts = [element('span', t('graph.trail'), 'trail-label')];
  if (visible.length < trail.length) parts.push(element('span', '…', 'trail-sep'));
  visible.forEach((gid, index) => {
    const last = index === visible.length - 1;
    const step = element(last ? 'strong' : 'button', shortId(gid), last ? 'trail-current' : 'trail-step');
    step.title = gid;
    if (!last) {
      step.type = 'button';
      step.addEventListener('click', () => inspect(gid));
      parts.push(step, element('span', '›', 'trail-sep'));
    } else {
      parts.push(step);
    }
  });
  container.replaceChildren(...parts);
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
async function inspect(gid, options = {}) {
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
    const visited = trail.indexOf(String(gid));
    if (visited >= 0) trail = trail.slice(0, visited + 1);
    else trail.push(String(gid));
    setMapSelection(gid);
    $('graph-error').hidden = true;
    $('account-area').hidden = false;
    renderAccount(true);
    if (options.reveal) $('account-area').scrollIntoView({behavior: 'smooth', block: 'start'});
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
  renderTrail();
  drawGraph(reset);
}
function color(node) {
  return $('color-mode').value === 'role' ? roleColors[node.role] : clusterPalette.get(node.cluster_id);
}
// Money reads left to right: accounts that pay the selected one sit to its left, accounts it pays sit to its right.
function egoPoints(center, shown, edges) {
  const paid = new Map(), received = new Map();
  for (const edge of edges) {
    if (edge.src === edge.dst) continue;
    if (edge.dst === center.gid) paid.set(edge.src, (paid.get(edge.src) || 0) + edge.sum_kzt);
    if (edge.src === center.gid) received.set(edge.dst, (received.get(edge.dst) || 0) + edge.sum_kzt);
  }
  const lane = new Map([[center.gid, 0]]);
  for (const node of shown) {
    const inbound = paid.get(node.gid), outbound = received.get(node.gid);
    // A reciprocal counterparty is shown on the side carrying the larger observed amount.
    if (inbound !== undefined && outbound !== undefined) lane.set(node.gid, inbound >= outbound ? -1 : 1);
    else if (inbound !== undefined) lane.set(node.gid, -1);
    else if (outbound !== undefined) lane.set(node.gid, 1);
  }
  const adjacency = new Map();
  for (const edge of edges) {
    if (edge.src === edge.dst) continue;
    if (!adjacency.has(edge.src)) adjacency.set(edge.src, []);
    if (!adjacency.has(edge.dst)) adjacency.set(edge.dst, []);
    adjacency.get(edge.src).push({peer: edge.dst, downstream: true});
    adjacency.get(edge.dst).push({peer: edge.src, downstream: false});
  }
  // Two-hop accounts sit one column beyond the neighbour that connects them to the centre.
  const queue = [...lane.keys()];
  while (queue.length) {
    const account = queue.shift();
    for (const {peer, downstream} of adjacency.get(account) || []) {
      if (lane.has(peer)) continue;
      lane.set(peer, Math.max(-2, Math.min(2, lane.get(account) + (downstream ? 1 : -1))));
      queue.push(peer);
    }
  }
  const groups = new Map();
  for (const node of shown) {
    const key = lane.has(node.gid) ? lane.get(node.gid) : 2;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(node);
  }
  const weight = (node) => Math.max(paid.get(node.gid) || 0, received.get(node.gid) || 0, node.in_kzt + node.out_kzt);
  for (const group of groups.values()) group.sort((a, b) => weight(b) - weight(a) || (a.gid < b.gid ? -1 : 1));
  const CX = 460, CY = 280, GAP = 205, STEP = 56, PER_COLUMN = 11;
  const points = new Map([[center.gid, {x: CX, y: CY}]]);
  let rightmost = 0;
  for (const [direction, lanes] of [[-1, [-1, -2]], [1, [1, 2]]]) {
    let column = 0;
    for (const key of lanes) {
      const group = groups.get(key) || [];
      for (let start = 0; start < group.length; start += PER_COLUMN) {
        column += 1;
        const slice = group.slice(start, start + PER_COLUMN);
        const x = CX + direction * column * GAP;
        slice.forEach((node, index) => points.set(node.gid, {x, y: CY - (slice.length - 1) * STEP / 2 + index * STEP}));
      }
    }
    if (direction === 1) rightmost = column;
  }
  // Lane 0 holds accounts fed by the same payers as the selected one: peers at the same stage,
  // so they share its column rather than implying a flow direction they do not have.
  (groups.get(0) || []).forEach((node, index) => {
    points.set(node.gid, {x: CX, y: CY + (Math.floor(index / 2) + 1) * STEP * (index % 2 ? 1 : -1)});
  });
  const stranded = shown.filter(node => !points.has(node.gid));
  stranded.forEach((node, index) => points.set(node.gid, {x: CX + (rightmost + 1 + Math.floor(index / PER_COLUMN)) * GAP,
    y: CY - (Math.min(PER_COLUMN, stranded.length) - 1) * STEP / 2 + (index % PER_COLUMN) * STEP}));
  return points;
}
function drawGraph(reset = false) {
  if (!current) return;
  const center = current.account;
  const neighborhood = current.graph;
  const shown = neighborhood.nodes.filter(n => n.gid !== center.gid);
  const points = egoPoints(center, shown, neighborhood.edges);
  // Community colours are assigned per view, so two visible communities never share one colour.
  clusterPalette = new Map();
  for (const node of [center, ...shown]) {
    if (!clusterPalette.has(node.cluster_id)) clusterPalette.set(node.cluster_id, palette[clusterPalette.size % palette.length]);
  }
  const graph = $('graph');
  const defs = svg('defs');
  const arrow = svg('marker', {id: 'arrow', markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto'});
  arrow.append(svg('path', {d: 'M0 0 L8 4 L0 8 Z', fill: 'var(--graph-edge)'}));
  defs.append(arrow);
  const viewport = svg('g', {id: 'graph-viewport'});
  const captions = svg('g');
  graph.replaceChildren(defs, viewport, captions);
  const links = neighborhood.edges;
  const heaviestEdge = Math.max(1, ...links.map(e => e.sum_kzt));
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
    const edge = svg('path', {d, class: e.src === center.gid || e.dst === center.gid ? 'edge direct' : 'edge',
      'marker-end': 'url(#arrow)', 'data-src': e.src, 'data-dst': e.dst});
    // The page CSP has no 'unsafe-inline' for styles, so a style attribute would be dropped.
    edge.style.strokeWidth = `${(1 + 3.4 * Math.sqrt(e.sum_kzt / heaviestEdge)).toFixed(2)}px`;
    edge.append(svg('title', {}, t('graph.edgeTitle', {src: e.src, dst: e.dst, amount: number(e.sum_kzt), count: number(e.n_tx)})));
    viewport.append(edge);
  }
  const previous = trail.length > 1 ? trail[trail.length - 2] : null;
  const heaviestNode = Math.max(1, ...[center, ...shown].map(n => n.in_kzt + n.out_kzt));
  const roomForRoles = shown.length <= 12;
  for (const node of [center, ...shown]) {
    const point = points.get(node.gid);
    const focus = node.gid === center.gid;
    const radius = focus ? 22 : 10 + 7 * Math.sqrt((node.in_kzt + node.out_kzt) / heaviestNode);
    const group = svg('g', {class: 'graph-node', tabindex: '0', role: 'button', 'aria-label': t('graph.inspect', {gid: node.gid}), 'data-gid': node.gid});
    group.append(svg('title', {}, t('graph.nodeTitle', {gid: node.gid, role: role(node.role), cluster: node.cluster_id})));
    if (focus) group.append(svg('circle', {cx: point.x, cy: point.y, r: radius + 7,
      fill: 'none', stroke: 'var(--brand)', 'stroke-width': 2, class: 'selection-ring'}));
    group.append(svg('circle', {cx: point.x, cy: point.y, r: radius, fill: color(node),
      stroke: node.boundary ? 'var(--boundary)' : 'var(--surface)',
      'stroke-width': 3, 'stroke-dasharray': node.boundary ? '4 3' : 'none'}));
    if (node.gid === previous) group.append(svg('circle', {cx: point.x, cy: point.y, r: radius + 8, class: 'came-from'}));
    group.append(svg('text', {x: point.x, y: point.y + radius + 16, 'text-anchor': 'middle', class: 'node-label'}, shortId(node.gid)));
    if (focus || roomForRoles) {
      group.append(svg('text', {x: point.x, y: point.y + radius + 29, 'text-anchor': 'middle', class: 'node-role'},
        `${role(node.role)}${node.boundary ? ' · ' + t('graph.depthFour') : ''}`));
    }
    group.addEventListener('click', () => inspect(node.gid));
    group.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); inspect(node.gid);}});
    viewport.append(group);
  }
  captions.append(svg('text', {x: 26, y: 24, class: 'lane-caption'}, t('graph.laneIn')));
  captions.append(svg('text', {x: 460, y: 24, 'text-anchor': 'middle', class: 'lane-caption focus'}, t('graph.laneFocus')));
  captions.append(svg('text', {x: 894, y: 24, 'text-anchor': 'end', class: 'lane-caption'}, t('graph.laneOut')));
  const isolation = neighborhood.total_nodes === 1 ? t(links.length ? 'graph.self' : 'graph.isolated') : '';
  $('graph-caption').textContent = isolation + t('graph.caption', {
    hops: t(neighborhood.hops === 1 ? 'graph.oneHop' : 'graph.twoHops'), visible: number(neighborhood.nodes.length),
    total: number(neighborhood.total_nodes), links: number(links.length), omitted: number(neighborhood.omitted_nodes)});
  $('node-limit').textContent = t('graph.limit', {count: number(neighborhood.node_limit)});
  $('expand').disabled = neighborhood.hops === 2;
  if (reset) {
    // Fit the actual column bounds, so one neighbour and forty neighbours both fill the frame.
    const xs = [...points.values()].map(p => p.x), ys = [...points.values()].map(p => p.y);
    const minX = Math.min(...xs) - 95, maxX = Math.max(...xs) + 95;
    const minY = Math.min(...ys) - 55, maxY = Math.max(...ys) + 65;
    const scale = Math.min(1, 900 / (maxX - minX), 500 / (maxY - minY));
    camera = {scale, x: 460 - (minX + maxX) / 2 * scale, y: 300 - (minY + maxY) / 2 * scale};
  }
  transformGraph();
  const legend = $('legend');
  const colors = $('color-mode').value === 'role' ? Object.entries(roleColors).map(([key, fill]) => [role(key), fill]) :
    [...clusterPalette].sort((a, b) => a[0] - b[0]).map(([id, fill]) => [t('community.name', {id}), fill]);
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
    info.append(element('strong', shortId(n.gid)), element('span', role(n.role)));
    button.title = n.gid;
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
  await loadMap(get);
  await loadFlows(get);
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
  renderMap();
  renderFlows();
  renderStatus();
  renderHistory();
  for (const [id, part] of messages) showMessage(id, part);
  renderTrail();
  if (current && !$('account-area').hidden) renderAccount();
  showView();
}
$('language').addEventListener('change', () => {
  setLocale($('language').value);
  renderLanguage();
});
for (const name of ['nodes', 'edges', 'transactions']) $('upload-' + name).addEventListener('change', renderFiles);
initializeMap(gid => inspect(gid, {reveal: true}));
initializeFlows();
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
