<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const router = useRouter()
const role = ref(localStorage.getItem('role') || '')
const limit = ref(10)
const compareId = ref('')
const points = ref([])
const compare = ref(null)
const diff = ref(null)
const snapshots = ref([])
const err = ref('')
const issueTitle = ref('')
const issueMsg = ref('')
let timer

const limitOptions = [5, 10, 20, 50]

// 轨迹与差额一律由服务端算好下发，本页不碰总览接口、不自拼
async function loadTrajectory() {
  if (!localStorage.getItem('tok')) return
  try {
    const q = new URLSearchParams({ limit: String(limit.value) })
    if (compareId.value) q.set('compare_id', String(compareId.value))
    const data = await api('/api/trajectory?' + q.toString())
    points.value = data.points || []
    compare.value = data.compare || null
    diff.value = data.diff || null
    err.value = ''
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function loadSnapshots() {
  if (!localStorage.getItem('tok')) return
  try {
    snapshots.value = await api('/api/snapshots')
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function refresh() {
  loadTrajectory()
  loadSnapshots()
}

async function issue() {
  err.value = ''
  issueMsg.value = ''
  try {
    const s = await api('/api/snapshots', {
      method: 'POST',
      body: JSON.stringify({
        title: issueTitle.value,
        limit: limit.value,
        compare_id: compareId.value ? Number(compareId.value) : null,
      }),
    })
    issueMsg.value = `已签发快照 #${s.id}（冻结 ${s.point_count} 个点）`
    issueTitle.value = ''
    await loadSnapshots()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function openSnapshot(id) {
  router.push(`/snapshots/${id}`)
}

const perPointDiff = computed(() => {
  const m = {}
  if (diff.value && diff.value.per_point) {
    for (const d of diff.value.per_point) m[d.id] = d
  }
  return m
})

const compareOptions = computed(() => {
  const opts = points.value.map((p) => ({ id: p.id, label: `#${p.id} ${p.lamp}` }))
  if (compareId.value && !opts.some((o) => o.id === Number(compareId.value))) {
    opts.push({ id: Number(compareId.value), label: `#${compareId.value}（窗口外）` })
  }
  return opts
})

function fmtTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

function fmtDiff(v) {
  if (v === null || v === undefined) return ''
  return (v > 0 ? '+' : '') + Number(v).toFixed(4)
}

onMounted(() => {
  role.value = localStorage.getItem('role') || ''
  refresh()
  timer = setInterval(refresh, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div>
    <p v-if="err" style="color:#b00020">{{ err }}</p>

    <section style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h3>近次偏差轨迹</h3>
      <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:8px;">
        <label>条数
          <select v-model.number="limit" @change="loadTrajectory">
            <option v-for="n in limitOptions" :key="n" :value="n">最近 {{ n }} 条</option>
          </select>
        </label>
        <label>对照点
          <select v-model="compareId" @change="loadTrajectory">
            <option value="">不选对照</option>
            <option v-for="o in compareOptions" :key="o.id" :value="String(o.id)">{{ o.label }}</option>
          </select>
        </label>
        <template v-if="role === 'writer'">
          <input v-model="issueTitle" placeholder="快照标题（可空）" />
          <button type="button" @click="issue">签发轨迹快照</button>
        </template>
        <span v-if="issueMsg" style="color:#0a7a2f">{{ issueMsg }}</span>
      </div>

      <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
        <thead>
          <tr>
            <th>时间</th>
            <th>编号</th>
            <th>灯种</th>
            <th>标称</th>
            <th>实测</th>
            <th>偏差</th>
            <th>结论</th>
            <th v-if="diff">实测差额</th>
            <th v-if="diff">偏差差额</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in points"
            :key="p.id"
            :class="{ 'compare-row': compare && p.id === compare.id }"
          >
            <td>{{ fmtTime(p.created_at) }}</td>
            <td>{{ p.id }}</td>
            <td>{{ p.lamp }}</td>
            <td>{{ p.nominal_nm }}</td>
            <td>{{ p.measured_nm }}</td>
            <td>{{ p.deviation_nm }}</td>
            <td>
              <span :class="p.verdict === '超差' ? 'verdict-bad' : 'verdict-ok'">{{ p.verdict }}</span>
            </td>
            <td v-if="diff">{{ perPointDiff[p.id] ? fmtDiff(perPointDiff[p.id].measured_diff_nm) : '' }}</td>
            <td v-if="diff">{{ perPointDiff[p.id] ? fmtDiff(perPointDiff[p.id].deviation_diff_nm) : '' }}</td>
          </tr>
          <tr v-if="!points.length">
            <td :colspan="diff ? 9 : 7" style="text-align:center; color:#888;">暂无已结案记录</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="compare && diff" style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h3>对照差额区</h3>
      <p>
        对照点：#{{ compare.id }} {{ compare.lamp }}
        （标称 {{ compare.nominal_nm }} / 实测 {{ compare.measured_nm }} / 偏差 {{ compare.deviation_nm }} /
        <span :class="compare.verdict === '超差' ? 'verdict-bad' : 'verdict-ok'">{{ compare.verdict }}</span>）
      </p>
      <p v-if="diff.latest_id !== null">
        最新点 #{{ diff.latest_id }} 相对对照点：
        标称差额 {{ fmtDiff(diff.nominal_diff_nm) }} nm，
        实测差额 {{ fmtDiff(diff.measured_diff_nm) }} nm，
        偏差差额 {{ fmtDiff(diff.deviation_diff_nm) }} nm
      </p>
    </section>

    <section style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h3>已签发快照</h3>
      <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
        <thead>
          <tr>
            <th>编号</th><th>标题</th><th>条数</th><th>对照点</th><th>签发人</th><th>签发时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in snapshots"
            :key="s.id"
            style="cursor:pointer"
            @click="openSnapshot(s.id)"
          >
            <td>{{ s.id }}</td>
            <td>{{ s.title }}</td>
            <td>{{ s.point_count }}</td>
            <td>{{ s.compare_id ? '#' + s.compare_id : '—' }}</td>
            <td>{{ s.created_by }}</td>
            <td>{{ fmtTime(s.created_at) }}</td>
          </tr>
          <tr v-if="!snapshots.length">
            <td colspan="6" style="text-align:center; color:#888;">暂无快照</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.verdict-ok {
  color: #0a7a2f;
  font-weight: 600;
}
.verdict-bad {
  color: #b00020;
  font-weight: 600;
}
.compare-row {
  background: #fff7d6;
}
</style>
