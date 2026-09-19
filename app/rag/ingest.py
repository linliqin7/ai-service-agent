"""Local operator-only JSON import. No public write endpoint."""
import argparse,json,os,tempfile
from pathlib import Path
from app.rag.governance import KnowledgeRecord
from app.rag.retriever import PATH

def ingest_document(path, destination=PATH):
    incoming=json.loads(Path(path).read_text())
    rows=[KnowledgeRecord.model_validate(r).model_dump(mode='json') for r in incoming]
    old=json.loads(Path(destination).read_text()) if Path(destination).exists() else []
    merged={r['id']:r for r in old}
    for row in rows:
        if row['id'] in merged and merged[row['id']] != row: raise ValueError('已有 ID 不可覆盖，请建立新版本并停用旧版本')
        merged[row['id']]=row
    values=list(merged.values())
    for i,a in enumerate(values):
        for b in values[i+1:]:
            if a['title']==b['title'] and a['review_status'] in ('approved','demo_reviewed') and b['review_status'] in ('approved','demo_reviewed') and max(a['effective_at'],b['effective_at'])<min(a['expires_at'],b['expires_at']):
                raise ValueError('同名规则有效期重叠')
    target=Path(destination); target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=target.parent,delete=False) as f:
        json.dump(values,f,ensure_ascii=False,indent=2); temp=f.name
    os.replace(temp,target)
    return len(rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path');a=p.parse_args();print('导入条数：',ingest_document(a.path))
