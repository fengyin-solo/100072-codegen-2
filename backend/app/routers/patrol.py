"""巡查任务接口：巡查登记照旧，新增派发看板、巡查路线视图与人员待办。

所有视图都读同一份巡查单数据，保证状态一致；动作接口覆盖
派发、接受、提交回执、关闭、退回（必填原因）与换人接管。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.patrol import (
    ALL_ACTIONS,
    STATUS_ORDER,
    PatrolService,
)

router = APIRouter(prefix="/api/patrol", tags=["巡查任务"])

service = PatrolService()

LIST_FIELDS = ["巡查单号", "巡查路线", "巡查人员", "巡查日期", "巡查里程", "发现问题数", "巡查时长", "巡查状态"]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按巡查单号检索"),
    status: str | None = Query(default=None, description="待派发、进行中、已回执、已关闭"),
    assignee: str | None = Query(default=None, description="按当前巡查人员精确筛选"),
    route: str | None = Query(default=None, description="按巡查路线名称模糊筛选"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按巡查单号、状态、人员与路线过滤巡查单；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, assignee=assignee, route=route, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/board")
def dispatch_board() -> dict[str, Any]:
    """派发看板：按待派发、进行中、已回执、已关闭四列返回全部巡查单。"""
    columns = service.board_columns()
    return {
        "columns": columns,
        "total": sum(len(column["items"]) for column in columns),
    }


@router.get("/routes")
def route_view() -> dict[str, Any]:
    """巡查路线视图：按巡查路线分组；路线为空的单据单独标记为派发受阻。"""
    groups = service.route_groups()
    return {
        "groups": groups,
        "total": sum(len(group["items"]) for group in groups),
    }


@router.get("/todo")
def personal_todo(
    person: str = Query(description="巡查人员姓名，只返回当前仍归属该人员的未关闭任务"),
) -> dict[str, Any]:
    """巡查人员本人待办：换人接管后单据归属改写，上一任人员这里自然查不到。"""
    person = person.strip()
    if not person:
        raise HTTPException(status_code=400, detail="请先选择巡查人员，再查看其待办")
    items = service.todo_entries(person)
    return {"person": person, "total": len(items), "items": items}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出巡查任务清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "patrol", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条巡查单明细（含每次状态变更的时间与操作人）；不存在时给出可读说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"巡查单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条巡查单，缺字段时说明原因而不是静默丢弃；登记入口与原有流程保持一致。"""
    operator = str(payload.values.pop("operator", "") or "").strip() or "值班管理员"
    entry, missing = service.create_entry(payload.values, operator)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="巡查单已登记，进入待派发", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行派发、接受、提交回执、关闭、退回、换人接管。

    values 里携带 action、operator、reason 以及可选的字段更新（如新巡查人员）。
    不允许的动作或不满足前置条件时拦下，并在 message 里说明卡在哪一步。
    """
    values = payload.values
    action = str(values.get("action") or "").strip()
    operator = str(values.get("operator") or "").strip() or "值班管理员"
    reason = str(values.get("reason") or payload.remark or "").strip()
    if action not in ALL_ACTIONS:
        return ActionResult(ok=False, message=f"动作「{action}」不属于巡查派发与回执可执行范围")
    updates = {key: value for key, value in values.items() if key not in ("action", "operator", "reason")}
    entry, message = service.run_action(entry_id, action, operator=operator, reason=reason, updates=updates)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
