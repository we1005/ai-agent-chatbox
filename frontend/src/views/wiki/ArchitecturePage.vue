<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { architecture } from './data/architecture'
</script>

<template><WikiPage :page="architecture" /></template>
