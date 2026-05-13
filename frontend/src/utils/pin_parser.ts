/**
 * Context Engine v2 · P5.2 · @pin 语法解析器
 *
 * 把用户在输入框里打的 `@kb:filename` / `@memory:topic` / `@last-turn` / `@reset`
 * 从消息文本里抽出来，产出一个前置指令列表；真正发送给后端时，消息文本
 * 去掉 @token（避免污染 RAG 召回），指令以 metadata 形式附加。
 *
 * 首版：客户端纯解析，不直接影响后端行为。后端真正消费 @pin 留给未来
 * InjectionPlan 扩展。
 */

export type PinDirective =
  | { kind: 'kb'; value: string }        // @kb:crud-0042  → 强制钉住此文件
  | { kind: 'memory'; value: string }    // @memory:偏好    → 按 topic 查询 memory
  | { kind: 'last-turn' }                // @last-turn     → 只引用上一轮
  | { kind: 'reset' }                    // @reset         → 要求后端忽略 memory / summary

export interface ParsedInput {
  cleanText: string
  directives: PinDirective[]
}

const RE_KB = /@kb:([a-zA-Z0-9_.\-]+)/g
const RE_MEM = /@memory:([^\s]+)/g
const RE_LAST_TURN = /@last-turn\b/g
const RE_RESET = /@reset\b/g

export function parsePinSyntax(input: string): ParsedInput {
  const directives: PinDirective[] = []
  let text = input

  text = text.replace(RE_KB, (_, v) => {
    directives.push({ kind: 'kb', value: v })
    return ''
  })
  text = text.replace(RE_MEM, (_, v) => {
    directives.push({ kind: 'memory', value: v })
    return ''
  })
  text = text.replace(RE_LAST_TURN, () => {
    directives.push({ kind: 'last-turn' })
    return ''
  })
  text = text.replace(RE_RESET, () => {
    directives.push({ kind: 'reset' })
    return ''
  })

  return {
    cleanText: text.replace(/\s+/g, ' ').trim(),
    directives,
  }
}
