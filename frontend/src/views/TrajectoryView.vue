<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import TrajectoryTable from '../components/TrajectoryTable.vue'

const router = useRouter()
const role = ref(localStorage.getItem('role') || '')
const limitOptions = [5, 10, 20, 50]
const limit = ref(10)
const compareId = ref(null)
const trajectory = ref({ points: [], compare: null })
const snapshots = ref([])
const err = ref('')
const msg = ref('')
let timer

const compare = computed(() => trajectory.value.compare)
const isWriter = computed(() => role.value === 'writer')

async function fetchTrajectory() {
  const qs = `?limit=${limit.value}` + (compareId.value ? `&compare_id=${compareId.value}` : '')
  trajectory.value = await api('/api/trajectory' + qs)
}

async function refresh() {
  if (!localStorage.getItem('tok')) return
  try {
    await fetchTrajectory()
    snapshots.value = await api('/api/trajectory/snapshots')
    err.value = ''
  } catch (e) {
    if (compareId.value && String(e.message || e).includes('对照点')) {
      compareId.value = null
      return refresh()
    }
    err.value = String(e.message || e)
  }
}

function selectCompare(id) {
  compareId.value = compareId.value === id ? null : id
  refresh()
}

function clearCompare() {
  compareId.value = null
  refresh()
}

async function issue() {
  err.value = ''
  msg.value = ''
  try {
    const r = await api('/api/trajectory/snapshots', {
      method: 'POST',
      body: JSON.stringify({ limit: limit.value, compare_id: compareId.value }),
    })
    msg.value = `已签发快照 #${r.id}，点集与差额已冻结`
    await refresh()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function openSnapshot(id) {
  router.push(`/trajectory/snapshots/${id}`)
}

function fmtTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  return Number.isNaN(d.getTime()) ? t : d.toLocaleString('zh-CN', { hour12: false })
}
function fmt(x) {
  return x === null || x === undefined ? '—' : Number(x).toFixed(4)
}

watch(limit, refresh)

onMounted(() => {
  role.value = localStorage.getItem('role') || ''
  refresh()
  timer = setInterval(refresh, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div>
    <h2>偏差轨迹台</h2>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="msg" class="ok-msg">{{ msg }}</p>

    <section class="panel controls">
      <label>
        条数
        <select v-model.number="limit">
          <option v-for="n in limitOptions" :key="n" :value="n">近 {{ n }} 条</option>
        </select>
      </label>
      <button v-if="compare" type="button" @click="clearCompare">清除对照</button>
      <button
        v-if="isWriter"
        type="button"
        class="issue-btn"
        :disabled="!trajectory.points.length"
        @click="issue"
      >签发轨迹副本</button>
      <span v-else class="hint">仅校准员可签发，当前为只读</span>
    </section>

    <section class="panel compare-area">
      <h3>对照点差额区</h3>
      <template v-if="compare">
        <p>
          对照点：#{{ compare.id }} {{ compare.lamp }}，
          标称 {{ fmt(compare.nominal_nm) }} nm，实测 {{ fmt(compare.measured_nm) }} nm，
          偏差 {{ fmt(compare.deviation_nm) }} nm，
          结论
          <span class="verdict" :class="compare.verdict === '合格' ? 'ok' : 'bad'">{{ compare.verdict }}</span>
        </p>
        <p class="hint">差额由服务端计算：实测差额 = 各点实测 − 对照点实测；偏差差额 = 各点偏差 − 对照点偏差。</p>
      </template>
      <p v-else class="hint">未选对照点。点击轨迹表中的行即可设为对照点，差额由服务端计算后展示。</p>
    </section>

    <section class="panel">
      <h3>近次已结案轨迹（按时间倒序）</h3>
      <TrajectoryTable
        :points="trajectory.points"
        :compare-id="compareId"
        :selectable="true"
        @select="selectCompare"
      />
    </section>

    <section class="panel">
      <h3>已签发快照</h3>
      <table class="snap-table" border="1" cellpadding="6">
        <thead>
          <tr>
            <th>编号</th><th>签发时间</th><th>签发人</th><th>条数</th><th>对照点</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!snapshots.length">
            <td colspan="6" class="empty">暂无已签发快照</td>
          </tr>
          <tr v-for="s in snapshots" :key="s.id">
            <td>#{{ s.id }}</td>
            <td>{{ fmtTime(s.created_at) }}</td>
            <td>{{ s.created_by }}</td>
            <td>{{ s.point_count }}</td>
            <td>{{ s.compare_id ? '#' + s.compare_id : '—' }}</td>
            <td><button type="button" @click="openSnapshot(s.id)">查看副本</button></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.panel {
  margin: 16px 0;
  padding: 12px;
  border: 1px solid #ccc;
}
.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.issue-btn {
  cursor: pointer;
  font-weight: 600;
}
.hint {
  color: #666;
  font-size: 13px;
}
.err {
  color: #b00020;
}
.ok-msg {
  color: #0a7a2f;
}
.verdict.ok {
  color: #0a7a2f;
  font-weight: 600;
}
.verdict.bad {
  color: #b00020;
  font-weight: 600;
}
.snap-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
}
.snap-table th {
  background: #f0f4f8;
}
.empty {
  text-align: center;
  color: #8a98a8;
}
</style>
