<template>
  <section class="page" data-module="patrol-routes">
    <header class="page-head">
      <div>
        <h2>巡查路线视图</h2>
        <p class="page-desc">
          按巡查路线查看任务执行情况；路线为空的单据无法派发，会单独标红提示卡在哪一步。
          状态与派发看板、人员待办完全同源。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新路线</button>
      </div>
    </header>

    <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <section
      v-for="group in groups"
      :key="group.route"
      class="route-group"
      :class="{ blocked: group.blocked }"
    >
      <header class="route-head">
        <span>
          {{ group.route }}
          <span v-if="group.blocked" class="badge badge-warn badge-mini">路线为空 · 卡在派发</span>
        </span>
        <span class="board-count">{{ group.items.length }} 单</span>
      </header>
      <div class="route-body">
        <table class="data-table">
          <thead>
            <tr>
              <th>巡查单号</th>
              <th>状态</th>
              <th>巡查人员</th>
              <th>接受情况</th>
              <th>巡查日期</th>
              <th>发现问题</th>
              <th>可执行动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in group.items" :key="entry.id">
              <td><button class="link" type="button" @click="detailEntry = entry">{{ entry.巡查单号 }}</button></td>
              <td><span :class="badgeClass(entry.status)">{{ entry.status }}</span></td>
              <td>{{ entry.巡查人员 || '未指定' }}</td>
              <td>
                <template v-if="entry.status === '进行中'">
                  <span v-if="entry.已接受" class="success-text">已接受</span>
                  <span v-else class="error-text">待本人接受</span>
                </template>
                <span v-else>—</span>
              </td>
              <td>{{ entry.巡查日期 || '—' }}</td>
              <td>{{ entry.发现问题数 ?? 0 }}</td>
              <td>
                <div class="card-actions">
                  <button
                    v-for="action in actionsFor(entry)"
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
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="!groups.length" class="empty-state">暂无巡查路线数据</p>

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

import {
  actionsFor,
  badgeClass,
  fetchRoutes,
  type PatrolAction,
  type PatrolEntry,
  type RouteGroup,
} from '../api'
import ActionDialog from '../ActionDialog.vue'
import DetailDialog from '../DetailDialog.vue'

const groups = ref<RouteGroup[]>([])
const errorMessage = ref('')
const successMessage = ref('')
const detailEntry = ref<PatrolEntry | null>(null)
const dialog = ref<{ entry: PatrolEntry | null; action: PatrolAction | null }>({ entry: null, action: null })

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await fetchRoutes()
    groups.value = payload.groups
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路线视图加载失败'
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
