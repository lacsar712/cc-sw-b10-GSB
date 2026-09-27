<script setup>
const props = defineProps({
  points: { type: Array, default: () => [] },
  compareId: { type: Number, default: null },
  selectable: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

function fmt(x) {
  return x === null || x === undefined ? '—' : Number(x).toFixed(4)
}
function fmtTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  return Number.isNaN(d.getTime()) ? t : d.toLocaleString('zh-CN', { hour12: false })
}
function onRowClick(p) {
  if (props.selectable) emit('select', p.id)
}
</script>

<template>
  <table class="traj-table" border="1" cellpadding="6">
    <thead>
      <tr>
        <th>时间</th>
        <th>编号</th>
        <th>灯种</th>
        <th>标称 nm</th>
        <th>实测 nm</th>
        <th>偏差 nm</th>
        <th>结论</th>
        <th>实测差额 nm</th>
        <th>偏差差额 nm</th>
        <th v-if="selectable">对照</th>
      </tr>
    </thead>
    <tbody>
      <tr v-if="!points.length">
        <td :colspan="selectable ? 10 : 9" class="empty">暂无已结案轨迹点</td>
      </tr>
      <tr
        v-for="p in points"
        :key="p.id"
        :class="{ 'is-compare': p.id === compareId, clickable: selectable }"
        @click="onRowClick(p)"
      >
        <td>{{ fmtTime(p.created_at) }}</td>
        <td>{{ p.id }}</td>
        <td>{{ p.lamp }}</td>
        <td>{{ fmt(p.nominal_nm) }}</td>
        <td>{{ fmt(p.measured_nm) }}</td>
        <td>{{ fmt(p.deviation_nm) }}</td>
        <td>
          <span class="verdict" :class="p.verdict === '合格' ? 'ok' : 'bad'">{{ p.verdict }}</span>
        </td>
        <td>{{ fmt(p.measured_diff_nm) }}</td>
        <td>{{ fmt(p.deviation_diff_nm) }}</td>
        <td v-if="selectable">
          <span v-if="p.id === compareId" class="compare-flag">对照点</span>
          <span v-else class="pick-hint">设为对照</span>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.traj-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
}
.traj-table th {
  background: #f0f4f8;
  white-space: nowrap;
}
tr.clickable {
  cursor: pointer;
}
tr.clickable:hover td {
  background: #f6f9fc;
}
tr.is-compare td {
  background: #fff7e0;
}
.verdict.ok {
  color: #0a7a2f;
  font-weight: 600;
}
.verdict.bad {
  color: #b00020;
  font-weight: 600;
}
.compare-flag {
  color: #8a6d00;
  font-weight: 600;
  white-space: nowrap;
}
.pick-hint {
  color: #8a98a8;
  font-size: 12px;
  white-space: nowrap;
}
.empty {
  text-align: center;
  color: #8a98a8;
}
</style>
