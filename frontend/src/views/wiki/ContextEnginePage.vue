<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { contextEngine } from './data/context-engine'
</script>

<template><WikiPage :page="contextEngine" /></template>
