// Offline behavior check for the generated diagnostic report's filters and views.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const page=fs.readFileSync(process.argv[2],'utf8');
class Element {
  constructor(){this.value='';this.textContent='';this.dataset={};this.children=[];this.listeners={};this.attrs={};this.hidden=false}
  addEventListener(name,fn){this.listeners[name]=fn}
  setAttribute(name,value){this.attrs[name]=value}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
}
const ids=Object.fromEntries(['data','status','filter','visible','selection','details','xy','xz'].map(id=>['#'+id,new Element()]));
ids['#data'].textContent=page.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const data=JSON.parse(ids['#data'].textContent);
assert(data.rows.length>0);
const rows=[...page.matchAll(/<tr data-row="(\d+)" data-status="([^"]+)"[^>]*>([\s\S]*?)<\/tr>/g)].map(m=>{const e=new Element();e.dataset={row:m[1],status:m[2]};e.textContent=m[3].replace(/<[^>]*>/g,' ');return e});
const context=vm.createContext({document:{querySelector:s=>ids[s],querySelectorAll:s=>s==='#paths tr'?rows:[],createElementNS:()=>new Element()},Math,JSON,Number,String,Object});
const js=page.match(/<\/script><script>([\s\S]*?)<\/script>/)[1];
vm.runInContext(js,context);
assert.equal(rows.filter(r=>!r.hidden).length,data.rows.length);
assert(ids['#xy'].children.some(n=>n.attrs.points));
assert(ids['#xz'].children.some(n=>n.attrs.points));
ids['#status'].value='different';ids['#status'].listeners.change();
assert.equal(rows.filter(r=>!r.hidden).length,data.rows.filter(r=>r.status!=='matched').length);
ids['#status'].value='matched';ids['#status'].listeners.change();
assert.equal(rows.filter(r=>!r.hidden).length,data.rows.filter(r=>r.status==='matched').length);
ids['#filter'].value='not-an-existing-route';ids['#filter'].listeners.input();assert(rows.every(r=>r.hidden));
ids['#filter'].value='';ids['#status'].value='';ids['#status'].listeners.change();
const row=rows.find(r=>r.dataset.status==='matched');assert(row);row.listeners.click();
assert(ids['#selection'].textContent.includes('matched'));
assert.equal(ids['#xy'].children.filter(n=>n.attrs.points).length,2);
assert(JSON.parse(ids['#details'].textContent).sionna.points.length>=2);
let prevented=false;row.listeners.keydown({key:'Enter',preventDefault:()=>{prevented=true}});assert(prevented);
console.log('PATH_REPORT_PASS: filters, row selection, XY/XZ routes, details, keyboard navigation');
