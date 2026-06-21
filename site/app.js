// Chennai Booth Analytics — app.js
// Loads data.json, renders the interactive Leaflet map + sidebar.

let P = null;

// ---- state ----
let selectedAc = 'ALL';
let domain = 'votes', cycle = null;
let vmode = 'winner', valliance = null;
let dmode = 'dominant', dage = '18-21', dsex = 'All', dyaxis = 'youth_share';
let dabs = '18-21', dskew = '18-21';
let selPart = null, cellLayer = null, outlineLayer = null, labelLayer = null;
let baseGrey, baseSat, baseActive;

// ---- helpers: AC filtering ----
function visFeatures() {
  if (selectedAc === 'ALL') return P.geojson.features;
  return P.geojson.features.filter(f => f.properties.ac === selectedAc);
}
function getCs(yr) {
  const tbl = selectedAc === 'ALL' ? P.all_summaries : P.ac_summaries[selectedAc];
  return tbl ? tbl[yr] : null;
}
function selAcName() {
  if (selectedAc === 'ALL') return 'all constituencies';
  return P.acs[selectedAc].name;
}

document.getElementById('tierNote').innerHTML =
  'Each polygon is a booth Voronoi cell clipped to its AC outline. ' +
  'Geocoding tier shown on hover; <b>centroid</b> booths are approximate.';

// ---- color helpers ----
function hexToRgb(h){h=h.replace('#','');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}
function rgb(a){return 'rgb('+a[0]+','+a[1]+','+a[2]+')';}
function seqColor(t,stops){t=Math.max(0,Math.min(1,t));let i=t<0.5?0:1,f=t<0.5?t*2:(t-0.5)*2;const a=stops[i][1],b=stops[i+1][1];return rgb([Math.round(a[0]+(b[0]-a[0])*f),Math.round(a[1]+(b[1]-a[1])*f),Math.round(a[2]+(b[2]-a[2])*f)]);}
const SEQ = {
  lowHigh:[[0,hexToRgb('#1a1a2e')],[0.5,hexToRgb('#4fc3f7')],[1,hexToRgb('#fff176')]],
  youth:[[0,hexToRgb('#0d1b2a')],[0.5,hexToRgb('#2ec4b6')],[1,hexToRgb('#ffd166')]],
  elder:[[0,hexToRgb('#0d1b2a')],[0.5,hexToRgb('#9d4edd')],[1,hexToRgb('#ffd166')]],
  gender:[[0,hexToRgb('#ec4899')],[0.5,hexToRgb('#c8c8d0')],[1,hexToRgb('#4fc3f7')]],
  margin:[[0,hexToRgb('#1a1a2e')],[0.5,hexToRgb('#ffa726')],[1,hexToRgb('#e53935')]],
};
function tierOpacity(p){return p.tier==='ac_centroid'?0.5:(p.tier==='locality'?0.75:0.88);}
function rangeOf(getter){let mn=1e9,mx=-1e9;for(const f of visFeatures()){const v=getter(f.properties);if(v==null)continue;if(v<mn)mn=v;if(v>mx)mx=v;}return [mn,mx];}

function colorOf(p) {
  if (domain==='demo') {
    if (dmode==='dominant') return P.band_colors[p.dominant_band]||'#666';
    if (dmode==='gender') return seqColor((p.male_ratio-0.40)/0.20, SEQ.gender);
    if (dmode==='youth') {
      const [mn,mx]=rangeOf(x=>x[dyaxis]);
      return seqColor((p[dyaxis]-mn)/Math.max(mx-mn,1e-6), dyaxis==='youth_share'?SEQ.youth:SEQ.elder);
    }
    if (dmode==='absolute') {
      const key = dabs+'|All';
      const [mn,mx]=rangeOf(x=>x.cohort_shares[key]*x.total);
      const v = p.cohort_shares[key]*p.total;
      return seqColor((v-mn)/Math.max(mx-mn,1e-6), SEQ.lowHigh);
    }
    if (dmode==='bandskew') {
      const v = p.band_gender_skew[dskew];
      return seqColor((v-0.40)/0.20, SEQ.gender);
    }
    if (dmode==='cohort') {
      const m = cohortMean();
      const v = (p.cohort_shares[dage+'|'+dsex]||0);
      return seqColor((v/Math.max(m,1e-6)-0.4)/1.2, SEQ.lowHigh);
    }
  } else {
    const cv = p.votes[cycle];
    if (!cv) return '#333';
    if (vmode==='winner') return P.alliance_colors[cv.winner]||'#888';
    if (vmode==='margin') return seqColor(cv.margin, SEQ.margin);
    if (vmode==='share') {
      const s = cv.shares[valliance]||0;
      return seqColor(s/0.7, SEQ.lowHigh);
    }
  }
  return '#666';
}
function cohortMean(){const k=dage+'|'+dsex;let s=0;const fs=visFeatures();for(const f of fs)s+=f.properties.cohort_shares[k]||0;return fs.length?s/fs.length:0;}
function valueStr(p){
  if (domain==='demo') {
    if (dmode==='dominant') return p.dominant_band;
    if (dmode==='gender') return (p.male_ratio*100).toFixed(1)+'% M';
    if (dmode==='youth') return (p[dyaxis]*100).toFixed(1)+'%';
    if (dmode==='absolute') return Math.round(p.cohort_shares[dabs+'|All']*p.total);
    if (dmode==='bandskew') return (p.band_gender_skew[dskew]*100).toFixed(1)+'% M';
    if (dmode==='cohort') return ((p.cohort_shares[dage+'|'+dsex]||0)*100).toFixed(1)+'%';
  } else {
    const cv=p.votes[cycle]; if(!cv) return 'no data';
    if (vmode==='winner') return cv.winner+' ('+(cv.shares[cv.winner]*100).toFixed(0)+'%)';
    if (vmode==='margin') return (cv.margin*100).toFixed(1)+'% lead';
    if (vmode==='share') return ((cv.shares[valliance]||0)*100).toFixed(1)+'%';
  }
}
function styleOf(feat){
  const p=feat.properties; const sel=selPart!==null&&p.uid===selPart;
  const dimmed = selectedAc!=='ALL' && p.ac!==selectedAc;
  let fo=tierOpacity(p);
  if(domain==='votes'&&vmode==='winner'&&p.votes[cycle]){
    const sh=p.votes[cycle].shares[p.votes[cycle].winner];
    fo=0.30+sh*0.65;
  }
  return {fillColor:colorOf(p),weight:sel?2.5:0.6,color:sel?'#1565c0':'rgba(50,50,50,0.35)',
          opacity:dimmed?0.2:0.85,fillOpacity:dimmed?0.08:Math.min(fo,0.95)};
}

function render(){
  if(cellLayer)cellLayer.remove();
  const visFC={type:'FeatureCollection',features:visFeatures()};
  cellLayer=L.geoJSON(visFC,{style:styleOf,
    onEachFeature:(feat,layer)=>{
      layer.on({
        mouseover:e=>{e.target.setStyle({weight:2,color:'#1565c0',opacity:1,fillOpacity:Math.min(1,tierOpacity(feat.properties)+0.12)});e.target.bringToFront();},
        mouseout:e=>{if(feat.properties.uid!==selPart)cellLayer.resetStyle(e.target);},
        click:e=>{selectBooth(feat.properties.uid);L.DomEvent.stopPropagation(e);}
      });
      const p=feat.properties;
      layer.bindTooltip('<b>'+p.ac+' Part '+p.part_no+'</b> &middot; '+(p.street||p.locality||'?')+'<br>'+valueStr(p)+' &middot; '+p.tier,{direction:'top',className:'ac18'});
    }
  }).addTo(map);
  if(outlineLayer)outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());
  renderLegend(); renderSummary(); renderDonut();
  if(labelLayer){labelLayer.remove();labelLayer=null;renderLabels();}
}

function renderLegend(){
  let html='', title='';
  if(domain==='votes'){
    if(vmode==='winner'){title='Winner by alliance';
      const cs=getCs(cycle);
      if(cs){const sorted=Object.entries(cs.alliance_shares).sort((a,b)=>b[1]-a[1]);const top=sorted.slice(0,6);const rest=sorted.slice(6);const restPct=rest.reduce((s,[,v])=>s+v,0);
        html='<div class="legend-cats">'+top.map(([a,s])=>'<span><i style="background:'+(P.alliance_colors[a]||'#888')+'"></i>'+a+' ('+(s*100).toFixed(1)+'%)</span>').join('')+(restPct>0?'<span><i style="background:#555"></i>Others ('+(restPct*100).toFixed(1)+'%)</span>':'')+'</div>';}
    } else if(vmode==='share'){title=valliance+' vote share';
      html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(79,195,247),rgb(255,241,118))"></div>'+
        '<div class="legend-labels"><span>0%</span><span>35%</span><span>70%+</span></div>';
    } else {title='Lead margin';
      html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(255,167,38),rgb(229,57,53))"></div>'+
        '<div class="legend-labels"><span>close (0%)</span><span>20%</span><span>landslide (40%+)</span></div>';
    }
  } else {
    const titles={dominant:'Dominant age band',cohort:'Cohort share',gender:'Male share',youth:dyaxis==='youth_share'?'Youth share (<30)':'Elderly share (60+)',absolute:'Absolute count ('+dabs+')',bandskew:'Male share within '+dskew};
    title=titles[dmode];
    if(dmode==='dominant'){html='<div class="legend-cats">'+P.age_bands.map(b=>'<span><i style="background:'+P.band_colors[b]+'"></i>'+b+'</span>').join('')+'</div>';}
    else if(dmode==='gender'||dmode==='bandskew'){html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(236,72,153),rgb(200,200,208),rgb(79,195,247))"></div><div class="legend-labels"><span>F female-skew</span><span>50/50</span><span>male-skew M</span></div>';}
    else if(dmode==='cohort'){const m=cohortMean();html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(79,195,247),rgb(255,241,118))"></div><div class="legend-labels"><span>0.4x avg</span><span>1.0x ('+(m*100).toFixed(1)+'%)</span><span>1.6x avg</span></div>';}
    else {const ramp=dmode==='youth'?(dyaxis==='youth_share'?'rgb(46,196,182)':'rgb(157,78,221)'):'rgb(79,195,247)';html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(13,27,42),'+ramp+',rgb(255,209,102))"></div><div class="legend-labels"><span>low</span><span>medium</span><span>high</span></div>';}
  }
  document.getElementById('legendTitle').textContent=title;
  document.getElementById('legendBody').innerHTML=html;
}

function renderSummary(){
  let cards=[], toplabel='', metric=null, fmt=null;
  const fs=visFeatures();
  if(domain==='votes'){
    const cs=getCs(cycle);
    const tv = cs?cs.total_valid:0;
    const wc = fs.filter(f=>f.properties.votes[cycle]).length;
    cards=[['Valid votes',tv.toLocaleString(),''],['Booths',wc,''],['Cycle',cycle,'']];
    if(cs){toplabel='Booths where '+(valliance||cs.winner)+' leads';metric=p=>{const cv=p.votes[cycle];return cv?cv.shares[valliance||cv.winner]||0:0;};fmt=v=>(v*100).toFixed(1)+'%';}
  } else {
    let yT=0,eT=0,tot=0,mT=0,fT=0;
    for(const f of fs){const p=f.properties;tot+=p.total;mT+=p.total_male;fT+=p.total_female;yT+=p.bands['18-21'].Total+p.bands['22-29'].Total;eT+=p.bands['60-69'].Total+p.bands['70+'].Total;}
    cards=[['Voters',tot.toLocaleString(),''],['M / F',tot?((mT/tot*100).toFixed(0)+'/'+(fT/tot*100).toFixed(0)):'-/-',''],['Under-30',tot?(yT/tot*100).toFixed(1)+'%':'-','of all'],['60+',tot?(eT/tot*100).toFixed(1)+'%':'-','of all']];
    if(dmode==='cohort'){toplabel='Top 5 &middot; '+dage+'/'+dsex;metric=p=>p.cohort_shares[dage+'|'+dsex]||0;fmt=v=>(v*100).toFixed(1)+'%';}
    else if(dmode==='youth'){toplabel='Top 5 &middot; '+(dyaxis==='youth_share'?'youth':'elderly');metric=p=>p[dyaxis];fmt=v=>(v*100).toFixed(1)+'%';}
    else if(dmode==='gender'){toplabel='Top 5 &middot; most male';metric=p=>p.male_ratio;fmt=v=>(v*100).toFixed(1)+'% M';}
    else if(dmode==='absolute'){toplabel='Top 5 &middot; largest '+dabs;metric=p=>p.cohort_shares[dabs+'|All']*p.total;fmt=v=>Math.round(v);}
    else if(dmode==='bandskew'){toplabel='Top 5 &middot; most-male '+dskew;metric=p=>p.band_gender_skew[dskew];fmt=v=>(v*100).toFixed(1)+'% M';}
    else {toplabel='Top 5 &middot; youngest';metric=p=>p.bands['18-21'].Total+p.bands['22-29'].Total;fmt=v=>v+' young';}
  }
  document.getElementById('cards').innerHTML=cards.map(c=>'<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+(c[2]?' <span class="unit">'+c[2]+'</span>':'')+'</div></div>').join('');
  if(metric){
    const ranked=fs.map(f=>[f.properties.part_no,f.properties.ac,f.properties.street||f.properties.locality||'?',metric(f.properties)]).sort((a,b)=>b[3]-a[3]).slice(0,5);
    document.getElementById('toplist').innerHTML='<div class="mini" style="margin-bottom:4px">'+toplabel+'</div>'+ranked.map((r,i)=>'<div class="row"><span class="rank">'+(i+1)+'</span><span class="name">'+r[1].replace('AC','')+'-'+r[0]+' &middot; '+r[2]+'</span><span class="val">'+fmt(r[3])+'</span></div>').join('');
  } else {document.getElementById('toplist').innerHTML='';}
}

function renderDonut(){
  const cs=getCs(cycle);
  const el=document.getElementById('donut');
  if(!cs||!cs.alliance_shares){el.innerHTML='';return;}
  const sorted=Object.entries(cs.alliance_shares).sort((a,b)=>b[1]-a[1]);
  const total=sorted.reduce((s,[,v])=>s+v,0);
  if(total<=0){el.innerHTML='';return;}
  const r=38,cx=50,cy=50,sw=12,C=2*Math.PI*r;
  let acc=0,arcs='';
  for(const [a,s] of sorted){
    const frac=s/total,dash=frac*C,off=-acc*C;
    const col=P.alliance_colors[a]||'#888';
    arcs+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${col}" stroke-width="${sw}" stroke-dasharray="${dash.toFixed(2)} ${(C-dash).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
    acc+=frac;
  }
  const w=cs.winner,ws=cs.alliance_shares[w];
  const svg=`<svg viewBox="0 0 100 100" width="100" height="100">${arcs}</svg>`;
  const center=`<div class="donut-center"><div class="dc-name" style="color:${P.alliance_colors[w]||'#fff'}">${w}</div><div class="dc-pct">${(ws*100).toFixed(1)}%</div></div>`;
  const top=sorted.slice(0,6);
  const rest=sorted.slice(6);
  const restPct=rest.reduce((s,[,v])=>s+v,0);
  let legItems=top.map(([a,s],i)=>`<div class="donut-leg-item${i===0?' lead':''}"><span class="wb-dot" style="background:${P.alliance_colors[a]||'#888'}"></span><span class="dl-name">${a}</span><span class="dl-val">${(s*100).toFixed(1)}%</span></div>`);
  if(restPct>0)legItems.push(`<div class="donut-leg-item"><span class="wb-dot" style="background:#555"></span><span class="dl-name">Others (${rest.length})</span><span class="dl-val">${(restPct*100).toFixed(1)}%</span></div>`);
  const legend=legItems.join('');
  let acSplit='';
  if(selectedAc==='ALL'){
    acSplit='<div class="donut-ac-split">';
    for(const [code,meta] of Object.entries(P.acs)){
      const acs=P.ac_summaries[code][cycle];
      if(!acs)continue;
      acSplit+=`<div class="das-row"><span class="das-name">${meta.name}</span><span class="wb-dot" style="background:${P.alliance_colors[acs.winner]||'#888'}"></span>${acs.winner} ${(acs.alliance_shares[acs.winner]*100).toFixed(1)}%</div>`;
    }
    acSplit+='</div>';
  }
  el.innerHTML=`<div class="donut-chart">${svg}${center}</div><div class="donut-legend">${legend}${acSplit}</div>`;
}

function renderLabels(){if(labelLayer){labelLayer.remove();labelLayer=null;}if(!document.getElementById('showLabels').checked)return;labelLayer=L.layerGroup().addTo(map);
  for(const f of visFeatures()){const ctr=L.geoJSON(f).getBounds().getCenter();L.tooltip({permanent:true,direction:'center',className:'ac18-label'}).setContent(String(f.properties.part_no)).setLatLng(ctr).addTo(labelLayer);}}

function renderOutline(){if(outlineLayer)outlineLayer.remove();if(!document.getElementById('showOutline').checked)return;
  outlineLayer=L.layerGroup().addTo(map);
  const hullsToShow = selectedAc==='ALL'?P.hulls:[P.hulls[P.acs[selectedAc].hull_idx]];
  for(const h of hullsToShow){L.geoJSON(h,{style:{weight:2,color:'#1565c0',dashArray:'6,4',fill:false,opacity:0.7}}).addTo(outlineLayer);}
  outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());}

function selectBooth(uid){
  selPart=uid;const f=P.geojson.features.find(x=>x.properties.uid===uid);if(!f)return;const p=f.properties;
  document.getElementById('infoTitle').textContent=p.ac.replace('AC','')+' Part '+p.part_no;
  document.getElementById('infoSub').innerHTML=(p.street||p.locality||'?')+' &middot; '+p.total.toLocaleString()+' voters &middot; M '+p.total_male+'/F '+p.total_female+' &middot; geocode: '+p.tier;
  let mx=0;for(const b of P.age_bands)mx=Math.max(mx,p.bands[b].Total);
  let py='';for(const b of P.age_bands){const bd=p.bands[b];const mh=bd.Total>0?(bd.Male/mx*100):0,fh=bd.Total>0?(bd.Female/mx*100):0;py+='<div class="pcol"><div class="pseg" style="height:'+fh+'%;background:#ec4899" title="'+b+' F '+bd.Female+'"></div><div class="pseg" style="height:'+mh+'%;background:#4fc3f7" title="'+b+' M '+bd.Male+'"></div></div>';}
  document.getElementById('pyramid').innerHTML=py;
  let t='<tr><th>Band</th><th>M</th><th>F</th><th>Tot</th><th>%</th></tr>';
  for(const b of P.age_bands){const bd=p.bands[b];const pct=p.total?(bd.Total/p.total*100).toFixed(1):'0.0';const w=mx?(bd.Total/mx*100).toFixed(0):0;t+='<tr><td>'+b+'</td><td>'+bd.Male+'</td><td>'+bd.Female+'</td><td>'+bd.Total+'</td><td><span class="bar" style="width:'+(w*0.5)+'px;background:'+P.band_colors[b]+'"></span> '+pct+'%</td></tr>';}
  document.getElementById('infoTable').innerHTML=t;
  let vh='<div class="src-label">🗳 FORM 20 &mdash; Vote shares by cycle (EVM only)</div>';
  for(const y of P.cycles){const cv=p.votes[y];if(!cv){vh+='<div class="wb-row"><span class="yr">'+y+'</span> no data</div>';continue;}
    const sorted=Object.entries(cv.shares).sort((a,b)=>b[1]-a[1]);
    vh+='<div class="wb-row"><span class="yr">'+y+'</span> '+sorted.map(([a,s])=>'<span class="wb-mini"><span class="wb-dot" style="background:'+(P.alliance_colors[a]||'#888')+'"></span>'+a+' '+(s*100).toFixed(0)+'%</span>').join(' ')+'</div>';}
  vh+='<div class="src-note">Top shares shown. Demographics above are from the Electoral Roll; votes are from Form 20 (EVM). These are independent datasets &mdash; one describes who can vote, the other how they voted.</div>';
  document.getElementById('infoVotes').innerHTML=vh;
  document.getElementById('infoPanel').style.display='block';render();
}
function clearSel(){selPart=null;document.getElementById('infoPanel').style.display='none';render();}

// ---- build dynamic controls ----
function buildAcBtns(){
  let html='<button class="ac-btn'+(selectedAc==='ALL'?' active':'')+'" data-ac="ALL">All</button>';
  for(const [code,meta] of Object.entries(P.acs)){
    html+='<button class="ac-btn'+(selectedAc===code?' active':'')+'" data-ac="'+code+'">'+meta.name+'</button>';
  }
  document.getElementById('acBtns').innerHTML=html;
  document.querySelectorAll('.ac-btn').forEach(b=>b.addEventListener('click',()=>{
    selectedAc=b.dataset.ac;
    document.querySelectorAll('.ac-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');
    valliance=null;
    buildAllianceBtns(); render(); renderOutline();
    if(selectedAc==='ALL'){
      map.fitBounds(cellLayer.getBounds().pad(0.05));
    } else {
      const acFeats=visFeatures();
      if(acFeats.length){const b=L.geoJSON({type:'FeatureCollection',features:acFeats}).getBounds();map.fitBounds(b.pad(0.05));}
    }
    updateStats();
  }));
}

function buildControls(){
  document.getElementById('cycleBtns').innerHTML=P.cycles.map(y=>'<button class="cycle-btn'+(y===cycle?' active':'')+'" data-cycle="'+y+'">'+y+'</button>').join('');
  document.querySelectorAll('.cycle-btn').forEach(b=>b.addEventListener('click',()=>{cycle=+b.dataset.cycle;document.querySelectorAll('.cycle-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(!valliance){const cs=getCs(cycle);valliance=cs?cs.winner:null;}buildAllianceBtns();render();}));
  document.getElementById('ageBtns').innerHTML=P.age_bands.map(b=>'<label><input type="radio" name="age" value="'+b+'"'+(b===dage?' checked':'')+'> '+b+'</label>').join('');
  document.getElementById('absBtns').innerHTML=P.age_bands.map(b=>'<button class="chip'+(b===dabs?' active':'')+'" data-abs="'+b+'">'+b+'</button>').join('');
  document.getElementById('skewBtns').innerHTML=P.age_bands.map(b=>'<button class="chip'+(b===dskew?' active':'')+'" data-skew="'+b+'">'+b+'</button>').join('');
  document.querySelectorAll('input[name=age]').forEach(el=>el.addEventListener('change',e=>{dage=e.target.value;render();}));
  document.querySelectorAll('[data-abs]').forEach(el=>el.addEventListener('click',()=>{dabs=el.dataset.abs;document.querySelectorAll('[data-abs]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
  document.querySelectorAll('[data-skew]').forEach(el=>el.addEventListener('click',()=>{dskew=el.dataset.skew;document.querySelectorAll('[data-skew]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
  buildAllianceBtns();
}
function buildAllianceBtns(){
  const cs=getCs(cycle);if(!cs)return;
  const alliances=Object.keys(cs.alliance_shares).sort((a,b)=>cs.alliance_shares[b]-cs.alliance_shares[a]);
  if(!valliance||!alliances.includes(valliance))valliance=alliances[0];
  document.getElementById('allianceBtns').innerHTML=alliances.map(a=>'<button class="chip'+(a===valliance?' active':'')+'" data-alliance="'+a+'" style="border-color:'+(P.alliance_colors[a]||'#888')+'"><span class="wb-dot" style="background:'+(P.alliance_colors[a]||'#888')+'"></span>'+a+'</button>').join('');
  document.querySelectorAll('[data-alliance]').forEach(el=>el.addEventListener('click',()=>{valliance=el.dataset.alliance;document.querySelectorAll('[data-alliance]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
}

function updateStats(){
  const n=selectedAc==='ALL'?P.n_booths:P.acs[selectedAc].n_booths;
  const v=selectedAc==='ALL'?P.n_voters:P.acs[selectedAc].n_voters;
  const acLabel=selectedAc==='ALL'?'all ACs':P.acs[selectedAc].name;
  document.getElementById('stats').innerHTML='<span>'+n+' booths</span><span>'+v.toLocaleString()+' voters</span><span>'+P.cycles.length+' cycles</span><span>'+acLabel+'</span>';
}

// ---- event wiring ----
function wireEvents(){
document.querySelectorAll('.domain-btn').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.domain-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');domain=b.dataset.domain;
  document.getElementById('votesControls').style.display=domain==='votes'?'block':'none';
  document.getElementById('demoControls').style.display=domain==='demo'?'block':'none';render();}));
document.querySelectorAll('.vmode-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.vmode-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');vmode=b.dataset.vmode;document.getElementById('shareControls').style.display=vmode==='share'?'block':'none';render();}));
document.querySelectorAll('.dmode-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.dmode-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');dmode=b.dataset.dmode;
  document.getElementById('cohortControls').style.display=dmode==='cohort'?'block':'none';
  document.getElementById('youthControls').style.display=dmode==='youth'?'block':'none';
  document.getElementById('absControls').style.display=dmode==='absolute'?'block':'none';
  document.getElementById('skewControls').style.display=dmode==='bandskew'?'block':'none';render();}));
document.querySelectorAll('input[name=sex]').forEach(el=>el.addEventListener('change',e=>{dsex=e.target.value;render();}));
document.querySelectorAll('input[name=yaxis]').forEach(el=>el.addEventListener('change',e=>{dyaxis=e.target.value;render();}));
document.getElementById('baseToggle').addEventListener('change',e=>{map.removeLayer(baseActive);baseActive=e.target.checked?baseSat:baseGrey;baseActive.addTo(map);if(cellLayer)cellLayer.bringToFront();if(outlineLayer)outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());});
document.getElementById('showOutline').addEventListener('change',renderOutline);
document.getElementById('showLabels').addEventListener('change',renderLabels);
document.getElementById('closeInfo').addEventListener('click',clearSel);
map.on('click',clearSel);
}

// ---- init ----
let map = null;
fetch('data.json').then(r=>r.json()).then(data=>{
  P = data;
  cycle = P.cycles[0];

  map = L.map('map', {zoomControl:true}).setView(P.center, 13);
  baseGrey = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    {attribution:'&copy; CARTO &copy; OSM', maxZoom:20});
  baseSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {attribution:'&copy; Esri', maxZoom:19});
  baseActive = baseGrey; baseGrey.addTo(map);

  buildAcBtns(); buildControls(); wireEvents(); updateStats();
  render(); renderOutline();
  map.fitBounds(cellLayer.getBounds().pad(0.05));
}).catch(err=>{
  document.body.innerHTML = '<div style="padding:40px;color:#e4e8ef;font-family:sans-serif"><h2>Failed to load data</h2><p>Run <code>python scripts/build_data.py</code> to generate data.json first.</p><pre>'+err+'</pre></div>';
});
