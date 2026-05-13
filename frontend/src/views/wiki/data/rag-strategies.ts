import type { WikiPageData } from '../types'

// 5 种主策略 + Graph 5 子模式 + Agentic 4 档
const Y = (i: number) => 80 + i * 140

export const ragStrategies: WikiPageData = {
  title: 'RAG 策略矩阵',
  caption: '5 主策略 · Graph RAG 5 档查询 · Agentic 4 档运行模式 · 实测命中数据',
  intro:
    '本项目 classic 路径同时支持 5 种 RAG 策略，运行时通过 /api/embedding/* 切换并持久化到 backend/data/embedding_config.json。\n\n优先级（高→低）：graph_rag > agentic > multi_query > classical > off。\n\n实测数据见 RAG评测/报告/full-2026-04-22-with-ragas.md（CRUD-mini 60 query × 10 配置）。',
  nodes: [
    // ── 5 主策略 ──
    { id: 'off', position: { x: 0, y: Y(0) }, data: { role: 'note', label: 'off · 直答', desc: '不召回 · 闲聊 / 通识题最快' } },
    { id: 'classical', position: { x: 0, y: Y(1) }, data: { role: 'storage', label: 'classical · 单次召回', desc: 'BGE-M3 dense + sparse hybrid · 主流 baseline', sourceFile: 'backend/app/services/vector_store/qdrant_backend.py' } },
    { id: 'mq', position: { x: 0, y: Y(2) }, data: { role: 'compute', label: 'multi_query · 多查询融合', desc: 'LLM 将 query 重写 N 条 · 并行召回 · RRF 融合' } },
    { id: 'agent', position: { x: 0, y: Y(3) }, data: { role: 'compute', label: 'agentic · 评估循环', desc: 'grade → rewrite → retrieve → hallucination check', sourceFile: 'backend/app/services/agentic_rag.py' } },
    { id: 'graph', position: { x: 0, y: Y(4) }, data: { role: 'storage', label: 'graph · 图检索', desc: 'LightRAG 实体/关系/社区聚合', sourceFile: 'backend/app/services/graph_rag.py' } },

    // ── Graph 5 子模式 ──
    { id: 'g-naive', position: { x: 440, y: Y(2.5) }, data: { role: 'storage', label: 'naive', desc: '纯向量召回（baseline 用于对照）' } },
    { id: 'g-local', position: { x: 440, y: Y(3.2) }, data: { role: 'storage', label: 'local', desc: '实体邻域 · 单点深挖' } },
    { id: 'g-global', position: { x: 440, y: Y(3.9) }, data: { role: 'storage', label: 'global', desc: '社区摘要 · 全局视角' } },
    { id: 'g-hybrid', position: { x: 440, y: Y(4.6) }, data: { role: 'storage', label: 'hybrid', desc: 'local + global 融合' } },
    { id: 'g-mix', position: { x: 440, y: Y(5.3) }, data: { role: 'storage', label: 'mix', desc: '推荐档位 · 综合最佳' } },

    // ── Agentic 4 档 ──
    { id: 'a-off', position: { x: 440, y: Y(0.8) }, data: { role: 'note', label: 'off' } },
    { id: 'a-grade', position: { x: 440, y: Y(1.5) }, data: { role: 'compute', label: 'grading_only', desc: '只评分不重写' } },
    { id: 'a-rw', position: { x: 440, y: Y(2.2) }, data: { role: 'compute', label: 'grading_rewrite', desc: '评分 + 失败时重写' } },
    { id: 'a-full', position: { x: 440, y: Y(2.9) }, data: { role: 'compute', label: 'full', desc: '全开 · 含 hallucination check' } },

    // ── 优先级提示节点 ──
    { id: 'pri', position: { x: 880, y: Y(2.5) }, data: { role: 'decision', label: '运行时优先级', desc: 'graph > agentic > multi_query > classical > off · classic 路径硬编码' } },
  ],
  edges: [
    { id: 'a1', source: 'agent', target: 'a-off' },
    { id: 'a2', source: 'agent', target: 'a-grade' },
    { id: 'a3', source: 'agent', target: 'a-rw' },
    { id: 'a4', source: 'agent', target: 'a-full' },

    { id: 'g1', source: 'graph', target: 'g-naive' },
    { id: 'g2', source: 'graph', target: 'g-local' },
    { id: 'g3', source: 'graph', target: 'g-global' },
    { id: 'g4', source: 'graph', target: 'g-hybrid' },
    { id: 'g5', source: 'graph', target: 'g-mix' },

    { id: 'p1', source: 'a-full', target: 'pri', strokeRole: 'decision' },
    { id: 'p2', source: 'g-mix', target: 'pri', strokeRole: 'decision' },
    { id: 'p3', source: 'mq', target: 'pri', strokeRole: 'decision' },
    { id: 'p4', source: 'classical', target: 'pri', strokeRole: 'decision' },
  ],
}
