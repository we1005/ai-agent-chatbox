<template>
  <div class="admin-shell">
    <!-- 左侧导航 -->
    <nav class="admin-nav">
      <div class="nav-brand">
        <div class="brand-icon">⚙</div>
        <span class="brand-text">后台管理</span>
      </div>

      <div class="nav-links">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
        </router-link>
      </div>

      <div class="nav-footer">
        <router-link to="/" class="nav-item back-btn">
          <span class="nav-icon">←</span>
          <span class="nav-label">返回聊天</span>
        </router-link>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="admin-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const navItems = ref([
  { path: '/admin/dashboard', icon: '📊', label: '仪表盘' },
  { path: '/admin/infra',     icon: '🔌', label: '基础设施' },
  { path: '/admin/models',    icon: '🤖', label: '模型配置' },
  { path: '/admin/tools',     icon: '🔧', label: '工具中心' },
  { path: '/admin/prompts',   icon: '✍️', label: 'Prompt 工作室' },
  { path: '/admin/costs',     icon: '💰', label: '费用监控' },
  { path: '/admin/sandbox',   icon: '🧪', label: '调试沙盒' },
])
</script>

<style scoped>
.admin-shell {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
  font-family: 'Inter', -apple-system, sans-serif;
}

/* ===== 左侧导航栏 ===== */
.admin-nav {
  width: 220px;
  flex-shrink: 0;
  background: #111827;
  display: flex;
  flex-direction: column;
  padding: 0;
  box-shadow: 2px 0 12px rgba(0,0,0,0.15);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.brand-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.brand-text {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: -0.01em;
}

.nav-links {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  text-decoration: none;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
  position: relative;
}

.nav-item:hover {
  background: rgba(255,255,255,0.07);
  color: #e2e8f0;
}

.nav-item.active {
  background: rgba(37, 99, 235, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(37, 99, 235, 0.3);
}

.nav-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  background: #ef4444;
  color: white;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 700;
}

.nav-footer {
  padding: 10px;
  border-top: 1px solid rgba(255,255,255,0.08);
}

.back-btn {
  color: #64748b;
}

.back-btn:hover {
  color: #94a3b8;
}

/* ===== 主内容区 ===== */
.admin-main {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}
</style>
