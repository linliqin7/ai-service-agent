import time,json
from dataclasses import dataclass
@dataclass
class LoopLimits:
    max_steps:int=6
    max_cost:float=30  # compatibility; token ceiling is used for current runtime
    max_seconds:float=75
    max_tokens:int=10000
class ToolRegistry:
    def __init__(self,tools=None): self.tools=tools or {}
    def invoke(self,name,args,context):
        if name not in self.tools: raise ValueError(f'未注册工具: {name}')
        return self.tools[name](context=context,**args)
def run_loop(state,planner,tools,limits=None):
    limits=limits or LoopLimits();steps=[];seen=set();start=time.monotonic()
    for _ in range(limits.max_steps):
        if time.monotonic()-start>limits.max_seconds: raise RuntimeError('Agent Loop 超时')
        step=planner(state,steps); steps.append(step)
        if step['action'] in ('answer','reject','handoff','clarify'): return {'status':step['action'],'steps':steps,'answer':step.get('answer','')}
        if step['action']=='tool':
            key=json.dumps([step['name'],step.get('args',{})],sort_keys=True)
            if key in seen: raise RuntimeError('Agent Loop 重复动作')
            seen.add(key);state['observation']=tools.invoke(step['name'],step.get('args',{}),state.get('auth'))
        else: raise ValueError('非法动作')
    raise RuntimeError('Agent Loop 达到最大步数')
