"""Deterministic support coverage gate. No model calls or global registry."""
from datetime import date
import json

from pydantic import ValidationError

from app.rag.governance import current
from app.runtime.evidence import FACT_FIELDS, fact_supports
from app.runtime.policy import risk_reason, unsafe_output
from app.schemas import AnswerabilityDecision, SessionState, TaskState, TaskStatus

REQUIRED = {
    'rules':['PUBLIC_DEFINITION'], 'account':['ACCOUNT_STATUS'],
    'funds':['ACCOUNT_BALANCE'], 'risk':['RISK_LEVEL'], 'holdings':['HOLDING_LIST'],
    'qualification':['PROFILE','QUALIFICATION_RULE'], 'order':['ORDER_STATUS'],
}


def required_supports(task: TaskState) -> list:
    required = list(REQUIRED.get(task.task_type, []))
    if task.task_type == 'order' and any(w in task.objective for w in ('为什么','原因','为何','怎么','诊断','没成','未成交','没有成交')):
        required.append('ORDER_REASON')
    return required


def evaluate(task: TaskState, session: SessionState, *, as_of: date | None = None,
             can_retrieve: bool = False, reason: str | None = None) -> AnswerabilityDecision:
    today = as_of or date.today()
    required = required_supports(task)
    accepted = []
    satisfied = set()

    def decision(status, action, code):
        return AnswerabilityDecision(task_id=task.task_id, status=status,
            required_supports=required, satisfied_supports=sorted(satisfied),
            missing_supports=[s for s in required if s not in satisfied],
            evidence_ids=[e.evidence_id for e in accepted], next_action=action, reason_code=code)

    if task.task_type == 'reject' or risk_reason(task.objective) or reason == 'unsafe':
        return decision('unsafe','reject','risk_policy')
    if reason in ('NOT_OWNER','AUTH_REQUIRED'):
        return decision('unauthorized','handoff',reason)
    if task.task_type not in REQUIRED:
        action='clarify' if task.task_type == 'unknown' and task.clarification_count < 2 else 'handoff'
        return decision('out_of_scope',action,'unsupported_task')
    if task.status in (TaskStatus.ABANDONED, TaskStatus.REJECTED, TaskStatus.HANDOFF):
        return decision('out_of_scope','handoff','terminal_task')
    needed = {'order':'order_id','qualification':'board'}.get(task.task_type)
    if needed and (needed not in task.entities or not task.entities[needed].value):
        return decision('missing_user_information','clarify',f'missing_{needed}')
    if task.task_type != 'rules' and not session.authenticated:
        return decision('missing_user_information','clarify','authentication_required')
    if reason == 'execution_failed':
        return decision('missing_business_evidence','handoff',reason)
    invalid = reason == 'unusable_knowledge'
    conflicts = {}
    for evidence in task.evidence:
        if evidence.task_id != task.task_id or not evidence.verified:
            invalid = True
            continue
        if ((evidence.valid_from and today < evidence.valid_from)
                or (evidence.valid_to and today >= evidence.valid_to)):
            invalid = True
            continue
        if evidence.kind == 'knowledge':
            try:
                usable = (evidence.source == 'search_knowledge' and evidence.audience == 'public'
                          and evidence.source_id == evidence.content.get('id')
                          and current(evidence.content, as_of=today, audience='public'))
            except (ValidationError, ValueError, TypeError):
                usable = False
            if not usable or unsafe_output(evidence.content.get('text','')):
                invalid = True
                continue
            expected_support = 'ORDER_RULE' if task.task_type == 'order' else 'PUBLIC_DEFINITION'
            supports = [s for s in evidence.supports if s == expected_support]
            value = evidence.content['text']
        else:
            if evidence.source not in {*FACT_FIELDS,'get_order_detail'} or evidence.content.get('error'):
                invalid = True
                continue
            binding = evidence.entity_binding
            if not session.authenticated or binding.get('user_id') != session.user_id:
                return decision('unauthorized','handoff','owner_mismatch')
            for key in ('order_id','board'):
                if key in binding and (key not in task.entities or task.entities[key].value != binding[key]):
                    return decision('unauthorized','handoff','resource_mismatch')
            supports = [s for s in evidence.supports if s in fact_supports(evidence.source,evidence.content)]
            value = evidence.content
        key = (evidence.kind, evidence.conflict_key)
        fingerprint = json.dumps(value,sort_keys=True,ensure_ascii=False)
        if key in conflicts and conflicts[key] != fingerprint:
            return decision('conflicting_evidence','handoff','conflicting_values')
        conflicts[key] = fingerprint
        if supports:
            accepted.append(evidence)
            satisfied.update(supports)
    if not set(required) <= satisfied:
        if invalid:
            return decision('expired_or_unusable_evidence','retrieve' if can_retrieve else 'handoff','unusable_evidence')
        return decision('missing_business_evidence','retrieve' if can_retrieve else 'handoff',reason or 'support_gap')
    return decision('sufficient','answer','supports_covered')
