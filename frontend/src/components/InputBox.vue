<template>
  <!--
    2026-04 · 一体化输入框（ChatGPT/Claude 式）：textarea 在上，工具栏（Model/Solo/设置）
    + 发送按钮在底部同一卡片内。原 ConfigPanel 的三控件已迁出到 ChatToolbar.vue。
  -->
  <div class="input-container">
    <div class="input-box">
      <!-- 上：textarea -->
      <el-input
        v-model="input"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 6 }"
        placeholder="Message AI..."
        @keydown.enter.prevent="handleEnter"
        :disabled="isLoading"
        resize="none"
        class="chat-input"
      />

      <!-- 下：工具栏 row -->
      <div class="toolbar-row">
        <ChatToolbar />

        <div class="actions">
          <el-button
            v-if="!isLoading"
            type="primary"
            circle
            @click="sendMessage"
            :disabled="!input.trim()"
            class="send-btn"
            :icon="Position"
          />
          <el-button
            v-else
            type="danger"
            circle
            @click="stopGeneration"
            class="stop-btn"
            :icon="CircleClose"
          />
        </div>
      </div>
    </div>
    <div class="disclaimer">AI can make mistakes. Consider verifying important information.</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../store/chat'
import { Position, CircleClose } from '@element-plus/icons-vue'
import ChatToolbar from './ChatToolbar.vue'

const store = useChatStore()
const input = ref('')
const isLoading = computed(() => store.isLoading)

const sendMessage = async () => {
  if (!input.value.trim() || isLoading.value) return
  const content = input.value
  input.value = ''
  await store.sendMessageToApi(content)
}

const stopGeneration = () => {
  store.stopGeneration()
}

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    sendMessage()
  }
}
</script>

<style scoped>
.input-container {
  padding: 0 24px 24px;
  background-color: var(--bg-primary);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.input-box {
  width: 100%;
  max-width: 800px;
  background-color: var(--bg-secondary);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: 14px 14px 10px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow-md);
  transition: all 0.3s ease;
}

.input-box:focus-within {
  box-shadow: var(--shadow-float);
  border-color: var(--accent-primary);
}

.chat-input {
  width: 100%;
}

.chat-input :deep(.el-textarea__inner) {
  box-shadow: none !important;
  background-color: transparent;
  padding: 4px 6px;
  font-size: 16px;
  line-height: 1.5;
  color: var(--text-primary);
  border: none;
  resize: none;
}

.chat-input :deep(.el-textarea__inner::placeholder) {
  color: var(--text-tertiary);
  font-weight: 500;
}

.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 2px;
  flex-wrap: wrap;
}

.actions {
  display: flex;
  align-items: center;
  margin-left: auto;
}

.send-btn {
  background-color: var(--accent-cta);
  border: none;
  width: 40px;
  height: 40px;
  font-size: 18px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.send-btn:not(:disabled):hover {
  background-color: #EA580C;
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
}

.send-btn:disabled {
  background-color: var(--bg-tertiary);
  color: var(--text-tertiary);
}

.stop-btn {
  width: 40px;
  height: 40px;
  font-size: 18px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.stop-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.3);
}

.disclaimer {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
