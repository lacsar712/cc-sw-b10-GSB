import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import JobDetailView from './views/JobDetailView.vue'
import TrajectoryView from './views/TrajectoryView.vue'
import SnapshotDetailView from './views/SnapshotDetailView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/jobs/:id', name: 'job-detail', component: JobDetailView, props: true },
    { path: '/trajectory', name: 'trajectory', component: TrajectoryView },
    { path: '/snapshots/:id', name: 'snapshot-detail', component: SnapshotDetailView, props: true },
  ],
})

export default router
