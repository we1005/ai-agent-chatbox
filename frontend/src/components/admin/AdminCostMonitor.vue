<template>
  <div class="cost-monitor">
    <div class="page-header">
      <h1>费用监控</h1>
      <p class="subtitle">实时追踪 API 余额、Token 消耗和花费明细</p>
    </div>

    <!-- 余额大卡 -->
    <div class="balance-big-grid">
      <div class="balance-big-card" v-for="acc in accounts" :key="acc.name">
        <div class="bbc-header">
          <span class="bbc-name">{{ acc.name }}</span>
          <button class="refresh-btn" @click="refreshAccount(acc)" :class="{ spinning: acc.refreshing }">↻</button>
        </div>
        <div class="bbc-main">
          <div class="bbc-amount">¥ {{ acc.available }}</div>
          <div class="bbc-status" :class="acc.statusClass">{{ acc.statusIcon }} {{ acc.statusText }}</div>
        </div>
        <div class="bbc-detail">
          <div class="bbc-detail-row">
            <span>充值余额</span>
            <span>¥ {{ acc.recharged }}</span>
          </div>
          <div class="bbc-detail-row">
            <span>赠送余额</span>
            <span>¥ {{ acc.gifted }}</span>
          </div>
          <div class="bbc-detail-row">
            <span>今日消耗</span>
            <span class="red">-¥ {{ acc.todayCost }}</span>
          </div>
        </div>
        <div class="bbc-bar">
          <div class="bbc-bar-fill" :style="{ width: acc.pct + '%', background: acc.color }"></div>
        </div>
        <div class="bbc-threshold">
          <span>低余额警告阈值</span>
          <div class="threshold-input">
            ¥ <input type="number" v-model.number="acc.threshold" class="threshold-num" />
          </div>
        </div>
      </div>
    </div>

    <!-- 价格参考表 -->
    <div class="card pricing-card">
      <div class="card-header">
        <span class="card-title">模型定价参考</span>
        <span class="card-sub">单位：元 / 百万 tokens</span>
      </div>
      <div class="pricing-table">
        <div class="pt-head">
          <span>模型</span>
          <span>输入（缓存命中）</span>
          <span>输入（缓存未命中）</span>
          <span>输出</span>
          <span>特殊</span>
        </div>
        <div class="pt-row" v-for="p in pricing" :key="p.model">
          <span class="pt-model" :style="{ color: p.color }">{{ p.model }}</span>
          <span class="pt-val green">¥ {{ p.inputHit }}</span>
          <span class="pt-val">¥ {{ p.inputMiss }}</span>
          <span class="pt-val">¥ {{ p.output }}</span>
          <span class="pt-special">{{ p.special }}</span>
        </div>
      </div>
    </div>

    <!-- 费用统计 + 缓存 -->
    <div class="stats-grid">
      <div class="card">
        <div class="card-header"><span class="card-title">本周费用汇总</span></div>
        <div class="weekly-bars">
          <div class="wb-item" v-for="d in weeklyData" :key="d.day">
            <div class="wb-bar-wrap">
              <div class="wb-bar" :style="{ height: (d.ds/maxDaily*100) + '%', background: '#2563eb' }">
                <div class="wb-tooltip">DeepSeek ¥{{ d.ds }}</div>
              </div>
              <div class="wb-bar kimi" :style="{ height: (d.kimi/maxDaily*100) + '%', background: '#10b981' }">
                <div class="wb-tooltip">Kimi ¥{{ d.kimi }}</div>
              </div>
            </div>
            <div class="wb-day">{{ d.day }}</div>
          </div>
        </div>
        <div class="weekly-legend">
          <span><span class="ld" style="background:#2563eb"></span>DeepSeek</span>
          <span><span class="ld" style="background:#10b981"></span>Kimi</span>
        </div>
        <div class="weekly-total">本周总计 <strong>¥ {{ weeklyTotal }}</strong></div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">KV 缓存命中分析</span></div>
        <div class="cache-analysis">
          <div class="ca-item" v-for="c in cacheAnalysis" :key="c.model">
            <div class="ca-top">
              <span class="ca-model" :style="{ color: c.color }">{{ c.model }}</span>
              <span class="ca-rate" :style="{ color: c.color }">{{ c.rate }}%</span>
            </div>
            <div class="ca-track">
              <div class="ca-fill" :style="{ width: c.rate + '%', background: c.color }"></div>
            </div>
            <div class="ca-detail">
              <span>命中：{{ c.hitTokens }}K tokens</span>
              <span class="ca-save">节省 ¥{{ c.saved }}</span>
            </div>
          </div>
          <div class="ca-tip">
            <div class="ca-tip-title">💡 提升缓存命中率的技巧</div>
            <ul class="ca-tips-list">
              <li>System Prompt 越长且固定，命中率越高</li>
              <li>避免每次修改 System Prompt</li>
              <li>长对话中固定内容放在靠前位置</li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- 明细记录 -->
    <div class="card detail-card">
      <div class="card-header">
        <span class="card-title">消费明细</span>
        <div class="filter-bar">
          <select class="filter-select" v-model="filterModel">
            <option value="">全部模型</option>
            <option value="deepseek-chat">deepseek-chat</option>
            <option value="kimi-k2-0905">kimi-k2-0905</option>
            <option value="kimi-k2.5">kimi-k2.5</option>
          </select>
          <select class="filter-select" v-model="filterDays">
            <option value="7">近 7 天</option>
            <option value="30">近 30 天</option>
          </select>
        </div>
      </div>
      <div class="detail-table">
        <div class="dt-head">
          <span>时间</span>
          <span>模型</span>
          <span>输入 tokens</span>
          <span>缓存命中</span>
          <span>输出 tokens</span>
          <span>工具调用</span>
          <span>费用</span>
        </div>
        <div class="dt-row" v-for="(row, i) in filteredLogs" :key="i">
          <span class="dt-time">{{ row.time }}</span>
          <span class="dt-model" :style="{ color: row.color }">{{ row.model }}</span>
          <span>{{ row.inputTokens.toLocaleString() }}</span>
          <span><span class="cache-chip" :class="row.cacheHit ? 'hit' : 'miss'">{{ row.cacheHit ? '✓ 命中' : '✗ 未中' }}</span></span>
          <span>{{ row.outputTokens.toLocaleString() }}</span>
          <span>{{ row.toolCalls > 0 ? `× ${row.toolCalls}` : '-' }}</span>
          <span class="dt-cost">¥ {{ row.cost }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const filterModel = ref('')
const filterDays = ref('7')

const accounts = ref([
  {
    name: 'DeepSeek API', available: '48.20', recharged: '43.20', gifted: '5.00',
    todayCost: '1.34', color: '#2563eb', pct: 82,
    statusClass: 'ok', statusIcon: '🟢', statusText: '余额充足',
    threshold: 10, refreshing: false,
  },
  {
    name: 'Kimi (Moonshot) API', available: '12.50', recharged: '12.50', gifted: '0.00',
    todayCost: '2.36', color: '#10b981', pct: 25,
    statusClass: 'warn', statusIcon: '🟡', statusText: '余额偏低',
    threshold: 10, refreshing: false,
  },
])

const refreshAccount = (acc: any) => {
  acc.refreshing = true
  setTimeout(() => { acc.refreshing = false }, 1500)
}

const pricing = ref([
  { model: 'deepseek-chat', color: '#2563eb', inputHit: '0.2', inputMiss: '2.0', output: '3.0', special: '思考模式 max_tokens 32K' },
  { model: 'kimi-k2-0905', color: '#10b981', inputHit: '自动缓存', inputMiss: '待查', output: '待查', special: '256K 上下文' },
  { model: 'kimi-k2.5', color: '#8b5cf6', inputHit: '自动缓存', inputMiss: '待查', output: '待查', special: '联网搜索 ¥0.03/次' },
])

const weeklyData = ref([
  { day: '周一', ds: 0.8, kimi: 0.5 },
  { day: '周二', ds: 1.2, kimi: 1.0 },
  { day: '周三', ds: 0.6, kimi: 1.5 },
  { day: '周四', ds: 2.1, kimi: 0.8 },
  { day: '周五', ds: 1.5, kimi: 2.3 },
  { day: '周六', ds: 0.9, kimi: 1.1 },
  { day: '今天', ds: 1.34, kimi: 2.36 },
])

const maxDaily = computed(() => Math.max(...weeklyData.value.map(d => d.ds + d.kimi)) * 1.2)
const weeklyTotal = computed(() => weeklyData.value.reduce((sum, d) => sum + d.ds + d.kimi, 0).toFixed(2))

const cacheAnalysis = ref([
  { model: 'deepseek-chat', color: '#2563eb', rate: 43, hitTokens: 530, saved: '2.34' },
  { model: 'kimi-k2-0905', color: '#10b981', rate: 61, hitTokens: 810, saved: '4.12' },
])

const detailLogs = ref([
  { time: '今天 14:32', model: 'kimi-k2-0905', color: '#10b981', inputTokens: 1240, cacheHit: true, outputTokens: 380, toolCalls: 0, cost: '0.012' },
  { time: '今天 14:28', model: 'deepseek-chat', color: '#2563eb', inputTokens: 890, cacheHit: false, outputTokens: 520, toolCalls: 0, cost: '0.034' },
  { time: '今天 14:15', model: 'kimi-k2-0905', color: '#10b981', inputTokens: 2100, cacheHit: true, outputTokens: 680, toolCalls: 2, cost: '0.021' },
  { time: '今天 13:58', model: 'deepseek-chat', color: '#2563eb', inputTokens: 450, cacheHit: true, outputTokens: 290, toolCalls: 0, cost: '0.008' },
  { time: '今天 13:42', model: 'kimi-k2.5', color: '#8b5cf6', inputTokens: 3200, cacheHit: false, outputTokens: 1200, toolCalls: 3, cost: '0.089' },
  { time: '昨天 22:10', model: 'kimi-k2-0905', color: '#10b981', inputTokens: 780, cacheHit: false, outputTokens: 320, toolCalls: 1, cost: '0.018' },
  { time: '昨天 20:35', model: 'deepseek-chat', color: '#2563eb', inputTokens: 1560, cacheHit: true, outputTokens: 840, toolCalls: 0, cost: '0.041' },
])

const filteredLogs = computed(() => {
  if (!filterModel.value) return detailLogs.value
  return detailLogs.value.filter(l => l.model.startsWith(filterModel.value))
})
</script>

<style scoped>
.cost-monitor { padding: 32px; max-width: 1200px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

.card {
  background: white; border-radius: 14px; padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}

/* ===== 余额大卡 ===== */
.balance-big-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.balance-big-card {
  background: white; border-radius: 14px; padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}
.bbc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.bbc-name { font-size: 14px; font-weight: 700; color: #374151; }
.refresh-btn { background: none; border: none; cursor: pointer; color: #9ca3af; font-size: 16px; padding: 4px; transition: all 0.2s; }
.refresh-btn:hover { color: #2563eb; }
.refresh-btn.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.bbc-main { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.bbc-amount { font-size: 32px; font-weight: 900; color: #111827; }
.bbc-status { font-size: 13px; font-weight: 600; }
.bbc-status.ok { color: #059669; }
.bbc-status.warn { color: #d97706; }

.bbc-detail { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.bbc-detail-row { display: flex; justify-content: space-between; font-size: 13px; color: #6b7280; }
.bbc-detail-row .red { color: #ef4444; font-weight: 600; }

.bbc-bar { height: 6px; background: #f1f5f9; border-radius: 10px; overflow: hidden; margin-bottom: 14px; }
.bbc-bar-fill { height: 100%; border-radius: 10px; }

.bbc-threshold { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #9ca3af; }
.threshold-input { display: flex; align-items: center; gap: 4px; color: #374151; font-weight: 600; }
.threshold-num {
  width: 52px; border: 1px solid #e5e7eb; border-radius: 6px;
  padding: 3px 6px; font-size: 13px; text-align: center; outline: none;
}

/* ===== 价格表 ===== */
.pricing-card { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.card-title { font-size: 14px; font-weight: 700; color: #374151; }
.card-sub { font-size: 12px; color: #9ca3af; }

.pricing-table { font-size: 13px; }
.pt-head, .pt-row {
  display: grid; grid-template-columns: 180px 160px 200px 100px 1fr;
  gap: 8px; padding: 10px 4px; align-items: center;
}
.pt-head { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #f1f5f9; }
.pt-row { border-bottom: 1px solid #f9fafb; }
.pt-row:last-child { border-bottom: none; }
.pt-model { font-weight: 700; }
.pt-val { font-weight: 600; color: #374151; }
.pt-val.green { color: #059669; }
.pt-special { font-size: 11px; color: #9ca3af; }

/* ===== 周数据柱图 ===== */
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.weekly-bars {
  display: flex; align-items: flex-end; gap: 8px;
  height: 120px; margin-bottom: 8px;
}
.wb-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%; }
.wb-bar-wrap { flex: 1; width: 100%; display: flex; align-items: flex-end; gap: 2px; }
.wb-bar {
  flex: 1; border-radius: 4px 4px 0 0; position: relative;
  min-height: 4px; transition: height 0.5s ease;
  cursor: pointer;
}
.wb-bar:hover .wb-tooltip { display: block; }
.wb-tooltip {
  display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
  background: #1e293b; color: white; font-size: 10px; padding: 3px 7px;
  border-radius: 4px; white-space: nowrap; margin-bottom: 4px; z-index: 10;
}
.wb-day { font-size: 11px; color: #9ca3af; }
.weekly-legend { display: flex; gap: 16px; font-size: 12px; color: #6b7280; margin-bottom: 8px; }
.ld { display: inline-block; width: 10px; height: 3px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.weekly-total { font-size: 13px; color: #374151; }
.weekly-total strong { color: #2563eb; font-size: 16px; }

/* ===== 缓存分析 ===== */
.cache-analysis { display: flex; flex-direction: column; gap: 16px; }
.ca-top { display: flex; justify-content: space-between; margin-bottom: 4px; }
.ca-model { font-size: 13px; font-weight: 700; }
.ca-rate { font-size: 16px; font-weight: 800; }
.ca-track { height: 8px; background: #f1f5f9; border-radius: 10px; overflow: hidden; margin-bottom: 4px; }
.ca-fill { height: 100%; border-radius: 10px; }
.ca-detail { display: flex; justify-content: space-between; font-size: 12px; color: #9ca3af; }
.ca-save { color: #059669; font-weight: 600; }
.ca-tip { background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 12px; }
.ca-tip-title { font-size: 13px; font-weight: 700; color: #92400e; margin-bottom: 6px; }
.ca-tips-list { margin: 0; padding-left: 16px; font-size: 12px; color: #78350f; line-height: 1.8; }

/* ===== 明细表格 ===== */
.detail-card { margin-top: 0; }
.filter-bar { display: flex; gap: 10px; }
.filter-select {
  border: 1px solid #e5e7eb; border-radius: 7px; padding: 5px 10px;
  font-size: 12px; color: #374151; outline: none; cursor: pointer;
}
.detail-table { font-size: 13px; }
.dt-head, .dt-row {
  display: grid;
  grid-template-columns: 120px 150px 100px 100px 100px 80px 80px;
  gap: 8px; padding: 10px 4px; align-items: center;
}
.dt-head { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #f1f5f9; }
.dt-row { border-bottom: 1px solid #f9fafb; }
.dt-row:last-child { border-bottom: none; }
.dt-time { color: #9ca3af; font-size: 12px; }
.dt-model { font-weight: 700; font-size: 12px; }
.dt-cost { font-weight: 700; color: #111827; }
.cache-chip { font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }
.cache-chip.hit { background: #d1fae5; color: #059669; }
.cache-chip.miss { background: #fee2e2; color: #dc2626; }
</style>
