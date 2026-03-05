<script setup lang="ts">
import { h, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NSpace,
  NDatePicker,
  NSelect,
  NInput,
  NDataTable,
  NPagination,
  NTag,
  NSpin,
  NCard,
} from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import { format, startOfDay, endOfDay } from 'date-fns'
import { useActivityStore } from '@/stores/activity'
import type { ActivityEvent, ActivityEventType } from '@/types/activity'

const { t } = useI18n()
const activityStore = useActivityStore()

const PAGE_SIZE = 50

const dateRange = ref<[number, number]>([startOfDay(new Date()).getTime(), endOfDay(new Date()).getTime()])
const eventType = ref<ActivityEventType | null>(null)
const appName = ref('')
const page = ref(1)

const typeOptions = [
  { label: () => t('activity.allTypes'), value: '' },
  { label: () => t('activity.activeWindow'), value: 'active_window' },
  { label: () => t('activity.idleStart'), value: 'idle_start' },
  { label: () => t('activity.idleEnd'), value: 'idle_end' },
]

const tagTypes: Record<string, 'success' | 'warning' | 'info'> = {
  active_window: 'success',
  idle_start: 'warning',
  idle_end: 'info',
}

const columns: DataTableColumn<ActivityEvent>[] = [
  {
    title: () => t('activity.colTime'),
    key: 'timestamp',
    width: 140,
    render: (row) => format(new Date(row.timestamp), 'HH:mm:ss'),
  },
  {
    title: () => t('activity.colType'),
    key: 'event_type',
    width: 140,
    render: (row) =>
      h(NTag, { type: tagTypes[row.event_type] ?? 'default', size: 'small' }, () =>
        row.event_type.replace('_', ' '),
      ),
  },
  { title: () => t('activity.colApp'), key: 'app_name', width: 160, ellipsis: { tooltip: true } },
  { title: () => t('activity.colWindowTitle'), key: 'window_title', ellipsis: { tooltip: true } },
  { title: () => t('activity.colUrl'), key: 'url', width: 200, ellipsis: { tooltip: true } },
]

async function fetchData() {
  const [startMs, endMs] = dateRange.value
  await activityStore.fetchEvents({
    start: new Date(startMs).toISOString(),
    end: new Date(endMs).toISOString(),
    limit: PAGE_SIZE,
    offset: (page.value - 1) * PAGE_SIZE,
    event_type: eventType.value || undefined,
    app_name: appName.value || undefined,
  })
}

watch([dateRange, eventType, appName], () => {
  page.value = 1
  fetchData()
})

watch(page, fetchData)

onMounted(fetchData)
</script>

<template>
  <NSpace vertical :size="16">
    <div style="font-size: 15px; font-weight: 600">{{ t('activity.title') }}</div>
    <NCard size="small">
      <NSpace vertical :size="16">
        <div class="filter-toolbar">
          <NSpace :size="12" align="center">
            <NDatePicker
              v-model:value="dateRange"
              type="daterange"
              clearable
              style="width: 300px"
            />
            <NSelect
              :value="eventType ?? ''"
              :options="typeOptions"
              style="width: 160px"
              @update:value="(v: string) => (eventType = (v || null) as ActivityEventType | null)"
            />
            <NInput
              v-model:value="appName"
              :placeholder="t('activity.filterByApp')"
              clearable
              style="width: 200px"
            />
          </NSpace>
        </div>

        <NSpin :show="activityStore.loading">
          <NDataTable
            :columns="columns"
            :data="activityStore.events"
            :bordered="false"
            :row-key="(row: ActivityEvent) => row.id"
            size="small"
          />
        </NSpin>

        <NSpace justify="end">
          <NPagination
            v-model:page="page"
            :page-count="Math.max(1, Math.ceil(activityStore.totalCount / PAGE_SIZE))"
            :page-slot="7"
          />
        </NSpace>
      </NSpace>
    </NCard>
  </NSpace>
</template>
