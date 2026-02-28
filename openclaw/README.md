# OpenClaw Integration

Connect TimeOracle to [OpenClaw](https://github.com/openclaw/openclaw) for automatic activity labeling. OpenClaw scans your activity sessions every hour and creates labeled timeline entries.

## Setup

### 1. Install the skill

```bash
mkdir -p ~/.openclaw/skills/timeoracle
cp skill.md ~/.openclaw/skills/timeoracle/SKILL.md
```

### 2. Set environment variables

Add to your OpenClaw environment (`~/.openclaw/.env` or shell profile):

```bash
TIMEORACLE_API_URL=https://your-timeoracle-instance.com   # no trailing slash
TIMEORACLE_TOKEN=your-jwt-token-here
```

To get a token, log in via the TimeOracle API:

```bash
# If you have email/password:
curl -s -X POST "$TIMEORACLE_API_URL/api/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "yourpassword"}' | jq -r .token
```

### 3. Add the cron job

```bash
openclaw cron add \
  --name "TimeOracle sync" \
  --cron "0 * * * *" \
  --tz "$(cat /etc/timezone 2>/dev/null || echo UTC)" \
  --session isolated \
  --message "Run the timeoracle skill. Scan activity sessions from the last 2 hours and create/update timeline entries for today."
```

### 4. Test it

Run manually to verify:

```bash
openclaw cron list                    # find the job ID
openclaw cron run <jobId>             # trigger it now
openclaw cron runs --id <jobId>       # check run history
```

## How it works

Every hour, OpenClaw:

1. Fetches your activity sessions for today (`GET /api/activity/sessions`)
2. Fetches existing timeline entries (`GET /api/timeline`)
3. Analyzes sessions and creates labeled time blocks with categories
4. Submits via bulk upsert (`POST /api/timeline/bulk`)

Entries you've manually edited are never overwritten.
