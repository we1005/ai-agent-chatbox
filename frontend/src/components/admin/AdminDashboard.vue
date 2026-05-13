<template>
  <div class="dashboard">
    <div class="page-header">
      <h1>仪表盘</h1>
      <p class="subtitle">今日 API 使用概览 · {{ today }}</p>
    </div>

    <!-- 顶部数字卡片 -->
    <div class="stat-cards">
      <div class="stat-card" v-for="card in statCards" :key="card.label">
        <div class="stat-icon" :style="{ background: card.iconBg }">{{ card.icon }}</div>
        <div class="stat-info">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-change" :class="card.changeType">{{ card.change }}</div>
        </div>
      </div>
    </div>

    <!-- 余额状态 -->
    <div class="section-grid">
      <div class="card balance-card">
        <div class="card-header">
          <span class="card-title">API 账户余额</span>
          <button class="refresh-btn" @click="refreshBalance" :class="{ spinning: refreshing }">↻</button>
        </div>
        <div class="balance-list">
          <div class="balance-item" v-for="bal in balances" :key="bal.name">
            <div class="bal-left">
              <span class="bal-dot" :style="{ background: bal.color }"></span>
              <span class="bal-name">{{ bal.name }}</span>
            </div>
            <div class="bal-right">
              <span class="bal-amount">¥ {{ bal.amount }}</span>
              <span class="bal-status" :class="bal.status">{{ bal.statusText }}</span>
            </div>
            <div class="bal-bar">
              <div class="bal-fill" :style="{ width: bal.percent + '%', background: bal.color }"></div>
            </div>
          </div>
        </div>
        <div class="balance-hint">⚠ 余额低于 10 元时将发出警告</div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">模型使用分布（今日）</span>
        </div>
        <div class="model-usage-chart">
          <div class="model-bar-item" v-for="m in modelUsage" :key="m.name">
            <div class="mbar-label">{{ m.name }}</div>
            <div class="mbar-track">
              <div class="mbar-fill" :style="{ width: m.pct + '%', background: m.color }"></div>
            </div>
            <div class="mbar-value">{{ m.calls }} 次</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 近7天费用趋势 -->
    <div class="card chart-card">
      <div class="card-header">
        <span class="card-title">近 7 天费用趋势（元）</span>
        <div class="chart-legend">
          <span class="legend-dot" style="background:#2563eb"></span><span>DeepSeek</span>
          <span class="legend-dot" style="background:#10b981"></span><span>Kimi</span>
        </div>
      </div>
      <div class="line-chart">
        <div class="chart-y-labels">
          <span v-for="y in yLabels" :key="y">{{ y }}</span>
        </div>
        <div class="chart-area">
          <div class="chart-gridlines">
            <div class="gridline" v-for="y in yLabels" :key="y"></div>
          </div>
          <svg class="chart-svg" viewBox="0 0 600 160" preserveAspectRatio="none">
            <!-- DeepSeek 折线 -->
            <polyline
              :points="deepseekPoints"
              fill="none"
              stroke="#2563eb"
              stroke-width="2.5"
              stroke-linejoin="round"
            />
            <polyline
              :points="deepseekPoints"
              fill="url(#blueGrad)"
              stroke="none"
              opacity="0.15"
            />
            <!-- Kimi 折线 -->
            <polyline
              :points="kimiPoints"
              fill="none"
              stroke="#10b981"
              stroke-width="2.5"
              stroke-linejoin="round"
            />
            <defs>
              <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#2563eb" stop-opacity="0.4"/>
                <stop offset="100%" stop-color="#2563eb" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <!-- 数据点 -->
            <circle v-for="(pt, i) in deepseekDots" :key="'d'+i" :cx="pt.x" :cy="pt.y" r="3.5" fill="#2563eb"/>
            <circle v-for="(pt, i) in kimiDots" :key="'k'+i" :cx="pt.x" :cy="pt.y" r="3.5" fill="#10b981"/>
          </svg>
          <div class="chart-x-labels">
            <span v-for="d in chartDays" :key="d">{{ d }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Token 构成 + 缓存命中 -->
    <div class="section-grid">
      <div class="card">
        <div class="card-header"><span class="card-title">今日 Token 构成</span></div>
        <div class="token-breakdown">
          <div class="donut-wrapper">
            <svg viewBox="0 0 100 100" class="donut-svg">
              <circle cx="50" cy="50" r="38" fill="none" stroke="#e2e8f0" stroke-width="14"/>
              <circle cx="50" cy="50" r="38" fill="none" stroke="#2563eb" stroke-width="14"
                stroke-dasharray="143 96" stroke-dashoffset="0" stroke-linecap="round"
                transform="rotate(-90 50 50)"/>
              <circle cx="50" cy="50" r="38" fill="none" stroke="#f59e0b" stroke-width="14"
                stroke-dasharray="60 179" stroke-dashoffset="-143" stroke-linecap="round"
                transform="rotate(-90 50 50)"/>
              <circle cx="50" cy="50" r="38" fill="none" stroke="#10b981" stroke-width="14"
                stroke-dasharray="36 203" stroke-dashoffset="-203" stroke-linecap="round"
                transform="rotate(-90 50 50)"/>
            </svg>
            <div class="donut-center">
              <div class="donut-total">1.23M</div>
              <div class="donut-sub">tokens</div>
            </div>
          </div>
          <div class="token-legend">
            <div class="token-leg-item" v-for="t in tokenBreakdown" :key="t.label">
              <span class="leg-dot" :style="{ background: t.color }"></span>
              <span class="leg-label">{{ t.label }}</span>
              <span class="leg-value">{{ t.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">KV 缓存命中率</span></div>
        <div class="cache-stats">
          <div class="cache-item" v-for="c in cacheStats" :key="c.name">
            <div class="cache-header-row">
              <span class="cache-name">{{ c.name }}</span>
              <span class="cache-rate" :style="{ color: c.color }">{{ c.rate }}%</span>
            </div>
            <div class="cache-track">
              <div class="cache-fill" :style="{ width: c.rate + '%', background: c.color }"></div>
            </div>
            <div class="cache-saving">节省费用：¥ {{ c.saving }}</div>
          </div>
          <div class="cache-tip">
            💡 System Prompt 越长、越固定，缓存命中率越高
          </div>
        </div>
      </div>
    </div>

    <!-- 最近对话 -->
    <div class="card recent-card">
      <div class="card-header">
        <span class="card-title">最近请求记录</span>
        <span class="card-sub">最近 10 条</span>
      </div>
      <div class="recent-table">
        <div class="rt-head">
          <span>时间</span><span>模型</span><span>输入 tokens</span><span>输出 tokens</span><span>缓存命中</span><span>费用</span>
        </div>
        <div class="rt-row" v-for="(row, i) in recentLogs" :key="i">
          <span class="rt-time">{{ row.time }}</span>
          <span class="rt-model" :style="{ color: row.color }">{{ row.model }}</span>
          <span>{{ row.input.toLocaleString() }}</span>
          <span>{{ row.output.toLocaleString() }}</span>
          <span>
            <span class="cache-badge" :class="row.cached ? 'hit' : 'miss'">
              {{ row.cached ? '命中' : '未命中' }}
            </span>
          </span>
          <span class="rt-cost">¥ {{ row.cost }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
const refreshing = ref(false)

const statCards = ref([
  { icon: '⚡', iconBg: 'linear-gradient(135deg,#2563eb,#7c3aed)', label: '今日 Tokens', value: '1,234,567', change: '↑ 12% vs 昨天', changeType: 'up' },
  { icon: '💴', iconBg: 'linear-gradient(135deg,#f59e0b,#ef4444)', label: '今日费用', value: '¥ 3.70', change: '↑ 8% vs 昨天', changeType: 'up' },
  { icon: '💬', iconBg: 'linear-gradient(135deg,#10b981,#059669)', label: '今日对话数', value: '47', change: '↑ 15% vs 昨天', changeType: 'up' },
  { icon: '⚡', iconBg: 'linear-gradient(135deg,#6366f1,#8b5cf6)', label: '平均响应时长', value: '2.3s', change: '↓ 0.4s vs 昨天', changeType: 'down-good' },
])

const balances = ref([
  { name: 'DeepSeek', amount: '48.20', color: '#2563eb', status: 'ok', statusText: '🟢 充足', percent: 82 },
  { name: 'Kimi (Moonshot)', amount: '12.50', color: '#10b981', status: 'warn', statusText: '🟡 偏低', percent: 25 },
])

const refreshBalance = () => {
  refreshing.value = true
  setTimeout(() => { refreshing.value = false }, 1500)
}

const modelUsage = ref([
  { name: 'kimi-k2-0905-preview', calls: 28, pct: 60, color: '#10b981' },
  { name: 'deepseek-chat', calls: 14, pct: 30, color: '#2563eb' },
  { name: 'kimi-k2.5', calls: 5, pct: 10, color: '#8b5cf6' },
])

const chartDays = ['周一', '周二', '周三', '周四', '周五', '周六', '今天']
const deepseekData = [1.2, 0.8, 2.1, 1.5, 3.2, 1.8, 1.4]
const kimiData = [0.5, 1.2, 0.9, 2.3, 1.1, 2.8, 2.3]
const maxVal = 4.0

function toPoints(data: number[]) {
  return data.map((v, i) => {
    const x = (i / (data.length - 1)) * 560 + 20
    const y = 150 - (v / maxVal) * 130
    return `${x},${y}`
  }).join(' ')
}
function toDots(data: number[]) {
  return data.map((v, i) => ({
    x: (i / (data.length - 1)) * 560 + 20,
    y: 150 - (v / maxVal) * 130
  }))
}
const deepseekPoints = toPoints(deepseekData)
const kimiPoints = toPoints(kimiData)
const deepseekDots = toDots(deepseekData)
const kimiDots = toDots(kimiData)
const yLabels = ['4', '3', '2', '1', '0']

const tokenBreakdown = ref([
  { label: '输入 (Prompt)', color: '#2563eb', value: '892K' },
  { label: '输出 (Completion)', color: '#f59e0b', value: '287K' },
  { label: '缓存命中', color: '#10b981', value: '55K' },
])

const cacheStats = ref([
  { name: 'DeepSeek', rate: 43, color: '#2563eb', saving: '2.34' },
  { name: 'Kimi', rate: 61, color: '#10b981', saving: '4.12' },
])

const recentLogs = ref([
  { time: '14:32', model: 'kimi-k2-0905', color: '#10b981', input: 1240, output: 380, cached: true, cost: '0.012' },
  { time: '14:28', model: 'deepseek-chat', color: '#2563eb', input: 890, output: 520, cached: false, cost: '0.034' },
  { time: '14:15', model: 'kimi-k2-0905', color: '#10b981', input: 2100, output: 680, cached: true, cost: '0.021' },
  { time: '13:58', model: 'deepseek-chat', color: '#2563eb', input: 450, output: 290, cached: true, cost: '0.008' },
  { time: '13:42', model: 'kimi-k2.5', color: '#8b5cf6', input: 3200, output: 1200, cached: false, cost: '0.089' },
  { time: '13:30', model: 'kimi-k2-0905', color: '#10b981', input: 780, output: 320, cached: false, cost: '0.018' },
  { time: '13:15', model: 'deepseek-chat', color: '#2563eb', input: 1560, output: 840, cached: true, cost: '0.041' },
  { time: '12:50', model: 'kimi-k2-0905', color: '#10b981', input: 920, output: 410, cached: true, cost: '0.019' },
])
</script>

<style scoped>
.dashboard {
  padding: 32px;
  max-width: 1200px;
}

.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

/* ===== 统计卡片 ===== */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border: 1px solid #f1f5f9;
  transition: box-shadow 0.2s;
}
.stat-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }

.stat-icon {
  width: 46px; height: 46px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.stat-value { font-size: 22px; font-weight: 800; color: #111827; line-height: 1.1; }
.stat-label { font-size: 12px; color: #9ca3af; margin-top: 4px; font-weight: 500; }
.stat-change { font-size: 12px; margin-top: 6px; font-weight: 600; }
.stat-change.up { color: #ef4444; }
.stat-change.down-good { color: #10b981; }

/* ===== 通用卡片 ===== */
.card {
  background: white;
  border-radius: 14px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border: 1px solid #f1f5f9;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.card-title { font-size: 14px; font-weight: 700; color: #374151; }
.card-sub { font-size: 12px; color: #9ca3af; }

.section-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

/* ===== 余额卡片 ===== */
.balance-card { margin-bottom: 0; }
.balance-list { display: flex; flex-direction: column; gap: 14px; }

.balance-item { display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; gap: 6px; }
.bal-left { display: flex; align-items: center; gap: 8px; }
.bal-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.bal-name { font-size: 13px; font-weight: 600; color: #374151; }
.bal-right { display: flex; align-items: center; gap: 8px; }
.bal-amount { font-size: 15px; font-weight: 700; color: #111827; }
.bal-status { font-size: 12px; }
.bal-bar { grid-column: 1 / -1; height: 5px; background: #f1f5f9; border-radius: 10px; overflow: hidden; }
.bal-fill { height: 100%; border-radius: 10px; transition: width 0.6s ease; }
.balance-hint { font-size: 11px; color: #f59e0b; margin-top: 14px; }

.refresh-btn {
  background: none; border: none; cursor: pointer;
  color: #6b7280; font-size: 16px;
  transition: transform 0.3s;
  padding: 4px;
}
.refresh-btn:hover { color: #2563eb; }
.refresh-btn.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 模型使用分布 ===== */
.model-usage-chart { display: flex; flex-direction: column; gap: 14px; }
.model-bar-item { display: grid; grid-template-columns: 140px 1fr 50px; align-items: center; gap: 10px; }
.mbar-label { font-size: 12px; color: #374151; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mbar-track { height: 8px; background: #f1f5f9; border-radius: 10px; overflow: hidden; }
.mbar-fill { height: 100%; border-radius: 10px; transition: width 0.8s ease; }
.mbar-value { font-size: 12px; color: #6b7280; text-align: right; }

/* ===== 折线图 ===== */
.chart-card { margin-bottom: 16px; }
.chart-legend { display: flex; gap: 16px; align-items: center; font-size: 12px; color: #6b7280; }
.legend-dot { width: 10px; height: 3px; border-radius: 2px; display: inline-block; margin-right: 4px; }

.line-chart { display: flex; gap: 8px; }
.chart-y-labels {
  display: flex; flex-direction: column; justify-content: space-between;
  font-size: 11px; color: #9ca3af;
  padding-bottom: 22px;
  text-align: right;
  min-width: 24px;
}

.chart-area { flex: 1; position: relative; }
.chart-gridlines {
  position: absolute; top: 0; left: 0; right: 0;
  display: flex; flex-direction: column; justify-content: space-between;
  height: calc(100% - 22px);
}
.gridline { border-top: 1px dashed #f1f5f9; width: 100%; }

.chart-svg { width: 100%; height: 160px; display: block; }
.chart-x-labels {
  display: flex; justify-content: space-between;
  font-size: 11px; color: #9ca3af;
  margin-top: 4px; padding: 0 20px;
}

/* ===== Token 饼图 ===== */
.token-breakdown { display: flex; align-items: center; gap: 24px; }
.donut-wrapper { position: relative; width: 120px; height: 120px; flex-shrink: 0; }
.donut-svg { width: 100%; height: 100%; }
.donut-center {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  text-align: center;
}
.donut-total { font-size: 16px; font-weight: 800; color: #111827; }
.donut-sub { font-size: 10px; color: #9ca3af; }

.token-legend { display: flex; flex-direction: column; gap: 10px; }
.token-leg-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.leg-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.leg-label { flex: 1; color: #374151; }
.leg-value { font-weight: 700; color: #111827; }

/* ===== 缓存命中 ===== */
.cache-stats { display: flex; flex-direction: column; gap: 16px; }
.cache-header-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
.cache-name { font-size: 13px; font-weight: 600; color: #374151; }
.cache-rate { font-size: 16px; font-weight: 800; }
.cache-track { height: 8px; background: #f1f5f9; border-radius: 10px; overflow: hidden; }
.cache-fill { height: 100%; border-radius: 10px; transition: width 0.8s ease; }
.cache-saving { font-size: 11px; color: #10b981; margin-top: 4px; }
.cache-tip { font-size: 12px; color: #6b7280; background: #fffbeb; border: 1px solid #fde68a; padding: 8px 12px; border-radius: 8px; margin-top: 4px; }

/* ===== 请求记录表格 ===== */
.recent-card { margin-top: 0; }
.recent-table { font-size: 13px; }
.rt-head, .rt-row {
  display: grid;
  grid-template-columns: 70px 160px 100px 100px 80px 80px;
  gap: 8px;
  padding: 10px 0;
  align-items: center;
}
.rt-head {
  font-size: 11px; font-weight: 700; color: #9ca3af;
  text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 2px solid #f1f5f9;
}
.rt-row { border-bottom: 1px solid #f9fafb; color: #374151; }
.rt-row:last-child { border-bottom: none; }
.rt-time { color: #9ca3af; }
.rt-model { font-weight: 600; font-size: 12px; }
.rt-cost { font-weight: 700; color: #111827; }
.cache-badge {
  font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600;
}
.cache-badge.hit { background: #d1fae5; color: #059669; }
.cache-badge.miss { background: #fee2e2; color: #dc2626; }
</style>
