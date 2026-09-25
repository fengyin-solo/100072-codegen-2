<template>
  <section class="page" data-module="dispatch">
    <header class="page-head">
      <div>
        <h2>巡查派发与回执</h2>
        <p class="page-desc">
          巡查单在待派发 → 待接受 → 进行中 → 已回执 → 已关闭之间流转；每次变更都留时间与操作人，退回必须写明原因。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡查单</button>
        <button class="btn" type="button" @click="exportRows">导出派发清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="dispatch-toolbar">
      <div class="tab-row">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          type="button"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>
      <label class="operator-box">
        <span>当前操作人</span>
        <input v-model="operator" list="dispatch-staff" placeholder="填写姓名后操作" />
        <datalist id="dispatch-staff">
          <option v-for="name in staff" :key="name" :value="name" />
        </datalist>
      </label>
    </div>

    <p v-if="message" class="tip-text" :class="{ 'error-text': !messageOk }">{{ message }}</p>

    <!-- 派发看板：按状态分列 -->
    <div v-if="activeTab === 'board'" class="board-grid">
      <section v-for="status in statuses" :key="status" class="board-col">
        <header class="board-col-head">
          <span>{{ status }}</span>
          <em>{{ board[status]?.length ?? 0 }}</em>
        </header>
        <article v-for="row in board[status]" :key="String(row.id)" class="board-card" :class="{ returned: row.abnormal }">
          <div class="board-card-title">
            <strong>{{ row['巡查单号'] }}</strong>
            <span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span>
          </div>
          <p class="board-card-line">路线：{{ row['巡查路线'] || '（未填写，无法派发）' }}</p>
          <p class="board-card-line">人员：{{ row['巡查人员'] || '（未指派）' }}<template v-if="row['已接受']"> · 已接受</template><template v-else-if="row['巡查人员']"> · 未接受</template></p>
          <p v-if="row['回执说明']" class="board-card-line receipt">回执：{{ row['回执说明'] }}</p>
          <div class="board-card-actions">
            <button class="link" type="button" @click="openHistory(row)">流转记录</button>
            <button
              v-for="action in availableActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openTakeOver(row)">换人接管</button>
          </div>
        </article>
        <p v-if="!(board[status]?.length)" class="board-empty">暂无单据</p>
      </section>
    </div>

    <!-- 巡查路线视图 -->
    <div v-else-if="activeTab === 'route'" class="route-list">
      <section v-for="group in routeGroups" :key="group['巡查路线']" class="route-group">
        <header class="route-head">
          <strong>{{ group['巡查路线'] || '（巡查路线为空：这些单卡在第一步，补路线后才能派发）' }}</strong>
          <span class="route-count">共 {{ group['单据总数'] }} 张 ·
            <template v-for="status in statuses" :key="status">
              {{ status }} {{ group['状态统计'][status] ?? 0 }}
            </template>
          </span>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>巡查单号</th>
              <th>巡查人员</th>
              <th>状态</th>
              <th>接受情况</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in group['巡查单']" :key="String(row.id)">
              <td>{{ row['巡查单号'] }}</td>
              <td>{{ row['巡查人员'] || '—' }}</td>
              <td><span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span></td>
              <td>{{ row['已接受'] ? '已接受' : '未接受' }}</td>
              <td class="row-actions">
                <button class="link" type="button" @click="openHistory(row)">流转记录</button>
                <button
                  v-for="action in availableActions(row)"
                  :key="action"
                  class="link"
                  type="button"
                  @click="openAction(action, row)"
                >
                  {{ action }}
                </button>
                <button class="link" type="button" @click="openTakeOver(row)">换人接管</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
      <p v-if="!routeGroups.length" class="empty-state">暂无巡查单</p>
    </div>

    <!-- 巡查人员待办 -->
    <div v-else class="todo-wrap">
      <form class="filter-bar" @submit.prevent="reloadTodo">
        <label class="filter-item">
          <span>查看谁的待办</span>
          <input v-model="todoAssignee" list="dispatch-staff" placeholder="输入或选择巡查人员" />
        </label>
        <button class="btn" type="submit">查询待办</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th>巡查单号</th>
            <th>巡查路线</th>
            <th>状态</th>
            <th>接受情况</th>
            <th>派发/接受时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in todoRows" :key="String(row.id)">
            <td>{{ row['巡查单号'] }}</td>
            <td>{{ row['巡查路线'] || '（未填写）' }}</td>
            <td><span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span></td>
            <td>{{ row['已接受'] ? '已接受' : '未接受' }}</td>
            <td>{{ row['接受时间'] || row['派发时间'] || '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openHistory(row)">流转记录</button>
              <button
                v-for="action in availableActions(row)"
                :key="action"
                class="link"
                type="button"
                @click="openAction(action, row)"
              >
                {{ action }}
              </button>
            </tr>
          </tr>
          <tr v-if="!todoRows.length">
            <td colspan="6" class="empty-state">{{ todoAssignee }} 名下暂无待办（已关闭或已改派给他人的单不会出现）</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 动作弹窗：派发 / 回执需要补字段；退回必须写原因 -->
    <div v-if="dialog.open" class="modal-mask" @click.self="closeDialog">
      <div class="modal-box">
        <h3>{{ dialog.title }}</h3>
        <p class="modal-sub">巡查单：{{ dialog.row?.['巡查单号'] }} · 当前状态：{{ dialog.row?.status }}</p>
        <label v-if="dialog.action === '派发'" class="modal-field">
          <span>巡查路线 *</span>
          <input v-model="dialog.form.route" placeholder="派发前必须明确路线" />
        </label>
        <label v-if="dialog.action === '派发'" class="modal-field">
          <span>巡查人员 *</span>
          <input v-model="dialog.form.assignee" list="dispatch-staff" placeholder="指派给谁" />
        </label>
        <label v-if="dialog.action === '提交回执'" class="modal-field">
          <span>回执说明 *</span>
          <textarea v-model="dialog.form.note" rows="4" placeholder="巡查情况、发现问题、处置说明"></textarea>
        </label>
        <label v-if="needsReason(dialog.action)" class="modal-field">
          <span>退回原因 *</span>
          <textarea v-model="dialog.form.reason" rows="3" placeholder="退回必须写明原因，留痕可查"></textarea>
        </label>
        <p class="modal-tip">操作人：{{ operator || '（请先在右上角填写当前操作人）' }}</p>
        <footer class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" @click="confirmAction">确认{{ dialog.action }}</button>
        </footer>
      </div>
    </div>

    <!-- 换人接管弹窗 -->
    <div v-if="takeoverDialog.open" class="modal-mask" @click.self="takeoverDialog.open = false">
      <div class="modal-box">
        <h3>换人接管</h3>
        <p class="modal-sub">
          巡查单：{{ takeoverDialog.row?.['巡查单号'] }} · 原巡查人员：{{ takeoverDialog.row?.['巡查人员'] || '未指派' }}
        </p>
        <label class="modal-field">
          <span>接替人员 *</span>
          <input v-model="takeoverDialog.assignee" list="dispatch-staff" placeholder="改派给谁" />
        </label>
        <p class="modal-tip">接管后原人员待办立即移除该单；进行中的单退回待接受，由新人重新接单。</p>
        <footer class="modal-actions">
          <button class="btn ghost" type="button" @click="takeoverDialog.open = false">取消</button>
          <button class="btn primary" type="button" @click="confirmTakeOver">确认接管</button>
        </footer>
      </div>
    </div>

    <!-- 登记弹窗 -->
    <div v-if="createDialog" class="modal-mask" @click.self="createDialog = false">
      <div class="modal-box">
        <h3>登记巡查单</h3>
        <label class="modal-field">
          <span>巡查单号 *</span>
          <input v-model="createForm.code" placeholder="如 DISP-0101" />
        </label>
        <label class="modal-field">
          <span>巡查路线（可留待派发时补）</span>
          <input v-model="createForm.route" />
        </label>
        <label class="modal-field">
          <span>巡查人员（可留待派发时补）</span>
          <input v-model="createForm.assignee" list="dispatch-staff" />
        </label>
        <footer class="modal-actions">
          <button class="btn ghost" type="button" @click="createDialog = false">取消</button>
          <button class="btn primary" type="button" @click="confirmCreate">登记</button>
        </footer>
      </div>
    </div>

    <!-- 流转记录 -->
    <div v-if="historyDialog.open" class="modal-mask" @click.self="historyDialog.open = false">
      <div class="modal-box modal-wide">
        <h3>流转记录 · {{ historyDialog.row?.['巡查单号'] }}</h3>
        <ul class="history-list">
          <li v-for="(trace, index) in historyDialog.row?.history ?? []" :key="index" class="history-item">
            <div class="history-dot"></div>
            <div>
              <p class="history-action">{{ trace['动作'] }}<span v-if="trace['原因']" class="history-reason">（原因：{{ trace['原因'] }}）</span></p>
              <p class="history-meta">{{ trace['时间'] }} · 操作人：{{ trace['操作人'] }}</p>
              <p v-if="trace['回执说明']" class="history-receipt">回执：{{ trace['回执说明'] }}</p>
            </div>
          </li>
        </ul>
        <footer class="modal-actions">
          <button class="btn primary" type="button" @click="historyDialog.open = false">知道了</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useSessionStore } from '@/stores/session'
import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null> & {
  history?: Array<Record<string, string>>
}
type RouteGroup = {
  巡查路线: string
  单据总数: number
  状态统计: Record<string, number>
  巡查单: Row[]
}

const ENDPOINT = '/api/dispatch'
const statuses = ['待派发', '待接受', '进行中', '已回执', '已关闭'] as const
const tabs = [
  { key: 'board', label: '派发看板' },
  { key: 'route', label: '巡查路线视图' },
  { key: 'todo', label: '巡查人员待办' },
] as const

const session = useSessionStore()
const operator = ref(session.operator)
const activeTab = ref<'board' | 'route' | 'todo'>('board')

const board = ref<Record<string, Row[]>>({})
const routeGroups = ref<RouteGroup[]>([])
const todoRows = ref<Row[]>([])
const todoAssignee = ref(session.operator)
const staff = ref<string[]>([])
const message = ref('')
const messageOk = ref(true)

// 每个状态允许出现的动作按钮；服务端还会再校验一次，这里只做入口收敛
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  待派发: ['派发'],
  待接受: ['接受', '拒绝接受'],
  进行中: ['提交回执'],
  已回执: ['回执退回', '关闭'],
  已关闭: [],
}
const REASON_ACTIONS = ['拒绝接受', '回执退回']

const stats = computed(() => [
  { label: '待派发', value: board.value['待派发']?.length ?? 0 },
  { label: '待接受', value: board.value['待接受']?.length ?? 0 },
  { label: '进行中', value: board.value['进行中']?.length ?? 0 },
  { label: '已回执', value: board.value['已回执']?.length ?? 0 },
  { label: '已关闭', value: board.value['已关闭']?.length ?? 0 },
])

const dialog = reactive({
  open: false,
  action: '',
  title: '',
  row: null as Row | null,
  form: { route: '', assignee: '', note: '', reason: '' },
})
const takeoverDialog = reactive({ open: false, row: null as Row | null, assignee: '' })
const createDialog = ref(false)
const createForm = reactive({ code: '', route: '', assignee: '' })
const historyDialog = reactive({ open: false, row: null as Row | null })

function availableActions(row: Row): string[] {
  return ACTIONS_BY_STATUS[String(row.status)] ?? []
}
function needsReason(action: string | undefined): boolean {
  return !!action && REASON_ACTIONS.includes(action)
}
function statusClass(status: unknown): string {
  return {
    待派发: 'tag-pending',
    待接受: 'tag-waiting',
    进行中: 'tag-doing',
    已回执: 'tag-receipt',
    已关闭: 'tag-closed',
  }[String(status)] ?? ''
}

function flash(text: string, ok = true) {
  message.value = text
  messageOk.value = ok
}

async function loadBoard() {
  const payload = await fetchJson(`${ENDPOINT}/board`)
  board.value = payload.columns ?? {}
}
async function loadRoutes() {
  const payload = await fetchJson(`${ENDPOINT}/routes`)
  routeGroups.value = payload.routes ?? []
}
async function reloadTodo() {
  if (!todoAssignee.value.trim()) {
    flash('请先填写要查看的巡查人员姓名', false)
    return
  }
  const payload = await fetchJson(`${ENDPOINT}/todos?assignee=${encodeURIComponent(todoAssignee.value.trim())}`)
  todoRows.value = payload.items ?? []
}
async function loadStaff() {
  const payload = await fetchJson(`${ENDPOINT}/staff`)
  staff.value = payload.staff ?? []
}

async function refreshAll() {
  try {
    await Promise.all([loadBoard(), loadRoutes(), loadStaff()])
    if (activeTab.value === 'todo') {
      await reloadTodo()
    }
  } catch (error) {
    flash(error instanceof Error ? error.message : '数据加载失败', false)
  }
}

async function fetchJson(path: string): Promise<any> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return response.json()
}

function switchTab(key: 'board' | 'route' | 'todo') {
  activeTab.value = key
  if (key === 'todo') {
    void reloadTodo()
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export/all`, '_blank')
}

function openCreate() {
  createForm.code = ''
  createForm.route = ''
  createForm.assignee = ''
  createDialog.value = true
}

async function confirmCreate() {
  if (!createForm.code.trim()) {
    flash('巡查单号为必填项', false)
    return
  }
  const body = {
    values: {
      巡查单号: createForm.code.trim(),
      巡查路线: createForm.route.trim(),
      巡查人员: createForm.assignee.trim(),
      操作人: operator.value.trim(),
    },
  }
  const result = await postAction('', body)
  if (result?.ok) {
    createDialog.value = false
    flash(result.message)
    await refreshAll()
  }
}

function openAction(action: string, row: Row) {
  dialog.action = action
  dialog.row = row
  dialog.title = `${action} · ${String(row['巡查单号'])}`
  dialog.form = {
    route: String(row['巡查路线'] ?? ''),
    assignee: String(row['巡查人员'] ?? ''),
    note: String((row as any)['回执说明'] ?? ''),
    reason: '',
  }
  dialog.open = true
}

function closeDialog() {
  dialog.open = false
  dialog.row = null
}

async function confirmAction() {
  if (!operator.value.trim()) {
    flash('请先在右上角填写当前操作人，状态变更必须留操作人', false)
    return
  }
  if (dialog.action === '派发' && (!dialog.form.route.trim() || !dialog.form.assignee.trim())) {
    flash('派发前必须补全巡查路线与巡查人员，否则任务无法流转', false)
    return
  }
  if (dialog.action === '提交回执' && !dialog.form.note.trim()) {
    flash('请填写回执说明', false)
    return
  }
  if (needsReason(dialog.action) && !dialog.form.reason.trim()) {
    flash(`${dialog.action}必须写明退回原因`, false)
    return
  }
  const values: Record<string, string> = {
    action: dialog.action,
    操作人: operator.value.trim(),
  }
  if (dialog.action === '派发') {
    values['巡查路线'] = dialog.form.route.trim()
    values['巡查人员'] = dialog.form.assignee.trim()
  }
  if (dialog.action === '提交回执') {
    values['回执说明'] = dialog.form.note.trim()
  }
  if (needsReason(dialog.action)) {
    values['原因'] = dialog.form.reason.trim()
  }
  const result = await postAction(`/${(dialog.row as Row)?.id}/actions`, { values })
  if (result?.ok) {
    closeDialog()
    flash(result.message)
    await refreshAll()
  }
}

function openTakeOver(row: Row) {
  takeoverDialog.row = row
  takeoverDialog.assignee = ''
  takeoverDialog.open = true
}

async function confirmTakeOver() {
  if (!operator.value.trim()) {
    flash('请先填写当前操作人', false)
    return
  }
  if (!takeoverDialog.assignee.trim()) {
    flash('请填写接替的巡查人员', false)
    return
  }
  const result = await postAction(`/${(takeoverDialog.row as Row)?.id}/take-over`, {
    values: { 操作人: operator.value.trim(), 巡查人员: takeoverDialog.assignee.trim() },
  })
  if (result?.ok) {
    takeoverDialog.open = false
    flash(result.message)
    await refreshAll()
  }
}

function openHistory(row: Row) {
  historyDialog.row = row
  historyDialog.open = true
}

async function postAction(path: string, body: unknown): Promise<{ ok: boolean; message: string } | null> {
  try {
    const response = await request(`${ENDPOINT}${path}`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const payload = await response.json()
    if (!payload.ok) {
      flash(payload.message || '操作未生效', false)
      return null
    }
    return payload
  } catch (error) {
    flash(error instanceof Error ? error.message : '操作请求失败', false)
    return null
  }
}

onMounted(() => {
  void refreshAll()
})
</script>
