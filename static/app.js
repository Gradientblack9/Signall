'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = u => /^(https?:\/\/|\/api\/)/.test(u || '') ? esc(u) : '#';
const date = d => d ? new Date(d).toLocaleDateString(undefined, {day:'numeric', month:'short'}) : 'Not yet';
const stamp = d => d ? new Date(d).toLocaleString(undefined, {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'}) : 'Not scheduled';
const tag = (text, color = '') => `<span class="tag ${color}">${esc(text)}</span>`;
const pct = n => Math.round(Number(n || 0) * 100);
const titles = {overview:'Overview',company:'Company profile',interview:'Strategy interview',stack:'Signal stack',feed:'Intelligence feed',brief:'Monday brief',actions:'Action tracker',automation:'Automation & settings'};
let state = {companies:[], cid:Number(localStorage.getItem('signal-company')) || null, page:'overview', company:null, signals:[], sources:[], actions:[], activeBrief:null, jobs:new Set(), render:0};
let token = sessionStorage.getItem('signal-token') || '';

async function api(path, options = {}) {
  const headers = {...(token ? {'Authorization':`Bearer ${token}`} : {}), ...options.headers};
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  const response = await fetch('/api' + path, {...options, headers});
  if (!response.ok) {
    let body; try { body = await response.json(); } catch { body = {detail:'The server returned an unexpected response.'}; }
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    throw new Error(response.status === 401 ? 'Access token required. Use the Access token button in the sidebar.' : detail || 'Request failed');
  }
  return response.json();
}
const base = () => `/companies/${state.cid}`;
function toast(text, error = false) {
  const el = document.createElement('div'); el.className = 'toast' + (error ? ' error' : ''); el.textContent = text;
  $('#toasts').append(el); setTimeout(() => el.remove(), error ? 12000 : 6500);
}
function modal(content) { $('#modal-content').innerHTML = content; if (!$('#modal').open) $('#modal').showModal(); }
function hero(title, subtitle, right = '') {
  return `<div class="hero"><div><h1>${title}</h1><p class="subtitle">${subtitle}</p></div>${right}</div>`;
}
function empty(title, text, button = '') { return `<div class="empty"><h3>${title}</h3><p>${text}</p>${button}</div>`; }
function button(text, action, secondary = false, extra = '') { return `<button class="button ${secondary ? 'secondary' : ''}" data-action="${action}" ${extra}>${text}</button>`; }
function jobButton(text, kind, secondary = false) { return button(text, 'job', secondary, `data-kind="${kind}"`); }
function statusTag(status) { return tag(status, ['failed','rejected'].includes(status) ? 'red' : ['running','queued','discovered','partial'].includes(status) ? 'orange' : ['skipped','unchecked'].includes(status) ? 'gray' : ''); }

function companyDialog() {
  modal(`<h2>Add company</h2><p class="subtitle">Enter the company name and public website.</p><form id="company-form"><div class="field"><label for="company-name">Company name</label><input id="company-name" name="name" required minlength="2" maxlength="200" placeholder="Your company name" autofocus></div><div class="field"><label for="company-url">Public company website</label><input id="company-url" name="url" type="url" required placeholder="https://yourcompany.com"><p class="help">Public pages only. Research follows robots.txt and uses your configured Gemini key.</p></div><button class="button" type="submit">Create company </button></form>`);
}

async function init() {
  try {
    state.companies = await api('/companies');
    if (!state.companies.some(c => c.id === state.cid)) state.cid = state.companies[0]?.id || null;
    updateWorkspace();
    const health = await fetch('/health').then(r => r.json());
    $('#connection').innerHTML = `${health.llm.configured ? 'Gemini configured' : 'Gemini key needed'}`;
    $('#connection').title = health.llm.note;
    await navigate();
    poll();
  } catch (error) { $('#content').innerHTML = empty('Workspace unavailable', esc(error.message), button('Set access token', 'token', true)); toast(error.message, true); }
}

function updateWorkspace() {
  const company = state.companies.find(c => c.id === state.cid);
  $('#workspace-name').textContent = company?.name || 'Your company';
  $('#company-select').innerHTML = state.companies.map(c => `<option value="${c.id}" ${c.id === state.cid ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  if (state.cid) localStorage.setItem('signal-company', state.cid);
}

async function navigate() {
  const page = location.hash.slice(1).split('?')[0] || 'overview';
  state.page = titles[page] ? page : 'overview';
  $$('#company-select').forEach(el => el.hidden = true);
  $$('nav a').forEach(a => { a.classList.toggle('active', a.dataset.page === state.page); if (a.dataset.page === state.page) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
  $('#page-label').textContent = titles[state.page]; document.title = `${titles[state.page]} — Signal Stack`;
  $('.sidebar').classList.remove('open');
  const renderId = ++state.render;
  if (!state.cid) {
    $('#content').innerHTML = hero('Overview', 'Set up a company to get started.') + `<div class="card">${empty('No company added', 'Add a company name and website to begin.', button('Add company', 'company-dialog'))}</div>`;
    return;
  }
  $('#content').innerHTML = '<div class="loading">Loading…</div>';
  try {
    state.company = await api(base());
    const html = await pages[state.page]();
    if (renderId === state.render) $('#content').innerHTML = html;
  } catch (error) { if (renderId === state.render) $('#content').innerHTML = `<div class="card">${empty('Something needs attention.', esc(error.message), button('Try again', 'reload', true))}</div>`; }
}

const pages = {};
pages.overview = async () => {
  const data = await api(base() + '/overview');
  const counts = data.counts;
  state.signals = data.signals;
  const answered = state.company.answers.filter(answer => answer.answer || answer.skipped).length;
  const metrics = [
    ['Approved sources', counts.approved],
    ['Evidence records', counts.documents],
    ['Signals', counts.signals],
    ['Briefs', counts.briefs],
  ];
  const steps = [
    [!!state.company.profile.summary, 'Research company', 'company'],
    [answered >= 10, `Complete interview (${answered}/10)`, 'interview'],
    [counts.approved > 0, 'Approve sources', 'stack'],
    [counts.briefs > 0, 'Generate a brief', 'brief'],
  ];
  return hero('Overview', esc(state.company.name)) +
    (!data.llm.configured ? `<div class="notice warning"><span>Gemini is not configured. Add GEMINI_API_KEY to .env and restart.</span><a class="text-link" href="#automation">Settings</a></div>` : '') +
    `<div class="metrics">${metrics.map(([label, count]) => `<div class="metric"><div class="metric-top">${label}</div><div class="metric-value">${count.toLocaleString()}</div></div>`).join('')}</div>
    <div class="grid-main">
      <section class="card"><div class="card-head"><h2>Recent signals</h2><a class="text-link" href="#feed">View all</a></div>${data.signals.length ? data.signals.map(smallSignal).join('') : empty('No signals yet', 'Approve sources, collect evidence, and run analysis.', '<a class="button secondary" href="#stack">Manage sources</a>')}</section>
      <section class="card"><div class="card-head"><h2>Setup checklist</h2></div>${steps.map(([done, label, page]) => `<div class="step"><span class="step-status">${done ? 'Done' : 'To do'}</span><a href="#${page}">${label}</a></div>`).join('')}</section>
    </div>
    <section class="card mt"><div class="card-head"><h2>Recent activity</h2><a class="text-link" href="#automation">View jobs</a></div>${data.jobs.length ? data.jobs.slice(0, 4).map(job => `<div class="activity-row"><div><b>${esc(job.kind)}: ${esc(job.status)}</b><small>${stamp(job.started_at)}${job.error ? ' - ' + esc(job.error.slice(0, 100)) : ''}</small></div></div>`).join('') : '<div class="card-body text-muted">No jobs have run yet.</div>'}</section>`;
};

function smallSignal(s) {
  return `<article class="signal-row"><div class="signal-meta">${tag(s.category)}${tag(s.evidence.verified?'Reviewed as verified':'Source-reported','gray')}${tag(s.interpretation.sentiment,s.interpretation.sentiment==='threat'?'orange':'gray')}<span>${date(s.created_at)}</span></div><h3 class="signal-title">${esc(s.interpretation.what)}</h3><div class="signal-bottom"><a href="${link(s.evidence.url)}" target="_blank" rel="noopener">${esc(s.evidence.title.slice(0,55))} </a><span class="score"><progress class="spark" value="${s.score}" max="100" aria-label="Signal score"></progress><b>${s.score}</b> score</span></div></article>`;
}

pages.company = async () => {
  const p = state.company.profile;
  const changes = await api(base()+'/context-changes');
  return hero('Company profile', 'Research the company website and review its profile.', `<div class="button-row">${jobButton(' Research website','research',true)}${p.summary?button('Edit profile','edit-profile'):''}</div>`) +
  (p.summary ? `<div class="grid-main"><section class="card"><div class="card-head"><h2>${esc(state.company.name)}</h2>${tag('Context v'+state.company.context_version,'gray')}</div><div class="card-body"><p class="profile-summary">${esc(p.summary)}</p><a class="text-link" href="${link(state.company.url)}" target="_blank" rel="noopener">${esc(state.company.url)} </a><dl class="definition"><dt>Industry</dt><dd>${esc(p.industry)}</dd><dt>Customers</dt><dd>${esc(p.customers?.join(' · '))}</dd><dt>Products</dt><dd>${esc(p.products?.join(' · '))}</dd><dt>Priorities</dt><dd>${esc(p.priorities?.join(' · '))}</dd></dl><div class="notice">Summary and classifications are AI interpretations. Only the quoted facts below are matched to retrieved text.</div><h3>Company facts</h3>${(p.facts||[]).map(f=>`<div class="fact">${tag(f.status,f.status==='assumption'?'orange':'')}<p>${esc(f.claim)}</p>${f.quote?`<blockquote>${esc(f.quote)}</blockquote><a href="${link(f.url)}" target="_blank" rel="noopener">${esc(f.url)} </a>`:''}</div>`).join('')}</div></section><aside class="side-stack"><section class="card"><div class="card-head"><h2>Competitors</h2></div><div class="card-body">${p.competitors?.length?p.competitors.map(c=>`<div class="fact"><h3>${esc(c.name)}</h3><p>${esc(c.reason)}</p>${tag('Candidate · requires review','orange')}<p><a href="${link(c.url)}" target="_blank" rel="noopener">${esc(c.url)} </a></p></div>`).join(''):'<p class="text-muted">Run source discovery to find company-specific competitors from real search results.</p>'}</div></section><div class="notice">Context changes mark sources for review. Reassessment updates source relevance and re-analyzes signals.</div>${jobButton('Reassess context ','reassess',true)}</aside></div>` : `<div class="card">${empty('No profile yet', 'Research the public website to create a source-backed profile. Gemini will label unsupported claims as assumptions.',jobButton('Research '+esc(state.company.name)+' ','research'),'')}</div>`) +
  (changes.length?`<section class="card mt"><div class="card-head"><h2>Context history</h2></div><div class="card-body">${changes.slice(0,10).map(c=>`<details class="context-diff"><summary>${stamp(c.created_at)} · ${esc(c.diff.type||'change')}</summary><pre>${esc(c.diff.patch || JSON.stringify(c.diff,null,2))}</pre></details>`).join('')}</div></section>`:'');
};

pages.interview = async () => {
  const answers = state.company.answers, done = answers.filter(a=>a.answer || a.skipped).length;
  const pending = answers.find(a=>!a.answer && !a.skipped);
  return hero('Strategy interview', 'Answer ten questions about the company. You can skip or edit answers.',jobButton('Reassess context','reassess',true)) +
  `<div class="interview-shell"><div class="panel-toolbar"><span class="text-muted">${done} of 10 questions completed</span>${tag(done===10?'Complete':'In progress','gray')}</div><progress class="progress-track" value="${done}" max="10" aria-label="Interview completion"></progress><section class="card question-card">${pending?`<div class="eyebrow">QUESTION ${String(pending.position).padStart(2,'0')} / 10</div><h2>${esc(pending.question)}</h2><form id="answer-form" data-id="${pending.id}"><label class="visually-hidden" for="answer">Your answer</label><textarea id="answer" name="answer" placeholder="Enter your answer…" maxlength="10000" required></textarea><p class="help">Be as specific as you can. You can always edit your answer later.</p><div class="button-row"><button class="button" type="submit">Save & continue </button>${button('Skip for now','skip',true,`data-id="${pending.id}"`)}</div></form>`:done>=10?empty('Interview complete', 'You can refine any answer below. Reassess your context to update source relevance and existing signals.',jobButton('Reassess context ','reassess'),''):empty(done?'Continue interview':'Start interview', 'Gemini uses the company profile and your earlier answers to ask the next relevant question.',button(done?'Get the next question ':'Begin the interview ','next-question'),'')}</section>
  ${answers.filter(a=>a.answer||a.skipped).map(a=>`<article class="card answer-card"><div class="eyebrow">QUESTION ${a.position} ${a.skipped?'· SKIPPED':''}</div><h3>${esc(a.question)}</h3><p>${esc(a.answer || 'Skipped for now.')}</p><div class="button-row">${a.answer?button('Ask a follow-up','follow-up',true,`data-id="${a.id}"`):''}</div>${a.follow_up?`<div class="follow-up"><b>Optional follow-up:</b> ${esc(a.follow_up)}<p class="help">Add your response to this question using Edit answer below.</p></div>`:''}<details class="mt"><summary>Edit answer</summary><form class="edit-answer" data-id="${a.id}"><label class="visually-hidden" for="edit-${a.id}">Edit your answer</label><textarea id="edit-${a.id}" name="answer" required maxlength="10000">${esc(a.answer)}</textarea><button class="button small secondary" type="submit">Save answer</button></form></details></article>`).join('')}</div>`;
};

pages.stack = async () => {
  state.sources = await api(base()+'/sources');
  const sources = state.sources;
  return hero('Signal stack', 'Add sources, review suggestions, and approve sources for monitoring.', `<div class="button-row">${button(' Add source','add-source',true)}${jobButton('Discover sources ','discover')}</div>`) +
  `<div class="panel-toolbar"><div class="filters"><label class="visually-hidden" for="source-category">Category</label><select id="source-category"><option value="">All channels</option>${['Customers','Competitors','Market','Internal'].map(c=>`<option>${c}</option>`).join('')}</select><label class="visually-hidden" for="source-status">Status</label><select id="source-status"><option value="">All statuses</option><option value="discovered">Needs review</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></div><div class="button-row">${tag(sources.filter(s=>s.status==='approved').length+' approved','gray')}${jobButton(' Crawl approved','crawl',true)}</div></div>
  <div class="notice"><span>Discovery scores are AI estimates. Approval controls monitoring. Every crawl checks robots.txt and records source health.</span></div><div class="source-grid" id="source-grid">${sourceCards(sources)}</div>`;
};
function sourceCards(sources) {
  return sources.length?sources.map(s=>`<article class="card source-card"><div class="source-title"><div><h3>${esc(s.name)}</h3><a class="source-url" href="${link(s.url)}" target="_blank" rel="noopener">${esc(s.url)} </a></div></div><div class="button-row">${tag(s.category)}${statusTag(s.status)}${s.stale?tag('Context review','orange'):''}${s.possible_duplicates?.length?tag('Possible duplicate domain','gray'):''}</div><p>${esc(s.reason)}</p><div class="source-scores">${[['Specificity',s.specificity],['Recency',s.recency],['Credibility',s.credibility],['Relevance',s.relevance]].map(([k,v])=>`<span>${k}<b>${pct(v)}<small>/100</small></b></span>`).join('')}</div><div class="button-row">${s.status!=='approved'?button(' Approve','source-status',false,`data-id="${s.id}" data-status="approved"`):''}${s.status!=='rejected'?button('Reject','source-status',true,`data-id="${s.id}" data-status="rejected"`):''}${button('History','source-history',true,`data-id="${s.id}"`)}${button('Remove','source-remove',true,`data-id="${s.id}"`)}</div><div class="source-health">${statusTag(s.health)} · Last checked ${stamp(s.last_checked)}${s.error?`<div class="error-inline">${esc(s.error)}</div>`:''}</div></article>`).join(''):`<div class="card">${empty('No sources yet', 'Discover public sources tailored to your company or add a source you already trust.',jobButton('Discover sources ','discover'),'')}</div>`;
}

pages.feed = async () => {
  state.signals = await api(base()+'/signals');
  return hero('Intelligence feed', 'Review signals, their sources, and analysis scores.',jobButton('Analyze evidence ','analyze')) +
  `<div class="panel-toolbar"><div class="filters" id="signal-filters"><label class="visually-hidden" for="signal-query">Search signals</label><input id="signal-query" type="search" placeholder="Search signals…"><label class="visually-hidden" for="signal-category">Channel</label><select id="signal-category"><option value="">All channels</option>${['Customers','Competitors','Market','Internal'].map(c=>`<option>${c}</option>`).join('')}</select><label class="visually-hidden" for="signal-sentiment">Sentiment</label><select id="signal-sentiment"><option value="">All types</option><option value="opportunity">Opportunities</option><option value="threat">Threats</option><option value="neutral">Neutral</option></select><label class="visually-hidden" for="signal-urgency">Urgency</label><select id="signal-urgency"><option value="">All urgency</option><option value="high">High urgency</option><option value="medium">Medium urgency</option><option value="low">Low urgency</option></select>
    <div class="filter-field"><label for="signal-competitor">Competitor</label><select id="signal-competitor"><option value="">All competitors</option>${(state.company.profile.competitors||[]).map(c=>`<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('')}</select></div>
    <div class="filter-field"><label for="signal-date-from">From date</label><input id="signal-date-from" type="date"></div>
    <div class="filter-field"><label for="signal-date-to">To date</label><input id="signal-date-to" type="date"></div>
    <div class="filter-field"><label for="signal-relevance">Minimum relevance</label><select id="signal-relevance"><option value="0">Any relevance</option><option value="0.4">40%</option><option value="0.7">70%</option><option value="0.9">90%</option></select></div>
    <div class="filter-field"><label for="signal-impact">Minimum impact</label><select id="signal-impact"><option value="0">Any impact</option><option value="0.4">40%</option><option value="0.7">70%</option><option value="0.9">90%</option></select></div>
    <div class="filter-field"><label for="signal-verification">Verification status</label><select id="signal-verification"><option value="">All statuses</option><option value="unverified">Source-reported</option><option value="verified">Reviewed as verified</option><option value="quote_matched">Quote matched</option></select></div>
    <div class="filter-field"><label for="signal-sort">Order</label><select id="signal-sort"><option value="latest">Newest first</option><option value="oldest">Oldest first</option><option value="importance">Highest importance</option></select></div>
    </div><span class="text-muted" id="signal-count">${state.signals.length} signals</span></div>
  <div class="feed-grid"><section class="card" id="signal-list">${signalCards(state.signals)}</section><aside class="card intake-card"><div class="card-head"><div><h2>Internal files</h2><p>Upload company notes or feedback.</p></div></div><div class="card-body"><form id="intake-form"><div class="upload-zone"><h3>Upload a file</h3><p>Sales notes, customer feedback,<br>lost deals and product requests.</p><label class="visually-hidden" for="intake-file">Upload internal evidence</label><input id="intake-file" type="file" name="file" accept=".csv,.xlsx,.pdf,.txt,.md" required><p>CSV, Excel, PDF or text · up to 10 MB</p></div><button class="button full-width" type="submit">Import evidence </button></form><p class="help">Files become traceable internal records. Running analysis sends extracted text to your configured LLM. Scanned PDFs need OCR first.</p><hr class="divider">${button('View collected records','documents',true)}<p class="help">Every signal must quote an excerpt that actually exists in a collected record.</p></div></aside></div>`;
};
function signalCards(signals) {
  return signals.length ? signals.map(s=>`<article class="signal-detail"><div class="signal-meta">${tag(s.category)}${tag(s.evidence.verified?'Reviewed as verified':'Source-reported','gray')}${tag(s.interpretation.sentiment,s.interpretation.sentiment==='threat'?'red':'gray')}${tag(s.interpretation.urgency+' urgency',s.interpretation.urgency==='high'?'orange':'gray')}<span class="score"><b>${s.score}</b> / 100</span></div>${s.context_version!==state.company.context_version?`<div class="notice warning">Earlier context version. Reassess before using this in a current brief.</div>`:''}<div class="eyebrow">AI INTERPRETATION</div><h3>${esc(s.interpretation.what)}</h3><p>${esc(s.interpretation.why_it_matters)}</p><div class="eyebrow mt">MATCHED EVIDENCE</div><blockquote>${esc(s.evidence.quote)}</blockquote><a class="text-link" href="${link(s.evidence.url)}" target="_blank" rel="noopener">${esc(s.evidence.title)} </a><p class="help">Published ${s.evidence.published_at?date(s.evidence.published_at):'date unknown'} · Discovered ${date(s.evidence.discovered_at)} · Quote matched to retrieved text; claim not independently corroborated.</p><details><summary>Why this ranks here · ${esc(s.interpretation.business_area)}</summary><div class="factor-grid">${Object.entries(s.factors).map(([k,v])=>`<div class="factor">${esc(k)}<b>${pct(v)} / 100</b></div>`).join('')}</div><p>${esc(s.explanation)}</p><p>Source reliability ${pct(s.reliability)}% · Evidence strength ${pct(s.evidence_strength)}% · Strategic relevance ${pct(s.strategic_relevance)}%</p>${s.category==='Internal'?`<p>Internal classification: ${esc(s.interpretation.internal_type)}</p>`:''}</details><div class="button-row">${button(' Track suggested action','signal-action',true,`data-id="${s.id}"`)}</div><p class="help">Suggested action (AI): ${esc(s.interpretation.suggested_action)}</p><p class="help">Suggested owner (role): ${esc(s.interpretation.suggested_owner||'Unassigned')} · ${s.interpretation.is_development===false?'Background context':'Reported development'}</p></article>`).join('') : empty('No signals in this view yet.', 'Collect public or internal evidence, then run analysis. Signals without a matching evidence excerpt are rejected.',jobButton('Analyze collected evidence ','analyze'),'');
}

function briefDetails(item) {
  const fields = {impact:'Impact (AI, /100)',priority:'Priority',urgency:'Urgency',next_step:'Next step (AI)',suggested_owner:'Suggested owner (role)',original_source:'Original source',published_at:'Published',discovered_at:'Discovered',freshness:'Freshness',verification:'Verification'};
  return '<dl class="brief-details">'+Object.entries(fields).filter(([key])=>key in item).map(([key,label])=>`<dt>${label}</dt><dd>${esc(item[key]??'Unknown')}</dd>`).join('')+'</dl>';
}

pages.brief = async () => {
  const briefs = await api(base()+'/briefs');
  let selected = briefs.find(b=>b.id===state.activeBrief) || briefs[0];
  const brief = selected ? await api(base()+`/briefs/${selected.id}`) : null;
  state.activeBrief = brief?.id || null;
  return hero('Monday brief', 'Generate a weekly brief and download previous briefs.',`<div class="button-row">${jobButton('Run weekly pipeline','weekly',true)}${jobButton('Generate brief ','brief')}</div>`) +
  (brief?`<div class="brief-layout"><aside class="brief-list">${briefs.map(b=>`<button data-action="select-brief" data-id="${b.id}" class="${b.id===brief.id?'active':''}"><b>${esc(b.title)}</b><small>${stamp(b.created_at)} · Context ${b.context_version}</small></button>`).join('')}</aside><article class="card brief-document"><h2>${esc(brief.title)}</h2><p class="text-muted">${stamp(brief.created_at)} · Last 7 days · Context version ${brief.context_version}</p><div class="button-row">${['md','html','pdf'].map(f=>button(' '+f.toUpperCase(),'export',true,`data-id="${brief.id}" data-format="${f}"`)).join('')}</div>${brief.context_version!==state.company.context_version?'<div class="notice warning mt">This saved brief reflects an earlier profile. Generate a new brief after reassessment for the current context.</div>':''}${brief.sections.map((section,i)=>`<section class="brief-section"><h2><span class="inline-count">${String(i+1).padStart(2,'0')} /</span> ${esc(section.title)}</h2>${section.note?`<p class="text-muted">${esc(section.note)}</p>`:''}${section.items.map(item=>`<div class="brief-item"><div class="eyebrow">${item.kind==='source_appendix'?'SOURCE RECORD':'AI INTERPRETATION'} · SCORE ${item.score}</div><p>${esc(item.text)}</p><blockquote><b>Evidence:</b> ${esc(item.evidence)}</blockquote><a href="${link(item.url)}" target="_blank" rel="noopener">View evidence </a><p class="help">Why it matters (AI): ${esc(item.why)}</p>${briefDetails(item)}${button(' Track action','brief-action',true,`data-id="${item.signal_id}"`)}</div>`).join('')}</section>`).join('')}</article></div>`:`<div class="card">${empty('No briefs yet', 'Collect and analyze evidence, then generate your first executive brief. Empty categories are stated explicitly.',jobButton('Generate your first brief ','brief'),'')}</div>`);
};

pages.actions = async () => {
  state.actions = await api(base()+'/actions');
  const groups=[['open','Open'],['in_progress','In progress'],['done','Completed']];
  return hero('Action tracker', 'Keep track of tasks, owners, due dates, and progress.',button(' Add action','add-action')) +
  `<div class="action-board">${groups.map(([status,title])=>`<section class="action-column"><h2>${title}<span>${state.actions.filter(a=>a.status===status).length}</span></h2>${state.actions.filter(a=>a.status===status).map(a=>`<article class="action-tile"><h3>${esc(a.title)}</h3><p>${esc(a.owner || 'Unassigned')}${a.due_date?' · Due '+esc(a.due_date):''}</p>${a.signal_id?`<span class="tag gray">From signal #${a.signal_id}</span>`:''}<label class="visually-hidden" for="action-${a.id}">Action status</label><select class="action-status" id="action-${a.id}" data-id="${a.id}">${['open','in_progress','done','dismissed'].map(s=>`<option value="${s}" ${a.status===s?'selected':''}>${s.replace('_',' ')}</option>`).join('')}</select><button class="button small ghost mt" data-action="edit-action" data-id="${a.id}">Edit details </button></article>`).join('') || '<p class="text-muted">No actions.</p>'}</section>`).join('')}</div>${state.actions.some(a=>a.status==='dismissed')?`<details class="context-diff"><summary>Dismissed actions (${state.actions.filter(a=>a.status==='dismissed').length})</summary>${state.actions.filter(a=>a.status==='dismissed').map(a=>`<div class="action-tile"><h3>${esc(a.title)}</h3>${button('Edit / reopen','edit-action',true,`data-id="${a.id}"`)}</div>`).join('')}</details>`:''}`;
};

pages.automation = async () => {
  const [settings,data,health] = await Promise.all([api(base()+'/settings'),api(base()+'/jobs'),fetch('/health').then(r=>r.json())]);
  return hero('Automation & settings', 'Manage schedules, run jobs, and check their results.') +
  `<div class="settings-grid"><section class="card"><div class="card-head"><h2>Schedule settings</h2>${tag(health.scheduler?'Scheduler active':'Scheduler off',health.scheduler?'':'orange')}</div><div class="card-body"><form id="settings-form"><div class="form-grid"><div><label for="timezone">Timezone</label><input name="timezone" id="timezone" value="${esc(settings.timezone)}" required placeholder="Asia/Kolkata"></div><div><label for="brief-day">Brief day</label><select id="brief-day" name="brief_day">${['mon','tue','wed','thu','fri','sat','sun'].map(d=>`<option value="${d}" ${d===settings.brief_day?'selected':''}>${d.toUpperCase()}</option>`).join('')}</select></div><div><label for="brief-time">Briefing time</label><input type="time" name="brief_time" id="brief-time" value="${esc(settings.brief_time)}" required></div><div><label for="audit-day">Monthly audit day</label><input type="number" name="audit_day" id="audit-day" min="1" max="28" value="${settings.audit_day}" required></div><div><label for="crawl-hours">Crawl every (hours)</label><input type="number" name="crawl_hours" id="crawl-hours" min="1" max="720" value="${settings.crawl_hours}" required></div><div><label for="refresh-days">Discovery refresh (days)</label><input type="number" name="refresh_days" id="refresh-days" min="1" max="365" value="${settings.refresh_days}" required></div><div><label for="request-delay">Request spacing (seconds)</label><input type="number" name="request_delay" id="request-delay" min="1" max="30" step="0.5" value="${settings.request_delay}" required></div><div><label for="max-sources">Sources per crawl</label><input type="number" name="max_sources_per_run" id="max-sources" min="1" max="100" value="${settings.max_sources_per_run}" required></div></div><p class="help">Scheduled jobs run while the app is running. Keep one server worker active. Missed runs during downtime do not replay.</p><button class="button mt" type="submit">Save settings</button></form></div></section>
  <aside class="side-stack"><section class="card"><div class="card-head"><h2>LLM connection</h2>${tag(health.llm.provider,'gray')}</div><div class="card-body"><h3>${esc(health.llm.model)}</h3><p class="text-muted">${esc(health.llm.note)}</p><p class="help">Copy .env.example to .env. Set GEMINI_API_KEY locally, then restart. Keys are read on the server and never sent to this dashboard.</p>${button('Test connection ','test-llm',true)}<hr class="divider"><h3>Run an operation</h3><div class="button-row mt">${jobButton('Weekly pipeline','weekly',true)}${jobButton('Source audit','audit',true)}${jobButton('Refresh discovery','refresh',true)}${jobButton('Reassess context','reassess',true)}</div></div></section><section class="card"><div class="card-head"><h2>Next scheduled runs</h2></div><div class="card-body">${data.schedules.length?data.schedules.map(s=>`<div class="schedule"><b>${esc(s.id.split(':')[1])}</b><span>${stamp(s.next_run)}</span></div>`).join(''):'<p class="text-muted">No schedules active. Enable SIGNAL_SCHEDULER and restart.</p>'}</div></section></aside></div>
  <section class="card job-list"><div class="card-head"><div><h2>Job history</h2><p>Failures, limitations and partial results stay visible.</p></div>${button(' Refresh','reload',true)}</div>${data.logs.length?data.logs.map(j=>`<div class="job-row"><div>${statusTag(j.status)}</div><div><b>${esc(j.kind)}</b><p><small>${stamp(j.started_at)}</small></p></div><div>${j.error?`<p class="error-inline">${esc(j.error)}</p>`:''}${j.result?`<details><summary>View results and limitations</summary><pre>${esc(JSON.stringify(j.result,null,2))}</pre></details>`:j.status==='running'||j.status==='queued'?'<span class="text-muted">Working in the background…</span>':''}</div></div>`).join(''):empty('No jobs yet', 'Run research, a crawl or a brief. Each job leaves a traceable outcome.','','')}</section>`;
};

function sourceDialog() {
  modal(`<h2>Add source</h2><p class="subtitle">New sources enter review. Approve one to start monitoring.</p><form id="source-form"><div class="field"><label for="source-name">Source name</label><input name="name" id="source-name" required maxlength="200" placeholder="Publication, community, company…"></div><div class="field"><label for="source-url">Public URL or RSS feed</label><input name="url" id="source-url" type="url" required placeholder="https://…"></div><div class="field"><label for="source-channel">Channel</label><select name="category" id="source-channel">${['Customers','Competitors','Market','Internal'].map(c=>`<option>${c}</option>`).join('')}</select></div><div class="field"><label for="source-reason">Reason for adding this source</label><textarea name="reason" id="source-reason" required maxlength="2000" placeholder="Explain why the source is relevant"></textarea></div><button class="button" type="submit">Add to review </button></form>`);
}
function actionDialog(action = {}, signal) {
  modal(`<h2>${action.id?'Edit action':'Add action'}</h2><p class="subtitle">Enter the task details below.</p><form id="action-form" data-id="${action.id||''}" data-signal="${action.signal_id||signal?.id||''}"><div class="field"><label for="action-title">Action</label><textarea name="title" id="action-title" required maxlength="1000">${esc(action.title||signal?.interpretation.suggested_action||'')}</textarea></div><div class="form-grid"><div class="field"><label for="action-owner">Owner</label><input name="owner" id="action-owner" maxlength="200" value="${esc(action.owner||'')}" placeholder="Owner name"></div><div class="field"><label for="action-due">Due date</label><input type="date" name="due_date" id="action-due" value="${esc(action.due_date||'')}"></div></div><div class="field"><label for="action-state">Status</label><select name="status" id="action-state">${['open','in_progress','done','dismissed'].map(s=>`<option value="${s}" ${s===(action.status||'open')?'selected':''}>${s.replace('_',' ')}</option>`).join('')}</select></div><button class="button" type="submit">Save action </button></form>`);
}

async function startJob(kind) {
  const job = await api(base()+`/jobs/${kind}`, {method:'POST'});
  if (job.status==='skipped') { toast('Another job is already active for this company. Check Automation for its progress.',true); return; }
  state.jobs.add(`${state.cid}:${job.job_id}`);
  toast(`${kind.charAt(0).toUpperCase()+kind.slice(1)} started. You can keep exploring; its result will appear in Automation.`);
  if (state.page==='automation') await navigate();
}
async function poll() {
  try {
    if (state.cid) {
      const data = await api(base()+'/jobs');
      let finished = false;
      for (const j of data.logs) {
        const key=`${state.cid}:${j.id}`;
        if (['running','queued'].includes(j.status)) state.jobs.add(key);
        else if (state.jobs.has(key)) {
          state.jobs.delete(key); finished=true;
          toast(`${j.kind}: ${j.status}${j.error?' — '+j.error:j.status==='partial'?' — check Automation for limitations.':'.'}`,j.status==='failed');
        }
      }
      if (finished && !$('#modal').open && !$('textarea:focus, input:focus, select:focus')) await navigate();
      const active=data.logs.some(j=>['running','queued'].includes(j.status));
      $('#connection').innerHTML=active?'Intelligence at work':`${$('#connection').title.includes('Add GEMINI')?'Gemini key needed':'Engine ready'}`;
    }
  } catch { /* Foreground actions display connectivity errors. Polling resumes automatically. */ }
  setTimeout(poll, state.jobs.size ? 2500 : 10000);
}

document.addEventListener('click', async event => {
  const evidenceLink = event.target.closest('a[href^="/api/companies/"]');
  if (evidenceLink) {
    event.preventDefault();
    try { const data = await api(evidenceLink.getAttribute('href').split('#')[0].slice(4));
      modal(`<h2>Internal evidence.</h2><p class="subtitle">Extracted original text, retained in this workspace.</p>${data.records.map(r=>`<article class="fact"><h3>${esc(r.title)}</h3><p>${esc(r.content)}</p></article>`).join('')}`);
    } catch(error) {toast(error.message,true);}
    return;
  }
  const target = event.target.closest('[data-action]'); if (!target) return;
  const action=target.dataset.action, id=Number(target.dataset.id);
  target.disabled=true;
  try {
    if (action==='company-dialog') companyDialog();
    else if (action==='reload') await navigate();
    else if (action==='token') tokenDialog();
    else if (action==='job') await startJob(target.dataset.kind);
    else if (action==='next-question') { await api(base()+'/interview/next',{method:'POST'}); await navigate(); }
    else if (action==='skip') { await api(base()+`/interview/${id}`,{method:'PUT',body:{skipped:true,answer:''}}); try {await api(base()+'/interview/next',{method:'POST'});} catch(error) {toast('Question skipped. Next question: '+error.message,true);} await navigate(); }
    else if (action==='follow-up') { const r=await api(base()+`/interview/${id}/follow-up`,{method:'POST'}); toast('Follow-up ready. Add your response using Edit answer.'); await navigate(); }
    else if (action==='add-source') sourceDialog();
    else if (action==='source-status') { await api(base()+`/sources/${id}`,{method:'PATCH',body:{status:target.dataset.status}}); await navigate(); }
    else if (action==='source-remove') { await api(base()+`/sources/${id}`,{method:'DELETE'}); toast('Source removed. Collected evidence is retained.'); await navigate(); }
    else if (action==='source-history') { const history=await api(base()+`/sources/${id}/history`); modal(`<h2>Source history.</h2><p class="subtitle">A trace of every monitoring attempt.</p>${history.length?history.map(h=>`<div class="fact">${statusTag(h.status)}<p>${stamp(h.started_at)} · ${h.records} new records</p><p>${esc(h.detail)}</p></div>`).join(''):'<p class="text-muted">This source has not been crawled yet.</p>'}`); }
    else if (action==='signal-action' || action==='brief-action') { let signal=state.signals.find(s=>s.id===id); if (!signal) {const list=await api(base()+'/signals'); signal=list.find(s=>s.id===id);} actionDialog({},signal); }
    else if (action==='add-action') actionDialog();
    else if (action==='edit-action') actionDialog(state.actions.find(a=>a.id===id));
    else if (action==='select-brief') {state.activeBrief=id; await navigate();}
    else if (action==='test-llm') { await api('/llm/test',{method:'POST'}); toast('Gemini connection verified. Structured JSON received.'); }
    else if (action==='export') {
      const response=await fetch('/api'+base()+`/briefs/${id}/export/${target.dataset.format}`,{headers:token?{'Authorization':`Bearer ${token}`}:{}});
      if (!response.ok) throw new Error('Export failed. Check your access token or the server log.');
      const blob=await response.blob(), url=URL.createObjectURL(blob), a=document.createElement('a');
      a.href=url; a.download=`signal-brief-${id}.${target.dataset.format}`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),5000);
    }
    else if (action==='edit-profile') {
      const p=state.company.profile;
      modal(`<h2>Edit company profile</h2><p class="subtitle">Editing creates a new context version and starts reassessment. New fact claims remain assumptions until researched.</p><form id="profile-form"><div class="field"><label for="profile-summary">Company summary</label><textarea id="profile-summary" name="summary" required>${esc(p.summary)}</textarea></div><div class="field"><label for="profile-industry">Industry</label><input id="profile-industry" name="industry" value="${esc(p.industry)}" required></div>${['customers','products','priorities'].map(k=>`<div class="field"><label for="profile-${k}">${k.charAt(0).toUpperCase()+k.slice(1)} (one per line)</label><textarea name="${k}" id="profile-${k}">${esc((p[k]||[]).join('\n'))}</textarea></div>`).join('')}<button class="button" type="submit">Save & reassess context </button></form>`);
    }
    else if (action==='documents') {
      const docs=await api(base()+'/documents');
      modal(`<h2>Collected records</h2><p class="subtitle">${docs.length} recent records. Original links stay attached.</p>${docs.map(d=>`<article class="fact">${tag(d.kind,'gray')} ${d.previous_id?tag('Changed record','orange'):''}<h3>${esc(d.title)}</h3><p>${esc(d.snippet)}</p><a href="${link(d.url)}" target="_blank" rel="noopener">View source </a><p class="help">Discovered ${stamp(d.discovered_at)}${d.published_at?' · Published '+date(d.published_at):' · Publication date unknown'}</p></article>`).join('')||'<p class="text-muted">No evidence collected yet.</p>'}`);
    }
  } catch(error) {toast(error.message,true);} finally {target.disabled=false;}
});

document.addEventListener('submit', async event => {
  const form=event.target; if (!(form instanceof HTMLFormElement)) return;
  event.preventDefault(); const submit=$('[type="submit"]',form); if(submit)submit.disabled=true;
  const values=Object.fromEntries(new FormData(form));
  try {
    if (form.id==='company-form') {
      const company=await api('/companies',{method:'POST',body:values}); state.cid=company.id;
      state.companies=await api('/companies'); state.activeBrief=null; updateWorkspace(); $('#modal').close();
      location.hash='company'; await navigate(); toast('Company created. Research its website to build the profile.');
    } else if (form.id==='source-form') { const result=await api(base()+'/sources',{method:'POST',body:values}); $('#modal').close(); toast(result.duplicate?'That URL is already in your stack.':'Source added for review.'); await navigate(); }
    else if (form.id==='answer-form' || form.classList.contains('edit-answer')) {
      await api(base()+`/interview/${form.dataset.id}`,{method:'PUT',body:{answer:values.answer,skipped:false}});
      toast('Answer saved. Reassess context when your interview is ready.');
      if(form.id==='answer-form') {try {await api(base()+'/interview/next',{method:'POST'});} catch(error) {toast('Answer saved. Next question: '+error.message,true);}}
      await navigate();
    } else if (form.id==='intake-form') {const result=await api(base()+'/intake',{method:'POST',body:new FormData(form)}); toast(`${result.records} internal records imported. ${result.note}`); form.reset();}
    else if (form.id==='action-form') {
      const body={...values,signal_id:Number(form.dataset.signal)||null,due_date:values.due_date||null};
      await api(base()+'/actions'+(form.dataset.id?'/'+form.dataset.id:''),{method:form.dataset.id?'PUT':'POST',body});
      $('#modal').close();toast('Action saved.'); if(state.page==='actions')await navigate();
    } else if (form.id==='settings-form') {
      for(const k of ['crawl_hours','refresh_days','audit_day','max_sources_per_run','request_delay'])values[k]=Number(values[k]);
      await api(base()+'/settings',{method:'PUT',body:values}); toast('Schedule saved.');await navigate();
    } else if (form.id==='profile-form') {
      const body={...state.company.profile,...values};for(const k of ['customers','products','priorities'])body[k]=values[k].split('\n').map(s=>s.trim()).filter(Boolean);
      const result=await api(base()+'/profile',{method:'PUT',body}); $('#modal').close();state.jobs.add(`${state.cid}:${result.job.job_id}`);toast('Profile updated. Sources and signals are being reassessed.');await navigate();
    } else if (form.id==='token-form') {token=values.token;sessionStorage.setItem('signal-token',token);$('#modal').close();await init();}
  } catch(error) {toast(error.message,true);} finally {if(submit)submit.disabled=false;}
});

document.addEventListener('change', async event => {
  const el=event.target;
  if(el.id==='company-select') {state.cid=Number(el.value);state.activeBrief=null;updateWorkspace();await navigate();}
  if(el.id==='source-category'||el.id==='source-status') {const category=$('#source-category').value,status=$('#source-status').value;$('#source-grid').innerHTML=sourceCards(state.sources.filter(s=>(!category||s.category===category)&&(!status||s.status===status)));}
  if(el.closest('#signal-filters')) filterSignals();
  if(el.classList.contains('action-status')) {try {const action=state.actions.find(a=>a.id===Number(el.dataset.id));await api(base()+`/actions/${action.id}`,{method:'PUT',body:{title:action.title,owner:action.owner,due_date:action.due_date,signal_id:action.signal_id,status:el.value}});await navigate();}catch(error){toast(error.message,true);}}
});
document.addEventListener('input',event=>{if(event.target.id==='signal-query')filterSignals();});
let filterRequest = 0;
async function filterSignals() {
  const request = ++filterRequest;
  const params = new URLSearchParams();
  const fields = {q:'signal-query', category:'signal-category', sentiment:'signal-sentiment', urgency:'signal-urgency', competitor:'signal-competitor', date_from:'signal-date-from', date_to:'signal-date-to', min_relevance:'signal-relevance', min_impact:'signal-impact', verification:'signal-verification', sort:'signal-sort'};
  for (const [name,id] of Object.entries(fields)) {
    const value = $('#'+id)?.value;
    if (value) params.set(name,value);
  }
  try {
    const rows = await api(base()+'/signals?'+params);
    if (request===filterRequest && state.page==='feed') {
      state.signals=rows;
      $('#signal-list').innerHTML=signalCards(rows);
      $('#signal-count').textContent=rows.length+' signals';
    }
  } catch(error) {toast(error.message,true);}
}

function tokenDialog() {modal('<h2>Workspace access.</h2><p class="subtitle">If SIGNAL_ACCESS_TOKEN is set on the server, enter it here. It stays in this browser session.</p><form id="token-form"><div class="field"><label for="access-token">Access token</label><input type="password" id="access-token" name="token" autocomplete="off"></div><button class="button" type="submit">Connect workspace</button></form>');}
$('#new-company').addEventListener('click',companyDialog);
$('#workspace-switch').addEventListener('click',()=>{if(!state.companies.length)companyDialog();else{$('#company-select').hidden=!$('#company-select').hidden;if(!$('#company-select').hidden)$('#company-select').focus();}});
$('#close-modal').addEventListener('click',()=>$('#modal').close());
$('#token-button').addEventListener('click',tokenDialog);
$('#menu-button').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
window.addEventListener('hashchange',navigate);
init();
