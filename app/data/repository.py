"""All records in this module are synthetic fixtures, never live brokerage data."""
from copy import deepcopy
USERS={
 'U1001':{'user_id':'U1001','asset':180000,'asset_bucket':'30万以下','lifecycle':'已入金未交易','risk_level':2,'trade_months':18,'kyc':True,'account_status':'正常','onboarding':'开户审核通过','risk_valid':True,'available':80000,'withdrawable':30000,'frozen':50000,'asset_basis':'模拟近20个交易日日均资产','holdings':[]},
 'U1002':{'user_id':'U1002','asset':620000,'asset_bucket':'50-100万','lifecycle':'活跃交易','risk_level':4,'trade_months':42,'kyc':True,'account_status':'正常','onboarding':'开户审核通过','risk_valid':True,'available':120000,'withdrawable':90000,'frozen':30000,'asset_basis':'模拟近20个交易日日均资产','holdings':[{'name':'示例证券A','quantity':1000,'valuation':500000}]},
 'U1003':{'user_id':'U1003','asset':0,'asset_bucket':'30万以下','lifecycle':'开户审核中','risk_level':1,'trade_months':0,'kyc':False,'account_status':'待补充材料','onboarding':'身份资料待复核，请在官方开户页面补充清晰证件影像','risk_valid':False,'available':0,'withdrawable':0,'frozen':0,'asset_basis':'模拟统计','holdings':[]},
 'U1004':{'user_id':'U1004','asset':260000,'asset_bucket':'30万以下','lifecycle':'账户维护','risk_level':3,'trade_months':36,'kyc':False,'account_status':'证件待更新，部分业务受限','onboarding':'已开户','risk_valid':False,'available':60000,'withdrawable':0,'frozen':60000,'asset_basis':'模拟近20个交易日日均资产','holdings':[]}}
ORDERS={
 'ORD1001':{'order_id':'ORD1001','user_id':'U1001','status':'已撤单','reason_code':'USER_CANCELLED','reason':'撤单回报已确认；仅凭订单状态不能推断此前未成交的行情原因','next':'查看当日委托回报与资金解冻记录，如有争议提交人工核查'},
 'ORD1002':{'order_id':'ORD1002','user_id':'U1002','status':'废单','reason_code':'INSUFFICIENT_FUNDS','reason':'交易校验返回可用资金不足','next':'核对委托金额、费用与资金占用；是否重新委托由你自行决定'},
 'ORD1003':{'order_id':'ORD1003','user_id':'U1002','status':'部分成交','reason_code':'PARTIAL_FILL','reason':'成交回报显示部分数量成交，剩余委托仍待处理','next':'查看未成交数量及委托状态；不能保证后续成交'}}
# Illustration only: never represented as current statutory eligibility thresholds.
RULES={b:{'asset':a,'months':24,'risk':3,'version':'simulation-2026.09','source':'本项目资格校验测试规则','review_status':'demo_reviewed','effective_at':'2026-01-01','expires_at':'2027-01-01'} for b,a in [('创业板',100000),('科创板',500000),('北交所',500000)]}
def profile(uid): return deepcopy(USERS.get(uid))
def order(oid,uid):
    o=ORDERS.get(oid)
    if not o: return {'error':'ORDER_NOT_FOUND'}
    if o['user_id']!=uid: return {'error':'NOT_OWNER'}
    return deepcopy(o)
def rule(board): return deepcopy(RULES.get(board))
