<template>
  <span class="gtag num" :class="`grade-${grade}`">{{ grade || '—' }}</span>
</template>

<script setup>
defineProps({ grade: { type: String, default: '' } })
</script>

<style scoped>
.gtag {
  display: inline-block; padding: 1px 8px; font-size: 12px; line-height: 18px;
  border: 1px solid transparent; border-radius: 4px; font-weight: 600;
}
</style>
