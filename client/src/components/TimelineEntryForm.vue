<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  NModal,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NTimePicker,
  NButton,
  NSpace,
  NPopconfirm,
  NColorPicker,
} from 'naive-ui'
import { set } from 'date-fns'
import { formatISO } from 'date-fns'
import type { TimelineEntry } from '@/types/timeline'

const props = defineProps<{
  show: boolean
  entry: TimelineEntry | null
  date: string
  defaultStartTime?: string
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'save', data: { label: string; start_time: string; end_time: string; date: string; category: string; color: string; description: string }): void
  (e: 'delete', id: string): void
}>()

const isEdit = computed(() => !!props.entry)

const label = ref('')
const startTime = ref<number | null>(null)
const endTime = ref<number | null>(null)
const category = ref('')
const color = ref('#3B82F6')
const description = ref('')

const presetColors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

watch(
  () => props.show,
  (show) => {
    if (!show) return
    if (props.entry) {
      label.value = props.entry.label
      startTime.value = new Date(props.entry.start_time).getTime()
      endTime.value = new Date(props.entry.end_time).getTime()
      category.value = props.entry.category ?? ''
      color.value = props.entry.color ?? '#3B82F6'
      description.value = props.entry.description ?? ''
    } else {
      label.value = ''
      category.value = ''
      color.value = '#3B82F6'
      description.value = ''
      if (props.defaultStartTime) {
        const dt = new Date(props.defaultStartTime)
        startTime.value = dt.getTime()
        endTime.value = new Date(dt.getTime() + 60 * 60 * 1000).getTime()
      } else {
        const now = new Date()
        startTime.value = now.getTime()
        endTime.value = new Date(now.getTime() + 60 * 60 * 1000).getTime()
      }
    }
  },
)

function buildISOFromTimePicker(timeMs: number): string {
  const d = new Date(timeMs)
  const dateParts = props.date.split('-').map(Number)
  const merged = set(d, { year: dateParts[0], month: dateParts[1] - 1, date: dateParts[2] })
  return formatISO(merged)
}

function handleSave() {
  if (!label.value || startTime.value === null || endTime.value === null) return
  emit('save', {
    label: label.value,
    start_time: buildISOFromTimePicker(startTime.value),
    end_time: buildISOFromTimePicker(endTime.value),
    date: props.date,
    category: category.value,
    color: color.value,
    description: description.value,
  })
}

function handleDelete() {
  if (props.entry) emit('delete', props.entry.id)
}

function close() {
  emit('update:show', false)
}
</script>

<template>
  <NModal :show="show" @update:show="close">
    <NCard :title="isEdit ? 'Edit Entry' : 'New Entry'" style="max-width: 480px" closable @close="close">
      <NForm @submit.prevent="handleSave">
        <NFormItem label="Label" required>
          <NInput v-model:value="label" placeholder="What were you doing?" />
        </NFormItem>
        <NSpace :size="12">
          <NFormItem label="Start" required>
            <NTimePicker v-model:value="startTime" format="HH:mm" style="width: 140px" />
          </NFormItem>
          <NFormItem label="End" required>
            <NTimePicker v-model:value="endTime" format="HH:mm" style="width: 140px" />
          </NFormItem>
        </NSpace>
        <NFormItem label="Category">
          <NInput v-model:value="category" placeholder="e.g. coding, meetings" />
        </NFormItem>
        <NFormItem label="Color">
          <NSpace :size="8" align="center">
            <NButton
              v-for="c in presetColors"
              :key="c"
              circle
              size="small"
              :style="{
                backgroundColor: c,
                border: c === color ? '2px solid white' : 'none',
                boxShadow: c === color ? '0 0 0 2px ' + c : 'none',
              }"
              @click="color = c"
            />
            <NColorPicker
              v-model:value="color"
              :modes="['hex']"
              size="small"
              style="width: 80px"
            />
          </NSpace>
        </NFormItem>
        <NFormItem label="Description">
          <NInput v-model:value="description" type="textarea" :rows="2" placeholder="Optional notes" />
        </NFormItem>
        <NSpace justify="space-between" style="margin-top: 8px">
          <NPopconfirm v-if="isEdit" @positive-click="handleDelete">
            <template #trigger>
              <NButton type="error" ghost>Delete</NButton>
            </template>
            Delete this entry?
          </NPopconfirm>
          <span v-else />
          <NSpace>
            <NButton @click="close">Cancel</NButton>
            <NButton type="primary" attr-type="submit" :disabled="!label">Save</NButton>
          </NSpace>
        </NSpace>
      </NForm>
    </NCard>
  </NModal>
</template>
