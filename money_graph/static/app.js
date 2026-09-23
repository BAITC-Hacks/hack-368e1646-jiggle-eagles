'use strict';
const $ = (id) => document.getElementById(id);
const palette = ['#087e8b', '#9b5bb5', '#d98839', '#527bc2', '#c95c72', '#61843b', '#b86d39', '#546e7a'];
const roleColors = {consolidator: '#087e8b', transit: '#527bc2', distributor: '#d98839', terminal: '#9b5bb5', coordinator: '#c95c72', peripheral: '#80918f'};
const number = (n) => new Intl.NumberFormat('en', {maximumFractionDigits: 2}).format(n);
const score = (n) => n.toFixed(3);
let current = null;
let page = 0;
let request = null;
const PAGE_SIZE = 16;

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
async function get(url, signal) {
  const response = await fetch(url, {signal});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
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
  const controller = new AbortController();
  request = controller;
  $('gid').value = gid;
  $('error').hidden = true;
  $('account-area').hidden = true;
  $('search-form').setAttribute('aria-busy', 'true');
  try {
    const data = await get(`/api/account?gid=${encodeURIComponent(gid)}`, controller.signal);
    if (controller.signal.aborted) return;
    current = data;
    page = 0;
    const a = data.account;
    $('account-id').textContent = `Client ${a.gid}`;
    $('role-badge').textContent = `${a.role} hypothesis`;
    $('account-warning').textContent = a.boundary ? 'Depth 4 boundary — onward transfers are unknown. Missing outgoing links do not establish a terminal recipient.' :
      a.is_seed ? 'Seed account — incoming flows from outside this sample are incomplete.' : 'Partial observed network — role is a structural hypothesis only.';
    $('metrics').replaceChildren(
      metric('Observed incoming KZT', number(a.in_kzt), `${a.in_deg} peers · ${a.in_tx} transfers`),
      metric('Observed outgoing KZT', number(a.out_kzt), `${a.out_deg} peers · ${a.out_tx} transfers`),
      metric('Heuristic role confidence', score(a.role_score), `Depth ${a.depth} · ${a.active_days} active days`),
      metric('Investigation priority', score(a.priority_score), `Community ${a.cluster_id}`));
    $('rule').textContent = a.role_rule;
    $('evidence').textContent = a.evidence;
    const scoring = $('scoring');
    scoring.replaceChildren(element('p', `Observed out/in ratio: ${a.observed_out_in_ratio === null ? 'undefined (no observed inflow)' : number(a.observed_out_in_ratio)}. This is not a retained-funds or balance measure.`));
    scoring.append(element('p', `Dates: ${a.first_date || 'no transfers'}${a.last_date ? ` to ${a.last_date}` : ''}. No time-of-day ordering is available.`));
    scoring.append(element('p', `Matched rules: ${a.candidates.map(c => `${c.role} ${score(c.base_score)}`).join(', ')}. Highest base score wins; ties: coordinator, consolidator, distributor, transit, terminal, peripheral. Subtract 0.10 for multiple matches; multiply by 0.60 at depth 4, then 0.85 for seeds.`));
    const list = element('ul');
    for (const [key, value] of Object.entries(a.priority_contributions)) list.append(element('li', `${key.replaceAll('_', ' ')}: +${value.toFixed(6)}`));
    scoring.append(element('p', 'Priority contributions (sum = priority; seed membership adds no priority):'), list);
    scoring.append(element('p', 'Rules: consolidator ≥3 incoming and ≥2× outgoing peers; distributor ≥5 outgoing and ≥2× incoming; coordinator ≥2 each direction and ≥3 neighbor communities; transit non-seed, both directions, ratio 0.8–1.2; terminal non-seed, depth<4, incoming but no outgoing peers. Otherwise peripheral.'));
    scoring.append(element('p', 'Priority = 0.30×min(incoming peers/10,1) + 0.25×min(outgoing peers/10,1) + 0.20×min(cross-community peers/5,1) + 0.15×min((incoming+outgoing transfers)/30,1) + 0.10×log(1+incoming+outgoing KZT)/log(1+maximum incident KZT in this dataset).'));
    const rows = data.edges.map(e => {
      const row = element('tr');
      const direction = element('td');
      direction.append(accountButton(e.src), document.createTextNode(' → '), accountButton(e.dst));
      row.append(direction, element('td', number(e.sum_kzt)), element('td', String(e.n_tx)));
      return row;
    });
    $('connections').replaceChildren(...rows);
    $('connections-summary').textContent = `All ${rows.length} observed directed connections`;
    const cluster = data.cluster;
    $('cluster-title').textContent = `Community ${cluster.cluster_id} · ${cluster.n_nodes} accounts`;
    $('cluster-description').textContent = `${cluster.hypothesis} Seeds: ${cluster.n_seed}. Internal observed transfers: ${number(cluster.sum_kzt_internal)} KZT (each directed transfer counted once).`;
    $('cluster-peers').replaceChildren(...cluster.top_gids.map(accountButton));
    for (const button of document.querySelectorAll('.queue-item')) button.classList.toggle('selected', button.dataset.gid === a.gid);
    $('account-area').hidden = false;
    drawGraph();
  } catch (error) {
    if (controller.signal.aborted) return;
    $('error').textContent = error.message || 'Account could not be loaded.';
    $('error').hidden = false;
  } finally {
    if (request === controller) $('search-form').setAttribute('aria-busy', 'false');
  }
}
function color(node) {
  return $('color-mode').value === 'role' ? roleColors[node.role] : palette[node.cluster_id % palette.length];
}
function drawGraph() {
  if (!current) return;
  const center = current.account;
  const others = current.neighbors.filter(n => n.gid !== center.gid);
  const shown = others.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const points = new Map([[center.gid, {x: 460, y: 270}]]);
  shown.forEach((n, i) => {
    const angle = 2 * Math.PI * i / shown.length - Math.PI / 2;
    points.set(n.gid, {x: 460 + 345 * Math.cos(angle), y: 270 + 210 * Math.sin(angle)});
  });
  const graph = $('graph');
  const defs = svg('defs');
  const arrow = svg('marker', {id: 'arrow', markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto'});
  arrow.append(svg('path', {d: 'M0 0 L8 4 L0 8 Z', fill: '#78929a'}));
  defs.append(arrow);
  graph.replaceChildren(defs);
  const links = current.edges.filter(e => points.has(e.src) && points.has(e.dst));
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
    edge.append(svg('title', {}, `${e.src} → ${e.dst} · ${number(e.sum_kzt)} KZT · ${e.n_tx} transfers`));
    graph.append(edge);
  }
  for (const node of [center, ...shown]) {
    const point = points.get(node.gid);
    const group = svg('g', {class: 'graph-node', tabindex: '0', role: 'button', 'aria-label': `Inspect client ${node.gid}`, 'data-gid': node.gid});
    group.append(svg('circle', {cx: point.x, cy: point.y, r: node.gid === center.gid ? 22 : 15, fill: color(node), stroke: node.boundary ? '#9a771d' : '#fff', 'stroke-width': 3, 'stroke-dasharray': node.boundary ? '4 3' : 'none'}));
    group.append(svg('text', {x: point.x, y: point.y + 34, 'text-anchor': 'middle', class: 'node-label'}, node.gid));
    group.append(svg('text', {x: point.x, y: point.y + 48, 'text-anchor': 'middle', class: 'node-role'}, `${node.role} · C${node.cluster_id}${node.boundary ? ' · depth 4' : ''}`));
    group.addEventListener('click', () => inspect(node.gid));
    group.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); inspect(node.gid);}});
    graph.append(group);
  }
  $('graph-caption').textContent = others.length ? `Peers ${page * PAGE_SIZE + 1}–${page * PAGE_SIZE + shown.length} of ${others.length} · ${links.length} of ${current.edges.length} directed links` :
    current.edges.length ? 'Self-transfer only; no other observed peers.' : 'Isolated account · no observed connections. Included in analysis.';
  $('previous').disabled = page === 0;
  $('next').disabled = (page + 1) * PAGE_SIZE >= others.length;
  const legend = $('legend');
  const colors = $('color-mode').value === 'role' ? Object.entries(roleColors) :
    [...new Set([center, ...shown].map(n => n.cluster_id))].sort((a, b) => a - b).map(c => [`Community ${c}`, palette[c % palette.length]]);
  legend.replaceChildren(...colors.map(([label, fill]) => {
    const item = element('span', undefined, 'legend-item');
    const dot = svg('svg', {viewBox: '0 0 10 10'});
    dot.append(svg('circle', {cx: 5, cy: 5, r: 4, fill}));
    item.append(dot, document.createTextNode(label));
    return item;
  }));
  legend.append(element('span', 'Dashed outline = depth 4; community colors repeat, IDs distinguish them.'));
}
$('search-form').addEventListener('submit', e => {e.preventDefault(); inspect($('gid').value.trim());});
$('color-mode').addEventListener('change', drawGraph);
$('previous').addEventListener('click', () => {page--; drawGraph();});
$('next').addEventListener('click', () => {page++; drawGraph();});
(async () => {
  try {
    const data = await get('/api/overview');
    const stats = [['Accounts', data.profile.nodes], ['Directed connections', data.profile.edges], ['Transactions', data.profile.transactions], ['Communities', data.profile.clusters], ['Isolated accounts', data.profile.isolates]];
    $('summary').replaceChildren(...stats.map(([label, value]) => {
      const stat = element('div', undefined, 'stat');
      stat.append(element('strong', number(value)), element('span', label));
      return stat;
    }));
    $('queue-count').textContent = `TOP ${data.top.length}`;
    $('queue').replaceChildren(...data.top.map(n => {
      const button = accountButton(n.gid);
      button.className = 'queue-item';
      button.dataset.gid = n.gid;
      const info = element('span', undefined, 'queue-info');
      info.append(element('strong', n.gid), element('span', n.role));
      button.replaceChildren(element('span', String(n.rank).padStart(2, '0'), 'rank'), info, element('span', score(n.priority_score), 'queue-score'));
      return button;
    }));
    if (data.top.length) await inspect(data.top[0].gid);
  } catch (error) {
    $('summary').textContent = 'Data unavailable.';
    $('error').textContent = error.message || 'Could not connect to the local server.';
    $('error').hidden = false;
  }
})();
