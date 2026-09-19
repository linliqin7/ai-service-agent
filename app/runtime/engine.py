"""Risk-first workflow with real model planning and bounded read-only execution."""
import re,time,uuid,json
from datetime import datetime,timezone
from app.schemas import TraceEvent,AgentResponse
from app.runtime.router import route,order_id,public_definition
from app.runtime.policy import normalize,redact,risk_reason,unsafe_output,REJECTION,evidence_supported
from app.runtime.tools import execute,render_facts,DESCRIPTIONS
from app.rag.retriever import search
from app.llm.deepseek import CALLS
from app.runtime.answerability import evaluate
from app.runtime.evidence import business_evidence,knowledge_evidence,citations,fact_observations
from app.schemas import EntityValue,SessionState,TaskState,TaskStatus
from app.runtime.task_manager import (abandon_task,complete_task,create_task,
    handoff_task,increment_clarification,reject_task,set_clarifying,set_entity,
    set_executing,update_missing_slots)

PRIVATE={'qualification','order','account','funds','risk','holdings'}
TOOLS={'qualification':['get_profile','get_rule'],'order':['get_order_detail','search_knowledge'], 'account':['get_account'],'funds':['get_funds','search_knowledge'],'risk':['get_risk'],'holdings':['get_holdings']}
EVIDENCE_LIMITATION='当前可核验资料不足或存在冲突，无法安全完成本次解释；已转入本地演示工单，请通过官方渠道核查。'

def _evaluate_task(task,session,**kwargs):
    task.answerability=evaluate(task,session,**kwargs)
    return task.answerability

TASK_REQUIRED={'qualification':['board','authentication'],'order':['order_id','authentication'],
               'account':['authentication'],'funds':['authentication'],'risk':['authentication'],
               'holdings':['authentication']}

def _task_domain(intent):
    return {'rules':'knowledge','qualification':'qualification','order':'trading',
            'account':'account','funds':'funds','risk':'risk','holdings':'holdings'}.get(intent)

def _missing_slots(task,session):
    missing=[]
    if 'order_id' in task.required_slots and 'order_id' not in task.entities:missing.append('order_id')
    if 'board' in task.required_slots and 'board' not in task.entities:missing.append('board')
    if 'authentication' in task.required_slots and not session.authenticated:missing.append('authentication')
    return missing

def _ensure_active_task(session: SessionState, intent: str, query: str) -> TaskState:
    task=session.active_task
    terminal={TaskStatus.COMPLETED,TaskStatus.HANDOFF,TaskStatus.REJECTED,TaskStatus.ABANDONED}
    if task is None or task.status in terminal or task.task_type != intent:
        if task is not None and task.status not in terminal:
            abandon_task(task,'new_task')
        task=create_task(intent,query,_task_domain(intent),TASK_REQUIRED.get(intent,[]))
        session.active_task=task
    set_executing(task)
    # Revalidate fresh results on each turn; never reuse stale account facts.
    task.evidence=[]
    task.answerability=None
    if intent=='order':
        oid=order_id(query)
        if oid:
            set_entity(task,EntityValue(name='order_id',value=oid,source='user',confirmed=False))
    if intent=='qualification':
        board=next((b for b in ['创业板','科创板','北交所'] if b in query),'')
        if board:
            set_entity(task,EntityValue(name='board',value=board,source='user',confirmed=False))
    update_missing_slots(task,_missing_slots(task,session))
    return task

def _sync_task_status(task,status,reason=None):
    if status=='answered':return complete_task(task,reason or 'answered')
    if status in ('clarify','need_auth'):return set_clarifying(task)
    if status=='handoff':return handoff_task(task,reason or 'handoff')
    if status=='rejected':return reject_task(task,reason or 'rejected')
    return task

def reset_pending_task_context(session):
    """Clear only transient task slots; identity, messages and traces live elsewhere."""
    session.pending_slots.clear()

class Engine:
    def __init__(self,llm=None): self.llm=llm

    def handle(self,s,q):
        start=time.monotonic();events=[];calls=[];token=CALLS.set(calls)
        def add(t,**data):events.append(TraceEvent(type=t,data=data,timestamp=datetime.now(timezone.utc)))
        q=redact(normalize(q));s.messages.append({'role':'user','content':q})
        if q in ('继续','继续查询','已登录') and s.pending_slots.get('query'):q=s.pending_slots['query']
        if s.pending_slots.get('intent')=='qualification' and q in ('创业板','科创板','北交所'):q='我能不能开'+q
        decision=route(q);intent=decision['intent'];docs=[];status='answered';ans='';observations=[]
        task=None
        add('input_policy',result='blocked' if intent=='reject' else 'passed')
        try:
            if intent=='reject':
                task=_ensure_active_task(s,intent,q)
                ans=REJECTION;status='rejected';reset_pending_task_context(s);add('risk_block',rule=decision.get('reason'))
            elif intent=='handoff':
                task=_ensure_active_task(s,intent,q)
                ans='我会把问题摘要和本轮处理记录保存为本地演示工单。这里没有真实客服接单；实际业务请联系开户券商官方客服。';status='handoff';reset_pending_task_context(s)
            else:
                if intent=='rules':
                    if self.llm and not public_definition(q) and q not in ('开户需要什么材料','开户需要什么材料？'):
                        d=self.llm.classify(q,[{'role':m['role'],'content':m['content']} for m in s.messages[-5:-1]]);add('llm_route',decision=d)
                        if d['confidence']>=.65:
                            intent=d['intent_id'];decision={'intent':intent,**d.get('slots',{})}
                            if intent=='rules':docs=search(q,domain=d.get('domain') or None)
                        else:intent='unknown'
                    else:
                        docs=search(q)
                        if not docs:intent='unknown'
                # Select the task only after the existing route has resolved.
                task=_ensure_active_task(s,intent,q)
                add('route',pipeline=('Agent Loop' if self.llm else '受控工具流程') if intent in PRIVATE else ('RAG' if docs else intent),intent=intent)
                if intent=='reject':ans=REJECTION;status='rejected';reset_pending_task_context(s);add('risk_block',rule='模型风险分类')
                elif intent=='handoff':ans='该问题需要进一步核查，已进入本地演示工单流程。没有真实坐席接单。';status='handoff';reset_pending_task_context(s)
                elif intent in PRIVATE:
                    # Never trust model-supplied identifiers that the user did not actually provide.
                    if intent=='order':
                        decision['order_id']=order_id(q)
                    if intent=='qualification':decision['board']=next((b for b in ['创业板','科创板','北交所'] if b in q),'')
                    if intent=='order' and not decision.get('order_id'):
                        status='clarify';ans='请提供要查询的模拟订单号，例如 ORD1001 或 ORD1002。仅凭“没成交”还不能判断具体原因。';s.pending_slots={'intent':intent,'query':q}
                    elif intent=='qualification' and not decision.get('board'):
                        status='clarify';ans='你想核对创业板、科创板还是北交所权限？';s.pending_slots={'intent':intent,'query':q}
                    elif not s.authenticated:
                        status='need_auth';ans='这个问题涉及本人账户信息，请先在上方登录模拟账户，我会继续处理。';s.pending_slots={'intent':intent,'query':q};add('auth',result='required')
                    else:
                        add('auth',result='simulation_verified',user_id=s.user_id)
                        ans,status,observations=self._diagnose(s,q,intent,decision,add,start,calls)
                        if status=='answered':
                            docs=citations(task)
                            reset_pending_task_context(s)
                elif docs:
                    task.evidence=knowledge_evidence(task,docs,q)
                    gate=_evaluate_task(task,s,reason='unusable_knowledge' if not task.evidence else None)
                    docs=citations(task) if gate.status=='sufficient' else []
                    if gate.status!='sufficient':raise ValueError('insufficient_evidence')
                    add('retrieve',method='关键词+中文双字词项排序',query=q,citations=[d['id'] for d in docs],version=[d['version'] for d in docs])
                    ans=docs[0]['text']
                    # Reviewed exact FAQ uses the inexpensive fixed response; other rules use grounded generation.
                    faq=q in ('开户需要什么材料','开户需要什么材料？')
                    if self.llm and not faq:
                        g=self.llm.grounded(q,docs)
                        ids={d['id'] for d in docs}
                        if not g.citation_ids or not set(g.citation_ids)<=ids:raise ValueError('invalid_citations')
                        cited=[d for d in docs if d['id'] in g.citation_ids]
                        evidence=' '.join(d['text'] for d in cited)
                        numbers=set(re.findall(r'\d+(?:\.\d+)?',g.answer))
                        if not numbers<=set(re.findall(r'\d+(?:\.\d+)?',evidence)):raise ValueError('unsupported_numeric_claim')
                        if not evidence_supported(g.answer,cited):raise ValueError('unsupported_generated_claim')
                        ans=g.answer;docs=cited
                    else:docs=docs[:1]
                    add('generation',mode='reviewed_FAQ' if faq else ('DeepSeek_evidence_selection' if self.llm else 'evidence_extract'))
                    reset_pending_task_context(s)
                else:
                    prior=task.clarification_count
                    status='handoff' if prior>=1 else 'clarify'
                    ans='还需要补充你正在办理的业务，以及卡在哪一步。涉及订单时请提供模拟订单号。' if status=='clarify' else '连续两轮仍缺少可核验信息，已转入本地演示工单，避免反复追问或猜测。'
                    increment_clarification(task)
                    s.pending_slots={'clarifications':task.clarification_count}
        except Exception as exc:
            # Only stable error codes and class names enter traces; never raw provider bodies.
            code=str(exc) if re.fullmatch(r'[a-z_0-9]{1,60}',str(exc)) else type(exc).__name__
            add('fallback',reason=code)
            if task is None:task=_ensure_active_task(s,intent,q)
            if docs and task.answerability and task.answerability.status=='sufficient':
                docs=docs[:1];ans=docs[0]['text'];status='answered';add('generation',mode='verified_extract_fallback')
            else:
                ans='本轮处理未能安全完成，已停止自动调用并生成本地演示工单。可以稍后重试；真实业务请通过券商官方渠道核查。';status='handoff'
                if task.answerability is None or task.answerability.status=='sufficient':
                    _evaluate_task(task,s,reason='execution_failed')
        finally:
            CALLS.reset(token)
        output_blocked=unsafe_output(ans)
        if output_blocked:
            ans='输出安全检查未通过，本轮不展示生成内容；已进入本地演示工单处理。';status='handoff';add('output_block',rule='禁止建议或敏感信息')
            _evaluate_task(task,s,reason='unsafe')
        elif intent!='handoff' and task.answerability is None:
            reason='unsafe' if status=='rejected' else ('execution_failed' if status=='handoff' and intent in PRIVATE else None)
            _evaluate_task(task,s,reason=reason)
        if status=='answered' and (not task.answerability or task.answerability.status!='sufficient'):
            ans=EVIDENCE_LIMITATION;status='handoff'
        if status!='answered':docs=[]
        if task.answerability:
            # Only knowledge actually rendered is a final supporting citation.
            cited_ids={d['id'] for d in docs}
            if status=='answered':
                task.answerability.evidence_ids=[e.evidence_id for e in task.evidence
                    if e.evidence_id in task.answerability.evidence_ids
                    and (e.kind=='business_fact' or e.source_id in cited_ids)]
            add('answerability',**task.answerability.model_dump(mode='json'))
        _sync_task_status(task,status)
        add('guardrail',result='blocked' if status=='rejected' or output_blocked else 'passed',policy_version='local-policy-v2')
        for call in calls:add('llm',**call)
        elapsed=round((time.monotonic()-start)*1000)
        add('metrics',latency_ms=elapsed,tool_calls=sum(e.type=='tool' for e in events),llm_calls=len(calls),tokens=sum(c.get('usage',{}).get('total_tokens',0) for c in calls),cost_cny=None)
        s.messages.append({'role':'assistant','content':redact(ans)})
        s.messages=s.messages[-100:]
        return AgentResponse(answer=redact(ans),status=status,trace=events,citations=docs,handoff={'reason':intent,'local_only':True} if status=='handoff' else None,intent=intent,trace_id=str(uuid.uuid4()),observations=observations,answerability=task.answerability)

    def _diagnose(self,s,q,intent,decision,add,start,calls):
        allowed=TOOLS[intent];seen=set();observations=[]
        preflight=evaluate(s.active_task,s,can_retrieve=True)
        add('answerability_preflight',**preflight.model_dump(mode='json'))
        for step_index in range(6):
            if time.monotonic()-start>75 or sum(c.get('usage',{}).get('total_tokens',0) for c in calls)>10000:raise ValueError('loop_budget_exceeded')
            if self.llm:
                step=self.llm.plan(q,observations,{n:DESCRIPTIONS[n] for n in allowed})
            else:
                sequence={'qualification':[('get_profile',{}),('get_rule',{'board':decision.get('board')})], 'order':[('get_order_detail',{'order_id':decision.get('order_id')})]}.get(intent,[(allowed[0],{})])
                step={'action':'tool','name':sequence[step_index][0],'args':sequence[step_index][1]} if step_index<len(sequence) else {'action':'answer'}
            add('loop',step=step_index+1,action=step['action'],tool=step.get('name',''))
            s.loop_steps=step_index+1
            if step['action']=='answer':
                gate=_evaluate_task(s.active_task,s)
                if gate.status!='sufficient':return EVIDENCE_LIMITATION,'handoff',observations
                answer=render_facts(fact_observations(s.active_task),intent)
                if answer:return answer,'answered',observations
                raise ValueError('answer_without_required_evidence')
            if step['action'] in ('reject','handoff','clarify'):
                return (REJECTION if step['action']=='reject' else '当前信息不足，无法自动完成核查，已生成本地演示工单。'),'rejected' if step['action']=='reject' else 'handoff',observations
            name,args=step.get('name'),step.get('args',{})
            if name not in allowed:raise ValueError('tool_not_allowed')
            if name=='get_order_detail' and args.get('order_id')!=decision.get('order_id'):raise ValueError('unrequested_resource')
            if name=='get_rule' and args.get('board')!=decision.get('board'):raise ValueError('unrequested_rule')
            key=json.dumps([name,args],sort_keys=True)
            if key in seen:raise ValueError('repeated_tool_call')
            seen.add(key);t=time.monotonic();result=execute(name,args,s)
            # Owner checks run before any observation is sent to the model.
            if name!='search_knowledge':
                add('tool',name=name,args=args,result=result,latency_ms=round((time.monotonic()-t)*1000),data_kind='simulation')
            if result.get('error'):
                reason=result['error'] if result['error'] in ('NOT_OWNER','AUTH_REQUIRED') else 'execution_failed'
                _evaluate_task(s.active_task,s,reason=reason)
                if result['error']=='NOT_OWNER':return '无法查询该订单：订单不属于当前登录账户。已阻止越权访问；本地工单只记录拒绝原因，不包含他人订单。','handoff',observations
                return '工具未能返回有效数据（'+result['error']+'）。请核对输入，已进入本地演示工单处理。','handoff',observations
            if name=='search_knowledge':
                promoted=knowledge_evidence(s.active_task,result.get('citations',[]),args['query'])
                s.active_task.evidence.extend(promoted)
                # Only governed records may be exposed to the next planner step.
                result={'citations':[e.content for e in promoted]}
                add('tool',name=name,args=args,result=result,latency_ms=round((time.monotonic()-t)*1000),data_kind='knowledge')
            else:
                promoted=business_evidence(s.active_task,s,name,args,result)
                if promoted is None:
                    _evaluate_task(s.active_task,s,reason='execution_failed')
                    return EVIDENCE_LIMITATION,'handoff',observations
                s.active_task.evidence.append(promoted)
            if name=='get_order_detail' and s.active_task is not None:
                entity=s.active_task.entities.get('order_id')
                if entity is not None and entity.value==args.get('order_id'):
                    set_entity(s.active_task,entity.model_copy(update={'confirmed':True}))
            observations.append({'name':name,'result':result})
        raise ValueError('max_loop_steps')
