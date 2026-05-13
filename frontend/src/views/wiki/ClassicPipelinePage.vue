<script setup lang="ts">
import WikiPage from './WikiPage.vue'
import { classicPipeline } from './data/classic-pipeline'
</script>

<template><WikiPage :page="classicPipeline" /></template>
