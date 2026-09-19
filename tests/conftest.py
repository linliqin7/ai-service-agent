"""Keep tests away from the user's credentials and persistent sessions."""
import os,tempfile,atexit,shutil
_test_dir=tempfile.mkdtemp(prefix='brokerage-tests-')
os.environ['AGENT_DB_PATH']=os.path.join(_test_dir,'test.sqlite3')
os.environ['DEEPSEEK_API_KEY']=''
atexit.register(shutil.rmtree,_test_dir,ignore_errors=True)
