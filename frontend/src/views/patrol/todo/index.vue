<template>
  <section class="page" data-module="patrol-todo">
    <header class="page-head">
      <div>
        <h2>巡查人员待办</h2>
        <p class="page-desc">
          只显示当前仍归属所选人员、且未关闭的巡查单；换人接管后单据改归新人，上一任的待办里立即不再出现。
          待派发（还没派给本人）与已关闭的单据都不会出现在这里。
        </p>
      </div>
    </header>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>巡查人员</span>
        <select v-model="person">
          <option v-for="name in staff" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询待办</button>
    </form>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">{{ person }} 的待办总数</span>
        <strong class="stat-value">{{ items.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待本人接受</span>
        <strong class="stat-value">{{ pendingAccept }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已接受 / 待回执</span>
        <strong class="stat-value">{{ accepted }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">回执被退回待重做</span>
        <strong class="stat-value">{{ returned }}</strong>
      </article>
    </div>

    <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th>巡查单号</th>
          <th>状态</th>
          <th>巡查路线</th>
          <th>接受情况</th>
          <th>巡查日期</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in items" :key="entry.id">
          <td><button class="link" type="button" @click="detailEntry = entry">{{ entry.巡查单号 }}</button></td>
          <td><span :class="badgeClass(entry.status)">{{ entry.status }}</span></td>
          <td>{{ entry.巡查路线 || '（路线为空）' }}</td>
          <td>
            <span v-if="entry.status === '进行中' && !entry.已接受" class="badge badge-warn badge-mini">待接受</span>
            <span v-else-if="entry.status === '进行中'" class="badge badge-closed badge-mini">已接受</span>
            <span v-else>—</span>
          </td>
          <td>{{ entry.巡查日期 || '—' }}</td>
          <td>
            <div class="card-actions">
              <button
                v-for="action in todoActions(entry)"
                :key="action"
                class="link"
                type="button"
                @click="openAction(entry, action)"
              >
                {{ action }}
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="empty-state">{{ person }} 当前没有待办巡查单（待派发与已关闭不在待办范围内）</td>
        </tr>
      </tbody>
    </table>

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
import { computed, onMounted, ref } from 'vue'

import { useSessionStore } from '@/stores/session'
import {
  ACTIONS,
  actionsFor,
  badgeClass,
  fetchTodo,
  type PatrolAction,
  type PatrolEntry,
} from '../api'
import ActionDialog from '../ActionDialog.vue'
import DetailDialog from '../DetailDialog.vue'

const store = useSessionStore()
// 待办是巡查人员视角，下拉只放一线人员，默认取当前登录的操作人（若不是一线人员则回退到第一个）。
const staff = store.personnel.filter((name) => !name.includes('调度') && name !== '值班管理员')
const person = ref(staff.includes(store.operator) ? store.operator : staff[0])

const items = ref<PatrolEntry[]>([])
const errorMessage = ref('')
const successMessage = ref('')
const detailEntry = ref<PatrolEntry | null>(null)
const dialog = ref<{ entry: PatrolEntry | null; action: PatrolAction | null }>({ entry: null, action: null })

const pendingAccept = computed(() => items.value.filter((e) => e.status === '进行中' && !e.已接受).length)
const accepted = computed(
  () => items.value.filter((e) => e.status === '进行中' && e.已接受 && !e.abnormal).length,
)
const returned = computed(() => items.value.filter((e) => e.abnormal).length)

// 待办里只保留本人能做的动作：接受、回执、退回重做；接管由调度在看板操作。
function todoActions(entry: PatrolEntry): PatrolAction[] {
  return actionsFor(entry).filter(
    (action) => action !== ACTIONS.takeover && action !== ACTIONS.close,
  )
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await fetchTodo(person.value)
    items.value = payload.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '待办加载失败'
  }
}

function openAction(entry: PatrolEntry, action: PatrolAction) {
  errorMessage.value = ''
  successMessage.value = ''
  dialog.value = { entry, action }
}

function closeDialog() {
  dialog.value = { entry: null, action: null }
}

async function onActionDone(message: string) {
  closeDialog()
  successMessage.value = message
  await reload()
}

onMounted(reload)
</script>
