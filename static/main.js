// ── Theme ────────────────────────────────────────────────────────────────────
const savedTheme=localStorage.getItem('tk-theme')||'dark';
document.body.className=savedTheme==='light'?'light':'';
function toggleTheme(){const l=document.body.classList.toggle('light');localStorage.setItem('tk-theme',l?'light':'dark');}

// ── Clock ────────────────────────────────────────────────────────────────────
function updateClock(){const c=document.getElementById('live-clock');if(!c)return;const now=new Date();c.textContent=now.toLocaleDateString('hi-IN',{weekday:'short',day:'numeric',month:'short',year:'numeric'})+' '+now.toLocaleTimeString('hi-IN',{hour:'2-digit',minute:'2-digit'});}
setInterval(updateClock,1000);updateClock();

// ── Mobile Nav ───────────────────────────────────────────────────────────────
function toggleNav(){document.getElementById('main-nav').classList.toggle('open');}

// ── Reading Progress ─────────────────────────────────────────────────────────
window.addEventListener('scroll',()=>{const el=document.getElementById('read-progress');if(!el)return;const doc=document.documentElement;const s=doc.scrollTop||document.body.scrollTop;const h=doc.scrollHeight-doc.clientHeight;el.style.width=h>0?Math.min(100,s/h*100)+'%':'0';const btt=document.getElementById('btt');if(btt){btt.classList.toggle('show',s>300);}},{passive:true});

// ── Shimmer → Fade In ────────────────────────────────────────────────────────
function fadeIn(img){const shimmer=img.previousElementSibling;if(shimmer&&shimmer.classList.contains('shimmer')){shimmer.classList.add('loaded');}img.classList.add('lazy-loaded');}

// ── Search Autocomplete ───────────────────────────────────────────────────────
const srch=document.getElementById('srch');const sug=document.getElementById('srch-suggest');if(srch&&sug){let timer;srch.addEventListener('input',()=>{clearTimeout(timer);const q=srch.value.trim();if(q.length<2){sug.classList.remove('show');return;}timer=setTimeout(()=>{fetch('/api/search?q='+encodeURIComponent(q)).then(r=>r.json()).then(data=>{if(data.results&&data.results.length){sug.innerHTML=data.results.map(r=>`<div class="suggest-item" onclick="location.href='/article/${r.slug}'">${r.title}</div>`).join('');sug.classList.add('show');}else{sug.classList.remove('show');}}).catch(()=>sug.classList.remove('show'));},300);});document.addEventListener('click',e=>{if(!srch.contains(e.target)&&!sug.contains(e.target))sug.classList.remove('show');});}

// ── Breaking News API Refresh ─────────────────────────────────────────────────
function refreshBreaking(){fetch('/api/breaking').then(r=>r.json()).then(d=>{const t=document.getElementById('ticker');if(t&&d.breaking)t.textContent=d.breaking;}).catch(()=>{});}
setInterval(refreshBreaking,120000);

// ── Font Size ────────────────────────────────────────────────────────────────
let fontSize=parseInt(localStorage.getItem('tk-fontsize')||'16');
function applyFontSize(){const b=document.getElementById('art-body');if(b)b.style.fontSize=fontSize+'px';}
function changeFontSize(d){fontSize=Math.min(22,Math.max(12,fontSize+d));localStorage.setItem('tk-fontsize',fontSize);applyFontSize();}
document.addEventListener('DOMContentLoaded',applyFontSize);

// ── Newsletter ────────────────────────────────────────────────────────────────
function subscribeNewsletter(e){e.preventDefault();const input=e.target.querySelector('input[type=email]');if(input){const email=input.value.trim();if(email){input.value='';alert(`✅ Subscribe ho gaya!\n${email} pe khabrain aayengi.`);}}return false;}

// ── Weather Widget ────────────────────────────────────────────────────────────
function loadWeather(){const el=document.getElementById('weather-body');if(!el)return;fetch('https://wttr.in/Delhi?format=%C+%t').then(r=>r.text()).then(text=>{el.innerHTML=`<p style="font-size:15px;padding:12px">${text}</p>`;}).catch(()=>{if(el)el.innerHTML='<p style="padding:12px;color:#555;font-size:12px">Weather unavailable</p>';});}
document.addEventListener('DOMContentLoaded',loadWeather);

// ── Copy Link ────────────────────────────────────────────────────────────────
function copyLink(){navigator.clipboard.writeText(window.location.href).then(()=>{const btn=document.querySelector('.share-btn.copy');if(btn){const orig=btn.textContent;btn.textContent='✅ Copied!';setTimeout(()=>btn.textContent=orig,2000);}}).catch(()=>alert('Link: '+window.location.href));}

// ── Flash Messages Auto-hide ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.flash').forEach(f=>{setTimeout(()=>{if(f&&f.parentElement)f.style.transition='opacity .5s';f.style.opacity='0';setTimeout(()=>{if(f&&f.parentElement)f.remove();},500);},6000);});});

