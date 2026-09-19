import re
import unicodedata

def normalize(text):
    return re.sub(r'[\u200b-\u200f\ufeff]', '', unicodedata.normalize('NFKC', text)).strip()

def redact(text):
    text=re.sub(r'sk-[A-Za-z0-9_-]{12,}', '[密钥已隐藏]', text)
    text=re.sub(r'(?<!\d)\d{11,19}(?!\d)', '[敏感号码已隐藏]', text)
    text=re.sub(r'((?:密码|验证码)\s*[:：是为]?\s*)[A-Za-z0-9]{4,}', r'\1[已隐藏]', text)
    return text

def risk_reason(query):
    q=normalize(query).lower()
    groups=[('提示词注入', r'忽略.{0,12}(规则|指令)|系统提示词|system prompt|ignore.{0,20}instructions|绕过.{0,10}(鉴权|验证|限制|规则)'),
            ('越权查询',r'(查|看|获取|导出).{0,12}(别人|他人|其他人|全部客户).{0,10}(账户|订单|资产|信息)|other.{0,8}(account|customer)'),
            ('代客操作',r'(帮我|替我|代我|直接).{0,8}(下单|买入|卖出|撤单|转账|交易)|execute.{0,10}(trade|order)'),
            ('投资建议',r'买哪只|买什么(股票|基金)|能不能买|值得买|会不会[涨跌]|预测.{0,8}[涨跌]|(推荐|建议).{0,12}(股票|基金|买入|卖出)|买入.{0,12}(合适|好吗)|which stock to buy|should i buy|收益多少|明天.{0,6}(涨|跌)')]
    for reason,pattern in groups:
        if re.search(pattern,q): return reason
    if re.search(r'稳赚|保本|保证收益',q) and not re.search(r'为什么不能|为何不能|不保本|不能保本|不能承诺|是什么|什么意思',q):
        return '收益承诺'
    return None

def unsafe_output(text):
    return bool(re.search(r'sk-[A-Za-z0-9_-]{12,}|(?:建议你|推荐你|你应该)(?:立即)?(?:买入|卖出)|(?:请提供|发给我|告诉我).{0,8}(?:密码|验证码)|保证(?:盈利|赚钱|收益)',text))

REJECTION='我不能提供具体买卖建议、涨跌预测、收益承诺、代客操作或查询他人信息。可以继续帮你了解业务规则、查询本人模拟账户；投资建议请通过券商官方渠道联系具备资质的投顾。'


def evidence_supported(answer, docs):
    """Only complete evidence sentences are selectable; do not permit removing negation."""
    def sentences(text):
        return [t.strip().rstrip('。！？') for t in re.split(r'(?<=[。！？])|\n',text) if t.strip()]
    allowed={t for d in docs for t in sentences(d['text'])}
    selected=sentences(answer)
    return bool(selected) and all(t in allowed for t in selected)
