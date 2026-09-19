const $ = s => document.querySelector(s);
const state = {sid:null,busy:false,last:null,knowledge:[],currentUser:null};
const labels={rules:'业务规则',qualification:'个人资格',order:'订单诊断',account:'账户状态',funds:'资金查询',risk:'风险测评',holdings:'持仓查询',reject:'合规拦截',handoff:'人工协同',unknown:'待澄清'};
const statuses={answered:'已答复',clarify:'待补充',need_auth:'待身份验证',rejected:'已安全拒答',handoff:'本地工单'};
const events={input_policy:'输入安全检查',route:'路由决策',auth:'身份校验',loop:'规划下一步',tool:'调用业务工具',retrieve:'检索知识依据',generation:'生成答复',guardrail:'输出安全检查',llm:'DeepSeek 调用',fallback:'失败降级',risk_block:'风险拦截',output_block:'输出拦截',metrics:'运行统计',llm_route:'语义意图识别'};
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function notice(text){$('#notice').textContent=text;$('#notice').hidden=false;clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('#notice').hidden=true,5500);}
async function api(path,{method='GET',body}={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
  try{const r=await fetch(path,{method,signal:controller.signal,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:`请求未完成（${r.status}），请检查输入或新建会话`);return data;}
  catch(e){if(e.name==='AbortError')throw new Error('处理超时，请稍后重试；不要重复提交相同问题。');throw e;}finally{clearTimeout(timer);}
}
function setBusy(value){state.busy=value;$('#busy').hidden=!value;$('#chat').setAttribute('aria-busy',String(value));document.querySelectorAll('#send,#login,#logout,#new-session,#handoff,[data-query]').forEach(e=>e.disabled=value);}
function showView(name){document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===name;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});for(const v of ['conversation','tickets','knowledge','evaluation'])$(`#${v}-view`).hidden=v!==name;}
function add(who,text,response){
  const message=node('article',undefined,`message ${who}`);
  if(who==='system')message.textContent=text;
  else{message.append(node('p',who==='user'?'你':'经纪业务智能客服','message-label'),node('div',text,'bubble'));}
  if(response?.citations?.length){const details=node('details',undefined,'citations');details.append(node('summary',`查看 ${response.citations.length} 条知识依据`));for(const c of response.citations){const block=node('div',undefined,'citation');block.append(node('strong',c.title),node('div',`${c.id} · ${c.version} · ${c.review_status==='demo_reviewed'?'演示审核':'审核资料'}`),node('div',c.source),node('div',`有效期 ${c.effective_at} 至 ${c.expires_at}（不含截止日）`));details.append(block);}message.append(details);}
  if(response?.handoff){const link=node('button',`查看工单 ${response.handoff.id}`,'text-button');link.onclick=()=>{showView('tickets');loadTickets();};message.append(link);}
  if(response?.trace_id){const group=node('div',undefined,'feedback');const inspect=node('button','处理记录');inspect.onclick=()=>{drawTrace(response);$('#audit').open=true;$('#audit').scrollIntoView({behavior:'smooth',block:'nearest'});};group.append(inspect);for(const [rating,title] of [['helpful','有帮助'],['unhelpful','需要改进']]){const b=node('button',title);b.onclick=async()=>{try{await api(`/api/sessions/${state.sid}/feedback`,{method:'POST',body:{trace_id:response.trace_id,rating}});group.replaceChildren(inspect,node('span','反馈已保存'));}catch(e){notice(e.message);}};group.append(b);}message.append(group);}
  $('#chat').append(message);$('#chat').scrollTop=$('#chat').scrollHeight;
}
function drawTrace(r){
  state.last=r;$('#trace').textContent=JSON.stringify(r,null,2);$('#trace-summary').textContent=`${labels[r.intent]||r.intent} · ${statuses[r.status]||r.status}`;
  const metric=r.trace.find(e=>e.type==='metrics')?.data||{};
  $('#trace-overview').replaceChildren(...[`${(metric.latency_ms/1000).toFixed(2)} 秒`,`${metric.tool_calls||0} 次工具调用`,`${metric.llm_calls||0} 次模型调用`,`${metric.tokens||0} tokens`].map(t=>node('span',t,'metric')));
  const rows=r.trace.filter(e=>e.type!=='metrics').map(e=>{const li=node('li');li.append(node('strong',events[e.type]||e.type));let summary='';const d=e.data;
    if(e.type==='tool')summary=`${d.name} · ${d.result?.error||'返回成功'} · ${d.latency_ms} ms`;
    else if(e.type==='loop')summary=`第 ${d.step} 步 · ${d.action}${d.tool?' · '+d.tool:''}`;
    else if(e.type==='route')summary=`${d.pipeline} · ${labels[d.intent]||d.intent}`;
    else if(e.type==='retrieve')summary=`${d.citations.join('、')} · ${d.method}`;
    else if(e.type==='llm')summary=`${d.status} · ${d.returned_model||d.requested_model} · ${d.latency_ms} ms`;
    else summary=d.reason||d.rule||d.mode||d.result||'';
    li.append(node('div',summary));return li;});$('#trace-timeline').replaceChildren(...rows);
}
async function profile(){
  if(!state.currentUser){$('#profile').replaceChildren();$('#status').textContent='尚未登录 · 公共规则可直接咨询';$('#logout').hidden=true;return;}
  const p=await api(`/api/sessions/${state.sid}/profile`);$('#logout').hidden=false;$('#user').value=p.user_id;$('#status').textContent=`${p.user_id} · 已完成模拟身份验证`;
  const fields=[['资产层级',p.asset_bucket],['生命周期',p.lifecycle],['风险测评',`R${p.risk_level}${p.risk_valid?' · 有效':' · 待更新'}`]];
  $('#profile').replaceChildren(...fields.flatMap(([k,v])=>[node('dt',k),node('dd',v)]));
}
async function start(fresh=false){
  let s;if(!fresh){const saved=localStorage.getItem('brokerage-session-v2');if(saved){try{s=await api(`/api/sessions/${saved}`);}catch{localStorage.removeItem('brokerage-session-v2');}}}
  if(!s)s=await api('/api/sessions',{method:'POST'});
  state.sid=s.session_id;state.currentUser=s.authenticated?s.user_id:null;state.last=null;localStorage.setItem('brokerage-session-v2',state.sid);$('#chat').replaceChildren();$('#trace').textContent='';$('#trace-timeline').replaceChildren();$('#trace-overview').replaceChildren();$('#trace-summary').textContent='尚无处理记录';$('#audit').open=false;
  if(s.messages.length){s.messages.forEach(m=>add(m.role,m.content,m.response));const latest=[...s.messages].reverse().find(m=>m.response);if(latest)drawTrace(latest.response);}
  else add('assistant','你好，我可以解答业务规则，也可以在你登录模拟账户后核对资格、查询资金或诊断订单。\n告诉我你正在办理什么，或卡在哪一步。');
  await profile();await loadTickets();showView('conversation');
}
async function send(q){
  if(state.busy||!q.trim())return;setBusy(true);showView('conversation');add('user',q);$('#input').value='';
  try{if(!state.sid)throw new Error('服务尚未连接，请刷新页面');const r=await api(`/api/sessions/${state.sid}/messages`,{method:'POST',body:{content:q}});add('assistant',r.answer,r);drawTrace(r);if(r.status==='need_auth')$('#user').focus();if(r.handoff)await loadTickets();}
  catch(e){add('system',e.message);notice(e.message);}finally{setBusy(false);}
}
$('#form').onsubmit=e=>{e.preventDefault();send($('#input').value.trim());};
$('#input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send($('#input').value.trim());}};
document.querySelectorAll('[data-query]').forEach(b=>b.onclick=()=>send(b.dataset.query));
$('#login').onclick=async()=>{const uid=$('#user').value;if(!uid){notice('请先选择一个模拟账户');return;}setBusy(true);try{const switching=state.currentUser&&state.currentUser!==uid;const s=await api(`/api/sessions/${state.sid}/auth`,{method:'POST',body:{user_id:uid}});state.currentUser=uid;if(switching){$('#chat').replaceChildren();state.last=null;$('#trace').textContent='';$('#trace-timeline').replaceChildren();$('#trace-overview').replaceChildren();$('#trace-summary').textContent='尚无处理记录';}await profile();add('system',`已登录模拟账户 ${uid}`);await loadTickets();setBusy(false);if(s.pending_slots?.query)await send('继续查询');}catch(e){notice(e.message);}finally{setBusy(false);}};
$('#logout').onclick=async()=>{try{await api(`/api/sessions/${state.sid}/logout`,{method:'POST'});$('#user').value='';await start();notice('已退出并清除本会话中的账户上下文');}catch(e){notice(e.message);}};
$('#new-session').onclick=async()=>{setBusy(true);try{await start(true);}catch(e){notice(e.message);}finally{setBusy(false);}};
$('#handoff').onclick=async()=>{try{const t=await api(`/api/sessions/${state.sid}/handoff`,{method:'POST'});add('system',`本地工单 ${t.id} 已创建。这里没有真实坐席接单。`);await loadTickets();notice('问题摘要已保存到服务工单');}catch(e){notice(e.message);}};
async function loadTickets(){if(!state.sid)return;const list=await api(`/api/sessions/${state.sid}/tickets`);$('#ticket-count').textContent=list.length;$('#tickets-list').replaceChildren();if(!list.length){$('#tickets-list').append(node('div','暂无工单。需要进一步核查时，可以从对话中创建。','empty'));return;}for(const t of list.reverse()){const el=node('article',undefined,'record');el.append(node('h3',t.id),node('p',t.summary||'用户主动申请人工协同'),node('p',`${t.status} · ${new Date(t.created_at*1000).toLocaleString('zh-CN')} · 仅本地演示`,'meta'));$('#tickets-list').append(el);}}
$('#refresh-tickets').onclick=()=>loadTickets().catch(e=>notice(e.message));
function drawKnowledge(){const q=$('#knowledge-filter').value.trim();const list=state.knowledge.filter(k=>(k.title+k.domain+k.text).includes(q));$('#knowledge-list').replaceChildren();for(const k of list){const el=node('article',undefined,'record');el.append(node('h3',`${k.title} · ${k.domain}`),node('p',k.text),node('p',`${k.id} / ${k.version} / ${k.source}`,'meta'),node('p',`生效 ${k.effective_at} · 失效 ${k.expires_at} · ${k.review_status==='demo_reviewed'?'演示审核':'待核验状态：'+k.review_status}`,'meta'));$('#knowledge-list').append(el);}if(!list.length)$('#knowledge-list').append(node('div','没有匹配的知识条目','empty'));}
$('#knowledge-filter').oninput=drawKnowledge;
async function loadEvaluation(){const report=await api('/api/evaluation');const root=$('#evaluation-content');root.replaceChildren();if(!report.splits){root.append(node('p',report.status||'尚未生成评测结果'));return;}
 root.append(node('p',`运行时间：${report.run_at} · 模式：确定性离线回归`,'muted'));
 const cards=node('div',undefined,'results');for(const s of report.splits){const card=node('div',undefined,'record');card.append(node('span',s.name==='main'?'主测试集':'留出集'),node('strong',`${s.passed}/${s.total}`),node('span','通过样本数'));cards.append(card);}root.append(cards,node('p','通过代表满足该样本的程序断言，不等同于人工事实评分或真实用户一次解决率。失败样本保留原始结果。','muted'));
 const table=node('table');const head=node('tr');['样本','类型','预期 / 实际','结果'].forEach(v=>head.append(node('th',v)));table.append(head);
 for(const s of report.splits)for(const c of s.results){const row=node('tr');[c.query,c.query_type,`${c.expected_status} / ${c.actual_status}`,c.passed?'通过':'未通过：'+c.failures.join('、')].forEach(v=>row.append(node('td',v)));table.append(row);}const wrap=node('div',undefined,'table-wrap');wrap.append(table);root.append(wrap);
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=async()=>{showView(b.dataset.view);try{if(b.dataset.view==='tickets')await loadTickets();if(b.dataset.view==='knowledge'){state.knowledge=await api('/api/knowledge');drawKnowledge();}if(b.dataset.view==='evaluation')await loadEvaluation();}catch(e){notice(e.message);}});
$('#export').onclick=()=>{if(!state.last){notice('请先完成一次对话');return;}const url=URL.createObjectURL(new Blob([JSON.stringify(state.last,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`trace-${state.last.trace_id}.json`;a.click();URL.revokeObjectURL(url);};
async function init(){try{const [health,users]=await Promise.all([api('/api/health'),api('/api/profiles')]);$('#model-status').textContent=health.llm_enabled?'DeepSeek · 已配置':'本地规则模式';for(const u of users){const o=node('option',`${u.user_id} · ${u.lifecycle}`);o.value=u.user_id;$('#user').append(o);}await start();}catch(e){$('#model-status').textContent='服务连接失败';notice(e.message);add('system','暂时无法连接后端，请确认本地服务正在运行后刷新。');}}
init();
