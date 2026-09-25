"""巡查任务派发与回执业务规则。

状态序列：待派发 → 待接受 → 进行中 → 已回执 → 已关闭
- 派发：把待派发的巡查单指定巡查路线与巡查人员，进入待接受；
- 接受：被指派人接单后进入进行中；
- 提交回执：进行中填写回执说明后进入已回执；
- 关闭：已回执由派发方确认关闭；
- 退回（拒绝接受 / 回执退回）：必须写明原因，回到待派发重新派发。

每次状态变化都会往 history 里追加一条 {时间, 操作人, 动作, 原因} 记录；
看板、路线视图、人员待办都直接读同一份数据，不存在对不上的可能。
换人接管后当前指派人更新为新人员，原指派人的待办自然不再出现这张单。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "dispatch"
REQUIRED_FIELDS = ["巡查单号"]
STATUS_ORDER = ["待派发", "待接受", "进行中", "已回执", "已关闭"]
# 终态：待办统计不再计入
DONE_STATUS = "已关闭"

# action -> 目标状态
ACTION_RULES: dict[str, str] = {
    "派发": "待接受",
    "接受": "进行中",
    "拒绝接受": "待派发",
    "提交回执": "已回执",
    "回执退回": "待派发",
    "关闭": "已关闭",
}
# 必须填写原因的退回类动作
REASON_REQUIRED = ["拒绝接受", "回执退回"]
NEGATIVE_ACTIONS = ["拒绝接受", "回执退回"]

# 状态发生变化时在单据上盖时间戳的字段
STATUS_TIMESTAMP_FIELD: dict[str, str] = {
    "待接受": "派发时间",
    "进行中": "接受时间",
    "已回执": "回执时间",
    "已关闭": "关闭时间",
}
STATUS_OPERATOR_FIELD: dict[str, str] = {
    "待接受": "派发操作人",
    "进行中": "接受人",
    "已回执": "回执人",
    "已关闭": "关闭操作人",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DispatchService:
    # ---------- 查询 ----------
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
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("巡查单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if assignee:
            rows = [row for row in rows if row.get("巡查人员") == assignee]
        if route:
            rows = [row for row in rows if row.get("巡查路线") == route]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def board(self) -> dict[str, list[dict[str, Any]]]:
        """派发看板：按状态分列，数据与列表/路线/待办同源。"""
        columns = {status: [] for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            status = str(row.get("status") or STATUS_ORDER[0])
            columns.setdefault(status, []).append(row)
        return columns

    def routes(self) -> list[dict[str, Any]]:
        """巡查路线视图：按路线分组，并给出每条路线上的单量与状态分布。"""
        grouped: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            route = str(row.get("巡查路线") or "").strip()
            bucket = grouped.setdefault(route, {
                "巡查路线": route,
                "单据总数": 0,
                "状态统计": {status: 0 for status in STATUS_ORDER},
                "巡查单": [],
            })
            bucket["单据总数"] += 1
            status = str(row.get("status") or STATUS_ORDER[0])
            bucket["状态统计"][status] = bucket["状态统计"].get(status, 0) + 1
            bucket["巡查单"].append(row)
        # 空路线排最后，提示这些单还卡着不能派发
        return sorted(grouped.values(), key=lambda item: (item["巡查路线"] == "", item["巡查路线"]))

    def todo(self, assignee: str) -> list[dict[str, Any]]:
        """巡查人员待办：只看当前指派人是本人、且尚未关闭的单。

        换人接管时巡查人员字段整体改写为新人，原人员的待办随即看不到这张单。
        """
        return [
            row for row in store.rows(MODULE)
            if row.get("巡查人员") == assignee and row.get("status") != DONE_STATUS
        ]

    def staff(self) -> list[str]:
        """当前出现过的巡查人员，供前端切换待办视角。"""
        names = {
            str(row.get("巡查人员") or "").strip()
            for row in store.rows(MODULE)
            if str(row.get("巡查人员") or "").strip()
        }
        return sorted(names)

    # ---------- 写入 ----------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["巡查单号"] = str(values.get("巡查单号")).strip()
        # 登记阶段路线与人员允许为空：等派发时补齐
        entry["巡查路线"] = str(values.get("巡查路线") or "").strip()
        entry["巡查人员"] = str(values.get("巡查人员") or "").strip()
        entry["登记时间"] = _now()
        entry["status"] = STATUS_ORDER[0]
        entry["已接受"] = False
        entry["回执说明"] = ""
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = [self._trace("登记", str(values.get("操作人") or "").strip(), "")]
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        operator: str = "",
        reason: str = "",
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于巡查派发可执行范围"
        operator = (operator or "").strip()
        if not operator:
            return None, "请选择或填写操作人后再变更状态"
        reason = reason.strip()
        if action in REASON_REQUIRED and not reason:
            return None, f"执行「{action}」必须写明退回原因"

        status = str(entry.get("status") or STATUS_ORDER[0])

        # 各动作的前置条件与卡点说明
        if action == "派发":
            blocked = self._dispatch_blocker(entry, values)
            if blocked:
                return None, blocked
            if values:
                route = str(values.get("巡查路线") or "").strip()
                assignee = str(values.get("巡查人员") or "").strip()
                if route:
                    entry["巡查路线"] = route
                if assignee:
                    entry["巡查人员"] = assignee
        elif action == "接受":
            blocked = self._accept_blocker(entry, operator)
            if blocked:
                return None, blocked
        elif action == "拒绝接受":
            if status != "待接受":
                return None, f"当前状态为「{status}」，只有待接受的巡查单可以拒绝"
        elif action == "提交回执":
            note = str((values or {}).get("回执说明") or "").strip()
            if status != "进行中":
                return None, f"当前状态为「{status}」，只有进行中的巡查单可以提交回执"
            if not entry.get("已接受"):
                return None, "巡查人员还没接受任务，先接受后再提交回执"
            if not note:
                return None, "请填写回执说明后再提交回执"
            entry["回执说明"] = note
        elif action == "回执退回":
            if status != "已回执":
                return None, f"当前状态为「{status}」，只有已回执的巡查单可以退回"
        elif action == "关闭":
            if status != "已回执":
                return None, f"当前状态为「{status}」，巡查单回执之后才能关闭"

        target = ACTION_RULES[action]
        entry["status"] = target
        # 盖状态时间戳与操作人
        stamp_field = STATUS_TIMESTAMP_FIELD.get(target)
        if stamp_field:
            entry[stamp_field] = _now()
        operator_field = STATUS_OPERATOR_FIELD.get(target)
        if operator_field:
            entry[operator_field] = operator

        if action == "派发":
            entry["已接受"] = False
        elif action == "接受":
            entry["已接受"] = True
        elif action in ("拒绝接受", "回执退回"):
            # 退回后任务重新进入待派发，旧的接单与回执结果都要清掉
            entry["已接受"] = False
            entry["回执说明"] = ""
        elif action == "提交回执":
            entry["已接受"] = True

        entry["pending"] = target != DONE_STATUS
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        trace = self._trace(action, operator, reason)
        if action == "提交回执":
            trace["回执说明"] = entry.get("回执说明", "")
        entry.setdefault("history", []).append(trace)
        return entry, f"巡查单已{action}"

    def take_over(
        self,
        entry_id: int,
        *,
        operator: str = "",
        new_assignee: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """换人接管：更新当前指派人。

        待派发的单本来就没有接单负担；待接受/进行中的单换人后，新人需要重新接受，
        原指派人待办随之消失。已回执及以后的单不再允许换人。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查单 {entry_id} 不存在或已归档"
        operator = (operator or "").strip()
        new_assignee = new_assignee.strip()
        if not operator:
            return None, "请选择或填写操作人后再换人接管"
        if not new_assignee:
            return None, "请填写接替的巡查人员"
        status = str(entry.get("status") or STATUS_ORDER[0])
        if status in ("已回执", "已关闭"):
            return None, f"当前状态为「{status}」，巡查单已提交回执，不能再换人接管"
        old_assignee = str(entry.get("巡查人员") or "").strip()
        if new_assignee == old_assignee:
            return None, "接替人员与当前巡查人员相同，无需换人"

        entry["巡查人员"] = new_assignee
        if status == "进行中":
            # 进行中换人：退回待接受，等新人接单后再继续
            entry["status"] = "待接受"
            entry["已接受"] = False
        entry.setdefault("history", []).append(
            self._trace("换人接管", operator, f"原巡查人员：{old_assignee or '未指派'}；新巡查人员：{new_assignee}")
        )
        entry["abnormal"] = False
        return entry, f"巡查单已改由 {new_assignee} 接管"

    # ---------- 内部规则 ----------
    def _dispatch_blocker(self, entry: dict[str, Any], values: dict[str, Any] | None) -> str:
        """派发前置条件：当前须为待派发，且路线、人员齐备。"""
        status = str(entry.get("status") or STATUS_ORDER[0])
        if status != "待派发":
            return f"当前状态为「{status}」，只有待派发的巡查单可以派发"
        route = str((values or {}).get("巡查路线") or entry.get("巡查路线") or "").strip()
        assignee = str((values or {}).get("巡查人员") or entry.get("巡查人员") or "").strip()
        missing = []
        if not route:
            missing.append("巡查路线为空")
        if not assignee:
            missing.append("巡查人员未指定")
        if missing:
            return "派发被拦下：" + "、".join(missing) + "，请在第一步补全后再派发"
        return ""

    def _accept_blocker(self, entry: dict[str, Any], operator: str) -> str:
        """接单前置条件：状态须为待接受，且只有被指派人本人能接。"""
        status = str(entry.get("status") or STATUS_ORDER[0])
        if status != "待接受":
            return f"当前状态为「{status}」，只有待接受的巡查单可以接受任务"
        route = str(entry.get("巡查路线") or "").strip()
        if not route:
            return "巡查路线为空，任务无法承接，请退回派发方补全路线"
        assignee = str(entry.get("巡查人员") or "").strip()
        if not assignee:
            return "巡查人员还没接受任务：该巡查单尚未指派人，请先派发"
        if operator != assignee:
            return f"该巡查单派给了「{assignee}」，请由本人接受任务（当前操作人：{operator}）"
        return ""

    def _trace(self, action: str, operator: str, reason: str) -> dict[str, Any]:
        trace: dict[str, Any] = {"时间": _now(), "操作人": operator or "系统", "动作": action}
        if reason:
            trace["原因"] = reason
        return trace
