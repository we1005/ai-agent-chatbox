// 项目品牌单点。改中英文 / tagline / 印章字都改这里。
// 语义：玄 = 幽深不透明（AI 黑盒）；鉴 = 映照反思（Context reflect / Mem0 judge / RAG 召回）。
export const brand = {
  chinese: '玄鉴',
  chinesePinyin: 'Xuánjiàn',
  english: 'Xuanjian',
  englishSub: 'The Deep Mirror',
  tagline: '一个会反思的知识伙伴',
  taglineEn: 'A reflective companion for knowledge — RAG × Agent × Long-Context Memory',
  // Hero 下方装饰汉字（单字浮动）
  hanziFloat: ['知', '鉴', '忆'] as const,
  // 印章四字（古风）
  seal: '博观约取',
  footerCite: {
    text: '博观而约取 · 厚积而薄发',
    author: '苏轼 · 《稼说送张琥》',
  },
  github: 'https://github.com/',
  poweredBy: [
    'Vue 3', 'FastAPI', 'MongoDB', 'Qdrant',
    'LightRAG', 'Mem0', 'LangGraph', 'LangSmith',
    'DeepSeek', 'Kimi', 'Doubao', 'BGE-M3',
  ] as const,
} as const
