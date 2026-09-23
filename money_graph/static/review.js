import {t, number, timestamp, currentLocale} from './i18n.js';

const $ = id => document.getElementById(id);
const active = review => ['queued', 'running'].includes(review?.state);
function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
}
function button(text, action, className = 'secondary') {
  const result = node('button', text, className);
  result.type = 'button'; result.addEventListener('click', action);
  return result;
}
function paragraphs(items) {
  const list = node('ul');
  list.append(...items.map(text => node('li', text)));
  return list;
}
function accountLabel(record) {
  // Evidence membership is sorted for identity; only src/dst defines transfer direction.
  const {src, dst} = record.details || {};
  return src && dst ? `${src} → ${dst}` : record.accounts?.join(', ') || '';
}
function measurements(findings) {
  const table = node('table');
  const head = node('tr');
  head.append(...['review.measurement', 'review.value', 'review.accounts'].map(key => node('th', t(key))));
  const body = node('tbody');
  for (const finding of findings) {
    const row = node('tr');
    const label = t('review.measure.' + finding.measurement);
    row.append(node('td', label.startsWith('review.measure.') ? finding.measurement : label), node('td', `${number(finding.value, {maximumFractionDigits: 6})} ${finding.unit}`),
      node('td', `${accountLabel(finding)}${finding.details?.date ? ' · ' + finding.details.date : ''}`));
    body.append(row);
  }
  const thead = node('thead'); thead.append(head); table.append(thead, body);
  const scroll = node('div', undefined, 'table-scroll'); scroll.append(table); return scroll;
}
function checkDetails(check) {
  const details = node('details');
  const target = check.arguments.gid ? ` · ${check.arguments.gid}` : '';
  details.append(node('summary', `${check.check_id}. ${t('review.check.' + check.tool)}${target}`));
  const coverage = check.result.coverage;
  details.append(node('p', t('review.checkCoverage', {
    returned: number(coverage.returned), total: number(coverage.total), omitted: number(coverage.omitted)
  })), node('pre', JSON.stringify({arguments: check.arguments, result: check.result}, null, 2)));
  return details;
}

export function createReviewPanel(graph) {
  let analysis = null, listing = null, review = null, selected = null, tab = 'findings';
  let savedGraph = null, timer = null, generation = 0, busy = false;
  let controller = new AbortController();
  const cache = new Map();
  const reason = code => {
    const label = t('review.reason.' + code);
    return label.startsWith('review.reason.') ? t('review.reason.request_failed') : label;
  };
  const root = () => `/api/analyses/${encodeURIComponent(analysis)}/reviews`;
  async function api(path, body) {
    const requestController = new AbortController();
    const abort = () => requestController.abort();
    const parent = controller;
    parent.signal.addEventListener('abort', abort, {once: true});
    const timeout = setTimeout(abort, 15000);
    try {
      const response = await fetch(path, {signal: requestController.signal,
        ...(body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error_code || 'request_failed');
      return result;
    } finally {
      clearTimeout(timeout); parent.signal.removeEventListener('abort', abort);
    }
  }
  function error(value) {
    $('review-error').textContent = t('review.error', {reason: reason(value?.message || 'request_failed')});
    $('review-error').hidden = false;
  }
  function closeInvestigation(restore = true) {
    if (savedGraph && restore) graph.restoreGraph(savedGraph);
    savedGraph = null; selected = null;
    $('investigation-panel').hidden = true;
  }
  async function refresh(version = generation) {
    try {
      const data = await api(root());
      if (version !== generation) return;
      listing = data;
      const id = listing.reviews.some(r => r.review_id === review?.review_id) ? review.review_id : listing.reviews[0]?.review_id;
      if (id) await loadReview(id, version);
      else render();
    } catch (failure) { if (version === generation) error(failure); }
  }
  async function loadReview(id, version = generation) {
    clearTimeout(timer);
    try {
      const data = await api(`${root()}/${id}`);
      if (version !== generation) return;
      review = data;
      if (listing) listing.reviews = [data, ...listing.reviews.filter(r => r.review_id !== id)].sort((a, b) => b.created_at.localeCompare(a.created_at));
      if (selected) selected = review.suggestions.find(s => s.suggestion_id === selected.suggestion_id) || null;
      render();
      if (active(review) || !review.usage_final && review.state === 'cancelled') timer = setTimeout(() => loadReview(id, version), 800);
    } catch (failure) {
      if (version !== generation) return;
      error(failure);
      if (active(review)) timer = setTimeout(() => loadReview(id, version), 2500);
    }
  }
  function selectAnalysis(id) {
    if (analysis === id) return;
    if (analysis && listing) cache.set(analysis, {listing, review});
    generation++; controller.abort(); controller = new AbortController(); clearTimeout(timer);
    closeInvestigation(); $('brief-dialog').close();
    analysis = id; listing = cache.get(id)?.listing || null; review = cache.get(id)?.review || null; busy = false;
    $('review-area').hidden = !id; $('review-error').hidden = true;
    render();
    if (id && !listing) refresh();
    else if (id && active(review)) loadReview(review.review_id);
  }
  async function start() {
    if (busy || !listing || active(review)) return;
    const version = generation;
    busy = true; $('review-error').hidden = true; render();
    try {
      const data = await api(root(), {snapshot_id: listing.snapshot_id, locale: currentLocale()});
      if (version !== generation) return;
      closeInvestigation(); review = data;
      listing.reviews = [data, ...listing.reviews.filter(r => r.review_id !== data.review_id)];
      await loadReview(data.review_id, version);
    } catch (failure) { if (version === generation) { error(failure); await refresh(version); } }
    finally { if (version === generation) { busy = false; render(); } }
  }
  async function openSuggestion(suggestion) {
    const version = generation, reviewId = review.review_id;
    try {
      const data = await api(`${root()}/${reviewId}/graph/${suggestion.suggestion_id}`);
      if (version !== generation || review?.review_id !== reviewId) return;
      if (!savedGraph) savedGraph = graph.captureGraph();
      selected = suggestion; tab = 'findings'; graph.showGraph(data); renderPanel();
      $('investigation-title').scrollIntoView({block: 'nearest'});
    } catch (failure) { if (version === generation) error(failure); }
  }
  function renderPanel() {
    $('investigation-panel').hidden = !selected;
    if (!selected || !review) return;
    $('investigation-title').textContent = selected.title;
    $('review-follow-up').textContent = t(selected.follow_up ? 'review.marked' : 'review.followUp');
    $('review-follow-up').setAttribute('aria-pressed', String(selected.follow_up));
    for (const name of ['findings', 'checks', 'evidence']) $('tab-' + name).setAttribute('aria-pressed', String(tab === name));
    const content = $('investigation-content'); content.replaceChildren();
    if (tab === 'findings') {
      content.append(node('p', selected.reason), measurements(selected.findings), node('h3', t('review.nextStep')),
        node('p', selected.next_step), node('h3', t('review.limitations')), paragraphs(selected.limitations));
    } else if (tab === 'checks') {
      for (const check of review.checks.filter(c => selected.check_ids.includes(c.check_id))) {
        content.append(checkDetails(check));
      }
    } else {
      for (const ref of selected.evidence_refs) {
        const evidence = review.evidence[ref];
        const section = node('section', undefined, 'evidence-card');
        section.append(node('h3', `${evidence.kind} · ${accountLabel(evidence)}`),
          measurements(Object.entries(evidence.measurements).map(([measurement, metric]) => ({measurement, ...metric, accounts: evidence.accounts, details: evidence.details}))),
          node('p', ref, 'evidence-reference'));
        const details = node('details'); details.append(node('summary', t('review.source')), node('pre', JSON.stringify(evidence.details, null, 2)));
        section.append(details); content.append(section);
      }
    }
  }
  function openBrief(brief) {
    const s = brief.suggestion, content = $('brief-content');
    content.replaceChildren(node('h3', s.title), node('p', s.reason), measurements(s.findings),
      node('h3', t('review.nextStep')), node('p', s.next_step), node('h3', t('review.limitations')), paragraphs(s.limitations),
      node('p', `${timestamp(brief.created_at)} · ${brief.provenance.model}`),
      node('p', `${t('review.snapshot')}: ${brief.snapshot_id}`, 'evidence-reference'));
    const details = node('details');
    details.append(node('summary', t('review.evidence')), node('pre', JSON.stringify({evidence: brief.evidence, checks: brief.checks, coverage: brief.coverage, provenance: brief.provenance}, null, 2)));
    content.append(details); $('brief-dialog').showModal();
  }
  function render() {
    if (!analysis) return;
    const enabled = listing?.availability.enabled;
    $('review-start').disabled = busy || !enabled || active(review);
    $('review-availability').textContent = listing ? (enabled ? t('review.enabled', {model: listing.availability.model, budget: number(listing.availability.max_usd)}) : t('review.disabled')) : t('review.loading');
    if (listing?.capabilities?.daily_activity === false) $('review-availability').textContent += ' ' + t('review.legacyDaily');
    const options = listing?.reviews.map(r => {
      const option = node('option', `${timestamp(r.created_at)} · ${t('review.state.' + r.state)}`);
      option.value = r.review_id; return option;
    }) || [];
    $('review-history').replaceChildren(...options); $('review-history').disabled = !options.length;
    if (review) $('review-history').value = review.review_id;
    $('review-cancel').hidden = !active(review);
    const coverage = review?.coverage || {};
    $('review-progress').textContent = review ? `${t('review.state.' + review.state)} · ${t('review.coverage', {
      scanned: number(coverage.accounts_scanned || 0), found: number(coverage.candidates_found || 0), examined: number(coverage.candidates_examined || 0)})}` +
      (review.stop_reason && review.stop_reason !== 'finished' ? ` · ${t('review.stop')}: ${reason(review.stop_reason)}` : '') +
      (review.usage?.cost_usd !== undefined ? ` · ${t('review.cost')}: $${number(review.usage.cost_usd, {maximumFractionDigits: 4})}` : '') : t('review.notStarted');
    const cards = (review?.suggestions || []).map(s => {
      const card = button('', () => openSuggestion(s), 'suggestion-card'); card.dataset.suggestionId = s.suggestion_id;
      card.append(node('span', t(s.disposition === 'investigate' ? 'review.suggestion' : 'review.insufficient'), 'eyebrow'), node('strong', s.title), node('span', s.reason),
        node('small', s.follow_up ? t('review.marked') : t('review.open'))); return card;
    });
    if (review && !cards.length && !active(review)) cards.push(node('p', t('review.noSuggestions'), 'muted'));
    $('review-suggestions').replaceChildren(...cards);
    const checks = review?.checks || [];
    if (checks.length) {
      const details = node('details'); details.append(node('summary', `${t('review.allChecks')} (${number(checks.length)})`),
        ...checks.map(checkDetails)); $('review-suggestions').append(details);
    }
    if (review?.failed_checks?.length) {
      const failures = node('details'); failures.append(node('summary', t('review.failedChecks')),
        paragraphs(review.failed_checks.map(check => `${check.tool?.replaceAll('_', ' ')}: ${check.error}`)));
      $('review-suggestions').append(failures);
    }
    if (review?.usage?.uncertain_usd) $('review-suggestions').append(node('p', t('review.uncertainCost', {amount: number(review.usage.uncertain_usd, {maximumFractionDigits: 4})}), 'warning'));
    $('review-briefs').replaceChildren(...(listing?.briefs || []).map(b => button(`${t('review.brief')}: ${b.suggestion.title}`, () => openBrief(b))));
    renderPanel();
  }
  $('review-start').addEventListener('click', start);
  $('review-cancel').addEventListener('click', async () => {
    const version = generation, id = review?.review_id; if (!id) return;
    try { await api(`${root()}/${id}/cancel`, {}); if (version === generation) await loadReview(id, version); }
    catch (failure) { if (version === generation) error(failure); }
  });
  $('review-history').addEventListener('change', () => { closeInvestigation(); loadReview($('review-history').value); });
  $('investigation-close').addEventListener('click', () => closeInvestigation());
  for (const name of ['findings', 'checks', 'evidence']) $('tab-' + name).addEventListener('click', () => { tab = name; renderPanel(); });
  $('review-follow-up').addEventListener('click', async () => {
    if (!selected) return;
    const version = generation, id = review.review_id;
    try { await api(`${root()}/${id}/follow-up`, {suggestion_id: selected.suggestion_id, marked: !selected.follow_up});
      if (version === generation) await loadReview(id, version); }
    catch (failure) { if (version === generation) error(failure); }
  });
  $('review-brief').addEventListener('click', async () => {
    if (!selected) return;
    const version = generation;
    try { const brief = await api(`${root()}/${review.review_id}/briefs`, {suggestion_id: selected.suggestion_id});
      if (version !== generation) return;
      listing.briefs = [brief, ...listing.briefs.filter(b => b.brief_id !== brief.brief_id)]; render(); openBrief(brief); }
    catch (failure) { if (version === generation) error(failure); }
  });
  $('brief-close').addEventListener('click', () => $('brief-dialog').close());
  return {selectAnalysis, render};
}
