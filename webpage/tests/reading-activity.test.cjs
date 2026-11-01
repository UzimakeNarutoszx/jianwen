const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const source = fs.readFileSync('webpage/js/reading-activity.js','utf8')
const flush = () => new Promise(resolve => setImmediate(resolve))
function setup() {
  let now = Date.parse('2026-10-17T08:00:00Z'), token = 'user-a', id = 1, focus = true, fail = false, batch = 0
  const timers=[], events={}, storage=new Map(), uploads=[]
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])) } static now() { return now } }
  const document={ hidden:false, hasFocus:()=>focus, addEventListener:(name,fn)=>{ events[name]=fn } }
  const window={ getToken:()=>token, getSessionUser:()=>({id}), addEventListener:(name,fn)=>{ events[name]=fn },
    jianwenApi:{ readingActivity:async body => { if(fail) throw new Error('offline'); uploads.push(body) } } }
  vm.runInNewContext(source,{window,document,Date:Clock,crypto:{randomUUID:()=>`batch-${++batch}`},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},setInterval:(fn,ms)=>timers.push({fn,ms})})
  return {window,document,uploads,storage,events,
    async seconds(count) { for(let i=0;i<count;i++){now+=1000;timers[0].fn();if(now%15000===0)timers[1].fn();await flush()} },
    focus(value){focus=value;events[value?'focus':'blur']()},
    offline(value){fail=value},
    account(value,newId){token=value;id=newId;events['jianwen-session-change']()},
    target(id='a'){window.jianwenReading.setTarget({kind:'article',content_id:id})},
    total(){return uploads.reduce((sum,p)=>sum+Date.parse(p.ended_at)-Date.parse(p.started_at),0)/1000}
  }
}
(async()=>{
  let r=setup();r.target();await r.seconds(30);assert.equal(r.total(),30,'Two heartbeats accumulate 30 seconds')
  assert.ok(r.uploads.every(p=>Date.parse(p.ended_at)-Date.parse(p.started_at)<=15000))
  r.document.hidden=true;r.events.visibilitychange();await r.seconds(20);assert.equal(r.total(),30,'Hidden time excluded')
  r.document.hidden=false;r.focus(false);await r.seconds(20);assert.equal(r.total(),30,'Unfocused time excluded')
  r=setup();r.target();await r.seconds(90);assert.equal(r.total(),60,'Idle time stops after 60 seconds')
  r.events.pointerdown();await r.seconds(15);assert.equal(r.total(),75,'Interaction resumes reading')
  r=setup();r.offline(true);r.target();await r.seconds(30);assert.equal(r.total(),0);assert.ok([...r.storage.values()].some(v=>JSON.parse(v).length));r.offline(false);await r.seconds(15);assert.equal(r.total(),45,'Offline batches retry without changing their time')
  r=setup();r.offline(true);r.target();await r.seconds(15);r.account('user-b',2);r.offline(false);await r.seconds(15);assert.equal(r.total(),15,'Previous account queue discarded');assert.equal(r.storage.has('jianwen_reading_queue_1'),false)
  r=setup();r.target('a');await r.seconds(5);r.target('b');await flush();await r.seconds(10);assert.equal(r.uploads.filter(p=>p.content_id==='a').reduce((s,p)=>s+Date.parse(p.ended_at)-Date.parse(p.started_at),0),5000,'Content switches flush the old target')
  console.log('Reading activity: foreground timing, idle pause/resume, bounded batches, retries, account switch and content switch passed.')
})().catch(error=>{console.error(error);process.exitCode=1})
