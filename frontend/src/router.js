import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import JobDetailView from './views/JobDetailView.vue'
import TrajectoryView from './views/TrajectoryView.vue'
import SnapshotView from './views/SnapshotView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/jobs/:id', name: 'job-detail', component: JobDetailView, props: true },
    { path: '/trajectory', name: 'trajectory', component: TrajectoryView },
    { path: '/trajectory/snapshots/:id', name: 'snapshot-detail', component: SnapshotView, props: true },
  ],
})

export default router
