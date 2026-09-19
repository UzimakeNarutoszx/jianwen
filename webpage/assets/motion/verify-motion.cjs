const assert = require('node:assert/strict')
const vm = require('node:vm')
const fs = require('node:fs')
const path = require('node:path')
class Element {
  constructor() { this.dataset={}; this.attributes={}; this.events={}; this.children=[]; this.style={}; this.paused=true; this.playCount=0; this.classList={ add(){},toggle(){} } }
  setAttribute(k,v){this.attributes[k]=v} getAttribute(k){return k==='src'?this.src:this.attributes[k]} hasAttribute(k){return k in this.attributes}
  addEventListener(k,v){this.events[k]=v} append(...items){this.children.push(...items)}
  pause(){this.paused=true} async play(){this.playCount++;this.paused=false}
}
function setup(reduced=false, saveData=false) {
  const container=new Element(); container.dataset.motionFilm='ambient'
  const doc={currentScript:{src:'http://localhost/js/motion.js'},hidden:false,events:{},createElement:()=>new Element(),querySelectorAll:s=>s==='[data-motion-film=ambient]'?[container]:[],addEventListener(k,v){this.events[k]=v}}
  const media={matches:reduced,addEventListener(){}}
  let intersect
  class Observer{constructor(fn){intersect=intersect||fn}observe(){}unobserve(){}}
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../js/motion.js'),'utf8'),{document:doc,window:{matchMedia:()=>media,IntersectionObserver:Observer,addEventListener(){}},navigator:{connection:{saveData}},URL,IntersectionObserver:Observer})
  return {container,doc,video:container.children[0],button:container.children[1],visible:value=>intersect([{target:container,isIntersecting:value}])}
}
const flush=()=>new Promise(resolve=>setImmediate(resolve))
async function main(){
  let p=setup(); assert.equal(p.video.src,undefined)
  p.visible(true);await flush();assert.equal(p.video.paused,false);assert.match(p.video.src,/ajin-ambient.mp4$/)
  p.visible(false);assert.equal(p.video.paused,true)
  p.visible(true);await flush();p.doc.hidden=true;p.doc.events.visibilitychange();assert.equal(p.video.paused,true)
  p=setup(true);p.visible(true);await flush();assert.equal(p.video.src,undefined,'Reduced motion avoids video download')
  p=setup();p.visible(true);await flush();assert.equal(p.container.children.length,1,'No video controls')
  p.video.currentTime=4.5;p.video.events.timeupdate();assert.equal(p.video.paused,true)
  p.visible(false);p.visible(true);assert.equal(p.video.paused,true,'Completed ambient animation stays stopped')
  p=setup(false,true);p.visible(true);await flush();assert.equal(p.video.src,undefined,'Save Data avoids download')
  p.video.events.error();assert.equal(p.video.paused,true)
  console.log('Motion controls: lazy loading, viewport/background pause, reduced motion, Save Data, no buttons, finite playback and error fallback passed.')
}
main().catch(e=>{console.error(e);process.exitCode=1})
