"""巡查任务派发与回执接口。

在原有「巡查登记」（/api/patrol）之外新增，覆盖派发看板、巡查路线视图、
巡查人员待办，以及派发/接受/退回/回执/关闭/换人接管等状态动作。
所有视图读同一份数据，换人接管后各视图同步更新。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.dispatch import STATUS_ORDER, DispatchService

router = APIRouter(prefix="/api/dispatch", tags=["巡查派发回执"])

service = DispatchService()

LIST_FIELDS = ["巡查单号", "巡查路线", "巡查人员", "status", "回执说明"]
DISPATCH_ACTIONS = ["派发", "接受", "拒绝接受", "提交回执", "回执退回", "关闭"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按巡查单号检索"),
    status: str | None = Query(default=None, description="待派发、待接受、进行中、已回执、已关闭"),
    assignee: str | None = Query(default=None, description="按当前巡查人员过滤"),
    route: str | None = Query(default=None, description="按巡查路线过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """巡查单列表：看板、路线视图、人员待办都在这份数据上过滤。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, assignee=assignee, route=route, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/board")
def board_entries() -> dict[str, Any]:
    """派发看板：按状态分列返回全部巡查单。"""
    return {"statuses": STATUS_ORDER, "columns": service.board()}


@router.get("/routes")
def route_view() -> dict[str, Any]:
    """巡查路线视图：按路线分组并附状态统计。"""
    return {"routes": service.routes()}


@router.get("/todos")
def todo_entries(assignee: str = Query(..., description="查看哪位巡查人员的待办")) -> dict[str, Any]:
    """巡查人员自己的待办：未关闭且当前指派人是本人的单。"""
    items = service.todo(assignee)
    return {"assignee": assignee, "total": len(items), "items": items}


@router.get("/staff")
def staff_list() -> dict[str, Any]:
    """可选巡查人员名单，供切换待办视角使用。"""
    return {"staff": service.staff()}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条巡查单明细（含状态流转历史）。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"巡查单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记巡查单：只要求巡查单号；路线与人员在派发时补全。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="巡查单已登记，等待派发", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行状态动作；不满足前置条件时返回卡点说明（路线为空/未接受/原因缺失等）。"""
    values = payload.values
    action = str(values.get("action") or "").strip()
    operator = str(values.get("操作人") or "").strip()
    reason = str(values.get("原因") or payload.remark or "").strip()
    entry, message = service.run_action(
        entry_id, action, operator=operator, reason=reason, values=values
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/take-over", response_model=ActionResult)
def take_over(entry_id: int, payload: EntryPayload) -> ActionResult:
    """换人接管：改派后原巡查人员待办不再出现这张单。"""
    values = payload.values
    operator = str(values.get("操作人") or "").strip()
    new_assignee = str(values.get("巡查人员") or "").strip()
    entry, message = service.take_over(entry_id, operator=operator, new_assignee=new_assignee)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export/all")
def export_entries() -> dict[str, Any]:
    """导出派发回执全量清单。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "dispatch", "total": total, "items": items}
