const API=location.origin;
const SCENES=[
  "今天下午是空的，想带老婆孩子出去玩几个小时。孩子5岁，老婆最近在减肥，帮我安排一下下午4-6小时的行程，玩完顺便吃个晚饭",
  "下午和3个朋友（2男2女）出去玩几个小时，帮我们安排一下，要好玩不无聊，玩完找个地方吃饭",
  "今天下午想和老婆约会，安排个浪漫的下午+晚餐，预算500左右",
  "下午带5岁孩子出去玩，寓教于乐那种，不要太远，玩到晚饭前回来",
  "今天下午想一个人待会儿，找个安静的地方喝咖啡看书，顺便吃个简餐",
  "晚上6个朋友聚会，帮我们找个好玩的地方，再安排晚饭"
];
const T_ICON={weather_api:['cloud-sun','w'],search_poi:['search','s'],book_restaurant:['utensils','b'],check_queue:['ticket','q'],order_delivery:['package','d'],book_venue:['landmark','b']};

// Meituan capability palette — keys must match poi_data.CAPABILITY_VOCAB
const CAP_STYLES={
  '团购券':'cap-coupon','闪送':'cap-flash','会员折扣':'cap-member',
  '秒杀':'cap-flash','积分':'cap-member','扫码点餐':'cap-scan','免预约':'cap-noresv',
};

function _capChipsHTML(t){
  const params=t?.params||{};
  const tags=Array.isArray(params.capability_tags)?params.capability_tags:[];
  const label=typeof params.deal_label==='string'?params.deal_label:'';
  if(!tags.length&&!label)return '';
  const chips=[];
  if(label)chips.push(`<span class="t-cap cap-coupon">${esc(label)}</span>`);
  tags.forEach(tag=>{
    if(label&&tag==='团购券')return; // 已在 deal_label 里展示
    const cls=CAP_STYLES[tag]||'cap-default';
    chips.push(`<span class="t-cap ${cls}">${esc(tag)}</span>`);
  });
  return chips.length?`<div class="t-caps">${chips.join('')}</div>`:'';
}
const C_COLOR={'餐厅':'#EF4444','咖啡馆':'#F59E0B','儿童乐园':'#FFD100','KTV':'#8B5CF6','会议室':'#3B82F6','博物馆':'#06B6D4','小吃街':'#F97316','轰趴馆':'#EC4899','密室逃脱':'#8B5CF6','书店':'#6366F1','花店':'#22C55E','SPA':'#14B8A6','电影院':'#A855F7','甜品店':'#EAB308','公园':'#22C55E','户外拓展':'#059669','桌游':'#7C3AED','电竞馆':'#6366F1','射箭':'#DC2626','保龄球':'#2563EB','陶艺':'#D97706','猫咖':'#F472B6','VR体验':'#8B5CF6','步行街':'#F97316','剧本杀':'#A855F7','酒店':'#0EA5E9','台球':'#7C3AED','健身房':'#059669','水族馆':'#06B6D4','动物园':'#22C55E'};
const C_ICON={'餐厅':'🍽️','咖啡馆':'☕','儿童乐园':'🎪','KTV':'🎤','会议室':'💼','博物馆':'🏛️','小吃街':'🍜','轰趴馆':'🎉','密室逃脱':'🔐','公园':'🌳','书店':'📚','花店':'💐','SPA':'💆','电影院':'🎬','甜品店':'🍰','户外拓展':'🏕️','桌游':'🎲','电竞馆':'🎮','射箭':'🏹','保龄球':'🎳','陶艺':'🏺','猫咖':'🐱','VR体验':'🥽','步行街':'🚶','剧本杀':'🎭','酒店':'🏨','台球':'🎱','健身房':'💪','水族馆':'🐠','动物园':'🦁'};
const TRANSPORT_ICON={walk:'🚶',bike:'🚲',taxi:'🚕',transit:'🚇',drive:'🚗'};

let sid=null,busy=false,lastInput='',lastEnableStory=false,currentAbortCtrl=null;
let _isLiveMode=false;
let _lastPlanData=null;  // last rendered plan (for diff overlay + restoration)

// ===== Module-level Leaflet state — enables in-place map patching =====
let _activeMap=null;          // current Leaflet map instance
let _activeMarkers={};        // poi_id -> Leaflet marker
let _activeRouteLines=[];     // polyline + label markers, cleared on patch
let _activeRoute=[];          // ordered route nodes currently rendered
let _activeRouteCard=null;    // current .route-card DOM root

// ===== 会话状态持久化（localStorage）=====
const STATE_KEY='mt_state_v2';
function saveState(){
  try{
    localStorage.setItem(STATE_KEY,JSON.stringify({sid,lastPlan:_lastPlanData}));
  }catch(e){console.warn('saveState failed:',e);}
}
function restoreState(){
  try{
    const raw=localStorage.getItem(STATE_KEY);
    if(!raw)return;
    const s=JSON.parse(raw);
    if(s.sid)sid=s.sid;
    if(s.lastPlan)_lastPlanData=s.lastPlan;
  }catch(e){console.warn('restoreState failed:',e);}
}
restoreState();

// Lucide icon refresh — call after dynamic DOM inserts
function refreshIcons(root){
  if(typeof lucide!=='undefined')lucide.createIcons({root:root||document});
}

// 强制刷新后回到顶部
if('scrollRestoration' in history) history.scrollRestoration='manual';
window.scrollTo(0,0);

// Loader
setTimeout(()=>document.getElementById('loader').classList.add('done'),700);
setTimeout(()=>document.querySelectorAll('.enter').forEach(el=>el.classList.add('show')),800);

// 模式指示器：页面加载时检测 LLM 模式
(async()=>{
  try{
    const r=await fetch(`${API}/api/agent/health`);
    const d=await r.json();
    _isLiveMode=d.llm_mode==='live';
    const pill=document.querySelector('.nav-pill');
    if(pill){
      pill.innerHTML=_isLiveMode
        ?'<div class="nav-dot"></div>MiMo Live'
        :'<div class="nav-dot" style="background:var(--orange)"></div>Mock 模式';
      pill.title=_isLiveMode?'使用 MiMo-v2.5-pro 真实模型':'离线演示模式，结果为模拟数据';
    }
  }catch(e){
    console.warn('Health check failed:',e);
  }
})();

// Scrollspy
(function(){
  const sections=['planner','demo','how','tools','diff','arch'].map(id=>document.getElementById(id)).filter(Boolean);
  const links=[...document.querySelectorAll('.nav-link')];
  function update(){
    const scrollY=window.scrollY+80;
    let current='';
    for(const sec of sections){if(sec.offsetTop<=scrollY)current=sec.id}
    links.forEach(a=>{
      const href=a.getAttribute('href').slice(1);
      a.classList.toggle('active',href===current&&href!=='demo');
    });
  }
  let ticking=false;
  window.addEventListener('scroll',()=>{if(!ticking){requestAnimationFrame(()=>{update();ticking=false});ticking=true}},{passive:true});
  update();
})();

function pickScene(i){document.querySelectorAll('.sc').forEach((el,j)=>el.classList.toggle('active',j===i));document.getElementById('inp').value=SCENES[i];document.getElementById('inp').focus()}
function fill(t){document.getElementById('inp').value=t;document.getElementById('inp').focus()}
function resetChat(){sid=null;_lastPlanData=null;saveState();document.getElementById('msgs').innerHTML=welcomeHTML()}

// ===== 历史会话面板 =====
function toggleHistory(){
  const panel=document.getElementById('historyPanel');
  const isOpen=panel.classList.toggle('open');
  if(isOpen)loadHistory();
}

async function loadHistory(){
  const list=document.getElementById('historyList');
  list.innerHTML='<div class="hp-empty">加载中...</div>';
  try{
    const r=await fetch(`${API}/api/agent/sessions?limit=20`);
    const sessions=await r.json();
    if(!sessions.length){
      list.innerHTML='<div class="hp-empty">暂无历史会话</div>';
      return;
    }
    let html='<button class="hp-new" onclick="startNewSession()">+ 新对话</button>';
    sessions.forEach(s=>{
      const t=new Date(s.updated_at);
      const timeStr=`${t.getMonth()+1}/${t.getDate()} ${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}`;
      const isActive=sid===s.session_id;
      html+=`<div class="hp-item${isActive?' active':''}" onclick="restoreSession('${s.session_id}')">
        <div class="hp-item-time">${timeStr}</div>
        <div class="hp-item-msg">${esc(s.last_message||'空会话')}</div>
        <div class="hp-item-count">${s.message_count} 条消息</div>
      </div>`;
    });
    list.innerHTML=html;
  }catch(e){
    list.innerHTML='<div class="hp-empty">加载失败</div>';
  }
}

function startNewSession(){
  sid=null;
  _lastPlanData=null;
  saveState();
  document.getElementById('msgs').innerHTML=welcomeHTML();
  toggleHistory();
}

async function restoreSession(sessionId){
  sid=sessionId;
  _lastPlanData=null;  // server-side state; if user modifies we'll re-run full plan
  saveState();
  // 清空聊天并显示恢复提示
  document.getElementById('msgs').innerHTML='';
  addMsg('bot','<span style="color:var(--t3)">📂 已恢复历史会话，可继续对话或重新规划</span>');
  // 关闭面板
  document.getElementById('historyPanel').classList.remove('open');
}
function welcomeHTML(){return`<div class="welcome" id="welcome"><div class="welcome-icon">🏙️</div><h3>你好，我是美团 AI 行程规划师</h3><p>选择下方场景快速体验，或直接在输入框描述你的需求</p><div class="welcome-chips"><div class="chip" onclick="pickScene(0)">家庭下午</div><div class="chip" onclick="pickScene(1)">朋友下午</div><div class="chip" onclick="pickScene(2)">情侣约会</div><div class="chip" onclick="pickScene(3)">亲子时光</div><div class="chip" onclick="pickScene(4)">独处充电</div><div class="chip" onclick="pickScene(5)">多人聚会</div></div><div style="margin-top:12px;font-size:11px;color:var(--t4)">验收？试试这 6 个场景，详见项目 VERIFY.md</div></div>`}
function esc(s){return s?String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):''}

function _msgTime(){const d=new Date();return`${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`}
function addMsg(type,html){
  const w=document.getElementById('welcome');if(w)w.remove();
  const d=document.createElement('div');d.className=`msg ${type}`;
  d.innerHTML=`<div class="msg-av"><i data-lucide="${type==='user'?'user':'bot'}" style="width:16px;height:16px"></i></div><div class="msg-body"><div class="msg-bubble">${html}</div><div class="msg-ts">${_msgTime()}</div></div>`;
  const box=document.getElementById('msgs');box.appendChild(d);box.scrollTop=box.scrollHeight;refreshIcons(d);return d;
}

// Multi-step thinking indicator (SSE-driven)
function addThinking(){
  const w=document.getElementById('welcome');if(w)w.remove();
  const d=document.createElement('div');d.className='msg bot';d.id='thinkMsg';
  d.innerHTML=`<div class="msg-av"><i data-lucide="bot" style="width:16px;height:16px"></i></div><div class="msg-body"><div class="thinking">
    <div class="think-steps" id="thinkSteps"></div>
    <div class="think-bar"><div class="think-bar-inner" id="thinkBar"></div></div>
    <div class="think-chunk" id="thinkChunk"></div>
    <div style="font-size:11px;color:var(--t4);margin-top:8px" id="thinkTimer">正在规划... 0s</div>
  </div></div>`;
  const box=document.getElementById('msgs');box.appendChild(d);box.scrollTop=box.scrollHeight;refreshIcons(d);
  return{
    el:d,
    addStep:(stepId,text)=>{
      const container=document.getElementById('thinkSteps');
      const div=document.createElement('div');
      div.className='think-step active';
      div.id='ts-'+stepId;
      div.innerHTML=`<div class="think-icon"><span class="think-spinner"></span></div><span>${esc(text)}</span>`;
      container.appendChild(div);
      box.scrollTop=box.scrollHeight;
    },
    doneStep:(stepId,text)=>{
      const div=document.getElementById('ts-'+stepId);
      if(div){
        div.classList.remove('active');
        div.classList.add('done');
        div.querySelector('.think-icon').innerHTML='<span class="think-check">✓</span>';
        if(text)div.querySelector('span:last-child').textContent=text;
      }
      // 更新进度条
      const steps=document.querySelectorAll('#thinkSteps .think-step');
      const done=document.querySelectorAll('#thinkSteps .think-step.done');
      const bar=document.getElementById('thinkBar');
      if(bar)bar.style.width=Math.round((done.length/steps.length)*100)+'%';
    },
    appendChunk:(text)=>{
      const chunk=document.getElementById('thinkChunk');
      if(chunk)chunk.textContent+=text;
      box.scrollTop=box.scrollHeight;
    },
    stop:()=>{
      const bar=document.getElementById('thinkBar');
      if(bar)bar.style.width='100%';
      // 标记所有未完成的步骤为完成
      document.querySelectorAll('#thinkSteps .think-step.active').forEach(el=>{
        el.classList.remove('active');el.classList.add('done');
        el.querySelector('.think-icon').innerHTML='<span class="think-check">✓</span>';
      });
    }
  };
}

function setBusy(v){
  busy=v;
  const sendBtn=document.getElementById('sendBtn');
  sendBtn.disabled=v;
  // 流式输出中显示取消按钮
  if(v){
    sendBtn.innerHTML='<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
    sendBtn.title='取消';
    sendBtn.onclick=cancelStream;
  }else{
    sendBtn.innerHTML='<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
    sendBtn.title='发送';
    sendBtn.onclick=send;
  }
}

let _sendDebounce=false;
function cancelStream(){
  if(currentAbortCtrl){
    currentAbortCtrl.abort();
    currentAbortCtrl=null;
  }
}

async function send(){
  // 防抖：300ms 内多次点击只触发一次
  if(_sendDebounce)return;
  _sendDebounce=true;
  setTimeout(()=>{_sendDebounce=false},300);
  const inp=document.getElementById('inp');const txt=inp.value.trim();
  if(!txt||busy)return;setBusy(true);inp.value='';
  lastInput=txt;
  lastEnableStory=document.getElementById('storyToggle')?.checked||false;
  document.querySelectorAll('.sc').forEach(el=>el.classList.remove('active'));
  addMsg('user',esc(txt));

  // 多轮对话分支：已有 plan 时走 /continue 端点（局部修改 / 普通对话）
  if(sid && _lastPlanData){
    await sendContinue(txt);
    setBusy(false);
    return;
  }

  const think=addThinking();
  let sec=0;const timer=setInterval(()=>{
    sec++;const el=document.getElementById('thinkTimer');
    if(el)el.textContent=sec>8?`AI 思考中... ${sec}s`:`正在规划... ${sec}s`;
  },1000);
  const t0=Date.now();
  try{
    currentAbortCtrl=new AbortController();
    const timeout=setTimeout(()=>currentAbortCtrl.abort(),90000);
    const response=await fetch(`${API}/api/agent/execute/stream`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({userInput:txt,sessionId:sid,enableStory:lastEnableStory}),
      signal:currentAbortCtrl.signal
    });
    clearTimeout(timeout);
    if(!response.ok){
      const err=await response.json();
      throw new Error(err.message||'请求失败');
    }
    const reader=response.body.getReader();
    const decoder=new TextDecoder();
    let buffer='',finalData=null,_eventCount=0;
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buffer+=decoder.decode(value,{stream:true});
      const lines=buffer.split('\n');
      buffer=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        try{
          const event=JSON.parse(line.slice(6));
          _eventCount++;
          if(event.type==='step'){
            if(event.step.endsWith('_done'))think.doneStep(event.step,event.text);
            else think.addStep(event.step,event.text);
          }else if(event.type==='chunk'){
            think.appendChunk(event.text);
          }else if(event.type==='done'){
            finalData=event.data;
          }else if(event.type==='error'){
            throw new Error(event.text);
          }
        }catch(parseErr){
          if(parseErr.message&&!parseErr.message.includes('JSON'))throw parseErr;
          console.warn('SSE parse error:',parseErr);
        }
      }
    }
    const s=((Date.now()-t0)/1000).toFixed(1);
    clearInterval(timer);think.stop();
    _trackStreamResponse(_eventCount,Date.now()-t0);
    setTimeout(()=>{
      if(finalData){
        sid=finalData.session_id||finalData.sessionId;
        renderPlan(finalData,s);
        // 渐隐 thinking（先渲染 plan 再移除，避免闪烁）
        think.el.style.transition='opacity .3s';
        think.el.style.opacity='0';
        setTimeout(()=>think.el.remove(),300);
        // 滚动到结果
        setTimeout(()=>{
          const msgs=document.getElementById('msgs');
          const lastMsg=msgs.lastElementChild;
          if(lastMsg)lastMsg.scrollIntoView({behavior:'smooth',block:'start'});
        },100);
      }else{
        think.el.remove();
        addMsg('bot','<span style="color:var(--red)"><i data-lucide="x-circle" style="width:14px;height:14px"></i> 未收到完整响应，请重试</span><div style="margin-top:8px"><button class="retry-btn" onclick="retryLastInput()"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> 重新发送</button></div>');
      }
    },200);
  }catch(e){
    clearInterval(timer);think.el.remove();
    currentAbortCtrl=null;
    if(e.name==='AbortError'){
      // 区分用户取消和超时
      const msg=lastInput?'已取消':'请求超时（90s）';
      addMsg('bot',`<span style="color:var(--red)"><i data-lucide="x-circle" style="width:14px;height:14px"></i> ${msg}</span><div style="margin-top:8px"><button class="retry-btn" onclick="retryLastInput()"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> 重新发送</button></div>`);
    }else{
      addMsg('bot',`<span style="color:var(--red)"><i data-lucide="x-circle" style="width:14px;height:14px"></i> ${esc(e.message)}</span><div style="margin-top:8px"><button class="retry-btn" onclick="retryLastInput()"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> 重试</button></div>`);
    }
  }
  setBusy(false);
}

function retryLastInput(){
  if(!lastInput||busy)return;
  document.getElementById('inp').value=lastInput;
  send();
}

// ===== 多轮对话：修改 / 普通回复 =====

const ERROR_REASON_LABELS={
  no_candidate:'找不到候选',
  busy_hours:'营业时间',
  over_budget:'超预算',
  location_mismatch:'目标不明',
  unknown:'未识别',
};

function renderErrorCard(entry){
  const reasonCode=entry?.reason_code||'unknown';
  const reasonLabel=ERROR_REASON_LABELS[reasonCode]||reasonCode;
  const message=entry?.message||'操作失败';
  const suggestions=Array.isArray(entry?.suggestions)?entry.suggestions:[];
  const chipsHTML=suggestions.map(s=>
    `<button class="err-chip" data-hint="${esc(s.hint||'')}" onclick="onSuggestionClick(this)">${esc(s.label||'')}</button>`
  ).join('');
  return `<div class="error-card">
    <div class="error-card-header">
      <span class="error-card-badge">${esc(reasonLabel)}</span>
      <span class="error-card-msg">${esc(message)}</span>
    </div>
    ${chipsHTML?`<div class="error-card-chips">${chipsHTML}</div>`:''}
  </div>`;
}

function onSuggestionClick(btn){
  const hint=btn.getAttribute('data-hint');
  if(!hint)return;
  const inp=document.getElementById('inp');
  if(!inp)return;
  inp.value=hint;
  inp.focus();
  inp.dispatchEvent(new Event('input'));
  inp.scrollIntoView({behavior:'smooth',block:'center'});
}

async function sendContinue(txt){
  // 显示简短 thinking
  const thinkEl=addMsg('bot','<div class="thinking-inline"><span class="think-spinner"></span> 正在处理...</div>');
  const t0=Date.now();
  try{
    const r=await fetch(`${API}/api/agent/continue`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({userInput:txt,sessionId:sid})
    });
    if(!r.ok){
      const err=await r.json();
      throw new Error(err.message||'请求失败');
    }
    const d=await r.json();
    thinkEl.remove();
    _trackContinueResponse(d,Date.now()-t0);

    if(d.status==='plan_modified'){
      // 局部修改成功：叠加 diff 高亮 + 更新摘要 + 替换路线渲染
      applyChangeLog(d.changeLog||[],d.planSummary||'',d);
      if(d.route?.length){
        // 用更新后的 plan 数据替换 _lastPlanData（route + stats 已经是最新）
        _lastPlanData={
          ..._lastPlanData,
          route:d.route,
          route_stats:d.routeStats||d.route_stats||_lastPlanData?.route_stats,
          tasks:d.tasks||[],
          plan_summary:d.planSummary,
          planSummary:d.planSummary,
        };
        saveState();
      }
    }else if(d.status==='plan_modify_failed'){
      const errEntry=(d.changeLog&&d.changeLog[0])||{message:d.reply||'修改失败'};
      addMsg('bot',renderErrorCard(errEntry));
    }else if(d.status==='replanned'){
      // 重新规划：渲染新方案
      _lastPlanData=d;
      saveState();
      renderPlan(d,((Date.now()-t0)/1000).toFixed(1));
    }else{
      // 普通对话回复
      const reply=d.reply||d.planSummary||'收到～';
      addMsg('bot',esc(reply));
    }
  }catch(e){
    thinkEl.remove();
    addMsg('bot',`<span style="color:var(--red)"><i data-lucide="x-circle" style="width:14px;height:14px"></i> ${esc(e.message)}</span><div style="margin-top:8px"><button class="retry-btn" onclick="retryLastInput()"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> 重试</button></div>`);
    refreshIcons();
  }
}

// ===== Diff 高亮：在最近一个 plan 卡片上叠加变更标识 =====
function applyChangeLog(changeLog,newSummary,fullData){
  if(!changeLog||!changeLog.length){
    if(newSummary)addMsg('bot',esc(newSummary));
    return;
  }
  // 找到最近一个 plan 卡片（route-card 容器）
  const allCards=document.querySelectorAll('.route-card');
  const latestCard=allCards[allCards.length-1];

  // 推送变更摘要消息
  const summaryHTML=[];
  changeLog.forEach(entry=>{
    if(entry.type==='replace'){
      const b=entry.before?.name||'?';
      const a=entry.after?.name||'?';
      summaryHTML.push(`<div class="change-line change-replace">🔄 已把「${esc(b)}」换成「${esc(a)}」</div>`);
    }else if(entry.type==='remove'){
      const n=entry.removed?.name||'?';
      summaryHTML.push(`<div class="change-line change-remove">✕ 已删除「${esc(n)}」</div>`);
    }else if(entry.type==='insert'){
      const n=entry.inserted?.name||'?';
      summaryHTML.push(`<div class="change-line change-insert">＋ 已加入「${esc(n)}」</div>`);
    }else if(entry.type==='shift_time'){
      summaryHTML.push(`<div class="change-line change-shift">🕐 时间已调整到 ${esc(entry.new_start||'')}</div>`);
    }else if(entry.type==='preference_noted'){
      const noted=entry.noted||{};
      const tag=noted.category||noted.location||noted.tag||'你的偏好';
      summaryHTML.push(`<div class="change-line change-pref">✓ 已记下：下次不再推荐「${esc(tag)}」</div>`);
    }else if(entry.type==='warning'){
      summaryHTML.push(`<div class="change-line change-warn">⚠️ ${esc(entry.message||'')}</div>`);
    }else if(entry.type==='error'){
      summaryHTML.push(renderErrorCard(entry));
    }
  });
  if(newSummary){
    summaryHTML.unshift(`<div class="change-summary">${esc(newSummary)}</div>`);
  }
  addMsg('bot',`<div class="change-card">${summaryHTML.join('')}</div>`);

  // 在最近 plan 卡片上叠加视觉高亮（短暂）
  if(latestCard){
    changeLog.forEach(entry=>{
      if(entry.type==='replace'){
        const beforeId=entry.before?.poi_id;
        const afterId=entry.after?.poi_id;
        // 老节点淡出红色，1.5s 后移除
        if(beforeId){
          latestCard.querySelectorAll(`.route-stop-item[data-poi-id="${beforeId}"]`).forEach(el=>{
            el.classList.add('diff-removed');
            setTimeout(()=>el.classList.remove('diff-removed'),2000);
          });
        }
        if(afterId){
          latestCard.querySelectorAll(`.route-stop-item[data-poi-id="${afterId}"]`).forEach(el=>{
            el.classList.add('diff-replaced');
            setTimeout(()=>el.classList.remove('diff-replaced'),3500);
          });
        }
      }else if(entry.type==='remove'){
        const id=entry.removed?.poi_id;
        if(id){
          latestCard.querySelectorAll(`.route-stop-item[data-poi-id="${id}"]`).forEach(el=>{
            el.classList.add('diff-removed');
          });
        }
      }else if(entry.type==='insert'){
        const id=entry.inserted?.poi_id;
        if(id){
          latestCard.querySelectorAll(`.route-stop-item[data-poi-id="${id}"]`).forEach(el=>{
            el.classList.add('diff-inserted');
            setTimeout(()=>el.classList.remove('diff-inserted'),3500);
          });
        }
      }
    });
  }

  // In-place update of map + sidebar + stats bar — preserves the existing card.
  // Wait ~600ms so the user notices the diff flash before items shift.
  if(fullData?.route?.length){
    setTimeout(()=>{
      patchMap(changeLog,fullData.route);
      patchSidebar(fullData.route,changeLog);
      if(fullData.route_stats||fullData.routeStats){
        patchStatsBar(fullData.route_stats||fullData.routeStats,fullData.route.length);
      }
    },600);
  }
}

// ===== 格式化工具 =====
function fmtDuration(mins){
  if(mins>=60){const h=Math.floor(mins/60);const m=mins%60;return m>0?`${h}小时${m}分钟`:`${h}小时`}
  return `${mins}分钟`
}
function fmtDistance(m){
  if(m>=1000)return `${(m/1000).toFixed(1)}km`
  return `${Math.round(m)}m`
}
function fmtCost(c){return `¥${c}`}

// ===== 渲染行程方案 =====
function renderPlan(d,s){
  let h='';

  // 故事区块（如果有）
  if(d.story&&d.story.title){
    h+=`<div class="result-section" role="article" aria-label="剧本杀故事"><div class="story"><div class="story-hd"><div class="story-badge"><i data-lucide="theater" style="width:14px;height:14px"></i> 剧本杀 CITYWALK</div><div class="story-title">${esc(d.story.title)}</div><div class="story-theme">${esc(d.story.theme||'')}</div></div><div class="story-desc">${esc(d.story.description||'')}</div>`;
    if(d.story.checkpoints?.length){
      h+='<div class="cps cps-timeline">';
      d.story.checkpoints.forEach((c,i)=>{
        const isLast=i===d.story.checkpoints.length-1;
        h+=`<div class="cp-tl${isLast?' cp-last':''}">
          <div class="cp-tl-connector"><div class="cp-tl-dot">${i+1}</div>${!isLast?'<div class="cp-tl-line"></div>':''}</div>
          <div class="cp-tl-content"><div class="cp-name">${esc(c.poi_name)}</div><div class="cp-text">${esc(c.narrative)}</div><div class="cp-task"><i data-lucide="target" style="width:12px;height:12px"></i> ${esc(c.task)}</div></div>
        </div>`;
      });
      h+='</div>';
    }
    h+='</div></div>';
  }

  // 方案摘要
  if(d.plan_summary||d.planSummary){
    const sm=(d.plan_summary||d.planSummary).replace(/^🎭[^]*?\n\n/,'').trim();
    if(sm)h+=`<div class="result-section"><div class="summary">${esc(sm)}</div></div>`;
  }

  // 路线卡片
  if(d.route?.length){
    const stats=d.route_stats||d.routeStats||{};
    h+=`<div class="result-section" role="article" aria-label="路线规划"><div class="route-card">`;

    // 统计条
    h+=`<div class="route-stats-bar">
      <div class="rs-item"><span class="rs-icon"><i data-lucide="clock" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtDuration(stats.total_duration||0)}</span><span class="rs-label">总时长</span></div>
      <div class="rs-item"><span class="rs-icon"><i data-lucide="map-pin" style="width:14px;height:14px"></i></span><span class="rs-val">${stats.poi_count||d.route.length}站</span><span class="rs-label">途经站点</span></div>
      <div class="rs-item"><span class="rs-icon"><i data-lucide="footprints" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtDistance(stats.walking_distance||0)}</span><span class="rs-label">步行距离</span></div>
      <div class="rs-item"><span class="rs-icon"><i data-lucide="wallet" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtCost(stats.total_cost||0)}</span><span class="rs-label">预估花费</span></div>
      ${stats.total_savings?`<div class="rs-item rs-save"><span class="rs-icon"><i data-lucide="flame" style="width:14px;height:14px"></i></span><span class="rs-val">省${fmtCost(stats.total_savings)}</span><span class="rs-label">团购优惠</span></div>`:''}
    </div>`;

    // 地图 + 侧边栏
    h+=`<div class="route-view-toggle" id="routeViewToggle"><button class="rvt-btn active" data-view="map" aria-label="显示地图"><i data-lucide="map" style="width:14px;height:14px"></i> 地图</button><button class="rvt-btn" data-view="list" aria-label="显示列表"><i data-lucide="list" style="width:14px;height:14px"></i> 列表</button></div>`;
    h+=`<div class="route-main">`;
    h+=`<div id="routeMap" class="route-map"></div>`;
    h+=`<div class="route-sidebar">`;
    h+=`<div class="route-stop-list">`;
    d.route.forEach((r,i)=>{
      const c=C_COLOR[r.category]||'#FFD100';
      const ic=C_ICON[r.category]||'📍';
      h+=`<div class="route-stop-item${i===0?' active':''}" data-idx="${i}" data-poi-id="${esc(r.poi_id||'')}" role="button" tabindex="0" aria-label="第${i+1}站：${r.poi_name}，${r.category}" onkeydown="if(event.key==='Enter')this.click()">
        <div class="rsi-dot" style="background:${c}">${i+1}</div>
        <div class="rsi-icon">${ic}</div>
        <div class="rsi-info"><div class="rsi-name">${esc(r.poi_name)}</div><div class="rsi-time">${esc(r.arrival_time||'')} - ${esc(r.departure_time||'')}</div></div>
      </div>`;
    });
    h+=`</div>`;
    h+=`<div class="route-stop-detail" id="routeDetail"></div>`;
    h+=`</div></div>`; // route-sidebar, route-main

    h+=`</div></div>`; // route-card, result-section
  }

  // 任务列表
  const taskList=d.tasks||d.tasks_preview||[];
  if(taskList.length){
    h+=`<div class="result-section" role="article" aria-label="执行任务列表"><div class="task-card"><div class="task-hd"><i data-lucide="list-checks" style="width:16px;height:16px"></i> AI 将自动执行以下任务</div>`;
    taskList.forEach(t=>{const[ic,cl]=T_ICON[t.tool_name]||['tag','s'];h+=`<div class="t-row"><div class="t-icon ${cl}"><i data-lucide="${ic}" style="width:16px;height:16px"></i></div><div class="t-mid"><div class="t-name">${esc(t.name)}</div>${_capChipsHTML(t)}<div class="t-tool">${esc(t.tool_name)}</div></div><div class="t-badge pending">待执行</div></div>`});
    h+='</div></div>';
  }

  // 操作按钮
  const llmBadge=(d.llmStatus||d.llm_status)==='live'?'<span class="llm-live"><i data-lucide="cpu" style="width:12px;height:12px"></i> MiMo-v2.5-pro</span>':'<span class="llm-mock"><i data-lucide="settings" style="width:12px;height:12px"></i> 规则引擎</span>';
  h+=`<div class="result-section"><div class="actions"><button class="act-btn go" onclick="confirm(true)" aria-label="确认执行所有任务"><i data-lucide="check" style="width:16px;height:16px"></i> 确认执行</button><button class="act-btn cancel" onclick="confirm(false)" aria-label="取消本次规划">取消</button></div><div class="timing"><div class="td"></div>AI 规划 ${s}s · ${llmBadge}</div></div>`;
  window._pendingTasks=d.tasks||d.tasks_preview||[];
  addMsg('bot',h);

  // 渲染地图
  if(d.route?.length)renderMap(d.route,d.route_stats||d.routeStats);

  // 地图/列表切换
  const viewToggle=document.getElementById('routeViewToggle');
  if(viewToggle){
    viewToggle.querySelectorAll('.rvt-btn').forEach(btn=>{
      btn.addEventListener('click',()=>{
        viewToggle.querySelectorAll('.rvt-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        const view=btn.dataset.view;
        const mapEl=document.querySelector('.route-map');
        const sideEl=document.querySelector('.route-sidebar');
        if(mapEl&&sideEl){
          if(view==='list'){
            mapEl.style.display='none';
            sideEl.style.display='flex';
            sideEl.style.maxHeight='none';
          }else{
            mapEl.style.display='';
            sideEl.style.display='';
            sideEl.style.maxHeight='';
          }
        }
      });
    });
  }

  // 数字动画
  document.querySelectorAll('.rs-val').forEach(el=>{
    const text=el.textContent;
    const num=parseFloat(text);
    if(!isNaN(num)&&num>0){
      const suffix=text.replace(/[\d.]/g,'');
      animateNumber(el,num,suffix);
    }
  });

  // 持久化 plan 数据（用于刷新后恢复 + 多轮对话识别）
  _lastPlanData=d;
  saveState();
}

// ===== OSRM 真实路线获取 =====
async function fetchOSRMRoute(from,to){
  // OSRM 免费步行路线 API
  const url=`https://router.project-osrm.org/route/v1/foot/${from[1]},${from[0]};${to[1]},${to[0]}?overview=full&geometries=geojson`;
  try{
    const r=await fetch(url,{signal:AbortSignal.timeout(5000)});
    const d=await r.json();
    if(d.routes&&d.routes.length){
      // 返回 GeoJSON 坐标数组 [[lng,lat], ...]
      return d.routes[0].geometry.coordinates.map(c=>[c[1],c[0]]);
    }
  }catch(e){
    console.warn('OSRM 路线获取失败，使用直线:',e);
  }
  // 降级：直线
  return [from,to];
}

// ===== 更新侧边栏详情面板 =====
function updateRouteDetail(r){
  const el=document.getElementById('routeDetail');
  if(!el)return;
  const c=C_COLOR[r.category]||'#FFD100';
  let h=`<div class="rsd-hd"><span class="rsd-cat" style="background:${c}15;color:${c}">${esc(r.category)}</span>`;
  if(r.rating)h+=`<span class="rsd-rating"><i data-lucide="star" style="width:12px;height:12px"></i> ${r.rating} ${r.review_count?`(${r.review_count}条评价)`:''}</span>`;
  h+=`</div>`;
  if(r.activity_desc)h+=`<div class="rsd-desc">${esc(r.activity_desc)}</div>`;
  // 价格
  if(r.coupon_price!=null&&r.original_price!=null&&r.coupon_price<r.original_price){
    const save=r.original_price-r.coupon_price;
    h+=`<div class="rsd-prices"><span class="rsd-price-coupon">团购 ¥${r.coupon_price}</span><span class="rsd-price-original">¥${r.original_price}</span><span class="rsd-price-save">省¥${save}</span></div>`;
  }else if(r.price_per_person){
    h+=`<div class="rsd-prices"><span class="rsd-price-normal">¥${r.price_per_person}/人</span></div>`;
  }
  if(r.highlights?.length){
    h+=`<div class="rsd-highlights">`;
    r.highlights.forEach(hl=>{h+=`<span class="rsd-hl">${esc(hl)}</span>`});
    h+=`</div>`;
  }
  if(r.tips)h+=`<div class="rsd-tip"><i data-lucide="lightbulb" style="width:12px;height:12px"></i> ${esc(r.tips)}</div>`;
  if(r.address)h+=`<div class="rsd-addr"><i data-lucide="map-pin" style="width:12px;height:12px"></i> ${esc(r.address)}</div>`;
  el.innerHTML=h;
  refreshIcons(el);
}

// ===== Marker icon (divIcon) — index number shown bottom-right =====
function _buildMarkerIcon(r,idx){
  const c=C_COLOR[r.category]||'#FFD100';
  const ic=C_ICON[r.category]||'📍';
  return L.divIcon({
    className:'',
    html:`<div class="map-marker-wrap" role="button" aria-label="第${idx+1}站：${esc(r.poi_name||'')}，${esc(r.category||'')}">
      <div class="map-marker-pulse" style="background:${c}33"></div>
      <div class="map-marker-icon" style="background:${c};border-color:${c}">${ic}</div>
      <div class="map-marker-num">${idx+1}</div>
    </div>`,
    iconSize:[44,44],
    iconAnchor:[22,22]
  });
}

function _buildPopupHTML(r,idx){
  const c=C_COLOR[r.category]||'#FFD100';
  let h=`<div class="map-popup">
    <div class="map-popup-hd"><span class="map-popup-num" style="background:${c}">${idx+1}</span><span class="map-popup-name">${esc(r.poi_name||'')}</span></div>
    <div class="map-popup-cat">${esc(r.category||'')} ${r.rating?'⭐'+r.rating:''}</div>
    <div class="map-popup-time">${esc(r.arrival_time||'')} - ${esc(r.departure_time||'')}</div>`;
  if(r.coupon_price!=null&&r.original_price!=null&&r.coupon_price<r.original_price){
    h+=`<div class="map-popup-price"><span style="color:#22C55E;font-weight:700">团购 ¥${r.coupon_price}</span> <span style="text-decoration:line-through;color:#666;font-size:11px">¥${r.original_price}</span></div>`;
  }else if(r.price_per_person){
    h+=`<div class="map-popup-price">¥${r.price_per_person}/人</div>`;
  }
  if(r.activity_desc)h+=`<div class="map-popup-desc">${esc(r.activity_desc)}</div>`;
  h+=`</div>`;
  return h;
}

function _addMarker(map,r,idx){
  return L.marker([r.location.lat,r.location.lng],{icon:_buildMarkerIcon(r,idx)})
    .addTo(map)
    .bindPopup(_buildPopupHTML(r,idx),{className:'leaflet-dark-popup',maxWidth:260});
}

// Draws OSRM segments + transport labels. Returns layers (for cleanup) and coords (for bounds).
async function _drawSegments(map,validRoute){
  const layers=[];
  const allCoords=[];
  for(let i=0;i<validRoute.length-1;i++){
    const from=[validRoute[i].location.lat,validRoute[i].location.lng];
    const to=[validRoute[i+1].location.lat,validRoute[i+1].location.lng];
    const segCoords=await fetchOSRMRoute(from,to);
    const halo=L.polyline(segCoords,{color:'#FFD100',weight:10,opacity:0.12,lineJoin:'round',lineCap:'round'}).addTo(map);
    const main=L.polyline(segCoords,{color:'#FFD100',weight:4,opacity:0.85,lineJoin:'round',lineCap:'round'}).addTo(map);
    const dash=L.polyline(segCoords,{color:'#ffffff',weight:1.5,opacity:0.4,dashArray:'6,10',className:'route-anim-line'}).addTo(map);
    layers.push(halo,main,dash);
    const midIdx=Math.floor(segCoords.length/2);
    const mid=segCoords[midIdx]||[(from[0]+to[0])/2,(from[1]+to[1])/2];
    const next=validRoute[i+1];
    const tIcon=TRANSPORT_ICON[next.transport_mode]||'🚶';
    const label=`${tIcon} ${next.travel_time_from_prev||''}min`;
    const labelIcon=L.divIcon({className:'',html:`<div class="map-segment-label">${label}</div>`,iconSize:[80,20],iconAnchor:[40,10]});
    const labelM=L.marker(mid,{icon:labelIcon,interactive:false}).addTo(map);
    layers.push(labelM);
    allCoords.push(...segCoords);
  }
  return {layers,allCoords};
}

// Bind sidebar stop-item click → fly map to that POI and open its popup.
function _bindStopClick(stopEl,r,marker){
  stopEl.addEventListener('click',()=>{
    if(_activeMap&&r.location)_activeMap.flyTo([r.location.lat,r.location.lng],16,{duration:0.8});
    if(marker)marker.openPopup();
    if(_activeRouteCard){
      _activeRouteCard.querySelectorAll('.route-stop-item').forEach(el=>el.classList.remove('active'));
    }
    stopEl.classList.add('active');
    updateRouteDetail(r);
  });
}

// ===== 渲染地图 =====
async function renderMap(route,stats){
  // Tear down previous map instance before rebinding module-level state.
  if(_activeMap){
    try{_activeMap.remove();}catch(e){}
    _activeMap=null;
  }
  _activeMarkers={};
  _activeRouteLines=[];
  _activeRoute=[];
  _activeRouteCard=null;

  // Find the route-card we just rendered (last on the page).
  const cards=document.querySelectorAll('.route-card');
  const card=cards[cards.length-1];
  if(!card||typeof L==='undefined')return;
  const mapEl=card.querySelector('.route-map');
  if(!mapEl)return;
  if(!mapEl.id||mapEl.id==='routeMap')mapEl.id=`routeMap-${Date.now()}`;

  const validRoute=route.filter(r=>r.location&&r.location.lat);
  if(validRoute.length<2)return;

  const map=L.map(mapEl,{zoomControl:false,attributionControl:false}).setView([validRoute[0].location.lat,validRoute[0].location.lng],14);
  _activeMap=map;
  _activeRouteCard=card;
  setTimeout(()=>map.invalidateSize(),100);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:19,subdomains:'abcd'}).addTo(map);

  validRoute.forEach((r,i)=>{
    const marker=_addMarker(map,r,i);
    if(r.poi_id)_activeMarkers[r.poi_id]=marker;
    const stopEl=card.querySelector(`.route-stop-item[data-idx="${i}"]`);
    if(stopEl)_bindStopClick(stopEl,r,marker);
  });

  const {layers,allCoords}=await _drawSegments(map,validRoute);
  _activeRouteLines=layers;
  _activeRoute=validRoute;

  if(stats){
    const overlay=L.control({position:'topleft'});
    overlay.onAdd=function(){
      const div=L.DomUtil.create('div','map-stats-overlay');
      div.innerHTML=`
        <div class="map-stats-title"><i data-lucide="bar-chart-3" style="width:14px;height:14px"></i> 行程总览</div>
        <div class="map-stats-row"><span><i data-lucide="clock" style="width:12px;height:12px"></i> 总时长</span><span>${fmtDuration(stats.total_duration||0)}</span></div>
        <div class="map-stats-row"><span><i data-lucide="map-pin" style="width:12px;height:12px"></i> 站点数</span><span>${stats.poi_count||route.length}站</span></div>
        <div class="map-stats-row"><span><i data-lucide="footprints" style="width:12px;height:12px"></i> 步行</span><span>${fmtDistance(stats.walking_distance||0)}</span></div>
        <div class="map-stats-row"><span><i data-lucide="wallet" style="width:12px;height:12px"></i> 预估花费</span><span>${fmtCost(stats.total_cost||0)}</span></div>
        ${stats.total_savings?`<div class="map-stats-row map-stats-save"><span><i data-lucide="flame" style="width:12px;height:12px"></i> 团购省</span><span>${fmtCost(stats.total_savings)}</span></div>`:''}
      `;
      setTimeout(()=>refreshIcons(div),0);
      return div;
    };
    overlay.addTo(map);
  }

  if(allCoords.length){
    map.fitBounds(L.latLngBounds(allCoords),{padding:[50,50]});
  }
  setTimeout(()=>map.invalidateSize(),200);
  if(validRoute.length>0)updateRouteDetail(validRoute[0]);
  refreshIcons(mapEl);
}

// ===== 多轮对话：地图就地更新（不重画整张卡片） =====
async function patchMap(changeLog,newRoute){
  if(!_activeMap||!newRoute||!newRoute.length)return;
  const validRoute=newRoute.filter(r=>r.location&&r.location.lat);

  // 1. Remove markers whose poi_id is no longer in the route.
  const newIds=new Set(validRoute.map(r=>r.poi_id));
  for(const id of Object.keys(_activeMarkers)){
    if(!newIds.has(id)){
      try{_activeMap.removeLayer(_activeMarkers[id]);}catch(e){}
      delete _activeMarkers[id];
    }
  }

  // 2. Add markers for new poi_ids; refresh icon+popup for ALL (numbers shift on insert/remove).
  validRoute.forEach((r,i)=>{
    if(!r.poi_id)return;
    let m=_activeMarkers[r.poi_id];
    if(!m){
      m=_addMarker(_activeMap,r,i);
      _activeMarkers[r.poi_id]=m;
    }else{
      m.setIcon(_buildMarkerIcon(r,i));
      m.setPopupContent(_buildPopupHTML(r,i));
    }
  });

  // 3. Clear old polylines + label markers, redraw from new ordering.
  _activeRouteLines.forEach(l=>{try{_activeMap.removeLayer(l);}catch(e){}});
  _activeRouteLines=[];
  if(validRoute.length>=2){
    const {layers,allCoords}=await _drawSegments(_activeMap,validRoute);
    _activeRouteLines=layers;
    if(allCoords.length){
      _activeMap.flyToBounds(L.latLngBounds(allCoords),{padding:[50,50],duration:0.8});
    }
  }
  _activeRoute=validRoute;
}

// Rebuild .route-stop-list sidebar with new ordering and rebind clicks.
function patchSidebar(newRoute,changeLog){
  if(!_activeRouteCard||!newRoute||!newRoute.length)return;
  const list=_activeRouteCard.querySelector('.route-stop-list');
  if(!list)return;

  // Mark which entries get a diff class on the new render
  const diffCls={};
  (changeLog||[]).forEach(e=>{
    if(e.type==='replace'&&e.after?.poi_id)diffCls[e.after.poi_id]='diff-replaced';
    else if(e.type==='insert'&&e.inserted?.poi_id)diffCls[e.inserted.poi_id]='diff-inserted';
  });

  let h='';
  newRoute.forEach((r,i)=>{
    const c=C_COLOR[r.category]||'#FFD100';
    const ic=C_ICON[r.category]||'📍';
    const extra=diffCls[r.poi_id]?` ${diffCls[r.poi_id]}`:'';
    h+=`<div class="route-stop-item${i===0?' active':''}${extra}" data-idx="${i}" data-poi-id="${esc(r.poi_id||'')}" role="button" tabindex="0" aria-label="第${i+1}站：${esc(r.poi_name||'')}，${esc(r.category||'')}" onkeydown="if(event.key==='Enter')this.click()">
      <div class="rsi-dot" style="background:${c}">${i+1}</div>
      <div class="rsi-icon">${ic}</div>
      <div class="rsi-info"><div class="rsi-name">${esc(r.poi_name||'')}</div><div class="rsi-time">${esc(r.arrival_time||'')} - ${esc(r.departure_time||'')}</div></div>
    </div>`;
  });
  list.innerHTML=h;

  newRoute.forEach((r,i)=>{
    const stopEl=list.querySelector(`.route-stop-item[data-idx="${i}"]`);
    if(stopEl)_bindStopClick(stopEl,r,_activeMarkers[r.poi_id]);
  });

  setTimeout(()=>{
    list.querySelectorAll('.diff-replaced,.diff-inserted').forEach(el=>{
      el.classList.remove('diff-replaced','diff-inserted');
    });
  },3500);

  if(newRoute[0])updateRouteDetail(newRoute[0]);
}

// Refresh the top stats bar (.route-stats-bar) within the active card.
function patchStatsBar(stats,routeLen){
  if(!_activeRouteCard||!stats)return;
  const bar=_activeRouteCard.querySelector('.route-stats-bar');
  if(!bar)return;
  bar.innerHTML=`
    <div class="rs-item"><span class="rs-icon"><i data-lucide="clock" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtDuration(stats.total_duration||0)}</span><span class="rs-label">总时长</span></div>
    <div class="rs-item"><span class="rs-icon"><i data-lucide="map-pin" style="width:14px;height:14px"></i></span><span class="rs-val">${stats.poi_count||routeLen}站</span><span class="rs-label">途经站点</span></div>
    <div class="rs-item"><span class="rs-icon"><i data-lucide="footprints" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtDistance(stats.walking_distance||0)}</span><span class="rs-label">步行距离</span></div>
    <div class="rs-item"><span class="rs-icon"><i data-lucide="wallet" style="width:14px;height:14px"></i></span><span class="rs-val">${fmtCost(stats.total_cost||0)}</span><span class="rs-label">预估花费</span></div>
    ${stats.total_savings?`<div class="rs-item rs-save"><span class="rs-icon"><i data-lucide="flame" style="width:14px;height:14px"></i></span><span class="rs-val">省${fmtCost(stats.total_savings)}</span><span class="rs-label">团购优惠</span></div>`:''}
  `;
  refreshIcons(bar);
}

async function confirm(ok){
  if(busy)return;setBusy(true);
  // 立即禁用所有确认/取消按钮，防止重复点击
  document.querySelectorAll('.act-btn').forEach(el=>{el.disabled=true;el.style.pointerEvents='none'});
  document.querySelectorAll('.actions').forEach(el=>el.style.display='none');
  if(!ok){addMsg('bot','好的，已取消本次规划。有需要随时告诉我～');setBusy(false);return;}

  // 显示执行进度卡片
  const tasks=window._pendingTasks||[];
  const progressEl=addMsg('bot',renderExecProgress(tasks));
  // 滚动到进度卡片
  setTimeout(()=>progressEl.scrollIntoView({behavior:'smooth',block:'center'}),100);

  try{
    const t0=Date.now();
    const r=await fetch(`${API}/api/agent/confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sessionId:sid,confirmed:true})});
    const d=await r.json();const s=((Date.now()-t0)/1000).toFixed(1);

    // 逐个更新任务状态动画（running → done）
    const taskEls=progressEl.querySelectorAll('.ep-task');
    for(let i=0;i<taskEls.length;i++){
      const icon=taskEls[i].querySelector('.ep-icon');
      const status=taskEls[i].querySelector('.ep-status');
      // 先设为执行中
      icon.className='ep-icon running';icon.innerHTML='<i data-lucide="loader-2" class="spin" style="width:14px;height:14px"></i>';refreshIcons(icon);
      status.textContent='执行中...';status.style.color='var(--y)';
      await sleep(300);
      // 再设为完成
      icon.className='ep-icon done';icon.textContent='✓';
      status.textContent='已完成';status.style.color='var(--green)';
    }

    await sleep(300);
    // 彩纸庆祝
    burstConfetti(progressEl);
    await sleep(200);
    // 显示完成卡片
    renderCompletionCard(d,s);
    // 执行确认后 pending 已清，下次输入应当走完整规划路径
    _lastPlanData=null;
    saveState();
    // 滚动到完成卡片
    setTimeout(()=>{
      const lastMsg=document.getElementById('msgs').lastElementChild;
      if(lastMsg)lastMsg.scrollIntoView({behavior:'smooth',block:'center'});
    },100);
  }catch(e){
    addMsg('bot',`<span style="color:var(--red)"><i data-lucide="x-circle" style="width:14px;height:14px"></i> ${esc(e.message)}</span><div style="margin-top:8px"><button class="retry-btn" onclick="retryConfirm()"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> 重新执行</button></div>`);
  }
  setBusy(false);
}

function retryConfirm(){
  if(!sid||busy)return;
  confirm(true);
}

function sleep(ms){return new Promise(r=>setTimeout(r,ms))}

function burstConfetti(container){
  const colors=['#FFD100','#FB923C','#818CF8','#22C55E','#F472B6'];
  const rect=container.getBoundingClientRect();
  for(let i=0;i<30;i++){
    const p=document.createElement('div');
    p.className='confetti-piece';
    p.style.cssText=`left:${Math.random()*100}%;background:${colors[i%colors.length]};animation-delay:${Math.random()*.5}s;animation-duration:${1+Math.random()}s`;
    container.style.position='relative';
    container.appendChild(p);
  }
  setTimeout(()=>container.querySelectorAll('.confetti-piece').forEach(e=>e.remove()),2500);
}

function renderExecProgress(tasks){
  let h='<div class="exec-progress"><div class="ep-hd"><i data-lucide="zap" style="width:16px;height:16px"></i> 正在执行任务</div>';
  tasks.forEach(t=>{
    const[ic]=T_ICON[t.tool_name]||['tag'];
    h+=`<div class="ep-task" data-tid="${t.task_id}"><div class="ep-icon pending"><i data-lucide="${ic}" style="width:14px;height:14px"></i></div><div class="ep-name">${esc(t.name)}</div><div class="ep-status">等待中...</div></div>`;
  });
  h+='</div>';
  return h;
}

function renderCompletionCard(d,s){
  let h='<div class="completion-card"><div class="cc-hd"><i data-lucide="check-circle-2" style="width:16px;height:16px"></i> 全部完成</div>';

  // 统计信息
  const tasks=d.tasks||[];
  const successCount=tasks.filter(t=>t.status==='SUCCESS').length;
  const totalSavings=d.route_stats?.total_savings||d.routeStats?.total_savings||0;

  h+=`<div class="cc-stats">`;
  h+=`<div class="cc-stat"><div class="cc-stat-num">${successCount}/${tasks.length}</div><div class="cc-stat-label">任务完成</div></div>`;
  h+=`<div class="cc-stat"><div class="cc-stat-num">${s}s</div><div class="cc-stat-label">执行耗时</div></div>`;
  if(totalSavings>0){
    h+=`<div class="cc-stat cc-stat-save"><div class="cc-stat-num">¥${totalSavings}</div><div class="cc-stat-label">团购节省</div></div>`;
  }
  h+=`</div>`;

  if(tasks.length){
    h+='<div class="cc-tasks">';
    tasks.forEach(t=>{
      const ok=t.status==='SUCCESS';
      h+=`<span class="cc-task"><i data-lucide="${ok?'check':'x'}" style="width:12px;height:12px"></i> ${esc(t.name)}</span>`;
    });
    h+='</div>';
  }
  if(d.shareText)h+=`<div class="cc-share"><div class="cc-share-hd"><i data-lucide="share-2" style="width:14px;height:14px"></i> 微信分享文案</div><div class="cc-share-text">"${esc(d.shareText)}"</div><button class="cc-copy-btn" onclick="copyShareText(this)"><i data-lucide="copy" style="width:12px;height:12px"></i> 复制</button></div>`;
  h+='</div>';
  addMsg('bot',h);
}

function renderResult(d,s){
  let h='';
  if(d.results&&Object.keys(d.results).length){
    for(const[tid,tr]of Object.entries(d.results)){if(!tr||typeof tr!=='object')continue;h+=`<div class="result-section">${execCard(tid,tr,d.tasks)}</div>`;}
  }else{
    h+='<div class="result-section"><div class="task-card"><div class="task-hd"><i data-lucide="check-circle-2" style="width:16px;height:16px"></i> 执行结果</div>';
    (d.tasks||[]).forEach(t=>{const[ic,cl]=T_ICON[t.tool_name]||['tag','s'];h+=`<div class="t-row"><div class="t-icon ${cl}"><i data-lucide="${ic}" style="width:16px;height:16px"></i></div><div class="t-mid"><div class="t-name">${esc(t.name)}</div>${_capChipsHTML(t)}</div><div class="t-badge done">✓ 完成</div></div>`});
    h+='</div></div>';
  }
  if(d.shareText)h+=`<div class="result-section"><div class="share"><div class="share-l"><i data-lucide="share-2" style="width:14px;height:14px"></i> 微信分享文案</div><div class="share-t">"${esc(d.shareText)}"</div></div></div>`;
  h+=`<div class="result-section"><div class="timing"><div class="td"></div>执行 ${s}s</div></div>`;
  addMsg('bot',h);
}

function execCard(tid,tr,tasks){
  const task=(tasks||[]).find(t=>t.task_id===tid);const nm=task?task.name:tid;
  const[ic,cl]=T_ICON[task?.tool_name]||['tag','s'];
  let det='',sub='',badge='✓ 完成',bg='#3D3000';
  if(tr.booking_id){
    const nm2=tr.restaurant_name||tr.venue_name||'';det=`${nm2} 预订成功`;
    sub=`预订号 ${tr.booking_id}`+(tr.time?` · ${tr.time}`:'')+(tr.party_size?` · ${tr.party_size}人`:'');
    if(tr.special_requests?.length)sub+=`<br>要求：${tr.special_requests.join('、')}`;badge=`预订号 ${tr.booking_id}`;bg='#422006';
  }else if(tr.my_number){
    det='取号成功';sub=`号码 ${tr.my_number} · 前方 ${tr.ahead_count||0} 桌 · 等待 ${tr.estimated_wait||'?'} 分钟`;badge=`号码 ${tr.my_number}`;bg='#4A1942';
  }else if(tr.delivery_type){
    det=`${tr.item_name||'商品'} 配送安排`;sub=`${tr.delivery_type}`+(tr.estimated_arrival?` · 预计 ${tr.estimated_arrival} 送达`:'');if(tr.note)sub+=`<br>${tr.note}`;bg='#3D3000';
  }else if(tr.weather||tr.temperature){
    det=`${tr.city||''} ${tr.weather||''}`;sub=`${tr.temperature||'?'}°C`+(tr.suggestion?` · ${tr.suggestion}`:'`');bg='#1E3A5F';
  }else if(tr.results&&Array.isArray(tr.results)){
    det=`找到 ${tr.results.length} 个结果`;sub=tr.results.slice(0,3).map(r=>r.name||r).join('、');if(tr.results.length>3)sub+=` 等`;bg='#2D2B55';
  }else{det=`${nm} 完成`;sub=JSON.stringify(tr).slice(0,80);}
  return`<div class="exec-card"><div class="exec-hd"><div class="ei" style="background:${bg}"><i data-lucide="${ic}" style="width:16px;height:16px"></i></div><div class="en">${esc(nm)}</div></div><div class="exec-bd"><div class="exec-det">${esc(det)}</div><div class="exec-sub">${sub}</div><div class="exec-badge">${esc(badge)}</div></div></div>`;
}

// ===== 交互式路线编辑器 =====
let plannerMap=null;
let plannerPOIs=[];
let plannerMarkers={};
let myRoute=[];       // POI ID 数组，有序
let _routeHistory=[]; // 撤销栈（最多 10 步）
let plannerRouteLines=[];
let plannerActiveFilter='all';
let dragSrcIdx=null;

function saveRouteSnapshot(){
  _routeHistory.push([...myRoute]);
  if(_routeHistory.length>10)_routeHistory.shift();
}
function undoRoute(){
  if(!_routeHistory.length)return;
  myRoute=_routeHistory.pop();
  updatePlannerUI();
}

function initPlannerMap(){
  const el=document.getElementById('plannerMap');
  if(!el||typeof L==='undefined'||plannerMap)return;

  plannerMap=L.map('plannerMap',{zoomControl:false,attributionControl:false}).setView([31.235,121.475],13);
  // 更清晰生动的瓦片
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',{
    maxZoom:19,subdomains:'abcd'
  }).addTo(plannerMap);

  // 延迟刷新地图尺寸
  setTimeout(()=>plannerMap.invalidateSize(),300);

  // 加载 POI 数据
  fetch(`${API}/api/pois`).then(r=>r.json()).then(pois=>{
    plannerPOIs=pois;
    renderPlannerMarkers(pois);
  }).catch(e=>console.error('POI 加载失败:',e));

  // 分类筛选按钮
  document.querySelectorAll('.pm-filter').forEach(btn=>{
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.pm-filter').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      plannerActiveFilter=btn.dataset.cat;
      filterPlannerMarkers();
    });
  });
}

function renderPlannerMarkers(pois){
  pois.forEach(p=>{
    if(!p.location||!p.location.lat)return;
    const c=C_COLOR[p.category]||'#FFD100';
    const ic=C_ICON[p.category]||'📍';

    const icon=L.divIcon({
      className:'',
      html:`<div class="poi-marker" data-poi="${p.id}" role="button" aria-label="${p.name}，${p.category}${p.rating?'，评分'+p.rating:''}"><div class="poi-marker-inner" style="background:${c};border-color:${c}">${ic}</div><div class="poi-marker-num">0</div></div>`,
      iconSize:[42,42],
      iconAnchor:[21,21]
    });

    const popupHTML=`<div class="planner-popup">
      <div class="planner-popup-hd"><span class="planner-popup-icon">${ic}</span><span class="planner-popup-name">${esc(p.name)}</span></div>
      <div class="planner-popup-cat">${esc(p.category)} ${p.rating?'⭐'+p.rating:''} ${p.review_count?`(${p.review_count}条)`:''}</div>
      <div class="planner-popup-info">${p.address||''}</div>
      ${p.coupon_price!=null&&p.original_price!=null&&p.coupon_price<p.original_price?`<div class="planner-popup-price"><span style="color:#22C55E;font-weight:700">团购 ¥${p.coupon_price}</span> <span style="text-decoration:line-through;color:#666;font-size:11px">¥${p.original_price}</span></div>`:p.price_per_person?`<div class="planner-popup-price">¥${p.price_per_person}/人</div>`:''}
      <button class="planner-popup-btn ${myRoute.includes(p.id)?'remove':'add'}" onclick="togglePOI('${p.id}')">${myRoute.includes(p.id)?'✕ 从路线移除':'+ 加入路线'}</button>
    </div>`;

    const marker=L.marker([p.location.lat,p.location.lng],{icon})
      .addTo(plannerMap)
      .bindTooltip(p.name,{direction:'top',offset:[0,-20],className:'poi-tooltip'})
      .bindPopup(popupHTML,{className:'leaflet-dark-popup',maxWidth:260});

    plannerMarkers[p.id]={marker,poi:p};
  });
}

function filterPlannerMarkers(){
  Object.entries(plannerMarkers).forEach(([id,{marker,poi}])=>{
    const show=plannerActiveFilter==='all'||poi.category===plannerActiveFilter;
    const el=marker.getElement();
    if(el)el.style.display=show?'':'none';
  });
}

let _autoOptTimer=null;

function togglePOI(poiId){
  saveRouteSnapshot();
  const idx=myRoute.indexOf(poiId);
  if(idx>=0){
    myRoute.splice(idx,1);
  }else{
    myRoute.push(poiId);
  }
  // 首次添加后隐藏指引
  const guide=document.getElementById('plannerGuide');
  if(guide&&myRoute.length>0)guide.classList.add('hidden');
  updatePlannerUI();
  // 刷新弹窗内容
  if(plannerMarkers[poiId]){
    const m=plannerMarkers[poiId];
    const p=m.poi;
    const ic=C_ICON[p.category]||'📍';
    const inRoute=myRoute.includes(poiId);
    const popupHTML=`<div class="planner-popup">
      <div class="planner-popup-hd"><span class="planner-popup-icon">${ic}</span><span class="planner-popup-name">${esc(p.name)}</span></div>
      <div class="planner-popup-cat">${esc(p.category)} ${p.rating?'⭐'+p.rating:''} ${p.review_count?`(${p.review_count}条)`:''}</div>
      <div class="planner-popup-info">${p.address||''}</div>
      ${p.coupon_price!=null&&p.original_price!=null&&p.coupon_price<p.original_price?`<div class="planner-popup-price"><span style="color:#22C55E;font-weight:700">团购 ¥${p.coupon_price}</span> <span style="text-decoration:line-through;color:#666;font-size:11px">¥${p.original_price}</span></div>`:p.price_per_person?`<div class="planner-popup-price">¥${p.price_per_person}/人</div>`:''}
      <button class="planner-popup-btn ${inRoute?'remove':'add'}" onclick="togglePOI('${p.id}')">${inRoute?'✕ 从路线移除':'+ 加入路线'}</button>
    </div>`;
    m.marker.setPopupContent(popupHTML);
  }
  // 自动优化：300ms 防抖，2+ 站点时触发
  clearTimeout(_autoOptTimer);
  if(myRoute.length>=2){
    _autoOptTimer=setTimeout(()=>autoOptimizeRoute(),300);
  }
}

async function autoOptimizeRoute(){
  if(myRoute.length<2)return;
  // 显示优化中状态
  const statsEl=document.getElementById('psStats');
  if(statsEl)statsEl.innerHTML='<span class="ps-stat-item" style="color:var(--y)">🧠 智能排序中...</span>';
  try{
    const r=await fetch(`${API}/api/optimize-route`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({poiIds:myRoute})
    });
    const d=await r.json();
    if(d.route?.length){
      const optimized=d.route.map(r=>r.poi_id);
      // 只在顺序有变化时更新
      if(JSON.stringify(optimized)!==JSON.stringify(myRoute)){
        saveRouteSnapshot();
        myRoute=optimized;
        updatePlannerUI();
      }
    }
  }catch(e){
    console.warn('自动优化失败，保持当前顺序:',e);
    updatePlannerUI();
  }
}

function updatePlannerUI(){
  // 更新撤销按钮状态
  const undoBtn=document.getElementById('undoRouteBtn');
  if(undoBtn)undoBtn.disabled=!_routeHistory.length;

  // 更新所有标记的选中状态和序号
  Object.entries(plannerMarkers).forEach(([id,{marker}])=>{
    const el=marker.getElement();
    if(!el)return;
    const wrap=el.querySelector('.poi-marker');
    const numEl=el.querySelector('.poi-marker-num');
    const idx=myRoute.indexOf(id);
    if(wrap)wrap.classList.toggle('selected',idx>=0);
    if(numEl)numEl.textContent=idx>=0?idx+1:'0';
  });

  updateRoutePanel();
  drawPlannerRoute();
}

function updateRoutePanel(){
  const list=document.getElementById('psList');
  const empty=document.getElementById('psEmpty');
  const footer=document.getElementById('psFooter');
  const statsEl=document.getElementById('psStats');

  if(myRoute.length===0){
    list.innerHTML='<div class="ps-empty" id="psEmpty">点击地图上的景点<br>添加到你的路线</div>';
    footer.style.display='none';
    statsEl.innerHTML='';
    return;
  }

  let totalDist=0,totalCost=0;
  let html='';
  myRoute.forEach((id,i)=>{
    const poi=plannerPOIs.find(p=>p.id===id);
    if(!poi)return;
    const c=C_COLOR[poi.category]||'#FFD100';
    const ic=C_ICON[poi.category]||'📍';
    const cost=poi.coupon_price||poi.price_per_person||0;
    totalCost+=cost;

    html+=`<div class="ps-route-item" draggable="true" data-idx="${i}" data-id="${id}">
      <span class="ps-grip">⠿</span>
      <span class="ps-idx" style="background:${c}">${i+1}</span>
      <div class="ps-item-info">
        <div class="ps-item-name">${esc(poi.name)}</div>
        <div class="ps-item-cat">${ic} ${esc(poi.category)}${cost?' · ¥'+cost:''}</div>
      </div>
      <div class="ps-item-actions">
        <button class="ps-move-btn${i===0?' disabled':''}" onclick="moveUp(${i})" ${i===0?'disabled':''} title="上移">▲</button>
        <button class="ps-move-btn${i===myRoute.length-1?' disabled':''}" onclick="moveDown(${i})" ${i===myRoute.length-1?'disabled':''} title="下移">▼</button>
        <button class="ps-item-remove" onclick="togglePOI('${id}')" title="移除">✕</button>
      </div>
    </div>`;
  });

  list.innerHTML=html;
  footer.style.display='block';

  // 统计
  statsEl.innerHTML=`<span class="ps-stat-item"><span><i data-lucide="map-pin" style="width:12px;height:12px"></i></span><span>${myRoute.length}站</span></span>${totalCost?`<span class="ps-stat-item"><span><i data-lucide="wallet" style="width:12px;height:12px"></i></span><span>约¥${totalCost}</span></span>`:''}`;
  refreshIcons(statsEl);

  // 拖拽排序
  initDragSort();
}

function initDragSort(){
  const items=document.querySelectorAll('.ps-route-item');
  items.forEach(item=>{
    item.addEventListener('dragstart',e=>{
      dragSrcIdx=parseInt(item.dataset.idx);
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed='move';
    });
    item.addEventListener('dragend',()=>{
      item.classList.remove('dragging');
      document.querySelectorAll('.ps-route-item').forEach(el=>el.classList.remove('drag-over'));
      dragSrcIdx=null;
    });
    item.addEventListener('dragover',e=>{
      e.preventDefault();
      e.dataTransfer.dropEffect='move';
      const target=parseInt(item.dataset.idx);
      if(dragSrcIdx!==null&&dragSrcIdx!==target){
        item.classList.add('drag-over');
      }
    });
    item.addEventListener('dragleave',()=>{
      item.classList.remove('drag-over');
    });
    item.addEventListener('drop',e=>{
      e.preventDefault();
      item.classList.remove('drag-over');
      const targetIdx=parseInt(item.dataset.idx);
      if(dragSrcIdx===null||dragSrcIdx===targetIdx)return;
      saveRouteSnapshot();
      // 移动元素
      const [moved]=myRoute.splice(dragSrcIdx,1);
      myRoute.splice(targetIdx,0,moved);
      updatePlannerUI();
    });
  });
}

function moveUp(idx){
  if(idx<=0)return;
  saveRouteSnapshot();
  [myRoute[idx-1],myRoute[idx]]=[myRoute[idx],myRoute[idx-1]];
  updatePlannerUI();
}

function moveDown(idx){
  if(idx>=myRoute.length-1)return;
  saveRouteSnapshot();
  [myRoute[idx],myRoute[idx+1]]=[myRoute[idx+1],myRoute[idx]];
  updatePlannerUI();
}

let _drawRouteGen=0;  // 生成器锁，防止并发绘制
let _drawRouteTimer=null;

async function drawPlannerRoute(){
  // debounce：50ms 内多次调用只执行最后一次
  clearTimeout(_drawRouteTimer);
  return new Promise(resolve=>{
    _drawRouteTimer=setTimeout(()=>_drawPlannerRouteInner().then(resolve),50);
  });
}

async function _drawPlannerRouteInner(){
  const gen=++_drawRouteGen;

  // 清除旧路线
  plannerRouteLines.forEach(l=>{try{l.remove()}catch(e){}});
  plannerRouteLines=[];

  if(myRoute.length<2)return;

  const coords=myRoute.map(id=>{
    const poi=plannerPOIs.find(p=>p.id===id);
    return poi?.location?[poi.location.lat,poi.location.lng]:null;
  }).filter(Boolean);

  if(coords.length<2)return;

  // 逐段获取 OSRM 路线
  let osrmFailed=false;
  for(let i=0;i<coords.length-1;i++){
    // 如果有新的绘制请求，放弃当前绘制
    if(gen!==_drawRouteGen)return;

    const from=coords[i];
    const to=coords[i+1];
    const segCoords=await fetchOSRMRoute(from,to);

    // 再次检查锁
    if(gen!==_drawRouteGen)return;

    // 判断是否降级为直线（2个点 = 降级）
    if(segCoords.length<=2)osrmFailed=true;

    // 光晕
    const glow=L.polyline(segCoords,{color:'#FFD100',weight:10,opacity:0.12,lineJoin:'round',lineCap:'round'}).addTo(plannerMap);
    // 主线
    const main=L.polyline(segCoords,{color:'#FFD100',weight:4,opacity:0.85,lineJoin:'round',lineCap:'round'}).addTo(plannerMap);
    // 流动虚线（动画效果）
    const dash=L.polyline(segCoords,{color:'#ffffff',weight:2,opacity:0.5,dashArray:'8,12',className:'planner-route-anim'}).addTo(plannerMap);

    plannerRouteLines.push(glow,main,dash);
  }

  // 最终检查锁
  if(gen!==_drawRouteGen)return;

  // OSRM 失败时显示提示
  if(osrmFailed){
    const tip=L.tooltip({permanent:true,className:'osrm-fail-tip',direction:'top',offset:[0,-30]})
      .setContent('⚠️ 路线API降级，显示直线');
    const center=coords[Math.floor(coords.length/2)];
    const tipMarker=L.marker(center,{icon:L.divIcon({className:'',html:'',iconSize:[0,0]}),interactive:false})
      .addTo(plannerMap)
      .bindTooltip(tip);
    plannerRouteLines.push(tipMarker);
  }

  // 自适应边界
  const bounds=L.latLngBounds(coords);
  plannerMap.fitBounds(bounds,{padding:[60,60]});
}

function clearMyRoute(){
  saveRouteSnapshot();
  myRoute=[];
  updatePlannerUI();
}

function optimizeMyRoute(){
  if(myRoute.length<2)return;
  saveRouteSnapshot();
  autoOptimizeRoute();
}

function confirmMyRoute(){
  if(myRoute.length<2)return;
  // 构建描述，发送给 Agent
  const names=myRoute.map(id=>{
    const poi=plannerPOIs.find(p=>p.id===id);
    return poi?poi.name:'';
  }).filter(Boolean);
  const desc=`帮我规划这条路线：${names.join(' → ')}，按顺序游玩`;
  document.getElementById('inp').value=desc;
  // 滚动到聊天区（减去导航栏高度）
  const y=document.getElementById('demo').getBoundingClientRect().top+window.scrollY-70;
  window.scrollTo({top:y,behavior:'smooth'});
  setTimeout(()=>send(),500);
}

// 页面加载后初始化路线编辑器
document.addEventListener('DOMContentLoaded',()=>{
  const obs=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        initPlannerMap();
        obs.disconnect();
      }
    });
  },{threshold:0.1});
  const sec=document.getElementById('planner');
  if(sec)obs.observe(sec);
});

// ===== Scroll Reveal =====
document.addEventListener('DOMContentLoaded',()=>{
  const revealSections=document.querySelectorAll('.how-section,.tools-section,.diff-section,.arch-section');
  const revealObserver=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        entry.target.classList.add('revealed');
        revealObserver.unobserve(entry.target);
      }
    });
  },{threshold:0.15});
  revealSections.forEach(s=>{
    s.classList.add('reveal-on-scroll');
    revealObserver.observe(s);
  });
});

// ===== Hero Entrance =====
setTimeout(()=>{
  document.querySelectorAll('.hero-tag,.hero h1,.hero-sub,.hero-stats').forEach((el,i)=>{
    setTimeout(()=>el.classList.add('show'),i*100);
  });
},800);

// ===== Mobile Nav =====
function toggleMobileNav(){
  document.getElementById('navHamburger').classList.toggle('active');
  document.querySelector('.nav-links').classList.toggle('open');
}
document.querySelectorAll('.nav-link').forEach(a=>a.addEventListener('click',()=>{
  document.querySelector('.nav-links').classList.remove('open');
  document.getElementById('navHamburger').classList.remove('active');
}));

// ===== Copy Share Text =====
function copyShareText(btn){
  const text=btn.previousElementSibling.textContent.replace(/^"|"$/g,'');
  navigator.clipboard.writeText(text).then(()=>{
    btn.innerHTML='<i data-lucide="check" style="width:12px;height:12px"></i> 已复制';btn.classList.add('copied');refreshIcons(btn);
    setTimeout(()=>{btn.innerHTML='<i data-lucide="copy" style="width:12px;height:12px"></i> 复制';btn.classList.remove('copied');refreshIcons(btn)},2000);
  });
}

// ===== Animate Number =====
function animateNumber(el,target,suffix='',duration=800){
  const startTime=performance.now();
  function update(t){
    const progress=Math.min((t-startTime)/duration,1);
    const eased=1-Math.pow(1-progress,3);
    el.textContent=Math.round(target*eased)+suffix;
    if(progress<1)requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

// ===== Inspector overlay (press D to toggle) =====
const _INSPECTOR={
  visible:false,
  patchHits:{replace:0,remove:0,insert:0,shift_time:0,declare_dislike:0},
  replanCount:0,
  lastActionType:'-',
  lastDurationMs:0,
  lastSseEvents:0,
  lastErrorReason:null,
};

function _renderInspector(){
  let el=document.getElementById('mt-inspector');
  if(!_INSPECTOR.visible){if(el)el.style.display='none';return;}
  if(!el){
    el=document.createElement('div');
    el.id='mt-inspector';
    el.style.cssText='position:fixed;right:12px;bottom:12px;z-index:99999;background:rgba(15,23,42,.92);color:#e2e8f0;font:11px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;padding:10px 12px;border-radius:8px;max-width:340px;min-width:260px;box-shadow:0 8px 24px rgba(0,0,0,.4);border:1px solid rgba(148,163,184,.2);backdrop-filter:blur(6px);pointer-events:none;white-space:pre';
    document.body.appendChild(el);
  }
  const ph=_INSPECTOR.patchHits;
  const route=_lastPlanData?.route||[];
  const tasks=_lastPlanData?.tasks||[];
  const ids=tasks.slice(0,3).map(t=>t.task_id||t.taskId).filter(Boolean).join(',');
  const tail=tasks.length>3?`+${tasks.length-3}`:'';
  const modeColor=_isLiveMode?'#10b981':'#fbbf24';
  const errRow=_INSPECTOR.lastErrorReason
    ?`last error   : <span style="color:#fca5a5">${_INSPECTOR.lastErrorReason}</span>\n`
    :'';
  // Aggregate Meituan capability usage across current task list
  const capCounts={};
  tasks.forEach(t=>{
    const tags=t?.params?.capability_tags;
    if(!Array.isArray(tags))return;
    const seen=new Set();
    tags.forEach(tag=>{
      if(typeof tag!=='string'||seen.has(tag))return;
      seen.add(tag);
      capCounts[tag]=(capCounts[tag]||0)+1;
    });
  });
  const capEntries=Object.entries(capCounts);
  const capsRow=capEntries.length
    ?`caps used    : <span style="color:#fde047">${capEntries.map(([k,v])=>v>1?`${k}×${v}`:k).join(' ')}</span>\n`
    :'';
  el.style.display='block';
  el.innerHTML=
    `<div style="color:#94a3b8;margin-bottom:4px;font-weight:600;display:flex;justify-content:space-between"><span>🔬 inspector</span><span style="color:#64748b;font-weight:400">[D] 切换</span></div>`+
    `sid          : <span style="color:#7dd3fc">${sid?sid.slice(0,8):'-'}</span>\n`+
    `mode         : <span style="color:${modeColor}">${_isLiveMode?'live':'mock'}</span>\n`+
    `last action  : <span style="color:#fde047">${_INSPECTOR.lastActionType}</span>\n`+
    `last duration: <span style="color:#fde047">${_INSPECTOR.lastDurationMs}ms</span>\n`+
    errRow+
    `patch hits   : R=${ph.replace} D=${ph.remove} I=${ph.insert} T=${ph.shift_time} X=${ph.declare_dislike}\n`+
    `replan count : ${_INSPECTOR.replanCount}\n`+
    `SSE events   : ${_INSPECTOR.lastSseEvents}\n`+
    `route nodes  : ${route.length}\n`+
    capsRow+
    `task ids     : <span style="color:#a5b4fc">${ids||'-'}${tail}</span>`;
}

function _trackContinueResponse(d,durationMs){
  _INSPECTOR.lastDurationMs=durationMs;
  _INSPECTOR.lastErrorReason=null;
  if(d.status==='plan_modified'&&d.actionType){
    _INSPECTOR.lastActionType=d.actionType;
    if(_INSPECTOR.patchHits[d.actionType]!==undefined)_INSPECTOR.patchHits[d.actionType]++;
  }else if(d.status==='replanned'){
    _INSPECTOR.lastActionType='replan';
    _INSPECTOR.replanCount++;
  }else if(d.status==='conversation_continued'){
    _INSPECTOR.lastActionType='chat';
  }else if(d.status==='plan_modify_failed'){
    _INSPECTOR.lastActionType=`${d.actionType||'?'}(fail)`;
    const entry=Array.isArray(d.changeLog)?d.changeLog[0]:null;
    _INSPECTOR.lastErrorReason=entry?.reason_code||null;
  }
  _renderInspector();
}

function _trackStreamResponse(eventCount,durationMs){
  _INSPECTOR.lastDurationMs=durationMs;
  _INSPECTOR.lastSseEvents=eventCount;
  _INSPECTOR.lastActionType='plan';
  _renderInspector();
}

document.addEventListener('keydown',e=>{
  const t=e.target;
  if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable))return;
  if((e.key==='d'||e.key==='D')&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
    _INSPECTOR.visible=!_INSPECTOR.visible;
    _renderInspector();
  }
});

// Mobile keyboard: scroll chat to bottom when viewport shrinks
if(window.visualViewport){
  let _prevH=window.visualViewport.height;
  window.visualViewport.addEventListener('resize',()=>{
    const h=window.visualViewport.height;
    if(h<_prevH-80){
      const box=document.getElementById('msgs');
      if(box)box.scrollTop=box.scrollHeight;
    }
    _prevH=h;
  });
}
