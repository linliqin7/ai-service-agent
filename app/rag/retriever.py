"""Chinese keyword + character-bigram lexical retrieval; no embedding claims."""
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from app.rag.governance import current
PATH=Path(__file__).parent/'fixtures'/'knowledge.json'
ALIASES={'没成':'未成交','钱转不出':'出金失败','银证':'银证转账','身份证到期':'证件更新','买卖记录':'订单','打新':'新股申购'}
def records(): return json.loads(PATH.read_text())
def tokens(text): return Counter(text[i:i+2] for i in range(len(text)-1) if text[i:i+2].strip())
def search(q,domain=None,top_k=3,as_of=None,audience='public',items=None):
    for word,rewrite in ALIASES.items(): q=q.replace(word,rewrite)
    pool=[k for k in (items if items is not None else records()) if current(k,as_of,audience) and (not domain or k['domain']==domain)]
    # Domain is determined by matched business terms, not global OR over unrelated documents.
    anchors=[(sum(len(w) for w in k['keywords'] if w in q),k['domain']) for k in pool]
    if not domain and anchors and max(a[0] for a in anchors)>0:
        selected=max(anchors,key=lambda x:x[0])[1]; pool=[k for k in pool if k['domain']==selected]
    qt=tokens(q); hits=[]
    for k in pool:
        count=sum(1 for w in k['keywords'] if w in q)
        kt=tokens(k['title']+' '+k['text']); overlap=sum(min(v,kt[t]) for t,v in qt.items())
        score=count*3 + overlap/max(1,math.sqrt(sum(kt.values())))
        if count or (overlap>=4 and score>=.8): hits.append((score,k))
    ranked=sorted(hits,key=lambda x:-x[0])
    # Multiple active versions of the same title are a governance conflict, never guess.
    titles={}
    for _,k in ranked:
        if k['title'] in titles and titles[k['title']]!=k['version']: return []
        titles[k['title']]=k['version']
    return [{**k,'score':round(s,3)} for s,k in ranked[:top_k]]
