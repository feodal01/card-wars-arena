"use strict";
const $ = id => document.getElementById(id);
const data = JSON.parse($("data").textContent);
$("data").remove();
const live = document.body.dataset.mode === "table";
const items = data.items, ids = Object.keys(items);
const storageKey = "cardwars-roster-v1";
let deck = {hero_id:null, card_ids:[]}, tab = "Cards", inspect = "", selected = null;
let state = {phase: live ? "connecting" : "offline"}, pending = false, lastView = "", cursor = 0, history = [];
const urls = new Map();
function asset(uri) {
  if (!urls.has(uri)) {
    const [header, encoded] = uri.split(",");
    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    urls.set(uri, URL.createObjectURL(new Blob([bytes], {type:header.slice(5,-7)})));
  }
  return urls.get(uri);
}
function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function button(label, fn, cls) {
  const b = node("button", label, cls); b.onclick = fn; return b;
}
function artwork(id, style = "") {
  const r = items[id];
  if (r?.atlas) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns,"svg"), img = document.createElementNS(ns,"image");
    svg.setAttribute("viewBox",r.rect); svg.setAttribute("class","art hero "+style);
    // Explicitly clip the atlas to its native sprite rectangle, including wide containers.
    svg.setAttribute("preserveAspectRatio","xMidYMid meet");
    const nested = document.createElementNS(ns,"svg");
    const [x,y,w,h] = r.rect.split(" ");
    for (const [k,v] of Object.entries({x,y,width:w,height:h,viewBox:r.rect})) nested.setAttribute(k,v);
    img.setAttribute("href",asset(data.atlases[r.atlas])); nested.append(img); svg.append(nested);return svg;
  }
  const img=node("img",undefined,"art "+style); img.alt=""; img.loading="lazy";
  if(r?.art) img.src=asset(r.art);
  return img;
}
const nameOf = id => items[id]?.name || id;
const variant = id => id?.startsWith("Leader_Super") ? "Enhanced hero" : "Hero";
function countText(id) {
  const c = items[id];
  return c.type === "Hero" ? variant(id) : [c.faction,c.type].join(" · ");
}
function valid(v, complete) {
  return v && (items[v.hero_id]?.type === "Hero" || (!complete && v.hero_id===null))
    && Array.isArray(v.card_ids) && (complete ? v.card_ids.length===20 : v.card_ids.length<=20)
    && new Set(v.card_ids).size===v.card_ids.length
    && v.card_ids.every(k=>Object.hasOwn(items,k) && items[k].type!=="Hero");
}
function message(msg) { $("notice").textContent=msg; $("notice").hidden=!msg; }
function persist() {
  try { localStorage.setItem(storageKey,JSON.stringify(deck)); } catch {}
}
try {
  const saved = JSON.parse(localStorage.getItem(storageKey));
  if(valid(saved,false)) deck=saved;
} catch {}
function choose(id) {
  const c = items[id];
  if(c.type==="Hero") deck.hero_id=id;
  else if(deck.card_ids.includes(id)) deck.card_ids=deck.card_ids.filter(k=>k!==id);
  else if(deck.card_ids.length<20) deck.card_ids.push(id);
  else { message("Your deck has 20 cards. Remove one to add another."); return; }
  message(""); persist(); drawDraft();
}
function detail(id, extra) {
  if (!items[id]) return node("div");
  const c=items[id], p=node("div",undefined,"panel");
  p.append(artwork(id,"detailArt"),node("span",countText(id),"tag"),node("h2",c.name),
    node("p",c.description),node("div",id,"id"));
  if(extra)p.append(extra);
  return p;
}
function factionFrame(element, faction) {
  if (data.colors[faction]) {
    element.classList.add("factionFrame");
    element.style.setProperty("--faction",data.colors[faction]);
  }
}
function ability(id) {
  const c=items[id], block=node("span",undefined,"ability");
  if(!c)return block;
  const label=c.type==="Hero"?"Hero ability":c.floop!=null?"Floop · "+c.floop+" MP":"Effect";
  block.append(node("span",label,"abilityLabel"),node("span",c.type==="Hero"?c.description:c.effect,"abilityText"));
  return block;
}
function tile(id, index, drafting) {
  const c=items[id], chosen=deck.hero_id===id || deck.card_ids.includes(id);
  const tile=node("div",undefined,"tile"+(drafting && chosen?" pick":""));
  if(c)factionFrame(tile,c.faction);
  const focus=drafting ? inspect===id : selected?.source==="hand" && selected.index===index;
  if(focus) tile.classList.add("focus");
  const b=button("",()=> {
    if(drafting){inspect=id;drawDraft();}
    else {selected={source:"hand",index,id};drawBattle();}
    if(matchMedia("(max-width:650px)").matches) $(drafting?"draftDetail":"battleDetail").scrollIntoView({block:"start"});
  },"inspect");
  const copy=node("span",undefined,"copy");
  copy.append(node("strong",nameOf(id)),node("span",c?countText(id):"","sub"));
  if(c?.type==="Creature") copy.append(node("small",c.atk+" ATK · "+c.hp+" DEF"));
  if(c)copy.append(ability(id));
  b.append(artwork(id),copy);
  if(c && c.type!=="Hero") b.append(node("span",c.cost+" MP","cost"));
  tile.append(b);
  if(drafting) tile.append(button(chosen?(c.type==="Hero"?"Selected hero":"− Remove"):(c.type==="Hero"?"Choose hero":"+ Add"),()=>choose(id),"pickButton"));
  return tile;
}
function drawDraft() {
  const hero=tab==="Heroes";
  $("cardsTab").classList.toggle("active",!hero);$("heroesTab").classList.toggle("active",hero);
  $("faction").hidden=$("kind").hidden=hero;
  const q=$("search").value.trim().toLowerCase();
  const shown=ids.filter(id=>{
    const c=items[id];
    return (c.type==="Hero")===hero && (hero || ((!$("faction").value || c.faction===$("faction").value)
      && (!$("kind").value || c.type===$("kind").value))) && (!q || [c.name,c.description,id].join(" ").toLowerCase().includes(q));
  }).sort((a,b)=>nameOf(a).localeCompare(nameOf(b)) || a.localeCompare(b));
  $("count").textContent=shown.length+" "+(hero?"heroes":"cards");
  $("library").replaceChildren(...shown.map(id=>tile(id,null,true)));
  $("draftDetail").replaceChildren(inspect ? detail(inspect,button(items[inspect].type==="Hero"?"Choose hero":deck.card_ids.includes(inspect)?"Remove from deck":"Add to deck",()=>choose(inspect),"wide")) : node("div"));
  $("deckCount").textContent=deck.card_ids.length+" / 20";
  const chosen=$("chosen"); chosen.replaceChildren();
  if(deck.hero_id){
    const h=node("div",undefined,"heroLine");h.append(artwork(deck.hero_id,"mini"),node("b",nameOf(deck.hero_id)));
    chosen.append(h);
  }else chosen.append(button("Choose your hero",()=>setTab("Heroes"),"wide"));
  const list=node("div",undefined,"decklist");
  for(const id of deck.card_ids){
    const row=node("div",undefined,"picked");
    row.append(node("span",nameOf(id)),button("Remove",()=>choose(id)));list.append(row);
  }
  $("roster").replaceChildren(list);
  $("export").disabled=!valid(deck,true);
  $("recordOption").hidden=!live || state.phase!=="lobby";
  $("start").hidden=!live;
  $("start").textContent=state.game>1?"Lock deck for game "+state.game:"Start match";
  $("start").disabled=pending || !valid(deck,true) || !["lobby","select_deck"].includes(state.phase) || Boolean(state.own_deck);
  $("startHint").textContent=live ? (state.phase==="lobby"?"Take your time. The match clock starts when you start the match.":"Confirm your deck before the draft clock expires.") : "Export one hero and 20 distinct cards, then import the JSON at your table.";
}
function setTab(next){tab=next;$("search").value="";drawDraft();}
$("cardsTab").onclick=()=>setTab("Cards");$("heroesTab").onclick=()=>setTab("Heroes");
for (const f of [...new Set(ids.map(id=>items[id].faction).filter(Boolean))].sort()) $("faction").add(new Option(f,f));
for(const k of ["search","faction","kind"]) $(k).oninput=drawDraft;
$("export").onclick=()=>{
  if(!valid(deck,true))return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(deck,null,2)],{type:"application/json"}));
  const a=node("a");a.href=url;a.download="card-wars-deck.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
$("import").onchange=async e=>{
  try {
    const file=e.target.files[0]; if(!file)return;
    if(file.size>8192)throw Error("Choose a deck JSON file under 8 KB.");
    const v=JSON.parse(await file.text());
    if(!valid(v,true))throw Error("This catalog requires one hero and 20 distinct cards.");
    deck={hero_id:v.hero_id,card_ids:v.card_ids};inspect=deck.hero_id;persist();drawDraft();message("Deck imported.");
  }catch(err){message(err.message);}
  finally {e.target.value="";}
};
$("rules").onclick=()=>$("guide").showModal();$("closeRules").onclick=()=>$("guide").close();
$("guideText").textContent=data.rules;
function seatLabel(text) {
  return text.replace(/\bseat ([01])\b/gi,(_,i)=>Number(i)===state.seat_index?"You":data.opponent);
}
async function send(route,body){
  if(pending)return; pending=true; message("");render(true);
  try{
    const res=await fetch(route,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const reply=await res.json();if(!res.ok)throw Error(reply.error || "Request failed.");
    if(route==="act")selected=null;
    if(route==="start")state={phase:"starting"};
  }catch(err){message(err.message);}
  finally{pending=false;await refresh();render(true);}
}
$("start").onclick=()=>state.phase==="lobby"
  ? send("start",{...deck,record:$("recordVideo").checked})
  : send("draft",{...deck,game:state.game});
function parts(a){return a.id.split("/").at(-1).split(":");}
function moveButton(a) {
  const b=button(seatLabel(a.label),()=>send("act",{action_id:a.id}),"action"+(parts(a)[0]==="end"?" end":""));
  b.disabled=pending;return b;
}
function inspectField(id,source,index,seat){selected={id,source,index,seat};drawBattle();}
function sideBlock(side, mine, ordered) {
  const block=node("div"), header=node("div",undefined,"sideHead"+(mine?"":" foe"));
  const h=button("",()=>inspectField(side.hero,"hero",null,side.seat),"heroButton");
  h.append(artwork(side.hero,"mini"),node("b",mine?"You":data.opponent));
  header.append(h,node("span",nameOf(side.hero)+" · "+state.hp[side.seat]+" HP · "+side.mp+" MP"+(side.spellMP?" + "+side.spellMP+" spell MP":"")),
    node("small","Hero cooldown "+side.heroCooldown+" · Hand "+side.handCount+" · Deck "+side.deckCount));
  if(items[side.hero]) header.append(node("small",items[side.hero].description,"heroAbility"));
  const row=node("div",undefined,"lanes");
  for(const lane of ordered) {
    const box=node("div",undefined,"lane");
    factionFrame(box,lane.landscape);
    box.append(node("b","Lane "+(lane.lane+1)),node("small",lane.landscape+(lane.flipped?" · flipped":"")+(lane.disabled?" · disabled":""),"sub"));
    const c=lane.creature;
    if(c){
      const b=button("",()=>inspectField(c.id,"creature",lane.lane,side.seat));
      b.append(artwork(c.id),node("strong",nameOf(c.id)),node("small",c.attack+" ATK · "+c.hp+"/"+c.maxHP+" HP","sub"));
      const flags=[["flooped","Flooped"],["cantAttack","Cannot attack"],["helpless","Helpless"],["protected","Protected"],["floopBlocked","Floop blocked"]].filter(([k])=>c[k]).map(x=>x[1]);
      if(flags.length)b.append(node("small",flags.join(" · "),"sub"));
      b.append(ability(c.id));box.append(b);
    }
    if(lane.building){
      const building=button(nameOf(lane.building),()=>inspectField(lane.building,"building",lane.lane,side.seat));
      building.append(ability(lane.building));box.append(building);
    }
    row.append(box);
  }
  block.append(header,row);return block;
}
function drawBattle(){
  const mine=state.board[state.seat_index], foe=state.board[1-state.seat_index];
  $("board").replaceChildren(sideBlock(foe,false,mine.lanes.map(l=>foe.lanes.find(f=>f.lane===l.opposingLane))),sideBlock(mine,true,mine.lanes));
  $("handCount").textContent=state.hand.length+" / 7";
  $("hand").replaceChildren(...state.hand.map((id,i)=>tile(id,i,false)));
  const opts=state.actions || [];
  $("battleDetail").replaceChildren(selected?detail(selected.id):node("div"));
  const actions=$("actions");actions.replaceChildren();
  const forCard=opts.filter(a=>{
    const [op,n]=parts(a);
    return selected?.source==="hand" && ["cast","play"].includes(op) && +n===selected.index;
  });
  if(selected?.source==="hand" && !forCard.length && opts.length)actions.append(node("p","This card has no available play now.","quiet"));
  for(const a of forCard)actions.append(moveButton(a));
  const other=opts.filter(a=>!["play","cast"].includes(parts(a)[0]));
  if(!selected && opts.some(a=>["play","cast"].includes(parts(a)[0])))actions.append(node("p","Select a card in your hand to see its legal plays.","quiet"));
  for(const a of other)actions.append(moveButton(a));
  if(!opts.length)actions.append(node("p",state.active_player==="human"?"Resolving your action…":data.opponent+" is playing.","quiet"));
  $("events").replaceChildren(...history.slice(-80).reverse().map(e=>node("li",e)));
}
function render(force=false){
  const s=state, mode=s.phase, draftMode=["lobby","offline"].includes(mode) || (mode==="select_deck" && !s.own_deck);
  const battle=mode==="battle" && !!s.board;
  const stamp=JSON.stringify({...s,seconds_remaining:0,events:null})+":"+pending+":"+cursor;
  if(s.seconds_remaining!=null && ["battle","select_deck"].includes(mode)){
    const n=Math.ceil(s.seconds_remaining);
    $("clock").textContent=(s.phase==="battle"?(s.active_player==="human"?"Your turn":"Opponent’s turn"):"Draft")+" · "+Math.floor(n/60)+":"+String(n%60).padStart(2,"0");
  }else $("clock").textContent="";
  if(!force && stamp===lastView)return;
  lastView=stamp;
  $("draft").hidden=!draftMode;$("battle").hidden=!battle;$("waiting").hidden=draftMode || battle;
  $("matchup").textContent=live?"You vs "+data.opponent+(data.effort?" · "+data.effort:""):"Offline catalog";
  $("eyeline").textContent=s.game?"Game "+s.game+" of 5  ·  Match score "+s.score.human+"–"+Object.entries(s.score).find(([k])=>k!=="human")[1]:live?"Player table":"Card collection";
  $("heading").textContent=draftMode?"Deck workshop":battle?(s.stage==="landscapes"?"Place landscapes":"Turn "+s.turn+" · "+(s.active_player==="human"?"Your turn":data.opponent)):(mode==="match_over"?"Match complete":"Your table");
  if(draftMode)drawDraft();
  if(battle)drawBattle();
  const last=s.last_result;
  const result=last?"Game "+last.game+" went to "+(last.winner==="human"?"you":data.opponent)+" ("+last.reason.replaceAll("_"," ")+"). ":"";
  if(!draftMode && !battle)$("waiting").textContent=result+({error:s.message,starting:"Starting the match…",connecting:"Connecting…",loading:"Loading the battlefield…",select_deck:"Your deck is locked. Waiting for the opponent.",match_over:"Final score above."}[mode] || "Preparing the table…");
  if(mode==="match_over" && s.replay_ready) {
    const link=node("a","Open the five-game replay"); link.href="replay";link.target="_blank";link.rel="noopener";
    $("waiting").append(node("p"),link);
  }
  if(mode==="match_over" && s.video){
    if(s.video==="ready"){
      const link=node("a","Download match video (MP4)");link.href="video";$("waiting").append(node("p"),link);
    }else $("waiting").append(node("p",s.video==="encoding"?"Preparing match video…":"Video export failed. The match trace is available."));
  }
  if(draftMode && last)$("startHint").textContent=result+"Keep your previous deck or change it before locking in.";
}
let pollId=0,applied=0;
async function refresh(){
  const n=++pollId;
  try{
    const res=await fetch("state?"+cursor,{cache:"no-store"});
    if(!res.ok)throw Error("Cannot reach the player table.");
    const next=await res.json(); if(n<applied)return;applied=n;
    if(next.game!==state.game){selected=null;history=[];}
    if(selected?.source==="hand" && next.hand?.[selected.index]!==selected.id)selected=null;
    state=next;
    for(const g of next.events || []){
      if(g.seq<=cursor)continue;
      if(g.game===next.game)history.push(...g.events.map(seatLabel));
      cursor=g.seq;
    }
    render();
  }catch(err){message("Connection interrupted. Retrying… "+err.message);}
}
if(live){(async function poll(){await refresh();setTimeout(poll,900);})();}else render(true);
