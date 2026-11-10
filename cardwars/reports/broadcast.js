const match = JSON.parse(document.querySelector('#match').textContent);
const players = match.players, games = match.games, cards = match.cards;
const mirroredDraft = players[1].harness === 'Card Wars';
const stage = document.querySelector('#stage'), menu = document.querySelector('#scenes');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const name = i => esc(players[i].name);
const img = (src, alt='') => src ? '<img alt="'+esc(alt)+'" src="'+esc(src)+'">' : '';
function mark(i) {
  const p = players[i];
  return '<span class="mark">'+(p.brand ? img(match.logos[p.brand], p.brand === 'openai' ? 'OpenAI' : 'Claude') : esc(p.name[0]))+'</span>';
}
function header(scores, label) {
  document.querySelector('header').innerHTML = '<div class="wordmark">Card Wars <em>Arena</em></div><div class="match-score">'+mark(0)+'<span class="corner0 tinted">'+name(0)+'</span><b class="score">'+scores.join(' – ')+'</b><span class="corner1 tinted">'+name(1)+'</span>'+mark(1)+'</div><b class="micro">'+esc(label)+'</b>';
}
function caption(text, i=null) {
  document.querySelector('footer').innerHTML = '<div class="credit '+(i===null?'':'corner'+i)+'"><small>'+(i===null?'Broadcast':'Public comment')+'</small><b>'+(i===null?'Arena desk':name(i))+'</b></div><div class="caption">'+(i===null?esc(text):'“'+esc(text)+'”')+'</div>';
}
function faceoff() {
  return '<div class="faceoff">'+players.map((p,i)=>'<article class="fighter corner'+i+'"><div class="identity slide">'+mark(i)+'<div class="micro">'+(i?'Orange corner':'Blue corner')+'</div><h1>'+name(i)+'</h1><div class="harness">'+[p.harness,p.effort?p.effort[0].toUpperCase()+p.effort.slice(1)+' reasoning':''].filter(Boolean).map(esc).join(' · ')+'</div></div></article>').join('')+'<span class="vs">VS</span></div>';
}
function poster(g, fight) {
  const n=g.number, previous=games.slice(0,n-1);
  const rail=games.map((_,k)=>'<span class="'+(k<n-1?'won corner'+previous[k].winner:k===n-1?'now':'')+'"></span>').join('');
  return '<div class="poster '+(fight?'fight':'')+'"><span class="giant">'+String(n).padStart(2,'0')+'</span><div class="slide"><div class="micro">'+(fight?'Decks locked':'Five-game match')+'</div><h1>'+(fight?'Fight!':'Game '+n)+'</h1><p>'+(fight?'First up · Landscape placement':'Up next · Choose a hero and build a deck')+'</p><div class="rail">'+rail+'</div></div></div>';
}
// One embedded texture per atlas, shared by all cropped hero portraits.
const atlasDefs = Object.entries(match.atlases).map(([atlas, src]) =>
  '<image id="atlas-'+esc(atlas)+'" href="'+esc(src)+'"/>'
).join('');
document.body.insertAdjacentHTML('afterbegin','<svg width="0" height="0" aria-hidden="true" style="position:absolute"><defs>'+atlasDefs+'</defs></svg>');
function heroHeader(i, deck) {
  let portrait = '<span class="hero-back" aria-hidden="true">?</span>';
  if (deck) {
    const sprite = match.portraits[deck.heroId];
    portrait = '<svg viewBox="'+esc(sprite.rect)+'" role="img" aria-label="'+esc(deck.hero)+'"><use href="#atlas-'+esc(sprite.atlas)+'"/></svg>';
  }
  return '<div class="hero-header"><div class="hero-portrait">'+portrait+'</div><div class="hero-details"><div class="deck-title">'+mark(i)+'<h2>'+name(i)+'</h2><span class="lock">'+(deck?deck.cards.length+' / 20 LOCKED':mirroredDraft && i===1?'WAITING':'SELECTING')+'</span></div><div class="hero-label">'+(deck?'Selected hero':'Hero selection')+'</div><h3>'+esc(deck?deck.hero:mirroredDraft && i===1?'Same as '+players[0].name:'Choosing a hero…')+'</h3></div></div>';
}
function roster(i, deck) {
  const ids=deck?.cards || Array(20).fill(null);
  const rows=ids.map(id=>{
    if (!id) return '<div class="card-row back"></div>';
    const card=cards[id];
    return '<div class="card-row">'+img(card.art)+'<b>'+esc(card.name)+'</b><span class="mana">'+esc(card.cost)+'</span></div>';
  }).join('');
  const counts={};
  if (deck) for(const id of ids) counts[cards[id].faction]=(counts[cards[id].faction]||0)+1;
  const factions=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([f,n])=>n+' '+esc(f)).join('  ·  ');
  return '<div class="deck corner'+i+'">' + heroHeader(i, deck) + '<div class="slots">'+rows+'</div>'+(deck?'':'<div class="waiting"><h3>'+((mirroredDraft && i===1)?'Waiting for the mirror':'Building deck')+'</h3><div class="sweep"></div></div>')+'<div class="breakdown">'+(deck?factions:mirroredDraft && i===1?'Copies the opposing hero and all 20 cards':'Choosing a hero and 20 cards')+'</div></div>';
}
function draft(g, count) {
  const locked=g.decks.slice(0,count);
  return '<div class="draft"><div class="section-head"><h1>Deck selection</h1><b class="micro">'+match.pool+' available cards &nbsp; / &nbsp; Card cost in MP</b></div><div class="decks">'+players.map((_,i)=>roster(i,locked.find(d=>d.player===i))).join('')+'</div></div>';
}
function boardSnapshot(a) {
  const label = id => cards[id]?.name || id;
  return '<div class="board-snap"><div class="micro">Position before the play</div>'+[1,0].map(i=>{
    const side=a.board[i], lanes=i ? [...side.lanes].reverse() : side.lanes;
    return '<div class="corner'+i+'"><h3 class="tinted">'+name(i)+' · '+side.mp+' MP</h3><div class="lanes">'+lanes.map(l=>'<div><small>'+esc(l.landscape)+'</small><p>'+esc(label(l.creature?.id)||'—')+'</p><p>'+esc(label(l.building?.id)||'')+'</p></div>').join('')+'</div><p class="hand"><b>Hand</b> · '+a.hands[i].map(id=>esc(label(id))).join(' · ')+'</p></div>';
  }).join('')+'</div>';
}
function play(a) {
  const c=cards[a.card], effect=(c.floop?'Floop · '+c.floop+' MP. ':'')+c.effect;
  return '<div class="battle"><div class="field">'+boardSnapshot(a)+'</div><div class="spot corner'+a.player+'"><b class="micro">Turn '+a.turn+' · Card played</b><div class="acting">'+name(a.player)+'</div><div class="art">'+img(c.art)+'<b class="cost">'+esc(c.cost)+' MP</b></div><h2>'+esc(c.name)+'</h2><p>'+esc(c.faction)+' '+esc(c.type.toLowerCase())+'</p><div class="stats">'+(c.atk==null?'':esc(c.atk)+' ATK &nbsp; / &nbsp; '+esc(c.hp)+' DEF')+'</div><p>'+esc(effect)+'</p></div></div>';
}
function chart(g) {
  if(!g.hp.length || !g.finalHp) return '<h3>'+esc(g.reason)+'</h3>';
  const end=Math.max(1,g.hp.at(-1)[0]), top=Math.max(match.health,...g.hp.flatMap(p=>p.slice(1)));
  const lines=players.map((_,i)=>{
    const path=g.hp.map(([t,...hp],k)=>(k?'L':'M')+(10+640*t/end).toFixed(1)+' '+(198-182*Math.max(0,hp[i])/top).toFixed(1)).join(' ');
    return '<path class="corner'+i+'" d="'+path+'" fill="none" stroke="var(--accent)" stroke-width="5"/>';
  }).join('');
  return '<h3>Hero health by turn</h3><svg viewBox="0 0 660 216" role="img" aria-label="Health history"><path d="M10 16H650 M10 108H650 M10 198H650" fill="none" stroke="#466069" stroke-dasharray="6 8"/>'+lines+'</svg><div class="legend">'+players.map((_,i)=>'<b class="corner'+i+' tinted">'+name(i)+' · '+g.finalHp[i]+' HP</b>').join('')+'</div>';
}
function result(g, final) {
  const winner=final?Number(g.after[1]>g.after[0]):g.winner;
  const panel=final?'<h3>Game winners</h3>'+games.map(x=>'<div class="ledger"><span>Game '+x.number+'</span><b class="corner'+x.winner+' tinted">'+name(x.winner)+'</b></div>').join(''):chart(g);
  return '<div class="result corner'+winner+'"><div class="slide">'+mark(winner)+'<div class="micro">'+(final?'Match winner':'Game '+g.number+' winner')+'</div><h1>'+name(winner)+'</h1><h2>'+g.after.join(' – ')+' in games</h2><p>'+(final?'Five games complete':g.number<games.length?'Up next · Game '+(g.number+1):'Up next · Match result')+'</p></div><div class="chart">'+panel+'</div></div>';
}
const scenes=[];
function add(g, kind, index, title) {
  scenes.push({g,kind,index,title});
  menu.add(new Option(title,scenes.length-1));
}
add(1,'intro',0,'Matchup');
for (const g of games) {
  add(g.number,'game',0,'Game '+g.number);
  for(let c=0;c<=g.decks.length;c++) add(g.number,'draft',c,'Game '+g.number+' · Draft · '+c+' locked');
  if(g.decks.length===2) add(g.number,'fight',0,'Game '+g.number+' · Fight');
  for(const a of g.placements) add(g.number,'land',a.rev,'Game '+g.number+' · Landscape · '+a.terrain+' · Lane '+(a.lane+1));
  for(const a of g.plays) add(g.number,'play',a.rev,'Game '+g.number+' · Turn '+a.turn+' · '+cards[a.card].name);
  add(g.number,'result',0,'Game '+g.number+' · Result');
}
add(games.length,'final',0,'Match result');
function renderScene(s) {
  const g=games[s.g-1], k=s.kind;
  header(['result','final'].includes(k)?g.after:g.before,k==='intro'?'Five-game match':k==='final'?'Match complete':'Game '+g.number+' of '+games.length);
  if(k==='intro') {stage.innerHTML=faceoff();caption(mirroredDraft?'Five games. The campaign AI plays the same hero and deck as '+players[0].name+'. Each deck is shuffled separately.':'Five games. Each player can change their hero and rebuild their deck between games. The player with the most wins takes the match.');}
  if(k==='game') {stage.innerHTML=poster(g,false);caption('Both heroes start at '+match.health+' HP. The players choose from the same pool of '+match.pool+' cards.');}
  if(k==='draft') {
    stage.innerHTML=draft(g,s.index);
    const d=g.decks[s.index-1];
    if(d?.comment) caption(d.comment,d.player);
    else if(mirroredDraft) caption(d?'Both players have the same hero and 20 cards.':players[0].name+' is choosing the roster for both sides.');
    else caption(d?players[d.player].name+' has locked in a hero and 20 cards.':'Both players are choosing. Each deck is revealed when its player locks in all 20 cards.');
  }
  if(k==='fight') {stage.innerHTML=poster(g,true);caption('The opening draw determines who goes first. Each player places four landscapes. The second player gets the first attack.');}
  if(k==='land') {
    const a=g.placements.find(p=>p.rev===s.index);
    const rows=players.map((_,i)=>'<div class="corner'+i+'"><h3 class="tinted">'+name(i)+'</h3><div class="lanes">'+[0,1,2,3].map(lane=>'<div><small>Lane '+(lane+1)+'</small><p>'+esc(g.placements.find(v=>v.rev<=a.rev && v.player===i && v.lane===lane)?.terrain || '—')+'</p></div>').join('')+'</div></div>').join('');
    stage.innerHTML='<div class="battle"><div class="field"><div class="board-snap"><div class="micro">Landscape placement</div>'+rows+'</div></div><div class="spot corner'+a.player+'"><b class="micro">Opening setup</b><div class="acting">'+name(a.player)+'</div><h2>'+esc(a.terrain)+'</h2><p>Place a landscape in lane '+(a.lane+1)+'.</p><div class="stats">Four lanes per side</div><p>Both players place their landscapes before either side can play a creature.</p></div></div>';
    if(a.comment) caption(a.comment,a.player); else caption(players[a.player].name+' places '+a.terrain+' in lane '+(a.lane+1)+'.');
  }
  if(k==='play') {
    const a=g.plays.find(p=>p.rev===s.index);
    stage.innerHTML=play(a);
    if(a.comment) caption(a.comment,a.player);else caption(players[a.player].name+' · '+a.label);
  }
  if(k==='result'||k==='final') {
    const final=k==='final'; stage.innerHTML=result(g,final);
    caption(final?'Final result after all five games.':g.reason==='health'?players[g.winner].name+' wins game '+g.number+' on turn '+g.turns+' by reducing the opposing hero to zero HP.':players[g.winner].name+' wins game '+g.number+' · '+g.reason);
  }
}
function select(i) {menu.selectedIndex=Math.max(0,Math.min(i,scenes.length-1));renderScene(scenes[menu.selectedIndex]);}
const controls = !new URLSearchParams(location.search).has('clean');
document.body.classList.toggle('controls',controls);
document.querySelector('nav').hidden = !controls;
if (!controls) document.querySelector('nav').style.display='none';
function resize() {document.body.style.setProperty('--zoom',Math.min(innerWidth/1920,(innerHeight-(controls?44:0))/1080));}
onresize=resize;resize();
menu.onchange=()=>select(menu.selectedIndex);
document.querySelector('#prev').onclick=()=>select(menu.selectedIndex-1);
document.querySelector('#next').onclick=()=>select(menu.selectedIndex+1);
onkeydown=e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowRight')select(menu.selectedIndex+1);if(e.key==='ArrowLeft')select(menu.selectedIndex-1);};
select(0);
