<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import {
  NSpace,
  NButton,
  NList,
  NListItem,
  NText,
  NCard,
  NSpin,
  NEmpty,
  NGrid,
  NGridItem,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import { formatDistanceToNow } from 'date-fns'
import { useActivityStore } from '@/stores/activity'
import { listEntries } from '@/api/timeline'
import { listSessions } from '@/api/activity'
import { useDayAnalytics } from '@/composables/useDayAnalytics'
import { SESSION_PALETTE, CATEGORY_COLORS } from '@/constants/palette'
import type { TimelineEntry } from '@/types/timeline'
import type { ActivitySession } from '@/types/activity'

const router = useRouter()
const activityStore = useActivityStore()
const todayEntries = ref<TimelineEntry[]>([])
const todaySessions = ref<ActivitySession[]>([])
const loading = ref(true)
const showAllEntries = ref(false)
const showAllSessions = ref(false)

const {
  totalActiveMinutes,
  sessionCount,
  topApp,
  appBreakdown,
  categoryBreakdown,
  formatMinutes,
} = useDayAnalytics(todaySessions, todayEntries)

const isActive = computed(() => {
  if (!activityStore.status?.last_event_at) return false
  return Date.now() - new Date(activityStore.status.last_event_at).getTime() < 5 * 60 * 1000
})

const lastEventText = computed(() => {
  if (!activityStore.status?.last_event_at) return 'No events yet'
  return formatDistanceToNow(new Date(activityStore.status.last_event_at), { addSuffix: true })
})

const maxAppMinutes = computed(() => appBreakdown.value[0]?.minutes ?? 1)
const maxCategoryMinutes = computed(() => categoryBreakdown.value[0]?.minutes ?? 1)

const displayedEntries = computed(() =>
  showAllEntries.value ? todayEntries.value : todayEntries.value.slice(0, 5)
)
const displayedSessions = computed(() =>
  showAllSessions.value ? todaySessions.value : todaySessions.value.slice(0, 5)
)

function appColor(app: string): string {
  const apps = [...new Set(todaySessions.value.map((s) => s.app_name))]
  const idx = apps.indexOf(app)
  return SESSION_PALETTE[(idx >= 0 ? idx : 0) % SESSION_PALETTE.length].main
}

function categoryColor(index: number): string {
  return CATEGORY_COLORS[index % CATEGORY_COLORS.length]
}

onMounted(async () => {
  const today = format(new Date(), 'yyyy-MM-dd')
  await Promise.all([
    activityStore.fetchStatus(),
    listEntries({ date: today }).then((res) => {
      todayEntries.value = res.entries
    }),
    listSessions({ date: today, limit: 200 }).then((res) => {
      todaySessions.value = res.sessions
    }),
  ])
  loading.value = false
})
</script>

<template>
  <NSpin :show="loading">
    <NSpace vertical :size="20">
      <div class="status-banner">
        <div class="status-dot" :class="isActive ? 'active' : 'inactive'" />
        <NText style="font-weight: 500">Daemon {{ isActive ? 'active' : 'inactive' }}</NText>
        <NText depth="3" style="font-size: 13px">{{ lastEventText }}</NText>
        <NText depth="3" style="font-size: 13px">{{ activityStore.status?.events_today ?? 0 }} events today</NText>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px">
        <div class="stat-card" style="border-left-color: var(--to-brand)">
          <div class="stat-label">Active Time</div>
          <div class="stat-value">{{ formatMinutes(totalActiveMinutes) }}</div>
        </div>
        <div class="stat-card" style="border-left-color: #6366F1">
          <div class="stat-label">Sessions</div>
          <div class="stat-value">{{ sessionCount }}</div>
        </div>
        <div class="stat-card" style="border-left-color: #14B8A6">
          <div class="stat-label">Top App</div>
          <div class="stat-value" style="font-size: 20px">{{ topApp ?? '—' }}</div>
        </div>
      </div>

      <NGrid :cols="2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard title="Time by App" size="small">
            <NEmpty v-if="!appBreakdown.length" description="No activity" />
            <div v-else>
              <div v-for="item in appBreakdown" :key="item.app" class="bar-row">
                <NText class="bar-label" :title="item.app">{{ item.app }}</NText>
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{ width: (item.minutes / maxAppMinutes * 100) + '%', background: appColor(item.app) }"
                  />
                </div>
                <NText depth="3" class="bar-value">{{ formatMinutes(item.minutes) }}</NText>
              </div>
            </div>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard title="Time by Category" size="small">
            <template #header-extra>
              <NButton text type="primary" size="small" @click="router.push({ name: 'timeline' })">
                View Calendar
              </NButton>
            </template>
            <NEmpty v-if="!categoryBreakdown.length" description="No timeline entries" />
            <div v-else>
              <div v-for="(item, index) in categoryBreakdown" :key="item.category" class="bar-row">
                <NText class="bar-label" :title="item.category">{{ item.category }}</NText>
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{ width: (item.minutes / maxCategoryMinutes * 100) + '%', background: categoryColor(index) }"
                  />
                </div>
                <NText depth="3" class="bar-value">{{ formatMinutes(item.minutes) }}</NText>
              </div>
            </div>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid :cols="2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard title="Today's Timeline" size="small">
            <NEmpty v-if="!todayEntries.length" description="No timeline entries today" />
            <template v-else>
              <NList :show-divider="false" style="margin: -4px 0">
                <NListItem v-for="entry in displayedEntries" :key="entry.id" class="list-item-compact">
                  <NSpace align="center" :size="8">
                    <div v-if="entry.color" class="color-dot" :style="{ backgroundColor: entry.color }" />
                    <NText strong class="item-label">{{ entry.label }}</NText>
                    <NText depth="3" class="item-meta">
                      {{ format(new Date(entry.start_time), 'HH:mm') }}–{{ format(new Date(entry.end_time), 'HH:mm') }}
                    </NText>
                    <NText v-if="entry.category" depth="3" class="item-meta">· {{ entry.category }}</NText>
                  </NSpace>
                </NListItem>
              </NList>
              <NButton
                v-if="todayEntries.length > 5"
                text
                type="primary"
                size="small"
                style="margin-top: 4px"
                @click="showAllEntries = !showAllEntries"
              >
                {{ showAllEntries ? 'Show less' : `Show all (${todayEntries.length})` }}
              </NButton>
            </template>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard title="Today's Activity" size="small">
            <NEmpty v-if="!todaySessions.length" description="No activity recorded today" />
            <template v-else>
              <NList :show-divider="false" style="margin: -4px 0">
                <NListItem v-for="session in displayedSessions" :key="session.id" class="list-item-compact">
                  <NSpace align="center" :size="8">
                    <div class="color-dot" :style="{ backgroundColor: appColor(session.app_name) }" />
                    <NText strong class="item-label">{{ session.app_name }}</NText>
                    <NText depth="3" class="item-meta">
                      {{ format(new Date(session.start_time), 'HH:mm') }}–{{ format(new Date(session.end_time), 'HH:mm') }}
                    </NText>
                  </NSpace>
                </NListItem>
              </NList>
              <NButton
                v-if="todaySessions.length > 5"
                text
                type="primary"
                size="small"
                style="margin-top: 4px"
                @click="showAllSessions = !showAllSessions"
              >
                {{ showAllSessions ? 'Show less' : `Show all (${todaySessions.length})` }}
              </NButton>
            </template>
          </NCard>
        </NGridItem>
      </NGrid>
    </NSpace>
  </NSpin>
</template>
