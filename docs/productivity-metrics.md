# Productivity Metrics: Research & Design

This document explains the productivity metrics used in digitalgulag, the research behind them, and how they're computed.

## Why Binary Productive/Non-Productive Fails

Traditional time trackers (RescueTime, Toggl) assign categories as "productive" or "distracting" and measure productivity as time-in-productive-apps. This is fundamentally flawed for knowledge work:

**The alt-tab problem**: A developer in VS Code for 45 minutes who alt-tabs to Discord every 3 minutes scores the same as someone in deep flow for 45 minutes straight. Research shows these produce dramatically different output quality.

**Context-switching costs**: Switching between tasks doesn't just cost the time of the switch — it creates "attention residue" where performance degrades for up to 23 minutes after returning to the original task. Brief interruptions can consume up to 40% of productive time through this residue effect [1][6].

**Non-linear effort-output relationship**: Four focused hours produce dramatically better output than eight interrupted hours, yet the interrupted day looks more "productive" by time-in-app metrics [2].

**Knowledge work is invisible**: Significant productive work (thinking, planning, learning) doesn't leave traces in app usage. Measuring only visible tool usage misses the cognitive work that must precede execution [3].

## Three-Layer Metrics Architecture

### Layer 1: Productivity Curve (AI-Assessed, 10-Minute Resolution)

The AI agent assesses focus and depth at **10-minute intervals** rather than per timeline entry. This produces a granular **productivity curve** stored in the `productivity_points` table.

Each point has:
- `interval_start` — aligned to 10-minute boundaries (e.g. 09:00, 09:10, 09:20)
- `focus_score` (0.0–1.0)
- `depth` (deep | shallow | reactive)
- `productivity_score` — composite score 0–100
- `category` and `color` — inherited from the covering timeline entry
- `is_work` — whether the category is flagged as work
- `timeline_entry_id` — FK to the covering timeline entry

**Why 10-minute resolution?** Per-entry assessment masks intra-entry variation — a 2-hour coding session might have 40 minutes of deep focus, 30 minutes of shallow browsing, and 50 minutes of reactive chat. 10-minute granularity captures these shifts while remaining coarse enough for the AI to assess reliably from activity data.

#### focus_score (0.0 – 1.0)

Measures how focused the user was during a 10-minute interval. The AI agent looks at the underlying activity sessions (app switches, window changes) to assess this.

| Score | Meaning | Example |
|-------|---------|---------|
| 0.9–1.0 | Pure sustained focus, near-zero switching | 10min in VS Code, zero distractions |
| 0.7–0.9 | Mostly focused, occasional relevant switches | Coding with a quick doc lookup |
| 0.5–0.7 | Moderate focus, noticeable fragmentation | Coding but checking chat mid-interval |
| 0.3–0.5 | Significantly fragmented | 30-40% of time on unrelated apps |
| 0.1–0.3 | Highly scattered, no clear sustained activity | Rapidly alternating 4-5 unrelated apps |
| 0.0–0.1 | Essentially no focus | Constant rapid switching |

**Research basis**: Context-switch frequency is the strongest predictor of degraded work quality, regardless of whether switches are to related or unrelated tasks [6]. The 0.7 threshold for "focused" corresponds to research showing meaningful deep work requires ≥75% of time on the primary task [2].

**Important nuance**: Switching between related tools in the same task (IDE → terminal → browser docs → IDE) is NOT unfocused — this is normal deep work workflow and scores 0.8+.

#### depth (deep | shallow | reactive)

Categorizes the cognitive nature of the work, based on Cal Newport's Deep Work framework [4]:

| Depth | Definition | Examples | Key Signal |
|-------|-----------|----------|------------|
| **deep** | Sustained complex work requiring expertise, produces complex output | Writing code, design work, data analysis, debugging, technical learning | Would suffer significantly if interrupted; requires holding complex state in working memory |
| **shallow** | Routine tasks that don't push cognitive limits | Email triage, file organization, admin, casual browsing | Interruptible without significant cost |
| **reactive** | Primarily responding to external stimuli | Chat sessions (Telegram/Discord/Slack), notification responses, support requests | Activity driven by external inputs, not user's own agenda |

#### productivity_score (0–100)

Composite score combining focus and depth into a single number per interval.

**Formula**: `focus_score × depth_weight × 100`

**Depth weights**:
| Depth | Weight | Rationale |
|-------|--------|-----------|
| deep | 1.0 | Full credit — this is the most valuable work |
| shallow | 0.6 | Necessary but lower cognitive value |
| reactive | 0.3 | Lowest weight — driven by external inputs, not user agenda |

**Examples**:
- Deep work, fully focused (1.0 × 1.0 × 100) = **100**
- Deep work, moderately focused (0.7 × 1.0 × 100) = **70**
- Shallow work, fully focused (1.0 × 0.6 × 100) = **60**
- Reactive, high engagement (1.0 × 0.3 × 100) = **30**

**Why multiply rather than average?** Focus and depth are multiplicative in reality — highly focused shallow work (email triage) is still limited by the task's ceiling, and unfocused deep work (distracted coding) doesn't produce deep output. The product captures this naturally.

### Layer 2: Work Flag (User-Configured)

Each category has a `work` boolean flag configurable in user settings. Categories like "Software Development", "Research", "Communication" default to `work: true`, while "Entertainment", "Personal", "Health" default to `work: false`.

The work flag determines:
- Which intervals count toward **work_minutes** in daily summaries
- Which intervals are included in the **productivity_score** daily average (only work intervals)
- Visual emphasis in the productivity curve (work segments have stronger fill opacity)

Users can override defaults per category in Settings.

### Layer 3: Daily Aggregates (Auto-Computed)

All daily metrics are deterministic computation from the productivity points and timeline entries — no AI judgment needed.

#### Productivity Score (productivity_score)

Average `productivity_score` across all **work** intervals. This is the headline metric shown on the dashboard.

**Formula**: Σ(point.productivity_score for work points) / count(work points)

#### Work Minutes (work_minutes)

Total minutes in intervals flagged as work. Count of work points × 10.

#### Deep Work Time (deep_work_minutes)

Sum of 10-minute intervals with depth="deep". This is the single most important time metric.

**Research basis**: Newport's analysis shows knowledge workers who protect 4+ hours of daily deep work produce transformatively better output, yet most get less than 2-3 hours [4]. The average productive focus session in 2025 was ~24 minutes, with only 39% of tracked work time in genuine concentration [2].

**What it tells the user**: "You did 3h 15m of deep work today" — immediately understandable, directly actionable.

#### Average Focus Score (avg_focus_score)

Simple average of per-point focus_score values. Answers: "When I was working, was I actually focused?"

**Formula**: Σ(point.focus_score) / count(points with focus_score not null)

#### Fragmentation Index (0–10)

Composite metric measuring how scattered attention was across the day.

**Computed from**:
- Context switches per hour (higher = more fragmented)
- Number of distinct depth categories across points (higher diversity = more fragmented)
- Average point interval relative to total time (shorter effective intervals = more fragmented)

**Scale**:
- 0–2: Very focused day, minimal switching
- 3–4: Normal focused work with some interruptions
- 5–6: Moderate fragmentation, attention was divided
- 7–8: Highly fragmented, constant switching
- 9–10: Extremely scattered, almost no sustained activity

**Research basis**: Mark et al. found that fragmented work produces higher stress, frustration, and perceived workload even when tasks are completed faster [6]. Chronic fragmentation reduces working memory capacity and sustained attention ability [8].

#### Switches Per Hour (switches_per_hour)

Context switches (changes in depth between consecutive points within 30 minutes) normalized by total active hours. Research suggests anything above ~2.4 switches/hour (one switch per 25 minutes) is associated with diminished productivity [1][2].

#### Focus Sessions (focus_sessions_25min, focus_sessions_90min)

Count of consecutive point blocks where focus_score ≥ 0.7 and combined duration meets the threshold.

- **25-minute threshold**: Research minimum for cognitively demanding work [2][6]. Corresponds to a Pomodoro cycle. Below this, the brain hasn't fully engaged with complex material.
- **90-minute threshold**: Optimal deep work block per cognitive science [2]. Corresponds to an ultradian rhythm cycle. Achieving even one 90-min session per day is associated with significantly higher output quality.

**5-minute gap tolerance**: Gaps ≤5 minutes between focused points don't break a session (quick bathroom break, getting coffee).

#### Longest Focus Streak (longest_focus_minutes)

Longest continuous block of focused work, using focus_score ≥ 0.7 across consecutive productivity points as the criterion (not category type). A "Work" interval with focus_score=0.3 does NOT count as focus time.

#### Depth Breakdown (shallow_work_minutes, reactive_minutes)

Completes the picture of where time went beyond deep work. Computed by summing 10-minute intervals per depth category.

## ADHD and Neurodivergent Considerations

Standard metrics were developed for and tested on neurotypical populations. Neurodivergent individuals (~15-20% of population) have fundamentally different but equally valid work patterns [7][9].

### Hyperfocus

People with ADHD experience hyperfocus — intense, absorbed concentration lasting hours — more frequently than neurotypical peers [9]. A 3-hour deep work block with focus_score=0.95 may represent hyperfocus. This is a superpower, not an anomaly.

Key characteristics:
- Interest-dependent: cannot be forced on non-preferred tasks regardless of importance
- Often followed by necessary recovery periods (15-30 min of low-demand activity)
- Produces output of higher quality and innovation [7]
- Companies leveraging neurodivergent strengths report up to 40% productivity gains [7]

### How Our Metrics Accommodate This

- **No daily hour targets**: We report what happened, not whether you hit an arbitrary "4 hours of deep work" goal
- **Recovery periods aren't penalized**: Low focus_score intervals following intense deep work blocks are natural recovery, not failure
- **Interest-based patterns are visible**: The depth breakdown shows where engagement was genuine vs. forced
- **Fragmentation is descriptive, not judgmental**: A highly fragmented afternoon after a 3-hour morning hyperfocus session is a known ADHD pattern, not a deficiency
- **The productivity curve shows the shape of your day**: Rather than reducing a day to a single number, the 10-minute resolution curve reveals patterns — morning ramp-up, post-lunch dip, evening second wind — that are especially relevant for neurodivergent individuals whose energy follows non-standard rhythms

## References

[1] Todoist. "The Real Cost of Context Switching." Based on research showing 23-minute refocus time and 40% productive time loss from switching.
https://www.todoist.com/inspiration/context-switching

[2] SpeakWise. "Deep Work Statistics." 2025 data showing 24-minute average focus sessions, 39% concentration rate, 3.5-hour threshold for productive day self-reports.
https://speakwiseapp.com/blog/deep-work-statistics

[3] Scalable. "How to Measure and Improve Employee Productivity." On knowledge work's invisible cognitive components and preparation time.
https://www.scalable.com/blog/how-to-measure-and-improve-employee-productivity

[4] Cal Newport. "Deep Work: Rules for Focused Success in a Distracted World" (2016). Deep vs. shallow work framework, 4-hour deep work target.
https://calnewport.com/deep-work-rules-for-focused-success-in-a-distracted-world/

[5] Moveworks. "The Real Cost of Context Switching in the Enterprise." 50%+ of employees report tool fatigue from switching negatively impacts productivity.
https://www.moveworks.com/us/en/resources/blog/the-real-cost-of-context-switching-in-the-enterprise

[6] Mark, G., Gudith, D., Klocke, U. (2008). "The Cost of Interrupted Work: More Speed and Stress." CHI 2008, UCI. Context switches cost similar disruption regardless of relatedness. Interrupted work is completed faster but with significantly higher stress, frustration, and workload.
https://www.ics.uci.edu/~gmark/chi08-mark.pdf

[7] Leantime. "Neurodivergent Strengths in Work." Interest-based nervous systems, 40% faster crisis resolution, motivation-sized task chunks.
https://leantime.io/neurodivergent-strengths-in-work/

[8] Ophir, E., Nass, C., Wagner, A.D. (2009/2018). "Cognitive control in media multitaskers." Stanford. Heavy multitaskers show reduced working memory and sustained attention capacity.
https://news.stanford.edu/stories/2018/10/decade-data-reveals-heavy-multitaskers-reduced-memory-psychologist-says

[9] Ashinoff, B.K., Abu-Akel, A. (2021). "Hyperfocus: the forgotten frontier of attention." PMC7851038. Hyperfocus frequency in ADHD exceeds neurotypical controls across all settings.
https://pmc.ncbi.nlm.nih.gov/articles/PMC7851038/

[10] Csikszentmihalyi, M. (1990). "Flow: The Psychology of Optimal Experience." Flow occurs when challenge and skill are balanced, with clear goals and immediate feedback.
https://pmc.ncbi.nlm.nih.gov/articles/PMC7033418/

[11] Kaplan, S. (1995). "The restorative benefits of nature: Toward an integrative framework." Directed attention as a depletable resource restored through nature exposure and low-stimulation activities.
https://positivepsychology.com/attention-restoration-theory/

[12] LeRoy, S. (2009). "Why is it so hard to do my work?" Attention residue — switching costs persist beyond the switch itself, degrading performance on the subsequent task.
Referenced in [1].
