<template>
  <div v-if="entry" class="modal-mask" @click.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3 class="modal-title">{{ action }} · {{ entry.巡查单号 }}</h3>
        <button class="modal-close" type="button" @click="close">×</button>
      </header>

      <div class="detail-grid">
        <div><dt>当前状态</dt><dd><span :class="badgeClass(entry.status)">{{ entry.status }}</span></dd></div>
        <div><dt>巡查人员</dt><dd>{{ entry.巡查人员 || '—' }}</dd></div>
        <div style="grid-column: 1 / -1"><dt>巡查路线</dt><dd>{{ entry.巡查路线 || '（为空，需先补全）' }}</dd></div>
      </div>

      <div v-if="action === ACTIONS.dispatch" class="form-grid">
        <div class="form-field">
          <label>巡查路线（派发前可补全）</label>
          <input v-model="form.巡查路线" placeholder="路线为空将无法派发" />
        </div>
        <div class="form-field">
          <label>巡查人员</label>
          <input v-model="form.巡查人员" list="patrol-personnel-list" placeholder="指定接单人" />
        </div>
      </div>

      <div v-else-if="action === ACTIONS.takeover" class="form-grid">
        <div class="form-field">
          <label>新巡查人员（必填）</label>
          <input v-model="form.巡查人员" list="patrol-personnel-list" placeholder="换人后原人员待办移除" />
        </div>
        <div class="form-field">
          <label>接管原因 / 说明</label>
          <input v-model="form.reason" placeholder="例如：原人员请假、路线调整" />
        </div>
      </div>

      <div v-else-if="action === ACTIONS.receipt" class="form-grid">
        <div class="form-field">
          <label>巡查里程（公里）</label>
          <input v-model="form.巡查里程" placeholder="如 6.5" />
        </div>
        <div class="form-field">
          <label>发现问题数</label>
          <input v-model="form.发现问题数" type="number" min="0" placeholder="如 2" />
        </div>
        <div class="form-field" style="grid-column: 1 / -1">
          <label>巡查时长</label>
          <input v-model="form.巡查时长" placeholder="如 2小时10分" />
        </div>
      </div>

      <div v-if="action === ACTIONS.return" class="form-field">
        <label>退回原因（必填）</label>
        <textarea v-model="form.reason" placeholder="写明为什么退回，后续流转记录里会一直保留"></textarea>
      </div>

      <p v-if="hint" class="page-desc">{{ hint }}</p>

      <datalist id="patrol-personnel-list">
        <option v-for="person in personnel" :key="person" :value="person" />
      </datalist>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <footer class="modal-foot">
        <button class="btn" type="button" :disabled="saving" @click="close">取消</button>
        <button class="btn primary" type="button" :disabled="saving" @click="submit">
          {{ saving ? '提交中…' : `确认${action}` }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { useSessionStore } from '@/stores/session'
import { ACTIONS, badgeClass, type PatrolAction, type PatrolEntry, runPatrolAction } from './api'

const props = defineProps<{
  entry: PatrolEntry
  action: PatrolAction
}>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done', message: string): void
}>()

const store = useSessionStore()
const personnel = store.personnel.filter((name) => !name.includes('调度') && name !== '值班管理员')

const form = reactive<Record<string, string>>({
  巡查路线: '',
  巡查人员: '',
  reason: '',
  巡查里程: '',
  发现问题数: '',
  巡查时长: '',
})
const saving = ref(false)
const errorMessage = ref('')

watch(
  () => props.entry.id,
  () => {
    form.巡查路线 = props.entry.巡查路线 ?? ''
    form.巡查人员 = props.entry.巡查人员 ?? ''
    form.reason = ''
    form.巡查里程 = String(props.entry.巡查里程 ?? '')
    form.发现问题数 = String(props.entry.发现问题数 ?? '')
    form.巡查时长 = String(props.entry.巡查时长 ?? '')
    errorMessage.value = ''
  },
  { immediate: true },
)

const hints: Partial<Record<PatrolAction, string>> = {
  [ACTIONS.dispatch]: '派发后单据进入「进行中」，需巡查人员本人接受才能继续。',
  [ACTIONS.accept]: '只有当前巡查人员本人可以接受；接受后才能提交回执。',
  [ACTIONS.return]: '未接受时退回到「待派发」；已回执时退回到「进行中」重做。',
  [ACTIONS.takeover]: '接管后状态保持「进行中」，但新人员需要重新接受，原人员待办立即移除。',
  [ACTIONS.close]: '关闭后为终态，不能再变更状态。',
  [ACTIONS.receipt]: '回执提交后进入「已回执」，可关闭或被退回重做。',
}
const hint = hints[props.action]

function close() {
  emit('close')
}

async function submit() {
  errorMessage.value = ''
  if (props.action === ACTIONS.return && !form.reason.trim()) {
    errorMessage.value = '退回必须写明原因'
    return
  }
  if (props.action === ACTIONS.takeover && !form.巡查人员.trim()) {
    errorMessage.value = '换人接管必须指定新的巡查人员'
    return
  }
  if (props.action === ACTIONS.dispatch && (!form.巡查路线.trim() || !form.巡查人员.trim())) {
    errorMessage.value = '巡查路线或巡查人员为空，派发会被拦下，请先补齐'
    return
  }
  saving.value = true
  try {
    const values: Record<string, unknown> = {
      action: props.action,
      operator: store.operator,
    }
    if (props.action === ACTIONS.dispatch) {
      values.巡查路线 = form.巡查路线.trim()
      values.巡查人员 = form.巡查人员.trim()
    }
    if (props.action === ACTIONS.takeover) {
      values.巡查人员 = form.巡查人员.trim()
      if (form.reason.trim()) values.reason = form.reason.trim()
    }
    if (props.action === ACTIONS.return) values.reason = form.reason.trim()
    if (props.action === ACTIONS.receipt) {
      if (form.巡查里程.trim()) values.巡查里程 = form.巡查里程.trim()
      if (form.发现问题数.trim()) values.发现问题数 = Number(form.发现问题数)
      if (form.巡查时长.trim()) values.巡查时长 = form.巡查时长.trim()
    }
    const result = await runPatrolAction(props.entry.id, values)
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    emit('done', result.message)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  } finally {
    saving.value = false
  }
}
</script>
