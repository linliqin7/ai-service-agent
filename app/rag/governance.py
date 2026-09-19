from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
class KnowledgeRecord(BaseModel):
    id: str
    title: str
    domain: str
    version: str
    source: str
    source_url: str = ''
    effective_at: date
    expires_at: date
    review_status: Literal['draft','demo_reviewed','approved','retired']
    audience: Literal['public','staff'] = 'public'
    scope: str = '个人项目演示'
    direct_answer: bool = True
    text: str = Field(min_length=10, max_length=5000)
    keywords: list[str]
    @model_validator(mode='after')
    def dates(self):
        if self.effective_at >= self.expires_at: raise ValueError('生效时间必须早于失效时间')
        return self

def current(record, as_of=None, audience='public'):
    r=KnowledgeRecord.model_validate(record)
    return r.effective_at <= (as_of or date.today()) < r.expires_at and r.review_status in ('demo_reviewed','approved') and (r.audience=='public' or audience=='staff') and r.direct_answer
