import json,sqlite3,uuid,time
from pathlib import Path
from app.schemas import SessionState
from app.runtime.policy import redact

class Store:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,payload TEXT,updated REAL);
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,session_id TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,session_id TEXT,trace_id TEXT,rating TEXT);''')
        Path(path).chmod(0o600)
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def save(self,s):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?)',(s.session_id,s.model_dump_json(),time.time()))
    def get(self,sid):
        with self.connect() as db:row=db.execute('SELECT payload,updated FROM sessions WHERE id=?',(sid,)).fetchone()
        return SessionState.model_validate_json(row[0]) if row and time.time()-row[1]<86400 else None
    def ticket(self,s,reason):
        ticket={'id':'TK-'+uuid.uuid4().hex[:10].upper(),'reason':reason,'status':'本地待处理','created_at':time.time(),'local_only':True,'summary':redact('\n'.join(m['content'] for m in s.messages[-6:] if m['role']=='user'))[:1500], 'authenticated':s.authenticated,'user_id':s.user_id,'trace_events':len(s.traces)}
        with self.connect() as db:db.execute('INSERT INTO tickets VALUES(?,?,?)',(ticket['id'],s.session_id,json.dumps(ticket,ensure_ascii=False)))
        return ticket
    def tickets(self,sid):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM tickets WHERE session_id=?',(sid,)).fetchall()]
    def feedback(self,sid,tid,rating):
        with self.connect() as db:db.execute('INSERT INTO feedback VALUES(?,?,?,?)',(uuid.uuid4().hex,sid,tid,rating))
    def clear_private(self,sid):
        with self.connect() as db:
            db.execute('DELETE FROM tickets WHERE session_id=?',(sid,));db.execute('DELETE FROM feedback WHERE session_id=?',(sid,))
    def delete(self,sid):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE id=?',(sid,));db.execute('DELETE FROM tickets WHERE session_id=?',(sid,));db.execute('DELETE FROM feedback WHERE session_id=?',(sid,))
