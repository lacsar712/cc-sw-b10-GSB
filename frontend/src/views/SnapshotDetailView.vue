<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const router = useRouter()
const snap = ref(null)
const err = ref('')

// 副本为签发时冻结的点集与差额，只取一次，不随后续新结论变化
async function load() {
  err.value = ''
  snap.value = null
  try {
    snap.value = await api(`/api/snapshots/${route.params.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  }
}

const points = computed(() => (snap.value && snap.value.points) || [])
const compare = computed(() => (snap.value && snap.value.compare_point) || null)
const diff = computed(() => (snap.value && snap.value.diff) || null)

const perPointDiff = computed(() => {
  const m = {}
  if (diff.value && diff.value.per_point) {
    for (const d of diff.value.per_point) m[d.id] = d
  }
  return m
})

function fmtTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

function fmtDiff(v) {
  if (v === null || v === undefined) return ''
  return (v > 0 ? '+' : '') + Number(v).toFixed(4)
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<template>
  <div>
    <p>
      <button type="button" @click="router.push('/trajectory')">返回轨迹台</button>
    </p>
    <p v-if="err" style="color:#b00020">{{ err }}</p>

    <template v-if="snap">
      <section style="margin:16px 0; padding:12px; border:1px solid #ccc;">
        <h3>快照 #{{ snap.id }}：{{ snap.title }}</h3>
        <p>
          签发人：{{ snap.created_by }}　签发时间：{{ fmtTime(snap.created_at) }}　条数：{{ points.length }}
          <template v-if="compare">　对照点：#{{ compare.id }} {{ compare.lamp }}</template>
        </p>
        <p style="color:#666; font-size:13px;">此副本为签发时冻结的点集与差额，后续新结论只影响在线轨迹，不影响本副本。</p>
      </section>

      <section style="margin:16px 0; padding:12px; border:1px solid #ccc;">
        <h3>冻结点集</h3>
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
              <td :colspan="diff ? 9 : 7" style="text-align:center; color:#888;">签发时暂无已结案记录</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="compare && diff" style="margin:16px 0; padding:12px; border:1px solid #ccc;">
        <h3>冻结对照差额</h3>
        <p>
          对照点：#{{ compare.id }} {{ compare.lamp }}
          （标称 {{ compare.nominal_nm }} / 实测 {{ compare.measured_nm }} / 偏差 {{ compare.deviation_nm }} /
          <span :class="compare.verdict === '超差' ? 'verdict-bad' : 'verdict-ok'">{{ compare.verdict }}</span>）
        </p>
        <p v-if="diff.latest_id !== null">
          签发时最新点 #{{ diff.latest_id }} 相对对照点：
          标称差额 {{ fmtDiff(diff.nominal_diff_nm) }} nm，
          实测差额 {{ fmtDiff(diff.measured_diff_nm) }} nm，
          偏差差额 {{ fmtDiff(diff.deviation_diff_nm) }} nm
        </p>
      </section>
    </template>
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
