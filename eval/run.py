"""Reproducible local contract evaluation. No LLM judge or production metric claims."""
import json,time,statistics,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.runtime.engine import Engine
from app.schemas import SessionState
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
if __name__=='__main__':
    report={'run_at':time.strftime('%Y-%m-%d %H:%M:%S'),'mode':'offline_contract','synthetic':True,'splits':[evaluate(ROOT/'main.json'),evaluate(ROOT/'holdout.json')]}
    (ROOT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    for s in report['splits']:
        print(s['name'],f"{s['passed']}/{s['total']}")
        for r in s['results']:
            if not r['passed']:print(r['id'],r['query'],r['failures'])
