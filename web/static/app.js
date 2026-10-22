(() => {
  'use strict';
  const USER = 'demo-user';
  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => [...root.querySelectorAll(q)];
  const sessionKey = 'roamready_session';
  let sessionId = sessionStorage.getItem(sessionKey) || '';
  let profile = null, savedTrips = [], activePlan = null, activeRescue = null, viewHtml = '', hostedDemo = false;
  const frames = new Map();

  function initJourneyMotion() {
    const story = $('.journey-story');
    const gsap = window.gsap;
    const trigger = window.ScrollTrigger;
    if (!story || !gsap || !trigger || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    gsap.registerPlugin(trigger);
    if (window.MotionPathPlugin) gsap.registerPlugin(window.MotionPathPlugin);
    gsap.fromTo('.destination-copy > *', {y:22, autoAlpha:0}, {y:0, autoAlpha:1, duration:.85, stagger:.12, ease:'power3.out', clearProps:'transform'});
    gsap.to('[data-float-ticket]', {y:-13, rotateZ:-1.2, duration:2.8, repeat:-1, yoyo:true, ease:'sine.inOut'});
    gsap.to('[data-float-icon]', {y:-9, rotateZ:8, duration:3.4, repeat:-1, yoyo:true, ease:'sine.inOut'});
    if (window.MotionPathPlugin) {
      const path = $('.hero-flight-path path');
      const plane = $('[data-flight-plane]');
      if (path && plane) gsap.to(plane, {duration:10, repeat:-1, ease:'none', motionPath:{path, align:'.hero-flight-path', autoRotate:true, alignOrigin:[.5,.5]}});
    }
    if (matchMedia('(max-width: 780px)').matches) return;
    const photo = $('[data-story-photo]');
    const cards = $$('[data-story-card]', story);
    const steps = $$('[data-story-step]', story);
    if (!photo || cards.length !== 3 || steps.length !== 3) return;

    gsap.set(cards, {autoAlpha:0, x:28, rotateY:-8, scale:.97, transformPerspective:900});
    gsap.set(cards[0], {autoAlpha:1, x:0, rotateY:-3, scale:1});
    const updateActive = progress => {
      const current = Math.min(2, Math.floor(progress * 3));
      steps.forEach((step, i) => step.classList.toggle('is-active', i === current));
    };
    const timeline = gsap.timeline({
      scrollTrigger:{
        trigger:story, start:'top top+=85', end:'bottom bottom', scrub:.7,
        onUpdate:self=>updateActive(self.progress)
      }
    });
    timeline.to(photo, {rotateY:5, rotateX:-1, rotateZ:1, x:-14, scale:1.045, ease:'none'}, .06)
      .to(cards[0], {autoAlpha:0, x:25, rotateY:9, scale:.96, ease:'none'}, .29)
      .to(cards[1], {autoAlpha:1, x:0, rotateY:0, scale:1, ease:'none'}, .31)
      .to(cards[1], {autoAlpha:0, x:25, rotateY:9, scale:.96, ease:'none'}, .61)
      .to(cards[2], {autoAlpha:1, x:0, rotateY:0, scale:1, ease:'none'}, .63);
  }

  function animatePageEntrance(page) {
    const gsap = window.gsap;
    const section = $(`#page-${page}`);
    if (!gsap || !section || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const items = $$('.page-intro,.panel,.disruption-banner,.rescue-controls,.snapshot-card,.destination-hero,.journey-story,.rescue-preview,.trip-card,.help-card', section);
    if (items.length) gsap.fromTo(items, {autoAlpha:0,y:20,rotateX:2,transformPerspective:1100}, {autoAlpha:1,y:0,rotateX:0,duration:.54,stagger:.045,ease:'power3.out',clearProps:'transform'});
  }

  function toast(message, error = false) {
    const el = $('#toast'); el.textContent = message; el.classList.toggle('toast-error', error); el.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.hidden = true; }, 4200);
  }
  function showError(id, message) { const el = $(id); el.textContent = message; el.hidden = !message; }
  async function request(url, body, options = {}) {
    const res = await fetch(url, { method: body ? 'POST' : 'GET', headers: { 'Content-Type':'application/json', ...(options.headers || {}) }, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }
  async function callTool(name, args = {}) { return request('/api/tool', { user_id: USER, name, arguments: args }); }
  function content(result) { return result?.structuredContent || {}; }
  function showPage(page) {
    const names = {overview:'Overview',planner:'Plan a trip',trips:'My trips',rescue:'Smart Rescue',preferences:'Preferences',help:'Demo & help'};
    if (!names[page]) return;
    $$('.page-section').forEach(x => { x.hidden = x.id !== `page-${page}`; x.classList.toggle('active', !x.hidden); });
    $$('[data-page]').forEach(x => x.classList.toggle('active', x.dataset.page === page));
    animatePageEntrance(page);
    $('#page-title').textContent = names[page];
    if (page === 'trips') return loadTrips();
    if (page === 'preferences') return loadProfile();
    if (page === 'overview') return loadDashboard();
    window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  async function mcp(name, args = {}) { return callTool(name,args); }

  // The embedded itinerary is the MCP App resource served by the MCP server.
  // Tool calls initiated inside it are proxied back through /api/tool.
  function mountFrame(frame, result, input = {}) {
    if (!frame || !viewHtml) return;
    frames.set(frame.contentWindow, {frame,result,input});
    frame.onload = () => {
      const target = frame.contentWindow;
      target.postMessage({jsonrpc:'2.0',method:'ui/initialize',params:{protocolVersion:'2025-11-25',hostInfo:{name:'RoamReady local web simulator',version:'1.0.0'},capabilities:{}}}, '*');
      target.postMessage({jsonrpc:'2.0',method:'ui/notifications/initialized',params:{}}, '*');
      target.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-input',params:{arguments:input.arguments || {}}}, '*');
      if (result) target.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:result}, '*');
    };
    frame.srcdoc = viewHtml;
  }
  window.addEventListener('message', async event => {
    const host = frames.get(event.source), msg = event.data;
    if (!host || !msg || typeof msg !== 'object') return;
    if (msg.method === 'ui/initialize') {
      event.source.postMessage({jsonrpc:'2.0',id:msg.id,result:{protocolVersion:'2025-11-25',hostInfo:{name:'RoamReady local web simulator',version:'1.0.0'},capabilities:{}}}, '*');
    } else if (msg.method === 'tools/call' || msg.method === 'ui/host/call-tool') {
      try {
        const p = msg.params || {}, result = await mcp(p.name, p.arguments || {});
        event.source.postMessage({jsonrpc:'2.0',id:msg.id,result}, '*');
        if (content(result).kind) host.result = result;
      } catch (err) { event.source.postMessage({jsonrpc:'2.0',id:msg.id,error:{code:-32000,message:err.message}}, '*'); }
    }
  });

  async function loadView() {
    if (!viewHtml) viewHtml = (await request('/api/view', null, {headers:{'X-User-Id':USER}})).html;
    return viewHtml;
  }
  async function loadProfile() {
    try {
      const sc = content(await mcp('get_travel_profile'));
      profile = sc.profile || {};
      $('#pref-budget').value = profile.tripBudgetEUR ?? 1800;
      $$('input[name="pref-interest"]').forEach(x => x.checked = (profile.interests || []).includes(x.value));
      $('#pref-step-free').checked = !!profile.stepFreeAccess;
      $('#preferences-source').textContent = hostedDemo ? 'Saved in temporary hosted storage' : 'Saved in local SQLite';
      $('#profile-mini-label').textContent = `${(profile.interests || []).length} interests · €${profile.tripBudgetEUR ?? 1800} default`;
    } catch (err) { $('#preferences-source').textContent = 'Could not load profile'; toast(`Profile unavailable: ${err.message}`, true); }
  }
  async function loadTrips() {
    const grid = $('#trips-grid'); grid.innerHTML = '<div class="loading-card">Loading saved trips…</div>';
    try {
      const sc = content(await mcp('list_saved_trips', {limit:20})); savedTrips = sc.trips || [];
      renderTrips();
    } catch (err) { grid.innerHTML = ''; showError('#trips-status', `Could not load saved trips: ${err.message}`); }
  }
  function renderTrips() {
    const grid = $('#trips-grid'); $('#trip-count').textContent = String(savedTrips.length); $('#overview-trip-count').textContent = String(savedTrips.length);
    $('#overview-trip-caption').textContent = savedTrips.length ? (hostedDemo ? 'Stored in temporary hosted travel memory' : 'Stored in your local travel profile') : 'No trips saved yet';
    if (!savedTrips.length) { grid.innerHTML = '<article class="empty-card"><div class="empty-art" aria-hidden="true"><span class="empty-orbit"></span><svg viewBox="0 0 112 112" fill="none"><path d="M39 43V32a17 17 0 0 1 34 0v11M27 43h58l-5 48H32l-5-48Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M45 58c0 7 5 12 11 12s11-5 11-12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></div><div class="eyebrow">A PLACE FOR YOUR PLANS</div><h2>Your next trip starts here.</h2><p>Build a Barcelona itinerary and save it to your travel profile. Saved plans come from your profile; this list is never prefilled.</p><button class="button button-primary" data-page="planner" type="button">Plan your first trip <span aria-hidden="true">→</span></button></article>'; return; }
    grid.innerHTML = savedTrips.map((trip,i) => {
      const data = trip.data || {}, title = escapeHtml(trip.label || data.destination || 'Saved trip');
      const isDemo = data.kind === 'demo-trip';
      const days = isDemo ? `${data.days || data.itinerary?.length || '—'} days` : 'Saved search';
      const cost = isDemo ? euro(data.estimatedTotal) : 'Estimate details';
      const art = isDemo
        ? '<img src="/static/barcelona-sagrada.jpg" alt="" loading="lazy"><span class="trip-art-caption">BARCELONA <i>·</i> YOUR DEMO ITINERARY</span>'
        : '<div class="trip-record-icon" aria-hidden="true"><svg viewBox="0 0 48 48" fill="none"><circle cx="22" cy="22" r="13" stroke="currentColor" stroke-width="1.6"/><path d="m32 32 9 9M22 15v14m-7-7h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></div><span class="trip-art-caption">SAVED TRAVEL RECORD</span>';
      return `<article class="trip-card ${isDemo?'trip-card-demo':''}"><div class="trip-card-art">${art}<button class="icon-button delete-trip" type="button" data-id="${escapeAttr(trip.id)}" aria-label="Delete ${title}" title="Delete trip">×</button></div><div class="trip-card-content"><span class="trip-tag">${isDemo?'DEMO ITINERARY':'SAVED TRIP'}</span><h2>${title}</h2><p>${days} <span aria-hidden="true">·</span> ${cost}</p><div class="trip-card-actions">${isDemo?`<button type="button" class="button button-secondary open-trip" data-index="${i}">Open itinerary <span aria-hidden="true">→</span></button>`:'<span class="small-status">Saved search record · itinerary view unavailable</span>'}</div></div></article>`;
    }).join('');
  }
  async function loadDashboard() {
    try { const [p,t] = await Promise.all([mcp('get_travel_profile'),mcp('list_saved_trips',{limit:20})]);
      profile=content(p).profile||{}; savedTrips=content(t).trips||[]; renderTrips();
      $('#overview-interest-count').textContent = String((profile.interests||[]).length);
      $('#overview-preference-caption').textContent = `${(profile.interests||[]).join(', ') || 'No interests selected'} · €${profile.tripBudgetEUR ?? 1800} default`;
        if (activePlan) { $('#overview-plan-total').textContent = euro(content(activePlan).estimatedTotal); $('#overview-plan-caption').textContent='Current illustrative estimate · not a live quote'; }
    } catch(err) { $('#overview-trip-caption').textContent=`Travel profile unavailable: ${err.message}`; }
  }
  function euro(v) { return Number.isFinite(Number(v)) ? `€${Number(v).toLocaleString('en-US',{maximumFractionDigits:0})}` : 'Estimate unavailable'; }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function escapeAttr(s) { return escapeHtml(s); }
  function tripFromResult(result) { const sc = content(result); return sc.kind === 'demo-rescue' ? sc.after : sc; }
  async function saveResult(result, label) {
    const trip = tripFromResult(result);
    if (!trip || trip.kind !== 'demo-trip') throw new Error('Only a complete demo itinerary can be saved.');
    const saved = await mcp('save_demo_trip_tool',{trip:{...trip,label}});
    if (saved.isError) throw new Error(content(saved).speech || 'Save failed');
    await loadTrips(); toast('Trip saved to your local travel profile.');
  }
  async function runChat(text, target) {
    const button = target === 'rescue' ? $('#run-rescue') : $('#plan-submit');
    if (button) { button.disabled=true; button.dataset.oldText=button.textContent; button.textContent='Working…'; }
    try {
      const data = await request('/api/chat',{session_id:sessionId,user_id:USER,text});
      sessionId=data.session_id; sessionStorage.setItem(sessionKey,sessionId);
      if (!data.trace?.some(x=>x.tool)) throw new Error(data.speech || 'The planner could not complete this request.');
      const tool = [...data.trace].reverse().find(x=>x.tool);
      const result = data.ui?.toolResult;
      if (tool.tool === 'plan_demo_trip' && result) {
        activePlan=result; await loadView(); mountFrame($('#result-view'),result,data.ui.toolInput);
        $('#results-workspace').hidden=false; $('#rescue-context').textContent='Using your current itinerary and preferences.';
        const sc=content(result); $('#overview-plan-total').textContent=euro(sc.estimatedTotal); $('#overview-plan-caption').textContent='Current illustrative estimate · not a live quote';
        $('#results-workspace').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
        toast('Your itinerary is ready.');
      } else if (['rescue_demo_trip_tool','simulate_provider_failure'].includes(tool.tool) && result) {
        activeRescue=result; await loadView(); mountFrame($('#rescue-view'),result,data.ui.toolInput);
        $('#rescue-results').hidden=false; $('#rescue-context').textContent='Recovery is based on your current trip settings.';
        const outage = tool.tool === 'simulate_provider_failure';
        $('#rescue-results .section-heading h2').textContent = outage ? 'Offline recovery verified.' : 'Your trip, adapted.';
        $('#return-original').hidden = outage; $('#save-rescue').hidden = outage;
        $('#rescue-results').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
        toast(tool.tool==='simulate_provider_failure'?'Provider failure simulated; offline recovery completed.':'Rescue plan ready.');
      } else throw new Error(data.speech || 'Unexpected response from the planner.');
      showError(target==='rescue'?'#rescue-error':'#planner-error','');
      await loadDashboard();
    } catch(err) { showError(target==='rescue'?'#rescue-error':'#planner-error',err.message); }
    finally { if (button) { button.disabled=false; button.textContent=button.dataset.oldText || (target==='rescue'?'Replan around the closure →':'Build my itinerary →'); } }
  }
  function planText() {
    const days=Math.max(1,Number($('#plan-days').value)||4), travelers=Math.max(1,Number($('#plan-travelers').value)||2), budget=Math.max(0,Number($('#plan-budget').value)||1800);
    const interests=$$('input[name="plan-interest"]:checked').map(x=>x.value);
    return `Plan a ${days}-day Barcelona trip for ${travelers} people under €${budget}; interests: ${interests.join(', ') || 'architecture, art, food'}${$('#plan-step-free').checked?'; prioritize step-free venues':''}.`;
  }
  document.addEventListener('click', async e => {
    const page=e.target.closest('[data-page]'); if(page){e.preventDefault();await showPage(page.dataset.page);return;}
    const brand=e.target.closest('[data-page-link]'); if(brand){e.preventDefault();await showPage('overview');return;}
    if(e.target.closest('[data-plan-demo]')) { showPage('planner'); await loadProfile(); $('#plan-days').value=4;$('#plan-travelers').value=2;$('#plan-budget').value=1800; $$('input[name="plan-interest"]').forEach(x=>x.checked=['architecture','art','food'].includes(x.value)); $('#plan-step-free').checked=false; $('#planner-form').requestSubmit(); return; }
    if(e.target.closest('#refresh-dashboard')) { await loadDashboard(); toast('Dashboard refreshed from your local profile.'); return; }
    if(e.target.closest('#open-rescue-from-plan')) { showPage('rescue'); return; }
    if(e.target.closest('#return-original')) { const original=activePlan || (content(activeRescue).before ? {structuredContent:content(activeRescue).before} : null); if(original){activePlan=original;mountFrame($('#rescue-view'),original,{arguments:{}});} else toast('Run a trip plan first to compare with its original itinerary.',true); return; }
    if(e.target.closest('#plan-with-preferences')) { showPage('planner'); await loadProfile(); $('#plan-budget').value=profile?.tripBudgetEUR??1800; $$('input[name="plan-interest"]').forEach(x=>x.checked=(profile?.interests||[]).includes(x.value)); $('#plan-step-free').checked=!!profile?.stepFreeAccess; $('#planner-form').requestSubmit(); return; }
    if(e.target.closest('#save-trip')) { try { await saveResult(activePlan,'Barcelona demo itinerary'); } catch(err){toast(err.message,true);} return; }
    if(e.target.closest('#save-rescue')) { try { await saveResult(activeRescue,'Barcelona revised itinerary'); } catch(err){toast(err.message,true);} return; }
    const open=e.target.closest('.open-trip'); if(open){ const trip=savedTrips[Number(open.dataset.index)], data=trip?.data; if(data?.kind==='demo-trip'){ activePlan={structuredContent:data}; await loadView(); mountFrame($('#result-view'),activePlan,{arguments:{}});$('#results-workspace').hidden=false;showPage('planner');toast('Opened saved itinerary.'); }else toast('This saved record does not contain an itinerary view.'); return; }
    const del=e.target.closest('.delete-trip'); if(del){ if(!confirm('Delete this saved trip? This cannot be undone.'))return; try{const r=await mcp('delete_saved_trip_tool',{trip_id:del.dataset.id});if(r.isError)throw new Error(content(r).speech||'Delete failed');await loadTrips();toast('Saved trip deleted.');}catch(err){showError('#trips-status',err.message);}return; }
    if(e.target.closest('#forget-all')) { if(!confirm('Delete all saved profile data, trips and price watches from the local demo?'))return; try{const r=await mcp('forget_travel_memory');if(r.isError)throw new Error(content(r).speech||'Could not clear memory');profile=null;savedTrips=[];await loadDashboard();toast('Local travel memory cleared.');}catch(err){toast(err.message,true);} return; }
    if(e.target.closest('#reset-demo')) { if(!confirm('Reset this demo conversation? Saved trips and preferences will remain.'))return; try{await request('/api/reset',{session_id:sessionId});sessionId='';sessionStorage.removeItem(sessionKey);activePlan=null;activeRescue=null;$('#results-workspace').hidden=true;$('#rescue-results').hidden=true;showPage('overview');toast('Demo conversation reset.');}catch(err){toast(err.message,true);} }
  });
  $('#planner-form').addEventListener('submit',e=>{e.preventDefault();showError('#planner-error','');runChat(planText(),'plan');});
  $('#run-rescue').addEventListener('click',()=>{showError('#rescue-error','');runChat('The Sagrada Família is closed; replan my Barcelona itinerary around the disruption.','rescue');});
  $('#run-provider-failure').addEventListener('click',()=>{showError('#rescue-error','');runChat('Simulate a flight provider failure and recover offline.','rescue');});
  $('#preferences-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter, interests=$$('input[name="pref-interest"]:checked').map(x=>x.value);if(!interests.length){$('#preferences-message').textContent='Choose at least one interest.';$('#preferences-message').hidden=false;return;}button.disabled=true;try{const args={trip_budget_eur:Number($('#pref-budget').value),interests,step_free_access:$('#pref-step-free').checked};const r=await mcp('set_travel_profile',args);if(r.isError)throw new Error(content(r).speech||'Could not save preferences');profile=content(r).profile||args;$('#preferences-message').textContent='Preferences saved and will be used by the planner.';$('#preferences-message').hidden=false;$('#preferences-source').textContent=hostedDemo?'Saved in temporary hosted storage':'Saved in local SQLite';await loadDashboard();toast('Preferences saved.');}catch(err){$('#preferences-message').textContent=err.message;$('#preferences-message').hidden=false;}finally{button.disabled=false;}});
  // Support keyboard activation and refresh all real backend snapshots on entry.
  $('#welcome-date').textContent = new Intl.DateTimeFormat(undefined,{weekday:'long',month:'long',day:'numeric'}).format(new Date()).toUpperCase();
  request('/api/config',null).then(config=>{
    hostedDemo=!!config.hosted;
    if(hostedDemo){
      $('#demo-status-title').textContent='Hosted demo mode';$('#hosting-notice').hidden=false;
      $('#mcp-endpoint').textContent=`${location.origin}/mcp`;
      $('#page-help .page-intro p').textContent='RoamReady is a hosted travel planning demo that uses MCP tools for planning and recovery.';
      $('#page-trips .page-intro p').textContent='Plans saved to temporary hosted travel memory. Demo estimates only; no bookings are made.';
      $('#page-preferences .page-intro p').textContent='Saved through the existing MCP profile tool in temporary hosted storage and applied by the demo planner.';
      $('#page-planner .aside-disclosure p').textContent='This planner uses RoamReady’s MCP server. It does not request flight or hotel provider data.';
      $('#page-help .help-danger p').textContent='Delete your saved profile, trips and price watches from this demo’s temporary storage. This cannot be undone.';
      $('#page-help .help-card:nth-child(3) p').textContent='Clear the current conversation and generated comparison. Saved trips and preferences remain in temporary hosted storage.';
    }
    return loadView();
  }).then(loadDashboard).catch(err=>toast(`MCP server unavailable: ${err.message}`,true));
  if (document.readyState === 'complete') initJourneyMotion();
  else window.addEventListener('load', initJourneyMotion, {once:true});
})();
