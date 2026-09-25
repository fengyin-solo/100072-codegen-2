<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>巡查任务管理</h2>
        <p class="page-desc">
          巡查登记与派发照旧：登记后进入待派发，再经人员接受、回执到关闭。
          看板 <RouterLink to="/patrol/board">派发看板</RouterLink>、
          <RouterLink to="/patrol/routes">巡查路线</RouterLink>、
          <RouterLink to="/patrol/todo">我的待办</RouterLink> 与本页状态同源一致。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showForm = !showForm">登记巡查单</button>
        <button class="btn" type="button" @click="exportRows">导出巡查任务清单</button>
      </div>
    </header>

    <form v-if="showForm" class="inline-form form-grid" @submit.prevent="submitCreate">
      <div class="form-field">
        <label>巡查单号 *</label>
        <input v-model="form.巡查单号" placeholder="如 PATR-0101" />
      </div>
      <div class="form-field">
        <label>巡查日期</label>
        <input v-model="form.巡查日期" type="date" />
      </div>
      <div class="form-field">
        <label>巡查路线 *</label>
        <input v-model="form.巡查路线" placeholder="登记时即填写，避免卡在派发" />
      </div>
      <div class="form-field">
        <label>巡查人员 *</label>
        <input v-model="form.巡查人员" list="patrol-personnel-list" placeholder="指定负责人员" />
      </div>
      <div class="form-field" style="grid-column: 1 / -1">
        <button class="btn primary" type="submit">确认登记</button>
        <button class="btn ghost" type="button" @click="showForm = false">取消</button>
      </div>
    </form>

    <datalist id="patrol-personnel-list">
      <option v-for="name in staff" :key="name" :value="name" />
    </datalist>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>巡查单号</span>
        <input v-model="filters.keyword" placeholder="按巡查单号检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="name in STATUSES" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>巡查人员</span>
        <input v-model="filters.assignee" list="patrol-personnel-list" placeholder="精确筛选" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="successMessage" class="success-text">{{ successMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>接受情况</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <button v-if="column === '巡查单号'" class="link" type="button" @click="detailEntry = row">
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td>
            <template v-if="row.status === '进行中'">
              <span v-if="row.已接受" class="success-text">已接受</span>
              <span v-else class="error-text">待本人接受</span>
            </template>
            <span v-else>—</span>
          </td>
          <td><span :class="badgeClass(row.status)">{{ row.status }}</span></td>
          <td class="row-actions">
            <button
              v-for="action in actionsFor(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(row, action)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="detailEntry = row">明细</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 3" class="empty-state">暂无巡查任务数据，可先登记巡查单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条巡查任务记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <ActionDialog
      v-if="dialog.entry && dialog.action"
      :entry="dialog.entry"
      :action="dialog.action"
      @close="closeDialog"
      @done="onActionDone"
    />
    <DetailDialog v-if="detailEntry" :entry="detailEntry" @close="detailEntry = null" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useSessionStore } from '@/stores/session'
import {
  STATUSES,
  actionsFor,
  badgeClass,
  createPatrol,
  fetchPatrolList,
  type PatrolAction,
  type PatrolEntry,
} from './api'
import ActionDialog from './ActionDialog.vue'
import DetailDialog from './DetailDialog.vue'

const ENDPOINT = '/api/patrol'
const store = useSessionStore()
const staff = store.personnel.filter((name) => !name.includes('调度') && name !== '值班管理员')

const columns = ['巡查单号', '巡查路线', '巡查人员', '巡查日期', '巡查里程', '发现问题数', '巡查时长']

const rows = ref<PatrolEntry[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = reactive<Record<string, string>>({ keyword: '', status: '', assignee: '' })
const showForm = ref(false)
const form = reactive({ 巡查单号: '', 巡查日期: '', 巡查路线: '', 巡查人员: '' })
const detailEntry = ref<PatrolEntry | null>(null)
const dialog = ref<{ entry: PatrolEntry | null; action: PatrolAction | null }>({ entry: null, action: null })

const stats = computed(() =>
  STATUSES.map((name) => ({
    label: name === '待派发' ? '待派发巡查单' : `${name}巡查单`,
    value: rows.value.filter((row) => row.status === name).length,
  })),
)

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  filters.assignee = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function submitCreate() {
  errorMessage.value = ''
  if (!form.巡查单号.trim() || !form.巡查路线.trim() || !form.巡查人员.trim()) {
    errorMessage.value = '巡查单号、巡查路线、巡查人员都是必填项'
    return
  }
  try {
    const result = await createPatrol({
      巡查单号: form.巡查单号.trim(),
      巡查路线: form.巡查路线.trim(),
      巡查人员: form.巡查人员.trim(),
      巡查日期: form.巡查日期,
      operator: store.operator,
    })
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    successMessage.value = result.message
    showForm.value = false
    Object.assign(form, { 巡查单号: '', 巡查日期: '', 巡查路线: '', 巡查人员: '' })
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查单登记失败'
  }
}

function openAction(row: PatrolEntry, action: PatrolAction) {
  errorMessage.value = ''
  successMessage.value = ''
  dialog.value = { entry: row, action }
}

function closeDialog() {
  dialog.value = { entry: null, action: null }
}

async function onActionDone(message: string) {
  closeDialog()
  successMessage.value = message
  await reload()
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await fetchPatrolList({
      keyword: filters.keyword,
      status: filters.status,
      assignee: filters.assignee,
    })
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查任务列表读取失败'
  }
}

onMounted(reload)
</script>
