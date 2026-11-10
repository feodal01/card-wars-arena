// The native JPEG stream owns the battlefield. Score and card information update
// independently so accepting an action never reconnects the video.
function nativeField(game, action, focus, quote, feed) {
  header(game.before, 'Game '+game.number+' of '+games.length);
  if (stage.dataset.fieldGame !== String(game.number) || !stage.querySelector('.field')) {
    stage.dataset.fieldGame=String(game.number);
    stage.innerHTML='<div class="battle"><div class="field"></div><div class="spot"></div></div>';
    if(feed) {const video=new Image();video.alt='Live Unity battlefield';video.src=feed;stage.querySelector('.field').append(video);}
  }
  const panel=stage.querySelector('.spot');
  const actor=action?.player, c=cards[focus?.card];
  panel.className='spot'+(actor==null?'':' corner'+actor);
  panel.innerHTML='<b class="micro">'+(action?(action.turn?'Turn '+action.turn:'Landscape placement'):'Opening draw')+'</b>'+
    (actor==null?'':'<div class="acting">'+name(actor)+'</div>')+
    (c?'<div class="art">'+img(c.art)+'<b class="cost">'+esc(c.cost)+' MP</b></div><h2>'+esc(c.name)+'</h2><p>'+esc(c.faction)+' '+esc(c.type.toLowerCase())+'</p><div class="stats">'+(c.atk==null?'':esc(c.atk)+' ATK / '+esc(c.hp)+' DEF')+'</div><p>'+esc((c.floop?'Floop · '+c.floop+' MP. ':'')+c.effect)+'</p>':
      '<h2>'+(action?'Landscapes':'Who goes first?')+'</h2><p>'+(action?'Each player sets four lanes before the first card is played.':'The opening draw decides which player places landscapes first.')+'</p>');
  if(quote)caption(quote.comment,quote.player);
  else caption(action?players[actor].name+' · '+action.label:'The first player sets up. The second player gets the first attack.');
}
