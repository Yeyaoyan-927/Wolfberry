<template>
  <el-tooltip :disabled="flag !== '灰'" content="AI 置信不足或未评估，不参与等级判定，人工审核">
    <span class="dtag num" :class="`diff-${flag}`">{{ label }}</span>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  flag: { type: String, default: '灰' },
  gap: { type: Number, default: null },
})

const label = computed(() => {
  if (props.flag === '灰') return '灰 · AI不参与'
  if (props.flag === '绿') return '一致'
  if (props.flag === '黄') return '高报1级'
  if (props.flag === '红') return `高报${props.gap ?? 2}级`
  if (props.flag === '蓝') return '低报'
  return props.flag
})
</script>

<style scoped>
.dtag {
  display: inline-block; padding: 1px 8px; font-size: 12px; line-height: 18px;
  border: 1px solid transparent; border-radius: 4px; font-weight: 600; white-space: nowrap;
}
</style>
