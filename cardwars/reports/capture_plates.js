// Render the existing spectator layout in a private headless Chrome window.
// Node 22 supplies WebSocket. Chrome publishes its own ephemeral debugger port.
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const {setTimeout: delay} = require('node:timers/promises');

async function capture(folder, chrome) {
  const profile = path.join(folder, 'chrome-profile');
  const proc = spawn(chrome, ['--headless=new', '--disable-background-networking',
    '--no-first-run', '--window-size=1920,1080', '--remote-debugging-port=0',
    '--user-data-dir='+profile, 'about:blank'], {stdio:'ignore'});
  let launchError;
  proc.on('error', err => { launchError=err; });
  try {
    let port;
    for(let attempt=0; attempt<300 && !port; attempt++) {
      if(launchError) throw launchError;
      if(proc.exitCode!==null) throw Error('Chrome exited during startup');
      try {port=(await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];}
      catch(err) {if(err.code!=='ENOENT') throw err; await delay(100);}
    }
    if(!port) throw Error('Chrome did not publish its debugger endpoint');
    const targets=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
    const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
    let id=0;
    const pending=new Map();
    ws.onmessage = ({data}) => {
      const m=JSON.parse(data), call=pending.get(m.id);
      if(!call) return;
      pending.delete(m.id);
      if(m.error) call.reject(Error(m.error.message)); else call.resolve(m.result);
    };
    ws.onclose=()=>{for(const call of pending.values())call.reject(Error('Chrome disconnected'));};
    function send(method,params={}) {
      return new Promise((resolve,reject)=>{
        pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));
      });
    }
    async function evaluate(expression) {
      const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
      if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    }
    await send('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:pathToFileURL(path.join(folder,'broadcast.html')).href+'?clean'});
    let ready=false;
    for(let attempt=0;attempt<300 && !ready;attempt++) {
      ready=await evaluate("typeof nativeField==='function' && document.readyState==='complete'");
      if(!ready)await delay(100);
    }
    if(!ready)throw Error('The broadcast page did not finish loading');
    const scenes=JSON.parse(await fs.readFile(path.join(folder,'scenes.json'),'utf8'));
    for(const scene of scenes) {
      const render = scene.program ? 'renderScene('+JSON.stringify(scene.program)+')' :
        'nativeField(games['+(scene.game-1)+'],'+[scene.action,scene.focus,scene.quote,null].map(v=>JSON.stringify(v??null)).join(',')+')';
      await evaluate('(async()=>{'+render+'; await document.fonts.ready; await Promise.all([...document.images].filter(i=>i.src).map(i=>i.decode()));for(const a of document.getAnimations()){a.pause();a.currentTime=1200;} await new Promise(requestAnimationFrame);})()');
      const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await fs.writeFile(path.join(folder,scene.key+'.png'),Buffer.from(shot.data,'base64'));
    }
    ws.close();
  } finally {
    if(proc.exitCode===null && !launchError){
      const exited=new Promise(resolve=>proc.once('exit',resolve));
      proc.kill();await exited;
    }
  }
}
capture(process.argv[2],process.argv[3]).catch(err=>{console.error(err);process.exitCode=1;});
