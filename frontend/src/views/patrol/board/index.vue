<template>
  <section class="page" data-module="patrol-board">
    <header class="page-head">
      <div>
        <h2>巡查派发看板</h2>
        <p class="page-desc">
          待派发 → 进行中（待接受 / 已接受）→ 已回执 → 已关闭，与巡查路线视图、人员待办共用同一份数据，状态始终一致。
          当前操作人：{{ store.operator }}
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新看板</button>
      </div>
    </header>

    <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <div class="board">
      <section
        v-for="column in columns"
        :key="column.status"
        class="board-column"
        :class="{ 'blocked-col': column.status === '待派发' }"
      >
        <header class="board-head">
          <span :class="badgeClass(column.status)">{{ column.status }}</span>
          <span class="board-count">{{ column.items.length }}</span>
        </header>
        <article
          v-for="entry in column.items"
          :key="entry.id"
          class="board-card"
          :class="{ blocked: !entry.巡查路线 }"
          @click="openDetail(entry)"
        >
          <div class="board-card-title">{{ entry.巡查单号 }}</div>
          <div class="board-card-meta">路线：{{ entry.巡查路线 || '（空，派发将被拦截）' }}</div>
          <div class="board-card-meta">人员：{{ entry.巡查人员 || '未指定' }}</div>
          <div class="board-card-meta">
            <template v-if="entry.status === '进行中'">
              <span v-if="entry.已接受" class="badge badge-closed badge-mini">已接受</span>
              <span v-else class="badge badge-warn badge-mini">待接受</span>
            </template>
          </div>
          <div class="card-actions" @click.stop>
            <button
              v-for="action in actionsFor(entry)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(entry, action)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openDetail(entry)">明细</button>
          </div>
        </article>
        <p v-if="!column.items.length" class="empty-state">暂无单据</p>
      </section>
    </div>

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
import { onMounted, ref } from 'vue'

import { useSessionStore } from '@/stores/session'
import {
  actionsFor,
  badgeClass,
  fetchBoard,
  type BoardColumn,
  type PatrolAction,
  type PatrolEntry,
} from '../api'
import ActionDialog from '../ActionDialog.vue'
import DetailDialog from '../DetailDialog.vue'

const store = useSessionStore()
const columns = ref<BoardColumn[]>([])
const errorMessage = ref('')
const successMessage = ref('')
const detailEntry = ref<PatrolEntry | null>(null)
const dialog = ref<{ entry: PatrolEntry | null; action: PatrolAction | null }>({ entry: null, action: null })

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await fetchBoard()
    columns.value = payload.columns
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '看板加载失败'
  }
}

function openAction(entry: PatrolEntry, action: PatrolAction) {
  errorMessage.value = ''
  successMessage.value = ''
  dialog.value = { entry, action }
}

function openDetail(entry: PatrolEntry) {
  detailEntry.value = entry
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
