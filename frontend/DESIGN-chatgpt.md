# Design System Inspired by ChatGPT

> 与 Linear 的对位：Linear 是"精密工程感 + 深色高密度"，ChatGPT 是"内容即主角 + 浅色低摩擦"。
> 同一个 StyleLab 页能切换两套 token，对比哪种更适合本项目对话产品的气质。

## 1. Visual Theme & Atmosphere

ChatGPT 的界面哲学是**"chrome disappears, content is the product"**——UI 几乎不存在于注意力前景，所有视觉服务于"读对话"这件事。近白底 `#FFFFFF`、细灰色描边 `#E5E5E5`、极大的行距 1.75，整体观感像翻开一本排版考究的书，而不是"使用一个软件"。

核心反差：
- Linear 在黑底上用亮度梯度雕刻信息层次；ChatGPT 在白底上用**留白和字号**自然分层
- Linear 字重 510 / 字距 -1.056px 追求"压缩的精确"；ChatGPT weight 400-500 / 字距 normal 追求"读起来舒服"
- Linear accent 是紫罗兰；ChatGPT **几乎无 accent**，偶见 OpenAI 品牌绿 `#10A37F` 用于极少数订阅/状态场景

**Key Characteristics:**
- Light-mode-native：`#FFFFFF` 主画布，`#F9F9F9` 侧栏，`#F4F4F4` 用户气泡
- Söhne / Inter / 系统字，weight 400 / 500 / 600，行距 1.75
- **AI 消息无气泡**——直接在白底上排文字，宽度受限（~720px 阅读宽度）
- **用户消息有气泡**——浅灰 `#F4F4F4`、18px 圆角、右对齐
- 输入框大圆角（24-26px）接近药丸形，单一主操作（送出按钮）黑色圆
- 边框永远是 `#E5E5E5`（或 `rgba(0,0,0,0.08)`），细到几乎不存在
- 无阴影或极淡阴影 `rgba(0,0,0,0.04) 0 1px 3px`
- OpenAI Teal `#10A37F` 仅用于极少 CTA / Upgrade / 成功图标

## 2. Color Palette & Roles

### Surfaces
- **Canvas** (`#FFFFFF`): 主画布
- **Sidebar** (`#F9F9F9`): 侧栏底色（比画布微暗）
- **Hover** (`#F4F4F4`): 按钮 / 侧栏项 hover
- **User Bubble** (`#F4F4F4`): 用户消息气泡底色

### Text
- **Primary** (`#0D0D0D`): 主文本，比纯黑略柔
- **Secondary** (`#676767`): 正文辅助、placeholder
- **Tertiary** (`#8E8EA0`): 元数据、时间戳、模型名

### Border
- **Default** (`#E5E5E5`): 输入框、卡片、分割线
- **Subtle** (`rgba(0,0,0,0.05)`): 侧栏内部细分

### Accent（极克制使用）
- **OpenAI Teal** (`#10A37F`): 成功状态、Upgrade CTA；**不用作常规 primary**
- **Primary CTA** 其实是**纯黑** (`#0D0D0D`): 黑底白字圆角按钮

## 3. Typography Rules

### Font Family
- **Primary**: `Söhne, "Helvetica Neue", Helvetica, Arial, sans-serif` — OpenAI 专属 Söhne 是付费字体；**本项目用已加载的 Inter Variable 代替**（质感接近，识别性强），fallback 到系统字
- **Monospace**: `"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace`
- **OpenType**: 不强制 `cv01/ss03`（这个是 Linear 的特征；ChatGPT 用 Inter 的默认 glyph 更温和）

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|
| Empty-state Hero | 30-32px | 600 | 1.2 | normal |
| Section Title | 20px | 600 | 1.4 | -0.01em |
| Chat Body | 16px | 400 | 1.75 | normal |
| Sidebar Item | 14px | 400 (active 500) | 1.4 | normal |
| Button Label | 14px | 500 | 1.2 | normal |
| Caption | 13px | 400 | 1.4 | normal |
| Code | 14px | 400 | 1.6 | normal (mono) |

**Principles:**
- **阅读是主场景**：Chat Body 用 16px + line-height 1.75 是 ChatGPT 最辨识度的决定，比 Linear 的 1.5 明显宽松
- **字重节制**：日常只用 400 / 500 / 600；不用 510 / 590 这类"精确中间值"
- **Headings 不招摇**：最大也就 32px，且 weight 600 而非 700/800；和正文之间的落差靠**留白**不靠字号

## 4. Component Stylings

### Buttons

**Primary (dark)**
- Background: `#0D0D0D`
- Text: `#FFFFFF`
- Radius: 12px
- Padding: 10px 16px
- Hover: `#1F1F1F`

**Secondary (outline)**
- Background: `#FFFFFF`
- Text: `#0D0D0D`
- Border: `1px solid #E5E5E5`
- Radius: 12px
- Hover: `#F7F7F7`

**Send (circular)**
- Background: `#0D0D0D`
- Icon: white arrow
- Size: 36px, fully round
- 输入框尾部专用

**Ghost Icon (sidebar tool)**
- Background: transparent → `#F4F4F4` on hover
- Padding: 8px, radius 6px

### Chat Message Bubble

**User message**
- Background: `#F4F4F4`
- Text: `#0D0D0D`, 16px weight 400, line-height 1.75
- Radius: 18px
- Padding: 10px 16px
- **Max width: ~70%**，右对齐

**Assistant message**
- Background: **none** (直接在 `#FFFFFF` 上)
- Text: `#0D0D0D`, 16px weight 400, line-height 1.75
- Max width: 720px，左对齐
- 通常前面有小 AI 标（32px 圆形，`#F4F4F4` 底）

### Cards
- Background: `#FFFFFF`
- Border: `1px solid #E5E5E5`
- Radius: 12px
- Padding: 16-24px
- Shadow: **none** 或 `rgba(0,0,0,0.04) 0 1px 3px`

### Input Box (核心组件)
- Background: `#FFFFFF`
- Border: `1px solid #E5E5E5`
- Radius: **24px**（接近药丸形，ChatGPT 的视觉标签）
- Padding: 12px 16px + 内部按钮留位
- Focus: border `#0D0D0D`（不加 ring 阴影，保持冷静）
- 末尾黑色圆形 Send 按钮

### Sidebar Item
- Padding: 10px 12px
- Radius: 6px
- Default: `#F9F9F9`（底色）/ text `#0D0D0D`
- Hover: `#ECECEC`
- Active: `#E5E5E5`

## 5. Layout Principles

### Spacing
- Base unit: 4px
- 常用值: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64
- **行距永远大于字号的 1.5 倍**

### Grid
- 对话主区最大宽度 **768px**（阅读宽度上限）
- 整页最大宽度 1200px，但 chat content 被限在 768 居中
- 侧栏固定 260-280px 宽

### Whitespace Philosophy
- **白底即留白**——不画分割线就不画（ChatGPT 整个应用几乎没有 divider）
- 空间分层靠 `padding` 和 `max-width`，不靠 border / shadow

### Border Radius
- Button: 12px
- Card: 12px
- Input box: **24px**（签名特征）
- User bubble: 18px
- Circular (icon / avatar / send): 50%

## 6. Do's and Don'ts

### Do
- 白底 + 16px/1.75 正文永远是默认
- AI 消息**不加气泡**——让内容和画布合一
- Primary action 用纯黑（`#0D0D0D`）—— ChatGPT 不用彩色 CTA
- 输入框圆角做大（24px+）—— 这是气质的核心
- 边框细到几乎不存在（`#E5E5E5`）

### Don't
- 不要用阴影堆出层次——ChatGPT 几乎无阴影
- 不要给 AI 消息加气泡或边框——它应该像直接排印的文字
- 不要用明显的 accent 色（紫/蓝/橙）—— 克制到位才是 ChatGPT 气质
- 不要在 Chat Body 用 weight 510 / 590 这些非标准值——对标的是 Inter 400/500/600
- 不要用彩色状态色——绿 `#10A37F` 只配合"订阅/完成"场景，其它状态用灰度

## 7. Agent Prompt Guide

### Quick Color Reference
- Canvas: `#FFFFFF`
- Sidebar: `#F9F9F9`
- User bubble: `#F4F4F4`
- Primary text: `#0D0D0D`
- Secondary text: `#676767`
- Tertiary text: `#8E8EA0`
- Border: `#E5E5E5`
- Success/Upgrade: `#10A37F`
- Primary CTA bg: `#0D0D0D`

### Example Component Prompts
- "Create a chat empty state centered on `#FFFFFF`: greeting at 30px Inter weight 600 color `#0D0D0D`. Below 4 suggestion cards in a 2x2 grid, each `#FFFFFF` bg, `1px solid #E5E5E5`, 12px radius, 16px padding, with 14px weight 500 title and 13px weight 400 `#676767` description."
- "Design a ChatGPT-style input bar at bottom: `#FFFFFF` bg, `1px solid #E5E5E5`, 24px radius, 52px height. Placeholder `Message AI…` at 16px `#8E8EA0`. Right side: 36px circular `#0D0D0D` send button with white arrow icon."
- "Build user message bubble: `#F4F4F4` bg, `#0D0D0D` 16px text weight 400 line-height 1.75, 18px radius, 10px 16px padding, max-width 70%, right-aligned. Above it, tiny timestamp at 12px `#8E8EA0`."
- "Render assistant message: no bubble, directly on `#FFFFFF`. Left side 32px circular avatar `#F4F4F4` bg with tiny icon. Content max-width 720px, 16px Inter weight 400 `#0D0D0D` line-height 1.75."
- "Sidebar item: 14px Inter weight 400 `#0D0D0D`, 10px 12px padding, 6px radius. Active state: `#ECECEC` bg, weight 500. Hover: `#F4F4F4`."

### Iteration Guide
1. 如果觉得某块界面"太设计"，就把 shadow / border 再减半，用留白代替
2. 任何 accent 色出现之前，先问：**纯灰度能不能解决？**——通常能
3. 字号只用 13 / 14 / 16 / 20 / 30，字重只用 400 / 500 / 600，简单粗暴
4. Input box 圆角宁大勿小；Button 圆角宁小勿大（12px 是黄金）
5. AI 消息永远无气泡；用户消息永远有气泡——这组对位是 ChatGPT 的灵魂
