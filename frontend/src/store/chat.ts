import { defineStore } from 'pinia'

export interface CitationRef {
  index: number
  source: string
  snippet: string
}

export interface AgentStage {
  id: string
  title: string
  status: 'running' | 'done'
  summary?: string   // 面向用户的描述文本（intent / plan 从 LLM 输出里抽出来）
}

export interface AgentToolCall {
  id: string
  name: string
  args?: Record<string, any>
  result_preview?: string
  status: 'running' | 'done'
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning?: string
  refs?: CitationRef[]
  recommend?: string[]
  // Solo 模式：思考链 / 工具链 trace（classic 模式为 undefined，模板自然隐藏）
  stages?: AgentStage[]
  toolCalls?: AgentToolCall[]
}

export interface Conversation {
  id: string
  title: string
  updated_at: string
  /** 后端 GET /api/conversations 返回时已带上完整 messages（含 content），
   *  前端用于 Sidebar 的 Fuse.js 模糊检索（标题 + 消息正文）。 */
  messages?: Message[]
}

const KB_FLAG_KEY = 'useKnowledgeBase'
const WS_FLAG_KEY = 'useWebSearch'
const SOLO_FLAG_KEY = 'enableSolo'
const getDefaultKnowledgeBaseState = () => {
  const saved = localStorage.getItem(KB_FLAG_KEY)
  if (saved === null) return true
  return saved === 'true'
}
const getDefaultWebSearchState = () => {
  const saved = localStorage.getItem(WS_FLAG_KEY)
  if (saved === null) return false
  return saved === 'true'
}
const getDefaultSoloState = () => {
  const saved = localStorage.getItem(SOLO_FLAG_KEY)
  if (saved === null) return false
  return saved === 'true'
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [] as Message[],
    currentModel: 'kimi-k2-0905-preview',
    isLoading: false,
    abortController: null as AbortController | null,
    conversationId: null as string | null,
    conversations: [] as Conversation[],
    useKnowledgeBase: getDefaultKnowledgeBaseState(),
    useWebSearch: getDefaultWebSearchState(),
    enableThinking: false,
    embeddingReady: false,
    rerankerLoaded: false,
    useReranker: false,
    enableSolo: getDefaultSoloState(),
  }),
  actions: {
    addMessage(message: Message) {
      this.messages.push(message)
    },
    updateLastMessage(content: string) {
      if (this.messages.length > 0) {
        this.messages[this.messages.length - 1].content = content
      }
    },
    clearMessages() {
      // 若当前有流正在跑，先中止——否则 SSE 回调会把 token 写进新会话的消息里
      this._abortInFlight()
      this.messages = []
      this.conversationId = null
    },
    // 中断当前 SSE 并把正在运行的 trace 项目 finalize 掉
    _abortInFlight() {
      if (this.abortController) {
        this.abortController.abort()
        this.abortController = null
      }
      this._finalizeRunningTrace('aborted')
      this.isLoading = false
    },
    // 把最后一条 assistant 消息里还处于 running 的 stage / toolCall 翻为 done，
    // 避免 UI 一直转圈。mode='aborted' 会在 result_preview 里追加中断标记。
    _finalizeRunningTrace(mode: 'aborted' | 'completed' = 'completed') {
      if (this.messages.length === 0) return
      const last = this.messages[this.messages.length - 1]
      if (last.role !== 'assistant') return
      if (last.stages) {
        for (const s of last.stages) {
          if (s.status === 'running') s.status = 'done'
        }
      }
      if (last.toolCalls) {
        for (const tc of last.toolCalls) {
          if (tc.status === 'running') {
            tc.status = 'done'
            if (mode === 'aborted' && !tc.result_preview) {
              tc.result_preview = '[已中断]'
            }
          }
        }
      }
    },
    setModel(model: string) {
      this.currentModel = model
    },
    setUseKnowledgeBase(val: boolean) {
      this.useKnowledgeBase = val
      localStorage.setItem(KB_FLAG_KEY, String(val))
    },
    setUseWebSearch(val: boolean) {
      this.useWebSearch = val
      localStorage.setItem(WS_FLAG_KEY, String(val))
    },
    setUseReranker(val: boolean) {
      this.useReranker = val
    },
    // 开 Solo 时如果当前模型不是 DeepSeek，自动切到 deepseek-chat（Kimi 的 function
    // calling 不稳，Solo 场景强烈推荐 DeepSeek）。返回 modelSwitched 供 UI toast 使用。
    setEnableSolo(val: boolean): { modelSwitched: boolean } {
      this.enableSolo = val
      localStorage.setItem(SOLO_FLAG_KEY, String(val))
      if (val && !this.currentModel.startsWith('deepseek')) {
        this.setModel('deepseek-chat')
        return { modelSwitched: true }
      }
      return { modelSwitched: false }
    },
    async fetchEmbeddingStatus() {
      try {
        const res = await fetch('http://localhost:8000/api/embedding/system-info')
        if (res.ok) {
          const data = await res.json()
          const ready = data.embedding_ready ?? false
          const rerankerLoaded = data.reranker_loaded ?? false
          this.embeddingReady = ready
          this.rerankerLoaded = rerankerLoaded
          // 模型已卸载时强制关闭知识库开关，防止 localStorage 残留值
          // 导致聊天请求携带 use_knowledge_base: true 打到未初始化的后端
          if (!ready && this.useKnowledgeBase) {
            this.setUseKnowledgeBase(false)
          }
          // reranker 卸载时自动关闭 reranker 开关
          if (!rerankerLoaded && this.useReranker) {
            this.useReranker = false
          }
        }
      } catch (e) {
        console.error('Failed to fetch embedding status', e)
      }
    },
    async fetchConversations() {
      try {
        const res = await fetch('http://localhost:8000/api/conversations')
        if (res.ok) {
          this.conversations = await res.json()
        }
      } catch (e) {
        console.error('Failed to fetch conversations', e)
      }
    },
    async loadConversation(id: string) {
      // 切换会话前中止当前流，否则 SSE chunks 会写到新会话的消息里
      this._abortInFlight()
      try {
        this.isLoading = true
        const res = await fetch(`http://localhost:8000/api/conversations/${id}`)
        if (res.ok) {
          const data = await res.json()
          this.conversationId = id
          this.messages = data.messages
        }
      } catch (e) {
        console.error('Failed to load conversation', e)
      } finally {
        this.isLoading = false
      }
    },
    async deleteConversation(id: string) {
      try {
        await fetch(`http://localhost:8000/api/conversations/${id}`, { method: 'DELETE' })
        this.conversations = this.conversations.filter(c => c.id !== id)
        if (this.conversationId === id) {
          this.clearMessages()
        }
      } catch (e) {
        console.error('Failed to delete conversation', e)
      }
    },
    async uploadFile(file: File) {
      const formData = new FormData()
      formData.append('file', file)
      try {
        const res = await fetch('http://localhost:8000/api/upload', {
          method: 'POST',
          body: formData
        })
        if (!res.ok) throw new Error('Upload failed')
        return await res.json()
      } catch (e) {
        console.error('Upload error', e)
        throw e
      }
    },
    stopGeneration() {
      // 复用 _abortInFlight：既中止 fetch 又 finalize trace 状态
      this._abortInFlight()
    },
    async _streamChat(options: { regenerate?: boolean } = {}) {
      this.isLoading = true
      this.abortController = new AbortController()

      const isSolo = this.enableSolo
      const endpoint = isSolo
        ? 'http://localhost:8000/api/chat/solo'
        : 'http://localhost:8000/api/chat/completions'

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: this.messages,
            model: this.currentModel,
            conversation_id: this.conversationId,
            stream: true,
            // 下列开关在 solo 模式由 planner 自主决定，后端会忽略；仍然带上保证兼容。
            use_knowledge_base: this.useKnowledgeBase,
            use_reranker: this.useReranker,
            use_web_search: this.useWebSearch,
            enable_thinking: this.enableThinking,
            regenerate: options.regenerate || false,
          }),
          signal: this.abortController.signal,
        })

        if (!response.body) throw new Error('ReadableStream not supported')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()

        // solo 模式预置空 stages/toolCalls 数组，用于模板条件渲染
        this.addMessage(
          isSolo
            ? { role: 'assistant', content: '', stages: [], toolCalls: [] }
            : { role: 'assistant', content: '' }
        )

        // 流式累积缓冲区（用于实时 XML 剥离，始终启用）
        let rawBuffer = ''
        // SSE 跨 chunk 粘包缓冲：只有遇到 '\n\n' 才算一条完整事件
        let sseBuffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          sseBuffer += decoder.decode(value, { stream: true })
          const events = sseBuffer.split('\n\n')
          sseBuffer = events.pop() || ''  // 最后一段留到下次合并

          for (const ev of events) {
            if (!ev.startsWith('data: ')) continue
            const data = ev.slice(6)
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)

              if (parsed.conversation_id) {
                this.conversationId = parsed.conversation_id
                if (!this.conversations.find(c => c.id === parsed.conversation_id)) {
                  this.fetchConversations()
                }
              }

              if (parsed.reasoning) {
                const lastMsg = this.messages[this.messages.length - 1]
                lastMsg.reasoning = (lastMsg.reasoning || '') + parsed.reasoning
              }

              if (parsed.content) {
                // 实时累积原始流
                rawBuffer += parsed.content

                // Solo 模式：从 rawBuffer 抽取 <intent> / <plan> / <thinking> 的内容到独立区域
                if (isSolo) {
                  const lastMsg = this.messages[this.messages.length - 1]
                  if (!lastMsg.stages) lastMsg.stages = []

                  // intent
                  const intentMatch = rawBuffer.match(/<intent>([\s\S]*?)(?:<\/intent>|$)/i)
                  if (intentMatch) {
                    const text = intentMatch[1].trim()
                    let s = lastMsg.stages.find(x => x.id === 'intent')
                    if (!s) {
                      s = { id: 'intent', title: '已识别需求', status: 'running' }
                      lastMsg.stages.push(s)
                    }
                    s.summary = text
                    if (/<\/intent>/i.test(rawBuffer)) s.status = 'done'
                  }

                  // plan
                  const planMatch = rawBuffer.match(/<plan>([\s\S]*?)(?:<\/plan>|$)/i)
                  if (planMatch) {
                    const text = planMatch[1].trim()
                    let s = lastMsg.stages.find(x => x.id === 'plan')
                    if (!s) {
                      s = { id: 'plan', title: '已规划任务', status: 'running' }
                      lastMsg.stages.push(s)
                    }
                    s.summary = text
                    if (/<\/plan>/i.test(rawBuffer)) s.status = 'done'
                  }

                  // thinking → 写入 reasoning 字段，复用已有的思考过程区块渲染
                  const thinkingMatches = rawBuffer.match(/<thinking>([\s\S]*?)(?:<\/thinking>|$)/gi)
                  if (thinkingMatches) {
                    const joined = thinkingMatches
                      .map(m => m.replace(/<\/?thinking>/gi, '').trim())
                      .filter(Boolean)
                      .join('\n\n')
                    if (joined) lastMsg.reasoning = joined
                  }
                }

                // 面向用户的正文：去除 trace 相关的整块（连同其内部文本），保留最终 <content> 正文
                let stripped = rawBuffer
                  // 删除完整的 intent/plan/thinking 块
                  .replace(/<intent>[\s\S]*?<\/intent>/gi, '')
                  .replace(/<plan>[\s\S]*?<\/plan>/gi, '')
                  .replace(/<thinking>[\s\S]*?<\/thinking>/gi, '')
                  // 流还没拿到闭合标签时，先隐藏未闭合片段（闭合后会被上一条替换清掉）
                  .replace(/<intent>[\s\S]*$/i, '')
                  .replace(/<plan>[\s\S]*$/i, '')
                  .replace(/<thinking>[\s\S]*$/i, '')
                  // 保留引用占位符
                  .replace(/<ref>(\d+)<\/ref>/g, '[$1]')
                  // 去除 content/recommend/rec 的外层标签（内部文字保留）
                  .replace(/<\/?(content|recommend|rec)>/g, '')
                  .trimStart()
                this.updateLastMessage(stripped)
              }

              // 流结束后收到的结构化解析结果
              if (parsed.parsed) {
                const lastMsg = this.messages[this.messages.length - 1]
                if (parsed.parsed.content) {
                  lastMsg.content = parsed.parsed.content
                }
                lastMsg.refs = parsed.parsed.refs || []
                lastMsg.recommend = parsed.parsed.recommend || []
              }

              // ── Solo 模式新增事件 ─────────────────────────────
              if (parsed.stage) {
                const lastMsg = this.messages[this.messages.length - 1]
                if (!lastMsg.stages) lastMsg.stages = []
                const existing = lastMsg.stages.find(s => s.id === parsed.stage.id)
                if (existing) {
                  existing.status = parsed.stage.status
                  existing.title = parsed.stage.title
                } else {
                  lastMsg.stages.push({ ...parsed.stage })
                }
              }

              if (parsed.tool_call) {
                const lastMsg = this.messages[this.messages.length - 1]
                if (!lastMsg.toolCalls) lastMsg.toolCalls = []
                const tc = parsed.tool_call
                const existing = lastMsg.toolCalls.find(t => t.id === tc.id)
                if (existing) {
                  existing.status = tc.status
                  if (tc.result_preview !== undefined) existing.result_preview = tc.result_preview
                  if (tc.args !== undefined) existing.args = tc.args
                  if (tc.name) existing.name = tc.name
                } else {
                  lastMsg.toolCalls.push({
                    id: tc.id,
                    name: tc.name,
                    args: tc.args,
                    result_preview: tc.result_preview,
                    status: tc.status,
                  })
                }
              }

              if (parsed.title_update) {
                const conv = this.conversations.find(c => c.id === this.conversationId)
                if (conv) {
                  conv.title = parsed.title_update
                }
              }

              if (parsed.error) {
                console.error('Backend error:', parsed.error)
                // 让用户能看到后端错误，而不是看到一个空的回答气泡
                const lastMsg = this.messages[this.messages.length - 1]
                const errText = `\n\n> ⚠️ 服务端错误：${parsed.error}`
                if (lastMsg && lastMsg.role === 'assistant') {
                  lastMsg.content = (lastMsg.content || '') + errText
                } else {
                  this.addMessage({ role: 'system', content: errText.trimStart() })
                }
              }
            } catch (e) {
              console.error('Error parsing SSE data', e, data)
            }
          }
        }
        // 流自然结束：兜底 finalize 任何遗漏未 done 的 trace 项
        this._finalizeRunningTrace('completed')
        this.fetchConversations()
      } catch (error: any) {
        if (error.name === 'AbortError') {
          // 中止属于正常路径，_abortInFlight 已经 finalize 过了
          this.fetchConversations()
        } else {
          console.error('Error sending message:', error)
          // 前端网络 / 解析失败时，也 finalize trace 避免 UI 卡 running 态
          this._finalizeRunningTrace('aborted')
          this.addMessage({ role: 'system', content: `⚠️ 请求失败：${error?.message || String(error)}` })
        }
      } finally {
        this.abortController = null
        this.isLoading = false
      }
    },
    async sendMessageToApi(content: string) {
      this.addMessage({ role: 'user', content })
      await this._streamChat()
    },
    async regenerateResponse() {
      if (this.isLoading || this.messages.length === 0) return
      if (this.messages[this.messages.length - 1].role === 'assistant') {
        this.messages.pop()
      }
      await this._streamChat({ regenerate: true })
    }
  }
})
