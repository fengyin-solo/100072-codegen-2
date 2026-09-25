<template>
  <div v-if="entry" class="modal-mask" @click.self="close">
    <div class="modal wide">
      <header class="modal-head">
        <h3 class="modal-title">巡查单明细 · {{ entry.巡查单号 }}</h3>
        <button class="modal-close" type="button" @click="close">×</button>
      </header>

      <dl class="detail-grid">
        <div><dt>当前状态</dt><dd><span :class="badgeClass(entry.status)">{{ entry.status }}</span></dd></div>
        <div><dt>是否已接受</dt>
          <dd>
            <span v-if="entry.已接受" class="badge badge-closed">已接受</span>
            <span v-else-if="entry.status === '进行中'" class="badge badge-warn">待本人接受</span>
            <span v-else>—</span>
          </dd>
        </div>
        <div><dt>巡查路线</dt><dd>{{ entry.巡查路线 || '（为空，派发会被拦截）' }}</dd></div>
        <div><dt>巡查人员</dt><dd>{{ entry.巡查人员 || '—' }}</dd></div>
        <div><dt>巡查日期</dt><dd>{{ entry.巡查日期 || '—' }}</dd></div>
        <div><dt>巡查里程</dt><dd>{{ entry.巡查里程 || '—' }}</dd></div>
        <div><dt>发现问题数</dt><dd>{{ entry.发现问题数 ?? 0 }}</dd></div>
        <div><dt>巡查时长</dt><dd>{{ entry.巡查时长 || '—' }}</dd></div>
      </dl>

      <h4 class="modal-title" style="margin: 8px 0">流转记录（时间 / 操作人 / 动作）</h4>
      <ul class="timeline">
        <li
          v-for="(record, index) in records"
          :key="index"
          :class="{ 'is-return': record.动作.includes('退回') }"
        >
          <span class="timeline-time">{{ record.时间 }}</span>
          <span class="timeline-action">{{ record.动作 }}</span>
          <span class="timeline-time">{{ record.原状态 || '—' }} → {{ record.目标状态 || record.原状态 }}</span>
          <div class="timeline-time">操作人：{{ record.操作人 }}</div>
          <div v-if="record.原因" class="timeline-reason">原因：{{ record.原因 }}</div>
          <div v-if="record.备注" class="timeline-note">{{ record.备注 }}</div>
        </li>
      </ul>

      <footer class="modal-foot">
        <button class="btn primary" type="button" @click="close">知道了</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { badgeClass, type FlowRecord, type PatrolEntry } from './api'

const props = defineProps<{ entry: PatrolEntry | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const records = computed<FlowRecord[]>(() => props.entry?.流转记录 ?? [])

function close() {
  emit('close')
}
</script>
