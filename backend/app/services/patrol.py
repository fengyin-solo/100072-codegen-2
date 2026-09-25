"""巡查任务业务规则：派发与回执状态机、流转留痕，以及各视图的统一筛选口径。

状态机：待派发 → 进行中（派发后等待巡查人员接受）→ 已回执 → 已关闭。
进行中未接受可退回待派发，已回执可退回进行中重做；进行中允许换人接管。
退回必须写明原因；路线为空、人员未接受等情况下禁止变更状态，并明确说明卡在哪一步。

派发看板、巡查路线视图与巡查人员待办都只读这同一份数据（store 里的 patrol 表），
换人接管直接改巡查单上的巡查人员，因此三个视图与本人待办的状态天然一致。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "patrol"
REQUIRED_FIELDS = ["巡查单号", "巡查路线", "巡查人员"]

STATUS_PENDING = "待派发"
STATUS_DOING = "进行中"
STATUS_RECEIPTED = "已回执"
STATUS_CLOSED = "已关闭"
STATUS_ORDER = [STATUS_PENDING, STATUS_DOING, STATUS_RECEIPTED, STATUS_CLOSED]

ACTION_REGISTER = "登记"
ACTION_DISPATCH = "派发"
ACTION_ACCEPT = "接受"
ACTION_RECEIPT = "提交回执"
ACTION_CLOSE = "关闭"
ACTION_RETURN = "退回"
ACTION_TAKEOVER = "换人接管"

# 正向动作与目标状态；接受只改「已接受」标记，换人接管不改状态，故不在此表中。
FORWARD_TARGETS = {
    ACTION_DISPATCH: STATUS_DOING,
    ACTION_RECEIPT: STATUS_RECEIPTED,
    ACTION_CLOSE: STATUS_CLOSED,
}
ALL_ACTIONS = [
    ACTION_DISPATCH,
    ACTION_ACCEPT,
    ACTION_RECEIPT,
    ACTION_CLOSE,
    ACTION_RETURN,
    ACTION_TAKEOVER,
]

DEFAULT_OPERATOR = "值班管理员"
EMPTY_ROUTE_LABEL = "（巡查路线为空）"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class PatrolService:
    # ---------- 读取：列表 / 看板 / 路线视图 / 人员待办，全部基于同一份数据 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        route: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter(keyword=keyword, status=status, assignee=assignee, route=route)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def board_columns(self) -> list[dict[str, Any]]:
        """派发看板：按四个状态分列。"""
        rows = store.rows(MODULE)
        return [
            {"status": name, "items": [row for row in rows if row.get("status") == name]}
            for name in STATUS_ORDER
        ]

    def route_groups(self) -> list[dict[str, Any]]:
        """巡查路线视图：按路线分组；路线为空的单据单独成组并标记为卡住。"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in store.rows(MODULE):
            route = str(row.get("巡查路线") or "").strip() or EMPTY_ROUTE_LABEL
            groups.setdefault(route, []).append(row)
        ordered = [
            {"route": route, "blocked": route == EMPTY_ROUTE_LABEL, "items": items}
            for route, items in groups.items()
            if route != EMPTY_ROUTE_LABEL
        ]
        if EMPTY_ROUTE_LABEL in groups:
            ordered.append({
                "route": EMPTY_ROUTE_LABEL,
                "blocked": True,
                "items": groups[EMPTY_ROUTE_LABEL],
            })
        return ordered

    def todo_entries(self, person: str) -> list[dict[str, Any]]:
        """巡查人员本人待办：只认巡查单当前的巡查人员字段。

        待派发（还没派出去）与已关闭都不算待办；换人接管后巡查人员被改写，
        单据自然从上一任人员的待办里消失，无需额外同步。
        """
        person = person.strip()
        return [
            row
            for row in store.rows(MODULE)
            if str(row.get("巡查人员") or "").strip() == person
            and row.get("status") in (STATUS_DOING, STATUS_RECEIPTED)
        ]

    def _filter(
        self,
        *,
        keyword: str | None,
        status: str | None,
        assignee: str | None,
        route: str | None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("巡查单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if assignee:
            rows = [row for row in rows if str(row.get("巡查人员") or "").strip() == assignee.strip()]
        if route:
            rows = [row for row in rows if route in str(row.get("巡查路线") or "")]
        return rows

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    # ---------- 登记 ----------

    def create_entry(self, values: dict[str, Any], operator: str) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        entry["巡查日期"] = str(values.get("巡查日期") or "").strip() or datetime.now().strftime("%Y-%m-%d")
        entry["巡查里程"] = str(values.get("巡查里程") or "").strip()
        entry["发现问题数"] = values.get("发现问题数") or 0
        entry["巡查时长"] = str(values.get("巡查时长") or "").strip()
        entry["status"] = STATUS_PENDING
        entry["巡查状态"] = STATUS_PENDING
        entry["已接受"] = False
        entry["pending"] = True
        entry["abnormal"] = False
        entry["流转记录"] = [self._record(operator, ACTION_REGISTER, "", STATUS_PENDING)]
        rows.append(entry)
        return entry, []

    # ---------- 状态流转 ----------

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        operator: str = DEFAULT_OPERATOR,
        reason: str = "",
        updates: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查单 {entry_id} 不存在或已归档"
        if action not in ALL_ACTIONS:
            return None, f"动作「{action}」不属于巡查派发与回执可执行范围"

        status = str(entry.get("status") or "")
        if status == STATUS_CLOSED:
            return None, "巡查单已关闭，属于终态不能再变更状态；如需继续处理请重新登记巡查单"

        reason = str(reason or "").strip()
        updates = updates or {}
        route = str(entry.get("巡查路线") or "").strip()
        person = str(entry.get("巡查人员") or "").strip()
        accepted = bool(entry.get("已接受"))

        # 退回一律要求写明原因，先拦下来，避免后面各分支重复判断。
        if action == ACTION_RETURN and not reason:
            return None, "退回必须写明原因，请在「退回原因」里说明为什么退回"

        target = status
        note = ""
        if action == ACTION_DISPATCH:
            blocked = self._dispatch_blocked(status, updates, route, person)
            if blocked:
                return None, blocked
            route = str(updates.get("巡查路线") or route).strip()
            person = str(updates.get("巡查人员") or person).strip()
            entry["巡查路线"] = route
            entry["巡查人员"] = person
            entry["已接受"] = False
            target = STATUS_DOING
            note = "已派发，等待巡查人员接受"
        elif action == ACTION_ACCEPT:
            blocked = self._accept_blocked(status, accepted, route, person, operator)
            if blocked:
                return None, blocked
            entry["已接受"] = True
            note = "巡查人员已接受"
        elif action == ACTION_RECEIPT:
            if status != STATUS_DOING:
                return None, f"巡查单当前为「{status}」，只有进行中的任务可以提交回执"
            if not accepted:
                return None, (
                    f"巡查人员「{person}」尚未接受任务，当前卡在第 2 步「人员接受」，"
                    "请先由本人接受后再提交回执"
                )
            target = STATUS_RECEIPTED
            for field in ("巡查里程", "发现问题数", "巡查时长"):
                if updates.get(field) not in (None, ""):
                    entry[field] = updates[field]
            note = "回执已提交，等待关闭"
        elif action == ACTION_CLOSE:
            if status != STATUS_RECEIPTED:
                return None, (
                    f"巡查单当前为「{status}」，还没走到回执环节，"
                    f"当前卡在第 3 步「提交回执」，不能直接关闭"
                )
            target = STATUS_CLOSED
            note = "巡查单关闭归档"
        elif action == ACTION_RETURN:
            # 未接受时退回到派发前；已回执时退回到执行环节重做。
            if status == STATUS_DOING and not accepted:
                target = STATUS_PENDING
                entry["已接受"] = False
                note = "人员拒绝接受，退回待派发"
            elif status == STATUS_RECEIPTED:
                target = STATUS_DOING
                note = "回执不符合要求，退回进行中重做"
            else:
                return None, f"巡查单当前为「{status}」，没有可退回的上一环节"
        elif action == ACTION_TAKEOVER:
            new_person = str(updates.get("巡查人员") or "").strip()
            if status != STATUS_DOING:
                return None, f"巡查单当前为「{status}」，只有进行中的任务可以换人接管"
            if not new_person:
                return None, "换人接管必须指定新的巡查人员，当前卡在「换人接管」这一步"
            if not route:
                return None, "巡查路线为空，无法换人接管：请先补全巡查路线，当前卡在「派发」这一步"
            if new_person == person:
                return None, f"「{new_person}」本来就是当前巡查人员，无需接管"
            note = f"由{new_person}接管，原巡查人员{person}的待办已移除"
            entry["巡查人员"] = new_person
            entry["已接受"] = False
            person = new_person
            # 状态保持进行中，但新接手的人需要重新接受。

        entry["status"] = target
        entry["巡查状态"] = target
        entry["pending"] = target != STATUS_CLOSED
        entry["abnormal"] = action == ACTION_RETURN
        entry.setdefault("流转记录", []).append(
            self._record(operator, action, status, target, reason=reason, note=note)
        )
        return entry, self._success_message(action, person=person, target=target)

    # ---------- 校验细则：每个卡点都要说明卡在哪一步 ----------

    @staticmethod
    def _dispatch_blocked(
        status: str, updates: dict[str, Any], route: str, person: str
    ) -> str:
        if status != STATUS_PENDING:
            return f"巡查单当前为「{status}」，不在待派发环节，无需再次派发"
        route = str(updates.get("巡查路线") or route).strip()
        person = str(updates.get("巡查人员") or person).strip()
        if not route:
            return "巡查路线为空，无法派发：当前卡在第 1 步「派发」，请先补全巡查路线后再派发"
        if not person:
            return "尚未指定巡查人员，无法派发：当前卡在第 1 步「派发」，请先落实巡查人员"
        return ""

    @staticmethod
    def _accept_blocked(
        status: str, accepted: bool, route: str, person: str, operator: str
    ) -> str:
        if status != STATUS_DOING:
            return f"巡查单当前为「{status}」，只有派发后的进行中任务可以接受"
        if accepted:
            return "该巡查单已经接受过，无需重复接受"
        if not route:
            return "巡查路线为空，无法接受：请联系派发人补全路线，当前卡在第 2 步「人员接受」"
        if person and str(operator).strip() != person:
            return f"当前巡查人员是「{person}」，只有本人可以接受；请切换到该人员账号后操作"
        return ""

    @staticmethod
    def _record(
        operator: str,
        action: str,
        source: str,
        target: str,
        *,
        reason: str = "",
        note: str = "",
    ) -> dict[str, str]:
        return {
            "时间": _now(),
            "操作人": str(operator or DEFAULT_OPERATOR).strip() or DEFAULT_OPERATOR,
            "动作": action,
            "原状态": source,
            "目标状态": target,
            "原因": reason,
            "备注": note,
        }

    @staticmethod
    def _success_message(action: str, *, person: str, target: str) -> str:
        if action == ACTION_DISPATCH:
            return f"巡查单已派发给{person}，进入进行中，等待对方接受"
        if action == ACTION_ACCEPT:
            return "已接受巡查任务，可按路线开展巡查"
        if action == ACTION_RECEIPT:
            return "巡查回执已提交，等待关闭"
        if action == ACTION_CLOSE:
            return "巡查单已关闭"
        if action == ACTION_RETURN:
            if target == STATUS_PENDING:
                return "已退回待派发，请按退回原因调整后重新派发"
            return "已退回进行中，请按退回原因重新巡查"
        if action == ACTION_TAKEOVER:
            return f"换人接管完成，任务已改派给{person}，原人员待办中不再显示"
        return "操作已生效"
