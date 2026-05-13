import { createRouter, createWebHistory } from 'vue-router'
import ChatLayout from '../components/ChatLayout.vue'
import KnowledgeBase from '../components/KnowledgeBase.vue'
import RagStrategyTest from '../components/RagStrategyTest.vue'
import StyleLab from '../components/StyleLab.vue'
import ChatUIStyle from '../components/ChatUIStyle.vue'
import MemoryAudit from '../components/MemoryAudit.vue'
import AdminLayout from '../components/admin/AdminLayout.vue'
import AdminDashboard from '../components/admin/AdminDashboard.vue'
import AdminModelConfig from '../components/admin/AdminModelConfig.vue'
import AdminToolHub from '../components/admin/AdminToolHub.vue'
import AdminPromptStudio from '../components/admin/AdminPromptStudio.vue'
import AdminCostMonitor from '../components/admin/AdminCostMonitor.vue'
import AdminSandbox from '../components/admin/AdminSandbox.vue'
import AdminInfra from '../components/admin/AdminInfra.vue'
import VistaChatPage from '../views/vista/VistaChatPage.vue'

// Home 落地页
import HomePage from '../views/home/HomePage.vue'

// Wiki 模块（项目架构可视化 · 见 plan-doc-dir/quizzical-spinning-parrot 计划）
import WikiHome from '../views/wiki/WikiHome.vue'
import WikiTreePage from '../views/wiki-tree/WikiTreePage.vue'
import ArchitecturePage from '../views/wiki/ArchitecturePage.vue'
import ClassicPipelinePage from '../views/wiki/ClassicPipelinePage.vue'
import SoloGraphPage from '../views/wiki/SoloGraphPage.vue'
import ContextEnginePage from '../views/wiki/ContextEnginePage.vue'
import MemoryLifecyclePage from '../views/wiki/MemoryLifecyclePage.vue'
import RagStrategiesPage from '../views/wiki/RagStrategiesPage.vue'
import BenchResultsPage from '../views/wiki/BenchResultsPage.vue'

const routes = [
  {
    path: '/',
    name: 'Chat',
    component: ChatLayout
  },
  {
    path: '/knowledge',
    name: 'KnowledgeBase',
    component: KnowledgeBase
  },
  {
    path: '/rag-test',
    name: 'RagStrategyTest',
    component: RagStrategyTest
  },
  {
    path: '/style-lab',
    name: 'StyleLab',
    component: StyleLab
  },
  {
    path: '/chat-ui-style',
    name: 'ChatUIStyle',
    component: ChatUIStyle
  },
  {
    path: '/settings/memory',
    name: 'MemoryAudit',
    component: MemoryAudit
  },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', name: 'AdminDashboard',    component: AdminDashboard },
      { path: 'infra',     name: 'AdminInfra',        component: AdminInfra },
      { path: 'models',    name: 'AdminModelConfig',  component: AdminModelConfig },
      { path: 'tools',     name: 'AdminToolHub',      component: AdminToolHub },
      { path: 'prompts',   name: 'AdminPromptStudio', component: AdminPromptStudio },
      { path: 'costs',     name: 'AdminCostMonitor',  component: AdminCostMonitor },
      { path: 'sandbox',   name: 'AdminSandbox',      component: AdminSandbox },
    ]
  },
  {
    path: '/home',
    name: 'Home',
    component: HomePage,
  },
  {
    path: '/wiki',
    name: 'WikiHome',
    component: WikiHome,
  },
  { path: '/wiki/architecture',     name: 'WikiArchitecture',     component: ArchitecturePage },
  { path: '/wiki/classic-pipeline', name: 'WikiClassicPipeline',  component: ClassicPipelinePage },
  { path: '/wiki/solo-graph',       name: 'WikiSoloGraph',        component: SoloGraphPage },
  { path: '/wiki/context-engine',   name: 'WikiContextEngine',    component: ContextEnginePage },
  { path: '/wiki/memory-lifecycle', name: 'WikiMemoryLifecycle',  component: MemoryLifecyclePage },
  { path: '/wiki/rag-strategies',   name: 'WikiRagStrategies',    component: RagStrategiesPage },
  { path: '/wiki/bench-results',    name: 'WikiBenchResults',     component: BenchResultsPage },
  { path: '/wiki-tree',             name: 'WikiTree',             component: WikiTreePage },
  { path: '/vista-chat',            name: 'VistaChat',            component: VistaChatPage },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
