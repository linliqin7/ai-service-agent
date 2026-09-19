import pytest
from pydantic import BaseModel
from app.llm.deepseek import DeepSeekClient,DeepSeekError
from app.runtime.loop import run_loop,ToolRegistry,LoopLimits
class X(BaseModel): value:str
def test_missing_api_key_is_explicit():
 with pytest.raises(DeepSeekError): DeepSeekClient().complete([],X)
def test_loop_enforces_registered_tools_and_stops():
 def plan(state,steps):
  return {'action':'tool','name':'ok'} if not steps else {'action':'answer','answer':'done'}
 tools=ToolRegistry({'ok':lambda context:'observed'})
 out=run_loop({},plan,tools); assert out['status']=='answer' and len(out['steps'])==2
def test_loop_unknown_tool_fails_closed():
 with pytest.raises(ValueError): run_loop({},lambda s,st:{'action':'tool','name':'bad'},ToolRegistry(),LoopLimits(max_steps=1))
