// Overview map: every analysed account at once, positioned so the role rules read as regions.
// Horizontal = distinct paying counterparties, vertical = distinct paid counterparties.
import {t, number} from './i18n.js';

export const roleColors = {consolidator: '#087e8b', transit: '#527bc2', distributor: '#d98839',
  terminal: '#9b5bb5', coordinator: '#c95c72', peripheral: '#93a3a1'};
export const roleOrder = ['coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral'];
// Full identifiers are 18 digits; a tail is enough to recognise one and keeps labels readable.
export const shortId = (gid) => '…' + String(gid).slice(-6);

const LEFT = 58, RIGHT = 702, TOP = 26, BOTTOM = 400;
const $ = (id) => document.getElementById(id);
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const volume = (node) => node.in_kzt + node.out_kzt;

let dataset = null;
let placed = [];
let selected = null;
let metric = 'volume';
let activeRoles = new Set();
let seedsOnly = false;
let hideBoundary = false;
let maxIn = 1, maxOut = 1, maxVolume = 1;
let select = () => {};
let failed = false;

function svg(tag, attributes = {}, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
const scaleX = (value) => LEFT + Math.log1p(value) / Math.log1p(maxIn) * (RIGHT - LEFT);
const scaleY = (value) => BOTTOM - Math.log1p(value) / Math.log1p(maxOut) * (BOTTOM - TOP);
const magnitude = (node) => metric === 'priority' ? node.priority_score : volume(node);
function radiusOf(node) {
  return metric === 'priority' ? 2 + 6.4 * node.priority_score : 2 + 6.4 * Math.sqrt(volume(node) / maxVolume);
}
function emphasised(node) {
  return (!activeRoles.size || activeRoles.has(node.role)) && (!seedsOnly || node.is_seed)
    && !(hideBoundary && node.boundary);
}
function ticks(maximum) {
  return [0, 1, 2, 3, 5, 10, 20, 50, 100, 200, 500].filter(value => value <= maximum);
}

// Many accounts share the same integer coordinates, so each cell spreads its members over a
// small disc. Phyllotaxis keeps that spread even and identical on every reload.
function layout() {
  const cells = new Map();
  for (const node of dataset.nodes) {
    const key = node.in_deg + ',' + node.out_deg;
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key).push(node);
  }
  placed = [];
  for (const cell of cells.values()) {
    cell.sort((a, b) => magnitude(b) - magnitude(a) || (a.gid < b.gid ? -1 : 1));
    const spread = Math.min(30, 3 + 2.4 * Math.sqrt(cell.length));
    cell.forEach((node, index) => {
      const distance = spread * Math.sqrt((index + 0.55) / cell.length);
      const angle = index * 2.399963229728653;
      placed.push({node,
        x: clamp(scaleX(node.in_deg) + distance * Math.cos(angle), LEFT + 2, RIGHT - 2),
        y: clamp(scaleY(node.out_deg) + distance * Math.sin(angle), TOP + 2, BOTTOM - 2)});
    });
  }
  placed.sort((a, b) => radiusOf(a.node) - radiusOf(b.node));
}

function renderChips() {
  if (!dataset) return;
  const counts = {};
  for (const node of dataset.nodes) counts[node.role] = (counts[node.role] || 0) + 1;
  const chips = roleOrder.filter(role => counts[role]).map(role => {
    const chip = element('button', undefined, 'chip');
    chip.type = 'button';
    chip.setAttribute('aria-pressed', String(activeRoles.has(role)));
    chip.style.setProperty('--chip', roleColors[role]);
    chip.append(svgDot(roleColors[role]), element('span', t('role.' + role)), element('small', number(counts[role])));
    chip.addEventListener('click', () => {
      activeRoles.has(role) ? activeRoles.delete(role) : activeRoles.add(role);
      render();
    });
    return chip;
  });
  const toggle = (label, state, apply) => {
    const chip = element('button', undefined, 'chip toggle');
    chip.type = 'button';
    chip.setAttribute('aria-pressed', String(state));
    chip.append(element('span', label));
    chip.addEventListener('click', () => {apply(); render();});
    return chip;
  };
  const all = element('button', undefined, 'chip');
  all.type = 'button';
  all.setAttribute('aria-pressed', String(!activeRoles.size));
  all.append(element('span', t('map.allRoles')), element('small', number(dataset.nodes.length)));
  all.addEventListener('click', () => {activeRoles.clear(); render();});
  $('map-filters').replaceChildren(all, ...chips,
    toggle(t('map.seedsOnly'), seedsOnly, () => {seedsOnly = !seedsOnly;}),
    toggle(t('map.hideBoundary'), hideBoundary, () => {hideBoundary = !hideBoundary;}));
}
function svgDot(fill) {
  const dot = svg('svg', {viewBox: '0 0 10 10', class: 'dot'});
  dot.append(svg('circle', {cx: 5, cy: 5, r: 4.5, fill}));
  return dot;
}

function renderAxes(target) {
  target.append(svg('line', {x1: LEFT, y1: BOTTOM, x2: RIGHT, y2: BOTTOM, class: 'axis'}));
  target.append(svg('line', {x1: LEFT, y1: TOP, x2: LEFT, y2: BOTTOM, class: 'axis'}));
  for (const value of ticks(maxIn)) {
    const x = scaleX(value);
    target.append(svg('line', {x1: x, y1: BOTTOM, x2: x, y2: TOP, class: 'grid'}));
    target.append(svg('text', {x, y: BOTTOM + 15, 'text-anchor': 'middle', class: 'tick'}, number(value)));
  }
  for (const value of ticks(maxOut)) {
    const y = scaleY(value);
    target.append(svg('line', {x1: LEFT, y1: y, x2: RIGHT, y2: y, class: 'grid'}));
    target.append(svg('text', {x: LEFT - 8, y: y + 3.5, 'text-anchor': 'end', class: 'tick'}, number(value)));
  }
  target.append(svg('text', {x: (LEFT + RIGHT) / 2, y: BOTTOM + 36, 'text-anchor': 'middle', class: 'axis-title'},
    t('map.axisIn')));
  const vertical = svg('text', {x: 14, y: (TOP + BOTTOM) / 2, 'text-anchor': 'middle', class: 'axis-title',
    transform: `rotate(-90 14 ${(TOP + BOTTOM) / 2})`}, t('map.axisOut'));
  target.append(vertical);
  // Accounts on this line pay out to as many counterparties as pay them.
  const balance = [];
  const limit = Math.min(maxIn, maxOut);
  for (let step = 0; step <= 40; step++) {
    const value = limit * step / 40;
    balance.push(`${step ? 'L' : 'M'}${scaleX(value).toFixed(1)} ${scaleY(value).toFixed(1)}`);
  }
  target.append(svg('path', {d: balance.join(' '), class: 'balance'}));
  target.append(svg('text', {x: scaleX(limit) - 4, y: scaleY(limit) - 8, 'text-anchor': 'end', class: 'zone'},
    t('map.balanced')));
  for (const [key, x, y, anchor] of [['map.zoneFanOut', LEFT + 12, TOP + 16, 'start'],
                                     ['map.zoneCollect', RIGHT - 6, BOTTOM - 74, 'end'],
                                     ['map.zoneNoOut', RIGHT - 6, BOTTOM - 8, 'end']]) {
    target.append(svg('text', {x, y, 'text-anchor': anchor, class: 'zone'}, t(key)));
  }
}

function renderLeaders(visible) {
  const top = [...visible].sort((a, b) => magnitude(b.node) - magnitude(a.node)).slice(0, 12);
  const best = top.length ? magnitude(top[0].node) : 1;
  $('map-leaders').replaceChildren(...top.map((point, index) => {
    const node = point.node;
    const item = element('li');
    const button = element('button', undefined, 'leader');
    button.type = 'button';
    button.dataset.gid = node.gid;
    button.classList.toggle('selected', node.gid === selected);
    const bar = element('span', undefined, 'leader-bar');
    bar.style.width = `${Math.max(3, 100 * magnitude(node) / (best || 1))}%`;
    bar.style.background = roleColors[node.role];
    const head = element('span', undefined, 'leader-head');
    head.append(element('span', String(index + 1), 'rank'), element('strong', shortId(node.gid)),
      element('span', t('role.' + node.role), 'leader-role'));
    const value = element('span', metric === 'priority'
      ? number(node.priority_score, {minimumFractionDigits: 3, maximumFractionDigits: 3})
      : t('map.kzt', {amount: number(volume(node), {notation: 'compact'})}), 'leader-value');
    button.append(head, value, bar);
    button.title = String(node.gid);
    button.addEventListener('click', () => select(node.gid));
    item.append(button);
    return item;
  }));
}

function showTooltip(node, event) {
  const tooltip = $('map-tooltip');
  tooltip.replaceChildren(
    element('strong', shortId(node.gid)),
    element('span', t('map.tipRole', {role: t('role.' + node.role), cluster: number(node.cluster_id)})),
    element('span', t('map.tipPeers', {incoming: number(node.in_deg), outgoing: number(node.out_deg)})),
    element('span', t('map.tipVolume', {amount: number(volume(node), {maximumFractionDigits: 0})})),
    element('span', t('map.tipPriority', {score: number(node.priority_score, {minimumFractionDigits: 3, maximumFractionDigits: 3})})));
  if (node.is_seed || node.boundary) {
    tooltip.append(element('em', node.boundary ? t('map.tipBoundary') : t('map.tipSeed')));
  }
  const box = $('map-plot-area').getBoundingClientRect();
  tooltip.hidden = false;
  const width = tooltip.offsetWidth, height = tooltip.offsetHeight;
  tooltip.style.left = `${clamp(event.clientX - box.left + 14, 4, Math.max(4, box.width - width - 4))}px`;
  tooltip.style.top = `${clamp(event.clientY - box.top - height - 12, 4, Math.max(4, box.height - height - 4))}px`;
}

export function render() {
  if (failed) $('map-error').textContent = t('map.unavailable');
  if (!dataset) return;
  renderChips();
  layout();
  const surface = $('map');
  const background = svg('g'), context = svg('g'), points = svg('g'), overlay = svg('g', {id: 'map-overlay'});
  renderAxes(background);
  let shown = 0;
  const visible = [];
  for (const point of placed) {
    const node = point.node;
    const lit = emphasised(node);
    if (lit) {shown++; visible.push(point);}
    const circle = svg('circle', {cx: point.x.toFixed(1), cy: point.y.toFixed(1),
      r: (lit ? radiusOf(node) : Math.min(2.4, radiusOf(node))).toFixed(1),
      fill: lit ? roleColors[node.role] : '#c3cfcf', 'fill-opacity': lit ? 0.82 : 0.3});
    if (lit) {
      circle.setAttribute('data-gid', node.gid);
      circle.setAttribute('class', 'point');
      if (node.is_seed) {circle.setAttribute('stroke', '#10333f'); circle.setAttribute('stroke-width', '1.3');}
      points.append(circle);
    } else {
      circle.setAttribute('class', 'point faded');
      context.append(circle);
    }
  }
  surface.replaceChildren(background, context, points, overlay);
  highlight();
  renderLeaders(visible);
  $('map-caption').textContent = t('map.caption', {shown: number(shown), total: number(dataset.nodes.length)})
    + (shown === dataset.nodes.length ? '' : ' ' + t('map.contextNote'));
}

function highlight() {
  const overlay = $('map-overlay');
  if (!overlay) return;
  const point = placed.find(item => item.node.gid === selected);
  overlay.replaceChildren();
  if (point) {
    overlay.append(svg('circle', {cx: point.x.toFixed(1), cy: point.y.toFixed(1),
      r: (radiusOf(point.node) + 7).toFixed(1), class: 'map-selected'}));
    overlay.append(svg('text', {x: clamp(point.x, LEFT + 34, RIGHT - 34).toFixed(1),
      y: clamp(point.y - radiusOf(point.node) - 12, TOP + 10, BOTTOM).toFixed(1),
      'text-anchor': 'middle', class: 'map-selected-label'}, shortId(point.node.gid)));
  }
  for (const button of document.querySelectorAll('.leader')) {
    button.classList.toggle('selected', button.dataset.gid === selected);
  }
}

// Selecting a role group in the flow schematic narrows the overview to the same accounts.
export function setRoleFilter(role) {
  activeRoles = role ? new Set([role]) : new Set();
  render();
}
export function setSelection(gid) {
  selected = gid === undefined || gid === null ? null : String(gid);
  highlight();
}

export async function load(get) {
  try {
    const data = await get('/api/map');
    maxIn = data.nodes.reduce((high, node) => Math.max(high, node.in_deg), 1);
    maxOut = data.nodes.reduce((high, node) => Math.max(high, node.out_deg), 1);
    maxVolume = data.nodes.reduce((high, node) => Math.max(high, volume(node)), 1);
    dataset = data;
    failed = false;
    $('map-error').hidden = true;
    render();
    return true;
  } catch (error) {
    failed = true;
    $('map-error').hidden = false;
    $('map-error').textContent = t('map.unavailable');
    return false;
  }
}

export function initialize(onSelect) {
  select = onSelect;
  const plot = document.querySelector('.map-plot');
  plot.id = 'map-plot-area';
  const surface = $('map');
  surface.addEventListener('pointermove', event => {
    const circle = event.target.closest('circle[data-gid]');
    if (!circle) {$('map-tooltip').hidden = true; return;}
    const point = placed.find(item => item.node.gid === circle.dataset.gid);
    if (point) showTooltip(point.node, event);
  });
  surface.addEventListener('pointerleave', () => {$('map-tooltip').hidden = true;});
  surface.addEventListener('click', event => {
    const circle = event.target.closest('circle[data-gid]');
    if (circle) select(circle.dataset.gid);
  });
  $('map-metric').addEventListener('change', () => {metric = $('map-metric').value; render();});
}
