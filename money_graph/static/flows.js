// Grouped flow schematic: how the network moves money, before any single account is opened.
// Groups are a presentation-only collapse of the analysed accounts; every mode totals the same KZT.
import {t, number} from './i18n.js';
import {roleColors, setRoleFilter} from './map.js';

const WIDTH = 760, HEIGHT = 430, PAD_X = 16, PAD_TOP = 40, PAD_BOTTOM = 34, BOX_W = 156, GAP = 16;
const TOP_LINKS = {role: 12, cluster: 18, depth_role: 20};
const $ = (id) => document.getElementById(id);
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

let payload = null;
let mode = 'role';
let selected = null;
let placed = new Map();
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
const compact = (value) => number(value, {notation: 'compact', maximumFractionDigits: 1});
const money = (value) => t('flows.amount', {amount: number(value, {notation: 'compact', maximumFractionDigits: 1})});

function groupName(group) {
  if (group.kind === 'role') return t('role.' + group.role);
  if (group.kind === 'depth_role') return t('flows.depthRole', {depth: number(group.depth), role: t('role.' + group.role)});
  return group.cluster_id === null ? t('flows.other') : t('community.name', {id: number(group.cluster_id)});
}

// Columns follow the money: groups that mostly pay out sit left, groups that mostly receive sit right.
// Ranking rather than fixed thresholds guarantees every column is populated.
function layout(groups) {
  const columns = groups.length <= 8 ? 3 : groups.length <= 16 ? 4 : 5;
  const ordered = [...groups].sort((a, b) => {
    const share = (g) => g.in_kzt + g.out_kzt ? g.in_kzt / (g.in_kzt + g.out_kzt) : 0.5;
    return share(a) - share(b) || b.throughput - a.throughput;
  });
  const perColumn = Math.ceil(ordered.length / columns);
  const boxWidth = Math.min(BOX_W, (WIDTH - 2 * PAD_X - (columns - 1) * 24) / columns);
  const heaviest = Math.max(1, ...groups.map(g => g.throughput));
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const step = columns > 1 ? (WIDTH - 2 * PAD_X - boxWidth) / (columns - 1) : 0;
  placed = new Map();
  for (let column = 0; column < columns; column++) {
    const slice = ordered.slice(column * perColumn, (column + 1) * perColumn);
    if (!slice.length) continue;
    const ceiling = (plotHeight - (slice.length + 1) * GAP) / slice.length;
    const heights = slice.map(g => clamp(38 + 92 * (g.throughput / heaviest), 24, Math.max(24, ceiling)));
    const total = heights.reduce((sum, h) => sum + h, 0) + (slice.length - 1) * GAP;
    let y = PAD_TOP + (plotHeight - total) / 2;
    slice.forEach((group, index) => {
      placed.set(group.id, {group, column, x: PAD_X + column * step, y, w: boxWidth, h: heights[index]});
      y += heights[index] + GAP;
    });
  }
}

function ribbon(from, to) {
  const start = {x: from.x + from.w, y: from.port};
  const end = {x: to.x, y: to.port};
  if (to.column > from.column) {
    const bend = Math.max(40, (end.x - start.x) * 0.45);
    return `M${start.x} ${start.y} C${start.x + bend} ${start.y},${end.x - bend} ${end.y},${end.x} ${end.y}`;
  }
  // Same column or a step back: bow just clear of the two boxes, never across the whole canvas,
  // so a returning flow stays readable instead of dominating the schematic.
  const above = (from.y + to.y) / 2 < HEIGHT / 2;
  const lift = above ? Math.max(10, Math.min(from.y, to.y) - 28)
                     : Math.min(HEIGHT - 10, Math.max(from.y + from.h, to.y + to.h) + 28);
  const reach = 62 + Math.max(0, start.x - end.x) * 0.3;
  const right = Math.min(WIDTH - 8, start.x + reach), left = Math.max(8, end.x - reach);
  return `M${start.x} ${start.y} C${right} ${start.y},${right} ${lift},`
       + `${(start.x + end.x) / 2} ${lift} C${left} ${lift},${left} ${end.y},${end.x} ${end.y}`;
}

export function render() {
  if (failed) $('flows-error').textContent = t('flows.unavailable');
  if (!payload) return;
  for (const button of document.querySelectorAll('.flow-mode')) {
    button.setAttribute('aria-pressed', String(button.dataset.mode === mode));
  }
  const data = payload.modes[mode];
  layout(data.groups);
  const links = data.links.slice(0, TOP_LINKS[mode]);
  const shown = links.reduce((sum, link) => sum + link.sum_kzt, 0);
  const heaviest = Math.max(1, ...links.map(link => link.sum_kzt));

  // Ribbons leave and arrive stacked by size, so the widest flow of a group is easiest to follow.
  const ports = new Map([...placed.keys()].map(id => [id, {out: 0, in: 0}]));
  const widthOf = (value) => 2 + 24 * Math.sqrt(value / heaviest);
  for (const id of placed.keys()) {
    const box = placed.get(id);
    const outgoing = links.filter(l => l.src === id).reduce((sum, l) => sum + widthOf(l.sum_kzt), 0);
    const incoming = links.filter(l => l.dst === id).reduce((sum, l) => sum + widthOf(l.sum_kzt), 0);
    box.outScale = outgoing > box.h - 6 ? (box.h - 6) / outgoing : 1;
    box.inScale = incoming > box.h - 6 ? (box.h - 6) / incoming : 1;
    box.outTop = box.y + (box.h - outgoing * box.outScale) / 2;
    box.inTop = box.y + (box.h - incoming * box.inScale) / 2;
  }
  const surface = $('flows');
  const ribbons = svg('g'), boxes = svg('g'), labels = svg('g');
  for (const link of links) {
    const from = placed.get(link.src), to = placed.get(link.dst);
    if (!from || !to) continue;
    const width = widthOf(link.sum_kzt);
    const fromPort = ports.get(link.src), toPort = ports.get(link.dst);
    from.port = from.outTop + (fromPort.out + width / 2) * from.outScale;
    to.port = to.inTop + (toPort.in + width / 2) * to.inScale;
    fromPort.out += width;
    toPort.in += width;
    const path = svg('path', {d: ribbon(from, to), class: 'ribbon',
      'data-src': link.src, 'data-dst': link.dst});
    path.style.strokeWidth = `${width.toFixed(2)}px`;
    path.style.stroke = roleColors[from.group.role];
    path.append(svg('title', {}, t('flows.tipLink', {src: groupName(from.group), dst: groupName(to.group),
      amount: money(link.sum_kzt), transfers: number(link.n_tx)})));
    ribbons.append(path);
  }
  for (const box of placed.values()) {
    const group = box.group;
    const node = svg('g', {class: box.w < 140 ? 'flow-group narrow' : 'flow-group', tabindex: '0', role: 'button', 'data-group': group.id,
      'aria-label': t('flows.tipGroup', {name: groupName(group), accounts: number(group.n_nodes)})});
    node.append(svg('rect', {x: box.x, y: box.y, width: box.w, height: box.h, rx: 7,
      fill: roleColors[group.role], 'fill-opacity': 0.16, stroke: roleColors[group.role], 'stroke-width': 1.6}));
    node.append(svg('rect', {x: box.x, y: box.y, width: 4, height: box.h, rx: 2, fill: roleColors[group.role]}));
    node.append(svg('text', {x: box.x + 12, y: box.y + 17, class: 'flow-name'}, groupName(group)));
    node.append(svg('text', {x: box.x + 12, y: box.y + 31, class: 'flow-meta'},
      t('flows.groupMeta', {accounts: number(group.n_nodes), seeds: number(group.n_seed)})));
    if (box.h >= 46) {
      node.append(svg('text', {x: box.x + 12, y: box.y + 45, class: 'flow-meta'},
        t('flows.groupFlow', {incoming: compact(group.in_kzt), outgoing: compact(group.out_kzt)})));
    }
    if (group.self_kzt > 0) {
      const cx = box.x + box.w - 15, cy = box.y + 11;
      const loop = svg('path', {d: `M${cx - 8} ${cy} a8 8 0 1 1 8 8`, class: 'self-loop'});
      loop.style.stroke = roleColors[group.role];
      node.append(loop);
      node.append(svg('title', {}, t('flows.self', {amount: money(group.self_kzt), transfers: number(group.self_tx)})));
    }
    node.addEventListener('click', () => choose(group.id));
    node.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); choose(group.id);}
    });
    boxes.append(node);
  }
  labels.append(svg('text', {x: PAD_X, y: 18, class: 'flow-axis'}, t('flows.axisOut')));
  labels.append(svg('text', {x: WIDTH - PAD_X, y: 18, 'text-anchor': 'end', class: 'flow-axis'}, t('flows.axisIn')));
  surface.replaceChildren(ribbons, boxes, labels);
  $('flows-caption').textContent = t('flows.caption', {
    links: number(links.length), total: number(data.links.length),
    share: number(100 * shown / Math.max(1, data.total_kzt), {maximumFractionDigits: 0}),
    amount: money(data.total_kzt), groups: number(data.groups.length)});
  highlight();
}

function choose(id) {
  selected = selected === id ? null : id;
  const group = payload.modes[mode].groups.find(g => g.id === id);
  // Roles are the one grouping the overview map can filter on, so selecting one carries through.
  if (selected && group && group.kind === 'role') setRoleFilter(group.role);
  else if (!selected) setRoleFilter(null);
  highlight();
}

function highlight() {
  const active = selected;
  for (const node of document.querySelectorAll('.flow-group')) {
    node.classList.toggle('selected', node.dataset.group === active);
    node.classList.toggle('dimmed', Boolean(active) && node.dataset.group !== active);
  }
  for (const path of document.querySelectorAll('.ribbon')) {
    const touches = !active || path.dataset.src === active || path.dataset.dst === active;
    path.classList.toggle('dimmed', !touches);
  }
  const detail = $('flows-detail');
  if (!active) {
    detail.textContent = t('flows.detailIdle');
    return;
  }
  const group = payload.modes[mode].groups.find(g => g.id === active);
  detail.textContent = t('flows.detail', {
    name: groupName(group), accounts: number(group.n_nodes), seeds: number(group.n_seed),
    incoming: money(group.in_kzt), outgoing: money(group.out_kzt),
    self: group.self_kzt > 0 ? t('flows.detailSelf', {amount: money(group.self_kzt)}) : ''});
}

export async function load(get) {
  try {
    payload = await get('/api/flows');
    failed = false;
    $('flows-error').hidden = true;
    render();
    return true;
  } catch (error) {
    failed = true;
    $('flows-error').hidden = false;
    $('flows-error').textContent = t('flows.unavailable');
    return false;
  }
}

export function initialize() {
  for (const button of document.querySelectorAll('.flow-mode')) {
    button.addEventListener('click', () => {
      mode = button.dataset.mode;
      selected = null;
      setRoleFilter(null);
      render();
    });
  }
}
