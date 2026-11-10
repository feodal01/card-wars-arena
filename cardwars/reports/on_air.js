const scores = [0,0];
let cursor=0, currentGame=1, rendered='', interrupted='', ended=false;
function eventRow([seq, timestamp, number, kind, d]) {
  cursor=seq;currentGame=number;
  const g=games[number-1], time=timestamp*1000;
  if(kind==='draft_start'){g.started=time;g.before=[...scores];}
  if(kind==='submit_deck'){g.decks.push(d);g.locked=time;}
  if(kind==='unity_state'){
    if(g.hp.at(-1)?.[0]===d.turn)g.hp.pop();
    g.hp.push([d.turn,...d.hp]);
  }
  if(kind==='act'){g.action=d;g.actionSeq=seq;if(d.card)g.focus=d;if(d.comment)g.quote=d;}
  if(kind==='run_interrupted')interrupted=String(d);
  if(kind==='game_end'){interrupted='';g.winner=d.winner;scores[d.winner]++;g.after=[...scores];g.end=time;g.turns=d.turns;g.finalHp=d.hp;g.reason=d.reason;}
  if(kind==='match_end'){
    ended=true;
    // The organizer can exit while the last game's victory slate is visible.
    setTimeout(()=>updateProgram(null),Math.max(0,g.end+4010-Date.now()));
  }
}
function updateProgram(feed) {
  let g=games[currentGame-1], scene='draft';
  const now=Date.now(), prev=games[currentGame-2];
  if(interrupted){caption('Match interrupted · '+interrupted);return;}
  if(prev && now-prev.end<4000){g=prev;scene='result';}
  else if(g.end){scene=ended && now-g.end>4000?'final':'result';}
  else if(g.number===1 && now-g.started<3000)scene='intro';
  else if(now-(prev?Math.max(prev.end+4000,g.started):g.started+3000)<1800)scene='game';
  else if(feed===g.number && g.decks.length===2){
    // The deck stays on screen across Unity startup. The title gets its own
    // short clock only when the first playable image is ready.
    if(!g.feedAt){
      g.feedAt=now;
      setTimeout(()=>{if(rendered===g.number+'/fight/')updateProgram(g.number);},1200);
    }
    scene=now-g.feedAt<1200?'fight':'battle';
  }
  const key=[g.number,scene,scene==='draft'?g.decks.length:scene==='battle'?g.actionSeq:''].join('/');
  if(key===rendered)return;
  rendered=key;
  if(scene==='battle')nativeField(g,g.action,g.focus,g.quote,'game-'+g.number+'.mjpg');
  else renderScene({g:g.number,kind:scene,index:g.decks.length});
}
async function followProgram() {
  try {
    const r=await fetch('events?after='+cursor,{cache:'no-store'});
    if(r.ok){const p=await r.json();p.rows.forEach(eventRow);updateProgram(p.feed);}
  } catch(e) { if(!ended)console.warn('Spectator update delayed',e); }
  if(!(ended && rendered.includes('/final/')))setTimeout(followProgram,160);
}
followProgram();
