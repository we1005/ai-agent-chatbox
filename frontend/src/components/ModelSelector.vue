<template>
  <el-select v-model="currentModel" placeholder="Select Model" style="width: 200px">
    <el-option label="Kimi (Moonshot 8k)" value="moonshot-v1-8k" />
    <el-option label="DeepSeek Chat" value="deepseek-chat" />
  </el-select>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '../store/chat'

const store = useChatStore()

const currentModel = computed({
  get: () => store.currentModel,
  set: (val) => store.setModel(val)
})
</script>
