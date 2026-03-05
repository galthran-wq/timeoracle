<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NText, NCollapse, NCollapseItem } from 'naive-ui'
import ProductivityCurve from '@/components/ProductivityCurve.vue'
import CategoryBreakdownChart from '@/components/CategoryBreakdownChart.vue'
import type { ProductivityPoint } from '@/types/productivityCurve'
import type { TimelineEntry } from '@/types/timeline'

const route = useRoute()
const router = useRouter()

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

const pages: Page[] = [
  {
    key: 'idea',
    title: 'The Idea',
    sections: [
      { id: 'idea-problem', label: 'The Problem' },
      { id: 'idea-solution', label: 'The Solution' },
      { id: 'idea-philosophy', label: 'The Philosophy' },
    ],
  },
  {
    key: 'curve',
    title: 'Productivity Curve',
    sections: [
      { id: 'curve-overview', label: 'Overview' },
      { id: 'curve-demo', label: 'Interactive Demo' },
    ],
  },
  {
    key: 'scoring',
    title: 'Scoring',
    sections: [
      { id: 'scoring-focus', label: 'Focus' },
      { id: 'scoring-depth', label: 'Depth' },
      { id: 'scoring-formula', label: 'The Formula' },
    ],
  },
  {
    key: 'categories',
    title: 'Categories',
    sections: [
      { id: 'cat-overview', label: 'Overview' },
      { id: 'cat-work-flag', label: 'Work Flag' },
      { id: 'cat-chart', label: 'Categories Chart' },
    ],
  },
  {
    key: 'aggregation',
    title: 'Aggregation',
    sections: [
      { id: 'agg-day', label: 'Day View' },
      { id: 'agg-week-month', label: 'Week & Month' },
      { id: 'agg-rules', label: 'Aggregation Rules' },
    ],
  },
  {
    key: 'dashboard',
    title: 'Dashboard Metrics',
    sections: [
      { id: 'dash-metrics', label: 'Metrics' },
      { id: 'dash-heatmap', label: 'Heatmap' },
      { id: 'dash-narrative', label: 'Narrative' },
    ],
  },
  {
    key: 'neurodivergent',
    title: 'Neurodivergent',
    sections: [
      { id: 'nd-hyperfocus', label: 'Hyperfocus' },
      { id: 'nd-accommodation', label: 'Accommodation' },
    ],
  },
  {
    key: 'background',
    title: 'Background',
    sections: [
      { id: 'bg-why', label: 'Why Not Binary?' },
      { id: 'bg-references', label: 'References' },
    ],
  },
]

const activePage = ref(pages[0].key)
const activeSection = ref('')
const contentRef = ref<HTMLElement | null>(null)

const currentPage = computed(() => pages.find((p) => p.key === activePage.value) ?? pages[0])

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

onMounted(() => {
  const pageParam = route.params.page as string
  if (pageParam && pages.some((p) => p.key === pageParam)) {
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
      <div class="docs-pages-title">Documentation</div>
      <a
        v-for="p in pages"
        :key="p.key"
        class="docs-page-link"
        :class="{ active: activePage === p.key }"
        @click.prevent="selectPage(p.key)"
      >{{ p.title }}</a>
    </nav>

    <div ref="contentRef" class="docs-content" @scroll="onContentScroll">

      <template v-if="activePage === 'idea'">
        <h1>DIGITAL GULAG</h1>

        <h2 id="idea-problem">The Problem</h2>
        <p>
          Have you ever spent an entire day at your computer and had no idea where the time went?
        </p>
        <p>
          Have you noticed you're suddenly out of time — somehow floating through hours without
          anything to show for it? Have you found yourself unable to answer a simple question:
          <strong>what did I actually do today?</strong> What did I do last week? Last month?
        </p>
        <p>
          Have you had days where you were completely off? Unproductive in a way you can feel
          but can't explain? Have you caught yourself <em>trying</em> to find reasons — searching
          for correlations, patterns, anything that would explain why some days work and others don't?
        </p>
        <p>
          Have you ever wished for someone to just <strong>make</strong> you work?
        </p>
        <p>
          Have you been in that position where you know exactly what you should be doing — but
          you're not doing it? Maybe because it's hard. Maybe because you're lazy. Maybe because
          you're tired. Maybe you don't even know why.
        </p>
        <p>
          Have you found yourself distracted by things that are completely, utterly unimportant?
          Watching TikToks. Scrolling Reddit. Clicking through YouTube rabbit holes. All while
          knowing — <em>knowing</em> — you should be working.
        </p>
        <p class="accent-line">
          That is precisely what we are here to solve.
        </p>

        <h2 id="idea-solution">The Solution</h2>
        <p>
          Digital Gulag measures every aspect of your computer activity — comprehensively,
          continuously, and with zero manual input. A daemon captures what you're doing. AI
          analyzes how well you're doing it. The dashboard shows you the truth.
        </p>
        <p>
          We use state-of-the-art technology and research to assess not just <em>what</em> you
          did, but <em>how effectively</em> you did it. Two people can spend 8 hours in VS Code.
          One produced exceptional work. The other alt-tabbed to Discord every 3 minutes. Traditional
          time trackers call that the same day. We don't.
        </p>
        <p>
          Every 10 minutes, we compute a
          <a class="page-link" @click.prevent="selectPage('scoring')">productivity score</a>
          that captures both your focus quality and the cognitive depth of your work. These scores
          form a
          <a class="page-link" @click.prevent="selectPage('curve')">productivity curve</a>
          — a real-time portrait of your output. Two headline numbers sit at the top:
          <strong>Productivity</strong> (your overall output quality) and
          <strong>Performance</strong> (how well you perform during
          <a class="page-link" @click.prevent="selectPage('categories')">work-flagged</a> activity).
        </p>

        <h2 id="idea-philosophy">The Philosophy</h2>
        <p>
          Our goal is to make you a better person. And by "better" we mean one thing:
          <strong>working as hard as possible, for as long as possible.</strong>
        </p>
        <p>
          That's where the name comes from. <strong>Digital Gulag</strong> is not a cozy
          productivity companion. It's a monitoring system designed to improve your direct
          performance metric. Your goal, when it comes to us, is to become an ultimate machine.
          An absolute icon of impact.
        </p>
        <p>
          The highest productivity score of <strong class="score-max">100</strong> is achieved by
          a person who works non-stop, 16 hours a day, with zero breaks and zero attention span
          issues. Deep, focused, relentless output from the moment they wake up until they
          physically cannot continue.
        </p>
        <p class="accent-line">
          This metric is, by design, impossible to achieve.
        </p>
        <p>
          We help you get as close as you possibly can.
        </p>
        <p>
          That is the core principle of the Digital Gulag philosophy.
        </p>
      </template>

      <template v-if="activePage === 'curve'">
        <h1>Productivity Curve</h1>
        <h2 id="curve-overview">Overview</h2>
        <p>
          The productivity curve is the centerpiece of your dashboard. It plots your
          <strong>productivity score</strong> (0–100) over time as a line chart, with each point
          representing a 10-minute interval of your day.
        </p>
        <p>
          Points are colored by their category and the curve reveals the shape of your focus —
          deep work ramps, post-interruption recovery dips, and end-of-day scatter. Hover over
          any point to see the activity label, focus score, depth, and category.
        </p>
        <p>
          Every 10 minutes, AI assesses two dimensions of your activity — <strong>focus</strong>
          (how concentrated you were) and <strong>depth</strong> (how cognitively demanding the work was).
          These combine into the productivity score that forms the curve.
        </p>

        <h2 id="curve-demo">Interactive Demo</h2>
        <p>
          This demo shows 3 hours of a typical morning — deep focus ramping up, a dip into
          admin and chat, recovery back into deep work, then a scattered ending. Hover to explore.
        </p>
        <div class="demo-chart">
          <ProductivityCurve key="demo-curve" :points="demoPoints" :entries="demoEntries" />
        </div>
      </template>

      <template v-if="activePage === 'scoring'">
        <h1>Scoring</h1>
        <h2 id="scoring-focus">Focus (0–100%)</h2>
        <p>
          How concentrated you were during a 10-minute window. The AI looks at your app switches,
          window changes, and activity patterns to assess this.
        </p>
        <table class="info-table">
          <thead><tr><th>Score</th><th>Meaning</th><th>Example</th></tr></thead>
          <tbody>
            <tr><td>90–100%</td><td>Sustained focus, near-zero switching</td><td>10 min in VS Code, no distractions</td></tr>
            <tr><td>70–90%</td><td>Mostly focused, occasional relevant switches</td><td>Coding with a quick doc lookup</td></tr>
            <tr><td>50–70%</td><td>Moderate focus, noticeable fragmentation</td><td>Coding but checking chat mid-interval</td></tr>
            <tr><td>30–50%</td><td>Significantly fragmented</td><td>30-40% of time on unrelated apps</td></tr>
            <tr><td>0–30%</td><td>Highly scattered</td><td>Rapidly alternating between 4-5 apps</td></tr>
          </tbody>
        </table>
        <p class="note">
          Switching between related tools in the same task (IDE → terminal → docs → IDE) is normal
          workflow and scores 80%+. Only unrelated switches degrade the score.
        </p>

        <h2 id="scoring-depth">Depth</h2>
        <p>The cognitive nature of what you're doing, independent of how focused you are.</p>
        <div class="depth-cards">
          <div class="depth-card deep">
            <div class="depth-label">Deep</div>
            <div class="depth-weight">Weight: 1.0×</div>
            <p>Complex work requiring expertise. Writing code, design, data analysis, debugging.</p>
            <NText depth="3" style="font-size: 12px">Would suffer significantly if interrupted.</NText>
          </div>
          <div class="depth-card shallow">
            <div class="depth-label">Shallow</div>
            <div class="depth-weight">Weight: 0.6×</div>
            <p>Routine tasks that don't push cognitive limits. Email triage, file organization, admin.</p>
            <NText depth="3" style="font-size: 12px">Interruptible without significant cost.</NText>
          </div>
          <div class="depth-card reactive">
            <div class="depth-label">Reactive</div>
            <div class="depth-weight">Weight: 0.3×</div>
            <p>Responding to external stimuli. Chat, notifications, support requests.</p>
            <NText depth="3" style="font-size: 12px">Driven by external inputs, not your agenda.</NText>
          </div>
        </div>

        <h2 id="scoring-formula">The Formula</h2>
        <p class="formula">Productivity = Focus × Depth Weight × 100</p>
        <p>
          Focus and depth are multiplicative because they are in reality — highly focused shallow work
          (email triage) is still limited by the task's ceiling, and unfocused deep work (distracted coding)
          doesn't produce deep output. The product captures this naturally.
        </p>
        <table class="info-table">
          <thead><tr><th>Scenario</th><th>Focus</th><th>Depth</th><th>Score</th></tr></thead>
          <tbody>
            <tr><td>Deep work, fully focused</td><td>1.0</td><td>deep (1.0×)</td><td class="score-high">100</td></tr>
            <tr><td>Deep work, moderately focused</td><td>0.7</td><td>deep (1.0×)</td><td class="score-high">70</td></tr>
            <tr><td>Shallow work, fully focused</td><td>1.0</td><td>shallow (0.6×)</td><td class="score-mid">60</td></tr>
            <tr><td>Reactive, high engagement</td><td>1.0</td><td>reactive (0.3×)</td><td class="score-low">30</td></tr>
          </tbody>
        </table>
      </template>

      <template v-if="activePage === 'categories'">
        <h1>Categories</h1>
        <h2 id="cat-overview">Overview</h2>
        <p>
          Your activities are organized into <strong>categories</strong> — user-defined labels like Work,
          Research, Communication, Entertainment. Each category has a color and a work flag
          that you configure in Settings.
        </p>

        <h2 id="cat-work-flag">Work Flag</h2>
        <p>The work flag on each category creates two complementary headline scores:</p>
        <ul>
          <li><strong>Productivity</strong> — average score across <em>all</em> activity. Your overall output quality.</li>
          <li><strong>Performance</strong> — average score across <em>work-only</em> activity. How well you perform when working.</li>
        </ul>
        <p>
          Categories like Work, Research, and Communication default to work. Entertainment, Personal, and
          Health default to non-work. You can override any of these in Settings.
        </p>

        <h2 id="cat-chart">Categories Chart</h2>
        <p>
          The categories chart shows each category as a slice — the radius reflects your average
          productivity score in that category. A large radius means high performance; a small one
          means room for improvement. The legend shows time spent and score.
        </p>
        <div class="demo-categories">
          <CategoryBreakdownChart :items="demoCategories" />
        </div>
      </template>

      <template v-if="activePage === 'aggregation'">
        <h1>Aggregation</h1>
        <p>
          The dashboard supports three period views: <strong>day</strong>, <strong>week</strong>,
          and <strong>month</strong>. How scores are aggregated changes with the period.
        </p>

        <h2 id="agg-day">Day View</h2>
        <p>
          Every 10-minute interval is plotted individually on the curve.
          The headline <strong>Productivity</strong> score is the simple average of all interval scores.
          <strong>Performance</strong> is the average of only work-flagged interval scores.
          Time metrics (Active, Work Time, Deep Work) are summed directly.
        </p>

        <h2 id="agg-week-month">Week &amp; Month Views</h2>
        <p>
          Individual 10-minute points are aggregated into larger <strong>time buckets</strong>. You can
          choose the granularity: 1 hour, 3 hours, 6 hours (default for week), or 1 day (default for month).
          Each bucket shows the average productivity score of all points within it.
        </p>
        <p>
          Headline scores for a week or month are computed by averaging across each day's score —
          not by averaging all individual points. This prevents a day with 12 hours of activity from
          dominating over a day with 4 hours. Each day carries equal weight regardless of length.
        </p>

        <h2 id="agg-rules">Aggregation Rules</h2>
        <table class="info-table">
          <thead><tr><th>Metric type</th><th>Aggregation</th><th>Examples</th></tr></thead>
          <tbody>
            <tr><td>Time metrics</td><td><strong>Sum</strong> across days</td><td>Active, Work Time, Deep Work</td></tr>
            <tr><td>Quality metrics</td><td><strong>Average</strong> across days</td><td>Focus, Productivity, Performance</td></tr>
            <tr><td>Count metrics</td><td><strong>Sum</strong> across days</td><td>Switches</td></tr>
            <tr><td>Peak metrics</td><td><strong>Maximum</strong> across days</td><td>Best Streak</td></tr>
          </tbody>
        </table>
      </template>

      <template v-if="activePage === 'dashboard'">
        <h1>Dashboard Metrics</h1>
        <h2 id="dash-metrics">Metrics</h2>
        <div class="metrics-explainer">
          <div class="metric-explain">
            <div class="metric-ex-value">5h 20m</div>
            <div class="metric-ex-label">Active</div>
            <div class="metric-ex-desc">Total time with detected computer activity.</div>
          </div>
          <div class="metric-explain">
            <div class="metric-ex-value">3h 45m</div>
            <div class="metric-ex-label">Work Time</div>
            <div class="metric-ex-desc">Time spent on categories flagged as work.</div>
          </div>
          <div class="metric-explain">
            <div class="metric-ex-value">2h 10m</div>
            <div class="metric-ex-label">Deep Work</div>
            <div class="metric-ex-desc">Time in deep, cognitively demanding focus — the most valuable type of work.</div>
          </div>
          <div class="metric-explain">
            <div class="metric-ex-value">72%</div>
            <div class="metric-ex-label">Focus</div>
            <div class="metric-ex-desc">Average concentration quality across all activity.</div>
          </div>
          <div class="metric-explain">
            <div class="metric-ex-value">48m</div>
            <div class="metric-ex-label">Best Streak</div>
            <div class="metric-ex-desc">Longest unbroken stretch of focused work (focus ≥ 70%).</div>
          </div>
          <div class="metric-explain">
            <div class="metric-ex-value">8</div>
            <div class="metric-ex-label">Switches</div>
            <div class="metric-ex-desc">Depth transitions. Fewer means more sustained, uninterrupted work.</div>
          </div>
        </div>
        <p style="margin-top: 16px">
          Each metric shows a <strong>delta</strong> compared to the previous period — green for
          improvement, red for decline. Context switches are inverted: fewer is better.
        </p>

        <h2 id="dash-heatmap">Heatmap</h2>
        <p>
          In week and month views, a color grid shows when you're most and least productive.
          Week view splits each day into four 6-hour blocks (00–06, 06–12, 12–18, 18–24).
          Month view shows a calendar grid. Green = high productivity, red = low, gray = no data.
        </p>

        <h2 id="dash-narrative">Narrative</h2>
        <p>
          An AI-generated summary that reacts to your current state during the day and provides a
          reflective summary at end of day. Updated every hour alongside the timeline.
        </p>
      </template>

      <template v-if="activePage === 'neurodivergent'">
        <h1>Neurodivergent Considerations</h1>
        <p>
          Standard productivity metrics were developed for neurotypical populations. Neurodivergent
          individuals (~15-20% of population) have fundamentally different but equally valid work patterns.
        </p>

        <h2 id="nd-hyperfocus">Hyperfocus</h2>
        <p>
          People with ADHD experience hyperfocus — intense, absorbed concentration lasting hours — more
          frequently than neurotypical peers. A 3-hour deep work block with near-perfect focus may represent
          hyperfocus. This is a superpower, not an anomaly. It's interest-dependent (can't be forced),
          often followed by necessary recovery periods, and produces output of exceptional quality.
        </p>

        <h2 id="nd-accommodation">How Our Metrics Accommodate This</h2>
        <p>
          <strong>No daily targets.</strong> We report what happened, not whether you hit an arbitrary goal.
        </p>
        <p>
          <strong>Recovery isn't penalized.</strong> Low-focus intervals following intense deep work are natural
          recovery, not failure.
        </p>
        <p>
          <strong>The curve shows your actual rhythm</strong> — morning ramp-up, post-lunch dip, evening
          second wind — patterns especially relevant for neurodivergent energy rhythms.
        </p>
      </template>

      <template v-if="activePage === 'background'">
        <h1>Background</h1>
        <h2 id="bg-why">Why Not Just Track Time in Apps?</h2>
        <p>
          <strong>The alt-tab problem.</strong>
          A developer in VS Code for 45 minutes who alt-tabs to Discord every 3 minutes scores the same as
          someone in deep flow for 45 minutes straight. Traditional trackers can't tell the difference —
          but the output quality is dramatically different.
        </p>
        <p>
          <strong>Context-switching costs.</strong>
          Switching between tasks creates "attention residue" — performance degrades for up to 23 minutes
          after returning to the original task. Brief interruptions can consume up to 40% of productive
          time through this residue effect.
        </p>
        <p>
          <strong>Non-linear effort vs. output.</strong>
          Four focused hours produce dramatically better output than eight interrupted hours, yet the
          interrupted day looks more "productive" by time-in-app metrics.
        </p>

        <h2 id="bg-references">References</h2>
        <NCollapse>
          <NCollapseItem title="Academic & industry sources">
            <div class="references">
              <p>[1] Todoist. "The Real Cost of Context Switching." 23-minute refocus time, 40% productive time loss.</p>
              <p>[2] SpeakWise. "Deep Work Statistics." 2025 data: 24-min avg focus sessions, 39% concentration rate.</p>
              <p>[3] Scalable. "How to Measure and Improve Employee Productivity." Knowledge work's invisible cognitive components.</p>
              <p>[4] Cal Newport. "Deep Work: Rules for Focused Success in a Distracted World" (2016). Deep vs. shallow framework.</p>
              <p>[5] Mark, Gudith, Klocke (2008). "The Cost of Interrupted Work: More Speed and Stress." CHI 2008, UCI.</p>
              <p>[6] Ophir, Nass, Wagner (2009/2018). "Cognitive control in media multitaskers." Stanford.</p>
              <p>[7] Leantime. "Neurodivergent Strengths in Work." Interest-based nervous systems, 40% faster crisis resolution.</p>
              <p>[8] Ashinoff, Abu-Akel (2021). "Hyperfocus: the forgotten frontier of attention." PMC7851038.</p>
              <p>[9] Csikszentmihalyi (1990). "Flow: The Psychology of Optimal Experience."</p>
            </div>
          </NCollapseItem>
        </NCollapse>
      </template>

    </div>

    <nav class="docs-toc">
      <div class="docs-toc-title">On this page</div>
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

<style scoped>
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

.accent-line {
  font-size: 16px;
  font-weight: 700;
  padding: 16px 0;
  letter-spacing: 0.3px;
}

.score-max {
  font-size: 18px;
  color: #22C55E;
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

.references p {
  font-size: 12px;
  opacity: 0.6;
  margin-bottom: 6px;
}

@media (max-width: 900px) {
  .docs-toc { display: none; }
}

@media (max-width: 640px) {
  .docs-pages { display: none; }
  .depth-cards { grid-template-columns: 1fr; }
  .metrics-explainer { grid-template-columns: repeat(2, 1fr); }
}
</style>
