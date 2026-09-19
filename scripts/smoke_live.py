"""Opt-in live integration smoke. The key is read only from the environment."""
import os,json,time,subprocess,getpass
from pathlib import Path
from app.llm.deepseek import DeepSeekClient
from app.runtime.engine import Engine
from app.schemas import SessionState

def main():
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        result=subprocess.run(['security','find-generic-password','-s','brokerage-support-agent.deepseek','-a',getpass.getuser(),'-w'],capture_output=True,text=True)
        if result.returncode==0:key=result.stdout.strip()
    if not key:raise SystemExit('请配置 DEEPSEEK_API_KEY 后运行')
    engine=Engine(DeepSeekClient(key));out=[]
    for query,user in [('请解释可用资金与可取资金为什么不同',None),('我能不能开创业板','U1002'),('查 ORD1001 为什么没成交','U1001'),('开户走到一半卡着了，能查查审核的情况吗','U1003')]:
        s=SessionState(session_id='live-probe',user_id=user,authenticated=bool(user))
        r=engine.handle(s,query)
        row={'query':query,'status':r.status,'answer':r.answer,'intent':r.intent,'llm_calls':[t.data for t in r.trace if t.type=='llm'],'tools':[t.data['name'] for t in r.trace if t.type=='tool'],'fallback':[t.data for t in r.trace if t.type=='fallback'],'passed':r.status=='answered' and any(t.type=='llm' and t.data.get('status')=='ok' for t in r.trace)}
        out.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    Path('eval/live-report.json').write_text(json.dumps({'run_at':time.strftime('%Y-%m-%d %H:%M:%S'),'data_kind':'simulation','results':out},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
