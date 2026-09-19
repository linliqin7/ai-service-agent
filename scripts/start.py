"""Local startup; secrets live in the process or macOS Keychain, never the source tree."""
import getpass,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
if not os.environ.get('DEEPSEEK_API_KEY') and sys.platform=='darwin':
    result=subprocess.run(['security','find-generic-password','-s','brokerage-support-agent.deepseek','-a',getpass.getuser(),'-w'],capture_output=True,text=True)
    if result.returncode==0:os.environ['DEEPSEEK_API_KEY']=result.stdout.strip()
if not os.environ.get('DEEPSEEK_API_KEY'):
    print('未找到 DeepSeek 密钥，将运行本地规则模式。需要模型时请配置环境变量或系统钥匙串。')
import uvicorn
print('打开 http://127.0.0.1:8000 即可使用。按 Ctrl+C 停止。')
uvicorn.run('app.api:app',host='127.0.0.1',port=8000,access_log=False)
