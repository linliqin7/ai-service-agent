"""Reproducible local contract evaluation. No LLM judge or production metric claims."""
import json,time,statistics,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.runtime.engine import Engine
from app.schemas import SessionState
from app.runtime.tools import execute
ROOT=Path(__file__).resolve().parent

def evaluate(path):
    cases=json.loads(Path(path).read_text());rows=[]
    for case in cases:
        s=SessionState(session_id=case['id'],user_id=case.get('user_id'),authenticated=bool(case.get('user_id')))
        start=time.monotonic()
        for q in case.get('turns',[case['query']]):r=Engine().handle(s,q)
        failures=[]
        if r.status!=case['expected_status']:failures.append('状态不符')
        if r.intent!=case['intent']:failures.append('意图不符')
        for text in case['expected_contains']:
            if text not in r.answer:failures.append('缺关键事实:'+text)
        for text in case['forbidden']:
            if text in r.answer:failures.append('包含禁止内容')
        if not any(e.type=='guardrail' for e in r.trace):failures.append('缺输出检查')
        if r.status=='answered' and r.intent=='rules' and not r.citations:failures.append('缺引用')
        retrieved={d['id'] for d in r.citations};gold=set(case.get('relevant_ids',[]))
        if gold and not gold & retrieved:failures.append('未命中标准依据')
        rows.append({'id':case['id'],'query':case['query'],'query_type':case['query_type'],'domain':case['domain'],'expected_status':case['expected_status'],'actual_status':r.status,'expected_intent':case['intent'],'actual_intent':r.intent,'passed':not failures,'failures':failures,'answer':r.answer,'retrieved_ids':sorted(retrieved),'relevant_ids':sorted(gold),'latency_ms':round((time.monotonic()-start)*1000,2)})
    unsafe=[r for r in rows if r['expected_status']=='rejected'];safe=[r for r in rows if r['expected_status']!='rejected']
    rag=[r for r in rows if r['relevant_ids']]
    return {'rag_topk_hit':sum(bool(set(r['relevant_ids'])&set(r['retrieved_ids'])) for r in rag),'rag_denominator':len(rag),'name':Path(path).stem,'total':len(rows),'passed':sum(r['passed'] for r in rows),'intent_correct':sum(r['actual_intent']==r['expected_intent'] for r in rows),'guardrail_missed':sum(r['actual_status']!='rejected' for r in unsafe),'guardrail_missed_denominator':len(unsafe),'guardrail_false_positive':sum(r['actual_status']=='rejected' for r in safe),'guardrail_false_positive_denominator':len(safe),'p50_ms':statistics.median(r['latency_ms'] for r in rows),'results':rows}
def evaluate_answerability(path):
    """Fixed synthetic contracts; the override is scoped to a single case.

    The source database and production fixture files are never changed.
    """
    rows=[]
    for case in json.loads(Path(path).read_text()):
        session=SessionState(session_id=case['id'],user_id=case.get('user_id'),authenticated=bool(case.get('user_id')))
        def local_tool(name,args,state):
            result=execute(name,args,state)
            if case.get('order_status_only') and name=='get_order_detail' and not result.get('error'):
                return {k:result[k] for k in ('order_id','user_id','status')}
            return result
        with patch('app.runtime.engine.execute',side_effect=local_tool):
            for query in case['turns']:response=Engine().handle(session,query)
        decision=response.answerability
        sources=sorted({e.source_id for e in session.active_task.evidence})
        failures=[]
        if decision is None:failures.append('missing_decision')
        else:
            if decision.status!=case['label']:failures.append('answerability_label')
            if set(decision.required_supports)!=set(case['required_supports']):failures.append('required_supports')
            if decision.next_action!=case['expected_next_action']:failures.append('next_action')
            if any(e.task_id!=session.active_task.task_id for e in session.active_task.evidence):failures.append('cross_task_evidence')
            if decision.status!='sufficient' and response.status=='answered':failures.append('gate_bypass')
        if 'evidence_sources' in case and set(sources)!=set(case['evidence_sources']):failures.append('evidence_sources')
        if set(sources)&set(case.get('forbidden_evidence_sources',[])):failures.append('evidence_pollution')
        if case.get('order_status_only') and any(s in response.answer for s in ('资金不足','价格不合适','流动性不足')):failures.append('invented_reason')
        rows.append({'id':case['id'],'query':case['turns'][-1], 'passed':not failures,'failures':failures,
            'expected_label':case['label'],'answerability_label':decision.status if decision else None,
            'required_supports':decision.required_supports if decision else [],
            'evidence_ids':decision.evidence_ids if decision else [], 'evidence_source_ids':sources,
            'expected_next_action':case['expected_next_action'], 'next_action':decision.next_action if decision else None})
    return {'name':'answerability','total':len(rows),'passed':sum(r['passed'] for r in rows),'results':rows}

if __name__=='__main__':
    report={'run_at':time.strftime('%Y-%m-%d %H:%M:%S'),'mode':'offline_contract','synthetic':True,'splits':[evaluate(ROOT/'main.json'),evaluate(ROOT/'holdout.json')], 'answerability':evaluate_answerability(ROOT/'answerability.json')}
    (ROOT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    results = [*report['splits'], report['answerability']]
    for s in results:
        print(s['name'],f"{s['passed']}/{s['total']}")
        for r in s['results']:
            if not r['passed']:print(r['id'],r['query'],r['failures'])
    if any(s['passed']!=s['total'] for s in results):sys.exit(1)
