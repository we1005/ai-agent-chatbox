<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { ragStrategies } from './data/rag-strategies'
</script>

<template><WikiPage :page="ragStrategies" /></template>
