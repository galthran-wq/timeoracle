<script setup lang="ts">
import { computed } from 'vue'
import { DEFAULT_ENTRY_COLOR } from '@/constants/palette'

const props = defineProps<{
  calendarEvent: any
}>()

const eventColor = computed(() => props.calendarEvent._color || DEFAULT_ENTRY_COLOR)
const title = computed(() => props.calendarEvent._label || props.calendarEvent.title || '')
const category = computed(() => props.calendarEvent._category || '')
const description = computed(() => props.calendarEvent.description || '')
</script>

<template>
  <div class="tge-card" :style="{ borderLeftColor: eventColor }">
    <div class="tge-text">
      <div class="tge-title">{{ title }}</div>
      <div v-if="category" class="tge-category">{{ category }}</div>
      <div v-if="description" class="tge-description">{{ description }}</div>
    </div>
  </div>
</template>
