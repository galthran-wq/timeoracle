<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { DEFAULT_ENTRY_COLOR } from '@/constants/palette'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  calendarEvent: any
}>()

const eventColor = computed(() => props.calendarEvent._color || DEFAULT_ENTRY_COLOR)
const title = computed(() => props.calendarEvent._label || props.calendarEvent.title || '')
const category = computed(() => props.calendarEvent._category || '')
const description = computed(() => props.calendarEvent.description || '')
const descriptionHtml = computed(() => {
  if (!description.value) return ''
  return DOMPurify.sanitize(marked.parse(description.value, { async: false }) as string)
})
</script>

<template>
  <div class="tge-card" :style="{ '--tge-color': eventColor } as any">
    <div class="tge-header">
      <div class="tge-title">{{ title }}</div>
      <div v-if="category" class="tge-category">{{ category }}</div>
    </div>
    <div v-if="description" class="tge-description" v-html="descriptionHtml"></div>
  </div>
</template>
