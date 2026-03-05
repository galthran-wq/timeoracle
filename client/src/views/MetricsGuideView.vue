<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import ProductivityCurve from '@/components/ProductivityCurve.vue'
import CategoryBreakdownChart from '@/components/CategoryBreakdownChart.vue'
import type { ProductivityPoint } from '@/types/productivityCurve'
import type { TimelineEntry } from '@/types/timeline'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const BASE_DATE = '2026-01-15'
const T = (h: number, m: number) => `${BASE_DATE}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`

function makePoint(h: number, m: number, focus: number, depth: string, category: string, color: string, isWork: boolean): ProductivityPoint {
  const weights: Record<string, number> = { deep: 1.0, shallow: 0.6, reactive: 0.3 }
  return {
    interval_start: T(h, m),
    focus_score: focus,
    depth,
    category,
    color,
    is_work: isWork,
    productivity_score: Math.round(focus * (weights[depth] ?? 1) * 100),
  }
}

const demoPoints: ProductivityPoint[] = [
  makePoint(9, 0, 0.75, 'deep', 'Work', '#3B82F6', true),
  makePoint(9, 10, 0.85, 'deep', 'Work', '#3B82F6', true),
  makePoint(9, 20, 0.92, 'deep', 'Work', '#3B82F6', true),
  makePoint(9, 30, 0.95, 'deep', 'Work', '#3B82F6', true),
  makePoint(9, 40, 0.88, 'deep', 'Work', '#3B82F6', true),
  makePoint(9, 50, 0.90, 'deep', 'Work', '#3B82F6', true),
  makePoint(10, 0, 0.70, 'shallow', 'Admin', '#6B7280', true),
  makePoint(10, 10, 0.65, 'shallow', 'Admin', '#6B7280', true),
  makePoint(10, 20, 0.50, 'reactive', 'Communication', '#8B5CF6', true),
  makePoint(10, 30, 0.45, 'reactive', 'Communication', '#8B5CF6', true),
  makePoint(10, 40, 0.60, 'deep', 'Work', '#3B82F6', true),
  makePoint(10, 50, 0.72, 'deep', 'Work', '#3B82F6', true),
  makePoint(11, 0, 0.80, 'deep', 'Work', '#3B82F6', true),
  makePoint(11, 10, 0.88, 'deep', 'Work', '#3B82F6', true),
  makePoint(11, 20, 0.91, 'deep', 'Work', '#3B82F6', true),
  makePoint(11, 30, 0.40, 'shallow', 'Research', '#F59E0B', true),
  makePoint(11, 40, 0.35, 'reactive', 'Entertainment', '#EF4444', false),
  makePoint(11, 50, 0.25, 'reactive', 'Entertainment', '#EF4444', false),
]

const demoEntries: TimelineEntry[] = [
  { id: '1', user_id: '', date: BASE_DATE, start_time: T(9, 0), end_time: T(10, 0), label: 'Coding in VS Code', description: 'Implementing new feature with deep focus', category: 'Work', color: '#3B82F6', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
  { id: '2', user_id: '', date: BASE_DATE, start_time: T(10, 0), end_time: T(10, 20), label: 'Email & admin tasks', description: 'Triaging inbox and scheduling', category: 'Admin', color: '#6B7280', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
  { id: '3', user_id: '', date: BASE_DATE, start_time: T(10, 20), end_time: T(10, 40), label: 'Team chat', description: 'Responding to Slack messages', category: 'Communication', color: '#8B5CF6', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
  { id: '4', user_id: '', date: BASE_DATE, start_time: T(10, 40), end_time: T(11, 20), label: 'Back to coding', description: 'Resumed feature work, ramping back up', category: 'Work', color: '#3B82F6', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
  { id: '5', user_id: '', date: BASE_DATE, start_time: T(11, 20), end_time: T(11, 30), label: 'Quick research', description: 'Looking up API docs', category: 'Research', color: '#F59E0B', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
  { id: '6', user_id: '', date: BASE_DATE, start_time: T(11, 30), end_time: T(12, 0), label: 'YouTube & Reddit', description: 'Distracted browsing', category: 'Entertainment', color: '#EF4444', source: 'demo', source_summary: null, confidence: null, edited_by_user: false, created_at: '', updated_at: '' },
]

const demoCategories = [
  { category: 'Work', minutes: 180, avgScore: 72, color: '#3B82F6' },
  { category: 'Communication', minutes: 60, avgScore: 45, color: '#8B5CF6' },
  { category: 'Research', minutes: 40, avgScore: 68, color: '#F59E0B' },
  { category: 'Entertainment', minutes: 30, avgScore: 22, color: '#EF4444' },
]

interface Section { id: string; label: string }
interface Page { key: string; title: string; sections: Section[] }

const pages = computed<Page[]>(() => [
  {
    key: 'idea',
    title: t('guide.pages.idea'),
    sections: [
      { id: 'idea-problem', label: t('guide.sections.ideaProblem') },
      { id: 'idea-solution', label: t('guide.sections.ideaSolution') },
      { id: 'idea-philosophy', label: t('guide.sections.ideaPhilosophy') },
    ],
  },
  {
    key: 'curve',
    title: t('guide.pages.curve'),
    sections: [
      { id: 'curve-overview', label: t('guide.sections.curveOverview') },
      { id: 'curve-demo', label: t('guide.sections.curveSeeIt') },
    ],
  },
  {
    key: 'scoring',
    title: t('guide.pages.scoring'),
    sections: [
      { id: 'scoring-focus', label: t('guide.sections.scoringFocus') },
      { id: 'scoring-depth', label: t('guide.sections.scoringDepth') },
      { id: 'scoring-formula', label: t('guide.sections.scoringFormula') },
    ],
  },
  {
    key: 'categories',
    title: t('guide.pages.categories'),
    sections: [
      { id: 'cat-question', label: t('guide.sections.catQuestion') },
      { id: 'cat-distinction', label: t('guide.sections.catDistinction') },
      { id: 'cat-yours', label: t('guide.sections.catYours') },
      { id: 'cat-rules', label: t('guide.sections.catRules') },
      { id: 'cat-flag', label: t('guide.sections.catFlag') },
      { id: 'cat-chart', label: t('guide.sections.catChart') },
    ],
  },
  {
    key: 'dashboard',
    title: t('guide.pages.dashboard'),
    sections: [
      { id: 'dash-numbers', label: t('guide.sections.dashNumbers') },
      { id: 'dash-time', label: t('guide.sections.dashTime') },
      { id: 'dash-aggregation', label: t('guide.sections.dashAggregation') },
      { id: 'dash-heatmap', label: t('guide.sections.dashHeatmap') },
      { id: 'dash-narrative', label: t('guide.sections.dashNarrative') },
    ],
  },
  {
    key: 'timeline',
    title: t('guide.pages.timeline'),
    sections: [
      { id: 'tl-raw', label: t('guide.sections.tlRaw') },
      { id: 'tl-ai', label: t('guide.sections.tlAi') },
      { id: 'tl-loop', label: t('guide.sections.tlLoop') },
    ],
  },
  {
    key: 'agent',
    title: t('guide.pages.agent'),
    sections: [
      { id: 'agent-what', label: t('guide.sections.agentWhat') },
      { id: 'agent-talk', label: t('guide.sections.agentTalk') },
      { id: 'agent-memory', label: t('guide.sections.agentMemory') },
    ],
  },
  {
    key: 'integrations',
    title: t('guide.pages.integrations'),
    sections: [
      { id: 'int-why', label: t('guide.sections.intWhy') },
      { id: 'int-current', label: t('guide.sections.intCurrent') },
      { id: 'int-planned', label: t('guide.sections.intPlanned') },
    ],
  },
  {
    key: 'security',
    title: t('guide.pages.security'),
    sections: [
      { id: 'sec-concern', label: t('guide.sections.secConcern') },
      { id: 'sec-collect', label: t('guide.sections.secCollect') },
      { id: 'sec-llm', label: t('guide.sections.secLlm') },
      { id: 'sec-open', label: t('guide.sections.secOpen') },
    ],
  },
  {
    key: 'conclusion',
    title: t('guide.pages.conclusion'),
    sections: [
      { id: 'end-summary', label: t('guide.sections.endSummary') },
      { id: 'end-references', label: t('guide.sections.endReferences') },
    ],
  },
])

const activePage = ref(pages.value[0].key)
const activeSection = ref('')
const contentRef = ref<HTMLElement | null>(null)

const currentPage = computed(() => pages.value.find((p) => p.key === activePage.value) ?? pages.value[0])

function selectPage(key: string) {
  activePage.value = key
  activeSection.value = ''
  router.replace({ name: 'guide', params: { page: key } })
  nextTick(() => {
    if (contentRef.value) contentRef.value.scrollTop = 0
  })
}

function scrollToSection(id: string) {
  const el = document.getElementById(id)
  if (el && contentRef.value) {
    const offset = el.offsetTop - contentRef.value.offsetTop
    contentRef.value.scrollTo({ top: offset - 16, behavior: 'smooth' })
  }
}

function onContentScroll() {
  if (!contentRef.value) return
  const scrollTop = contentRef.value.scrollTop + 60
  const secs = currentPage.value.sections
  for (let i = secs.length - 1; i >= 0; i--) {
    const el = document.getElementById(secs[i].id)
    if (el) {
      const offset = el.offsetTop - contentRef.value.offsetTop
      if (offset <= scrollTop) {
        activeSection.value = secs[i].id
        return
      }
    }
  }
  activeSection.value = secs[0]?.id ?? ''
}

function onContentClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.tagName === 'A' && target.dataset.page) {
    e.preventDefault()
    selectPage(target.dataset.page)
  }
}

onMounted(() => {
  const pageParam = route.params.page as string
  if (pageParam && pages.value.some((p) => p.key === pageParam)) {
    activePage.value = pageParam
  }
})

watch(activePage, () => {
  nextTick(() => {
    activeSection.value = currentPage.value.sections[0]?.id ?? ''
  })
}, { immediate: true })
</script>

<template>
  <div class="docs-layout">
    <nav class="docs-pages">
      <div class="docs-pages-title">{{ t('guide.docTitle') }}</div>
      <a
        v-for="p in pages"
        :key="p.key"
        class="docs-page-link"
        :class="{ active: activePage === p.key }"
        @click.prevent="selectPage(p.key)"
      >{{ p.title }}</a>
    </nav>

    <div class="docs-mobile-nav">
      <select :value="activePage" @change="selectPage(($event.target as HTMLSelectElement).value)">
        <option v-for="p in pages" :key="p.key" :value="p.key">{{ p.title }}</option>
      </select>
    </div>

    <div ref="contentRef" class="docs-content" @scroll="onContentScroll" @click="onContentClick">

      <template v-if="activePage === 'idea'">
        <div v-html="t('guide.idea.content')"></div>
      </template>

      <template v-if="activePage === 'curve'">
        <div v-html="t('guide.curve.content')"></div>
        <div class="demo-chart">
          <ProductivityCurve key="demo-curve" :points="demoPoints" :entries="demoEntries" />
        </div>
      </template>

      <template v-if="activePage === 'scoring'">
        <div v-html="t('guide.scoring.content')"></div>
      </template>

      <template v-if="activePage === 'categories'">
        <div v-html="t('guide.categories.content')"></div>
        <div class="demo-categories">
          <CategoryBreakdownChart :items="demoCategories" />
        </div>
      </template>

      <template v-if="activePage === 'dashboard'">
        <div v-html="t('guide.dashboard.content')"></div>
      </template>

      <template v-if="activePage === 'timeline'">
        <div v-html="t('guide.timeline.content')"></div>
      </template>

      <template v-if="activePage === 'agent'">
        <div v-html="t('guide.agent.content')"></div>
      </template>

      <template v-if="activePage === 'integrations'">
        <div v-html="t('guide.integrations.content')"></div>
      </template>

      <template v-if="activePage === 'security'">
        <div v-html="t('guide.security.content')"></div>
      </template>

      <template v-if="activePage === 'conclusion'">
        <div v-html="t('guide.conclusion.content')"></div>
      </template>

    </div>

    <nav class="docs-toc">
      <div class="docs-toc-title">{{ t('guide.onThisPage') }}</div>
      <a
        v-for="s in currentPage.sections"
        :key="s.id"
        class="docs-toc-link"
        :class="{ active: activeSection === s.id }"
        @click.prevent="scrollToSection(s.id)"
      >{{ s.label }}</a>
    </nav>
  </div>
</template>

<style>
.docs-layout {
  display: flex;
  gap: 0;
  height: 100%;
}

.docs-pages {
  width: 190px;
  flex-shrink: 0;
  padding: 8px 16px 24px 0;
  border-right: 1px solid rgba(150, 150, 150, 0.1);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.docs-pages-title {
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.4;
  margin-bottom: 10px;
}

.docs-page-link {
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 5px;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.15s, background 0.15s;
  text-decoration: none;
  color: inherit;
}

.docs-page-link:hover {
  opacity: 0.85;
  background: rgba(150, 150, 150, 0.08);
}

.docs-page-link.active {
  opacity: 1;
  background: rgba(150, 150, 150, 0.1);
  font-weight: 600;
}

.docs-content {
  flex: 1;
  min-width: 0;
  padding: 0 40px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.7;
}

.docs-content h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 20px;
}

.docs-content h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 32px 0 10px;
  padding-top: 8px;
}

.docs-content h2:first-of-type {
  margin-top: 0;
}

.docs-content h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 20px 0 8px;
}

.docs-content p {
  margin: 0 0 12px;
}

.docs-content ul {
  margin: 0 0 12px;
  padding-left: 20px;
}

.docs-content li {
  margin-bottom: 4px;
}

.docs-toc {
  width: 160px;
  flex-shrink: 0;
  padding: 8px 0 24px 16px;
  border-left: 1px solid rgba(150, 150, 150, 0.1);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.docs-toc-title {
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.4;
  margin-bottom: 8px;
}

.docs-toc-link {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0.45;
  transition: opacity 0.15s, background 0.15s;
  text-decoration: none;
  color: inherit;
}

.docs-toc-link:hover {
  opacity: 0.8;
  background: rgba(150, 150, 150, 0.08);
}

.docs-toc-link.active {
  opacity: 1;
  background: rgba(150, 150, 150, 0.1);
  font-weight: 600;
}

.hero {
  text-align: center;
  padding: 24px 0 16px;
  margin-bottom: 8px;
}

.hero h1 {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: 8px;
  margin: 0;
}

.hero .tagline {
  font-size: 14px;
  opacity: 0.4;
  margin: 8px 0 0;
  letter-spacing: 1px;
}

.idea-section {
  margin-top: 48px !important;
}

.question-cascade {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.question-cascade p {
  font-size: 15px;
  line-height: 1.8;
  margin: 0;
}

.question-cascade p:nth-child(1) { opacity: 0.5; }
.question-cascade p:nth-child(2) { opacity: 0.6; }
.question-cascade p:nth-child(3) { opacity: 0.7; }
.question-cascade p:nth-child(4) { opacity: 0.85; }
.question-cascade p:nth-child(5) { opacity: 0.9; }
.question-cascade p:nth-child(6) { opacity: 1; }

.question-standalone {
  margin-top: 8px !important;
  font-size: 16px !important;
  font-weight: 600;
}

.accent-line {
  font-size: 19px;
  font-weight: 700;
  text-align: center;
  padding: 28px 0;
  letter-spacing: 0.3px;
  position: relative;
}

.accent-line::before {
  content: '';
  display: block;
  width: 40px;
  height: 2px;
  background: rgba(255, 255, 255, 0.25);
  margin: 0 auto 20px;
}

.score-hero {
  text-align: center;
  padding: 32px 0;
}

.score-hero .score-number {
  display: block;
  font-size: 56px;
  font-weight: 800;
  color: #22C55E;
  line-height: 1;
  text-shadow: 0 0 40px rgba(34, 197, 94, 0.3), 0 0 80px rgba(34, 197, 94, 0.1);
}

.score-hero .score-caption {
  display: block;
  font-size: 13px;
  opacity: 0.4;
  margin-top: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.manifesto-line {
  font-size: 16px;
  font-weight: 600;
  border-left: 3px solid #EF4444;
  padding-left: 16px;
  margin: 20px 0;
}

.manifesto-line.closing {
  border-left-color: rgba(255, 255, 255, 0.2);
  opacity: 0.7;
  margin-top: 24px;
}

.page-link {
  color: var(--to-brand, #3B82F6);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.page-link:hover {
  opacity: 0.7;
}

.note {
  font-size: 13px;
  opacity: 0.6;
  font-style: italic;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin: 12px 0;
}

.info-table th {
  text-align: left;
  font-weight: 600;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(150, 150, 150, 0.15);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.5;
}

.info-table td {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(150, 150, 150, 0.06);
}

.score-high { color: #22C55E; font-weight: 700; }
.score-mid { color: #EAB308; font-weight: 700; }
.score-low { color: #EF4444; font-weight: 700; }

.depth-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 12px 0;
}

.depth-card {
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.depth-card p { margin: 6px 0 4px; }
.depth-card.deep { background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3B82F6; }
.depth-card.shallow { background: rgba(234, 179, 8, 0.1); border-left: 3px solid #EAB308; }
.depth-card.reactive { background: rgba(239, 68, 68, 0.1); border-left: 3px solid #EF4444; }
.depth-label { font-weight: 700; font-size: 14px; }
.depth-weight { font-size: 12px; opacity: 0.5; font-weight: 600; }

.formula {
  font-family: monospace;
  font-size: 16px;
  font-weight: 600;
  padding: 12px 16px;
  background: rgba(150, 150, 150, 0.06);
  border-radius: 6px;
  text-align: center;
  margin-bottom: 12px;
}

.demo-chart { margin: 16px 0 24px; }

.demo-categories {
  max-width: 350px;
  margin: 16px auto 24px;
}

.metrics-explainer {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.metric-explain {
  text-align: center;
  padding: 12px 8px;
  border-radius: 8px;
  background: rgba(150, 150, 150, 0.04);
}

.metric-ex-value { font-size: 22px; font-weight: 700; color: var(--to-brand); }
.metric-ex-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.5; margin: 4px 0; font-weight: 600; }
.metric-ex-desc { font-size: 12px; line-height: 1.4; opacity: 0.6; }

.event-log {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 14px 16px;
  margin: 12px 0 16px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.9;
  overflow-x: auto;
}

.event-line {
  display: flex;
  gap: 12px;
  white-space: nowrap;
}

.event-line.dim {
  opacity: 0.35;
}

.ev-time {
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
  width: 62px;
}

.ev-app {
  color: #22C55E;
  flex-shrink: 0;
  width: 70px;
}

.ev-detail {
  color: rgba(255, 255, 255, 0.55);
}

.timeline-demo {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 12px 0 16px;
}

.tl-entry {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 8px 14px;
  border-left: 3px solid;
  background: rgba(150, 150, 150, 0.04);
  border-radius: 0 6px 6px 0;
}

.tl-time {
  font-size: 12px;
  font-family: monospace;
  opacity: 0.4;
  flex-shrink: 0;
}

.tl-label {
  font-size: 13px;
  font-weight: 500;
}

.chat-examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 16px 0;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 85%;
}

.chat-bubble.user {
  background: rgba(59, 130, 246, 0.12);
  align-self: flex-end;
  font-style: italic;
}

.chat-bubble.agent {
  background: rgba(150, 150, 150, 0.08);
  align-self: flex-start;
  opacity: 0.7;
  font-size: 12px;
}

.integration-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 16px 0;
}

.integration-card {
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(150, 150, 150, 0.04);
  border: 1px solid rgba(150, 150, 150, 0.08);
}

.integration-card.planned {
  opacity: 0.6;
}

.integration-card p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
}

.int-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.int-name {
  font-weight: 700;
  font-size: 14px;
}

.int-badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 700;
}

.int-badge.live {
  background: rgba(34, 197, 94, 0.15);
  color: #22C55E;
}

.int-badge.planned {
  background: rgba(150, 150, 150, 0.12);
  color: inherit;
  opacity: 0.5;
}

.github-cta {
  text-align: center;
  margin: 20px 0;
}

.github-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  background: rgba(150, 150, 150, 0.08);
  border: 1px solid rgba(150, 150, 150, 0.12);
  color: inherit;
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s;
}

.github-link:hover {
  background: rgba(150, 150, 150, 0.15);
}

.example-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}

.example-categories.custom {
  margin-top: 12px;
}

.example-cat {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(150, 150, 150, 0.06);
  font-size: 13px;
}

.cat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cat-name {
  font-weight: 600;
}

.cat-flag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.cat-flag.work {
  background: rgba(34, 197, 94, 0.12);
  color: #22C55E;
}

.cat-flag.not-work {
  background: rgba(239, 68, 68, 0.12);
  color: #EF4444;
}

.example-rules {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 16px 0;
}

.example-rule {
  font-size: 13px;
  font-style: italic;
  padding: 8px 14px;
  border-left: 2px solid rgba(150, 150, 150, 0.15);
  opacity: 0.7;
}

.references p {
  font-size: 12px;
  opacity: 0.6;
  margin-bottom: 6px;
}

.docs-mobile-nav {
  display: none;
}

@media (max-width: 900px) {
  .docs-toc { display: none; }
}

@media (max-width: 640px) {
  .docs-layout {
    flex-direction: column;
    height: auto;
  }

  .docs-pages { display: none; }

  .docs-mobile-nav {
    display: block;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(150, 150, 150, 0.1);
    flex-shrink: 0;
  }

  .docs-mobile-nav select {
    width: 100%;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: 600;
    background: rgba(150, 150, 150, 0.08);
    border: 1px solid rgba(150, 150, 150, 0.15);
    border-radius: 6px;
    color: inherit;
    appearance: auto;
  }

  .docs-content {
    padding: 0 16px 24px;
    overflow-y: visible;
  }

  .docs-content h1 { font-size: 20px; }
  .docs-content h2 { font-size: 16px; }

  .hero h1 {
    font-size: 26px;
    letter-spacing: 4px;
  }

  .hero .tagline { font-size: 12px; }

  .accent-line { font-size: 16px; padding: 20px 0; }

  .score-hero .score-number { font-size: 40px; }

  .depth-cards { grid-template-columns: 1fr; }
  .metrics-explainer { grid-template-columns: 1fr 1fr; }

  .formula { font-size: 13px; padding: 10px 12px; }

  .info-table { font-size: 12px; }
  .info-table th, .info-table td { padding: 5px 6px; }

  .event-log { font-size: 11px; padding: 10px 12px; }
  .ev-time { width: 50px; }
  .ev-app { width: 56px; }

  .example-categories { gap: 6px; }
  .example-cat { padding: 5px 8px; font-size: 12px; }

  .chat-bubble { max-width: 95%; }

  .integration-card { padding: 10px 12px; }

  .github-link { font-size: 13px; padding: 8px 14px; }
}

@media (max-width: 400px) {
  .metrics-explainer { grid-template-columns: 1fr; }
  .hero h1 { font-size: 22px; letter-spacing: 2px; }
}
</style>
