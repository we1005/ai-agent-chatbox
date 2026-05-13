<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { soloGraph } from './data/solo-graph'
</script>

<template><WikiPage :page="soloGraph" /></template>
