// SPDX-FileCopyrightText: 2026 plovecraft
// SPDX-License-Identifier: AGPL-3.0-only
// Local files only: SVG measurement/rendering; no live EDA or browser-session access.
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');

function playwright() {
  try { return require(process.env.SCHEMATIC_PLAYWRIGHT_MODULE || 'playwright'); }
  catch { throw Error('Install the optional browser dependency: npm install --prefix scripts ; see README.md'); }
}

function executable() {
  if (process.env.SCHEMATIC_BROWSER) {
    if (!fs.existsSync(process.env.SCHEMATIC_BROWSER)) throw Error('SCHEMATIC_BROWSER does not exist');
    return process.env.SCHEMATIC_BROWSER;
  }
  const candidates = [
    process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES,'Google/Chrome/Application/chrome.exe'),
    process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES,'Microsoft/Edge/Application/msedge.exe'),
    process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'],'Microsoft/Edge/Application/msedge.exe'),
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA,'Google/Chrome/Application/chrome.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome','/usr/bin/chromium','/usr/bin/chromium-browser'
  ];
  return candidates.find(p => p && fs.existsSync(p)); // Otherwise use Playwright's installed Chromium.
}

async function main() {
  const [mode,input,output,extraTextFile] = process.argv.slice(2);
  if (!['measure','render','check-preview'].includes(mode) || !input || !output)
    throw Error('Usage: node browser_svg.cjs measure|render|check-preview INPUT OUTPUT [EXTRA_TEXTS.json]');
  const {chromium} = playwright();
  const browser = await chromium.launch({headless:true,executablePath:executable()});
  try {
    const url = pathToFileURL(path.resolve(input)).href;
    const context = await browser.newContext({viewport:{width:1500,height:950},deviceScaleFactor:1,
      offline:true,javaScriptEnabled:mode==='check-preview'});
    await context.route('**/*', route => {
      const request = route.request().url();
      const ownPreview = mode==='check-preview' && request.startsWith(pathToFileURL(path.dirname(path.resolve(input))+path.sep).href);
      return request===url || request.startsWith('data:') || ownPreview ? route.continue() : route.abort();
    });
    const page = await context.newPage();
    await page.goto(url);
    await page.evaluate(() => document.fonts.ready);
    if (mode==='measure') {
      const extras = extraTextFile ? JSON.parse(fs.readFileSync(extraTextFile,'utf8').replace(/^\uFEFF/,'')) : [];
      const result = await page.evaluate(extras => {
        const root=document.querySelector('svg');
        if (!root) throw Error('No SVG root');
        const inverse=root.getCTM().inverse();
        const elements=[...root.querySelectorAll('[id]')].filter(e=>typeof e.getBBox==='function').map(e=>{
          const b=e.getBBox(),m=inverse.multiply(e.getCTM());
          const pts=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]]
            .map(([x,y])=>new DOMPoint(x,y).matrixTransform(m));
          return {id:e.id,tag:e.tagName,text:e.tagName==='text'?e.textContent:null,
            bbox:{minX:Math.min(...pts.map(p=>p.x)),maxX:Math.max(...pts.map(p=>p.x)),
              minY:-Math.max(...pts.map(p=>p.y)),maxY:-Math.min(...pts.map(p=>p.y))}};
        });
        if (new Set(elements.map(e=>e.id)).size!==elements.length) throw Error('Duplicate SVG IDs');
        const textMetrics={},nativeLabelMetrics={},annotationMetrics={};
        const extraNames=extras.filter(e=>typeof e==='string');
        for (const value of new Set([...elements.filter(e=>e.tag==='text').map(e=>e.text),...extraNames])) {
          const t=document.createElementNS('http://www.w3.org/2000/svg','text');
          t.setAttribute('x','0');t.setAttribute('y','0');t.setAttribute('font-family','Arial');
          t.setAttribute('font-size','7.006200555911909');t.setAttribute('dominant-baseline','text-before-edge');
          t.textContent=value;root.appendChild(t);const b=t.getBBox();
          textMetrics[value]={width:b.width,height:b.height,bearingX:b.x,bearingY:b.y};
          t.textContent='';t.setAttribute('dominant-baseline','ideographic');
          const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');
          span.setAttribute('x','0');span.setAttribute('dx','0');span.setAttribute('dy','0');span.textContent=value;t.appendChild(span);
          const n=t.getBBox();nativeLabelMetrics[value]={minX:n.x,maxX:n.x+n.width,minY:-(n.y+n.height),maxY:-n.y};t.remove();
        }
        for(const row of extras.filter(e=>typeof e==='object')) {
          const t=document.createElementNS('http://www.w3.org/2000/svg','text');
          t.setAttribute('x','0');t.setAttribute('y','0');t.setAttribute('font-family','Arial');
          t.setAttribute('font-size',String(row.fontSize));t.setAttribute('dominant-baseline','text-before-edge');
          t.textContent=row.text;root.appendChild(t);const b=t.getBBox();
          annotationMetrics[row.text]={fontSize:row.fontSize,width:b.width,height:b.height,bearingX:b.x,bearingY:b.y};t.remove();
        }
        return {elements,textMetrics,nativeLabelMetrics,annotationMetrics};
      },extras);
      fs.writeFileSync(output,JSON.stringify({method:'Local SVG getBBox; raw Y-up; system Arial metrics',...result},null,2));
    } else if (mode==='render') {
      await page.evaluate(()=>{
        const root=document.querySelector('svg'),b=root.viewBox.baseVal;
        root.setAttribute('width','1500');root.setAttribute('height',Math.ceil(1500*b.height/b.width));
      });
      await page.locator('svg').screenshot({path:output});
    } else {
      const ids=await page.locator('#pick option').evaluateAll(nodes=>nodes.map(e=>e.value));
      const results=[];
      for (const id of ids) {
        await page.selectOption('#pick',id);
        await page.waitForFunction(id=>{const img=document.querySelector('#drawing');return img.src.endsWith('/pages/'+id+'/candidate.svg')&&img.complete&&img.naturalWidth>0},id);
        await page.locator('#fit').click();
        const size=await page.locator('#drawing').evaluate(e=>({width:e.clientWidth,height:e.clientHeight,frameWidth:e.parentElement.clientWidth}));
        results.push({id,...size,passed:size.width<=size.frameWidth+1});
      }
      await page.selectOption('#pick',ids[0]);
      await page.waitForFunction(()=>document.querySelector('#drawing').complete);
      await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
      fs.writeFileSync(output,JSON.stringify({passed:results.every(r=>r.passed),pages:results},null,2));
    }
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error.message);process.exit(1)});
