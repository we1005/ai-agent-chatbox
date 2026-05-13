<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { memoryLifecycle } from './data/memory-lifecycle'
</script>

<template><WikiPage :page="memoryLifecycle" /></template>
