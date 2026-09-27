<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import TrajectoryTable from '../components/TrajectoryTable.vue'

const route = useRoute()
const router = useRouter()
const snap = ref(null)
const err = ref('')

async function load() {
  err.value = ''
  snap.value = null
  try {
    snap.value = await api(`/api/trajectory/snapshots/${route.params.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function fmtTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  return Number.isNaN(d.getTime()) ? t : d.toLocaleString('zh-CN', { hour12: false })
}
function fmt(x) {
  return x === null || x === undefined ? '—' : Number(x).toFixed(4)
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
        <h3>轨迹副本 #{{ snap.id }}（已签发，冻结）</h3>
        <p>签发人：{{ snap.created_by }}　签发时间：{{ fmtTime(snap.created_at) }}　条数：{{ snap.points.length }}</p>
        <p v-if="snap.compare">
          对照点：#{{ snap.compare.id }} {{ snap.compare.lamp }}，
          标称 {{ fmt(snap.compare.nominal_nm) }} nm，实测 {{ fmt(snap.compare.measured_nm) }} nm，
          偏差 {{ fmt(snap.compare.deviation_nm) }} nm
        </p>
        <p v-else>对照点：未设置</p>
        <p style="color:#666; font-size:13px;">
          本副本在签发时冻结点集与差额，后续新结论只影响在线轨迹，不影响此副本。
        </p>
      </section>
      <TrajectoryTable
        :points="snap.points"
        :compare-id="snap.compare ? snap.compare.id : null"
        :selectable="false"
      />
    </template>
  </div>
</template>
