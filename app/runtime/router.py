import re
from app.runtime.policy import risk_reason

def order_id(q):
    match=re.search(r'(?<![A-Z0-9_])ORD\d{4,10}(?![A-Z0-9_])',q.upper())
    return match.group() if match else ''

def public_definition(q):
    public_terms=['解释','区别','材料','为什么不能','办理流程','什么意思','什么是','怎么理解','定义','代表什么','怎么找回','如何找回']
    private_terms=['我的账户','我的订单','我的委托','我的资金','帮我查','这笔','那笔','委托编号','订单号','订单状态']
    return any(t in q for t in public_terms) and not any(t in q for t in private_terms)

def route(q):
    risk=risk_reason(q)
    if risk:return {'intent':'reject','reason':risk}
    if any(t in q for t in ['投诉','转人工','找人工','工单','申诉']):return {'intent':'handoff'}
    oid=order_id(q)
    board=next((b for b in ['创业板','科创板','北交所'] if b in q),'')
    if (board or '权限' in q) and any(w in q for w in ['我能','我符合','我是否','我可以','还差','帮我核对','我的资格']):
        return {'intent':'qualification','board':board}
    # Public concept questions must be classified before generic order terms.
    # For example, “未成交是什么意思？” asks for a definition; it is not
    # a request to inspect the user's order.
    if public_definition(q):return {'intent':'rules'}
    if oid or any(w in q for w in ['我的委托','我的订单','没成交','没有成交','未成交','那笔','这笔']):
        return {'intent':'order','order_id':oid}
    personal=any(w in q for w in ['我','查一下','帮查','到哪了'])
    for intent,terms in [('funds',['可取','可用','出金','取钱','入金','转账','到账','资金']),('risk',['风险测评','测评结果','风险等级']),('holdings',['持仓','资产','盈亏']),('account',['开户进度','审核','账户状态','证件到期','账户冻结'])]:
        if personal and any(t in q for t in terms):return {'intent':intent}
    return {'intent':'rules'}
