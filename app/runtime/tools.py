from datetime import date
from pydantic import BaseModel, ConfigDict, Field
from app.data.repository import profile, order, rule
from app.rag.retriever import search

class Empty(BaseModel):
    model_config=ConfigDict(extra='forbid')
class OrderArgs(Empty):
    order_id: str = Field(pattern=r'^ORD\d{4,10}$')
class RuleArgs(Empty):
    board: str = Field(pattern=r'^(创业板|科创板|北交所)$')
class SearchArgs(Empty):
    query: str = Field(min_length=2,max_length=500)

SCHEMAS={'get_profile':Empty,'get_account':Empty,'get_funds':Empty,'get_risk':Empty,'get_holdings':Empty,'get_order_detail':OrderArgs,'get_rule':RuleArgs,'search_knowledge':SearchArgs}
DESCRIPTIONS={'get_profile':'模拟资产、交易经验和画像，无参数','get_account':'本人开户进度及账户状态，无参数','get_funds':'本人可用可取冻结资金，无参数','get_risk':'本人风险测评状态，无参数','get_holdings':'本人模拟持仓，无参数','get_order_detail':'本人订单状态，参数 order_id','get_rule':'演示权限规则，参数 board','search_knowledge':'查询业务说明，参数 query'}

def execute(name,args,session):
    if name not in SCHEMAS: raise ValueError('tool_not_allowed')
    params=SCHEMAS[name].model_validate(args).model_dump()
    if name=='search_knowledge': return {'citations':search(params['query'])}
    if name=='get_rule':
        r=rule(params['board'])
        if not r or not r['effective_at']<=date.today().isoformat()<r['expires_at']: return {'error':'RULE_EXPIRED'}
        return {**r,'board':params['board'],'data_kind':'simulation'}
    if not session.authenticated or not profile(session.user_id): return {'error':'AUTH_REQUIRED'}
    u=profile(session.user_id)
    if name=='get_order_detail':
        result=order(params['order_id'],session.user_id)
        return {**result,'data_kind':'simulation'} if 'error' not in result else result
    fields={'get_profile':['user_id','asset','asset_bucket','lifecycle','trade_months','risk_level','risk_valid','kyc','asset_basis'],
            'get_account':['account_status','onboarding','kyc'], 'get_funds':['available','withdrawable','frozen'],
            'get_risk':['risk_level','risk_valid'], 'get_holdings':['holdings','asset']}
    return {**{k:u[k] for k in fields[name]},'data_kind':'simulation'}

def render_facts(observations,intent):
    by={o['name']:o['result'] for o in observations}
    if intent=='qualification':
        u,r=by.get('get_profile'),by.get('get_rule')
        if not u or not r: return None
        checks=[('资产',u['asset']>=r['asset'],f"{u['asset']:,} / {r['asset']:,} 元（{u['asset_basis']}）"),('交易经验',u['trade_months']>=r['months'],f"{u['trade_months']} / {r['months']} 个月"),('风险测评',u['risk_level']>=r['risk'] and u['risk_valid'],f"R{u['risk_level']} / 演示要求 R{r['risk']}，有效状态：{'有效' if u['risk_valid'] else '待更新'}"),('身份资料',u['kyc'],'已完成' if u['kyc'] else '待补充')]
        miss=[n for n,ok,_ in checks if not ok]
        return f"{r['board']}模拟资格核对\n"+'\n'.join(f"{'✓' if ok else '待补充'} {n}：{v}" for n,ok,v in checks)+'\n'+('当前未满足：'+'、'.join(miss) if miss else '这些演示校验项均满足')+'。\n这不是开通批准：以上数字仅为测试规则，不能作为最新监管门槛。真实开通还需券商核验完整适当性条件。'
    if intent=='order':
        o=by.get('get_order_detail')
        if not o:return None
        return f"模拟订单 {o['order_id']}\n状态：{o['status']}\n原因：{o['reason']}\n下一步：{o['next']}。\n数据来自本地测试接口，不代表真实委托。"
    names={'account':'get_account','funds':'get_funds','risk':'get_risk','holdings':'get_holdings'}
    d=by.get(names.get(intent,''))
    if not d:return None
    if intent=='account': return f"模拟账户状态：{d['account_status']}。\n开户进度：{d['onboarding']}。\n实际办理请使用开户券商官方 App。"
    if intent=='funds': return f"模拟资金状态\n可用：{d['available']:,} 元\n可取：{d['withdrawable']:,} 元\n冻结：{d['frozen']:,} 元\n可用不等于可取。本接口未提供冻结明细及银行回执，不能进一步断言具体冻结原因或到账时间；有争议可提交人工核查。"
    if intent=='risk': return f"模拟风险测评为 R{d['risk_level']}，{'当前有效' if d['risk_valid'] else '已失效，需在官方 App 重新如实测评'}。风险等级不代表某产品适合购买，不能据此给出投资推荐。"
    if intent=='holdings': return '模拟资产：'+f"{d['asset']:,} 元。\n"+ ('\n'.join(f"{h['name']}：{h['quantity']} 份，模拟估值 {h['valuation']:,} 元" for h in d['holdings']) if d['holdings'] else '当前测试账户无持仓。')+'\n没有连接实时行情，不能据此计算真实收益。'
