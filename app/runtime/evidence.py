"""Task-local promotion of controlled tool results and governed knowledge.

Only the executor calls business_evidence after execute(); planner output is
never an observation source. This module does not run tools or models.
"""
from copy import deepcopy
from datetime import date

from pydantic import ValidationError

from app.data.repository import profile
from app.rag.governance import current
from app.rag.retriever import search
from app.runtime.tools import SCHEMAS
from app.schemas import Evidence, SessionState, TaskState

FACT_FIELDS = {
    'get_account': ('ACCOUNT_STATUS', ('account_status','onboarding','kyc')),
    'get_funds': ('ACCOUNT_BALANCE', ('available','withdrawable','frozen')),
    'get_risk': ('RISK_LEVEL', ('risk_level','risk_valid')),
    'get_holdings': ('HOLDING_LIST', ('holdings','asset')),
    'get_profile': ('PROFILE', ('asset','trade_months','risk_level','risk_valid','kyc','asset_basis')),
    'get_rule': ('QUALIFICATION_RULE', ('asset','months','risk','board')),
}


def fact_supports(name: str, result: dict) -> list:
    if name == 'get_order_detail':
        supports = ['ORDER_STATUS'] if result.get('status') else []
        # A rule/definition or a reason code alone is not an individual cause.
        if isinstance(result.get('reason'), str) and result['reason'].strip():
            supports.append('ORDER_REASON')
        return supports
    if name not in FACT_FIELDS:
        return []
    support, fields = FACT_FIELDS[name]
    if all(k in result and result[k] is not None and result[k] != '' for k in fields):
        return [support]
    return []


def business_evidence(task: TaskState, session: SessionState, name: str,
                      args: dict, result: dict, *, as_of: date | None = None) -> Evidence | None:
    if name not in {*FACT_FIELDS, 'get_order_detail'} or result.get('error'):
        return None
    try:
        SCHEMAS[name].model_validate(args)
    except ValidationError:
        return None
    if not session.authenticated or not profile(session.user_id):
        return None
    binding = {'user_id': session.user_id}
    if result.get('user_id', session.user_id) != session.user_id:
        return None
    if name == 'get_order_detail':
        entity = task.entities.get('order_id')
        if (entity is None or entity.value != args.get('order_id')
                or result.get('order_id') != entity.value
                or result.get('user_id') != session.user_id):
            return None
        binding['order_id'] = entity.value
    if name == 'get_rule':
        entity = task.entities.get('board')
        if entity is None or entity.value != args.get('board') or result.get('board') != entity.value:
            return None
        binding['board'] = entity.value
    try:
        valid_from = date.fromisoformat(result['effective_at']) if result.get('effective_at') else None
        valid_to = date.fromisoformat(result['expires_at']) if result.get('expires_at') else None
    except (ValueError, TypeError):
        return None
    today = as_of or date.today()
    if (valid_from and today < valid_from) or (valid_to and today >= valid_to):
        return None
    resource = binding.get('order_id') or binding.get('board') or session.user_id
    return Evidence(task_id=task.task_id, kind='business_fact', source=name,
        source_id=resource, version=result.get('version'), valid_from=valid_from,
        valid_to=valid_to, audience='private', scope='本人模拟业务查询',
        content=deepcopy(result), verified=True, supports=fact_supports(name,result),
        entity_binding=binding, conflict_key=f'{name}:{resource}')


def knowledge_evidence(task: TaskState, items: list[dict], query: str,
                       *, as_of: date | None = None) -> list[Evidence]:
    usable = []
    for record in items:
        try:
            if record.get('id') and current(record, as_of=as_of, audience='public'):
                usable.append(record)
        except (ValidationError, ValueError, TypeError):
            continue
    # Reuse the existing lexical matcher, without its conflict suppression:
    # keep distinct versions so the gate can explain a conflict.
    domain = {'order':'交易','funds':'资金'}.get(task.task_type)
    admitted = []
    for record in usable:
        if not search(query, items=[record], domain=domain, as_of=as_of):
            continue
        support = 'ORDER_RULE' if task.task_type == 'order' else 'PUBLIC_DEFINITION'
        admitted.append(Evidence(task_id=task.task_id, kind='knowledge',
            source='search_knowledge', source_id=record['id'], version=record['version'],
            valid_from=record['effective_at'], valid_to=record['expires_at'],
            audience=record['audience'], scope=record['scope'], content=deepcopy(record),
            verified=True, supports=[support],
            conflict_key=f"{record['domain']}:{record['title']}"))
    return admitted


def citations(task: TaskState) -> list[dict]:
    """Only selected, current-task knowledge can be shown as citations."""
    selected = set(task.answerability.evidence_ids if task.answerability else [])
    return [deepcopy(e.content) for e in task.evidence
            if e.task_id == task.task_id and e.kind == 'knowledge' and e.evidence_id in selected]


def fact_observations(task: TaskState) -> list[dict]:
    selected = set(task.answerability.evidence_ids if task.answerability else [])
    observations = [{'name':e.source, 'result':deepcopy(e.content)} for e in task.evidence
                    if e.kind == 'business_fact' and e.evidence_id in selected]
    docs = citations(task)
    if docs:
        observations.append({'name':'search_knowledge','result':{'citations':docs}})
    return observations
