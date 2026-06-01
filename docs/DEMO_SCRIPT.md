# Demo Script — 美团 AI Agent v2.2

A 90-second live walkthrough designed to land four claims with the judges:

1. **真多轮对话** — say it in three sentences, watch the plan reshape.
2. **task_id 全程稳定** — same plan card, animated diff, no re-render storm.
3. **地图就地联动** — markers/lines patch in place, no flicker.
4. **剧本杀剧情自适应** — checkpoints follow the new POI's name & narrative.

Open the browser. F12 → Console (optional). Press `D` once to show the inspector overlay (bottom-right).

---

## Setup (off-camera, 30 s)

```
# Terminal 1 — backend
cd "E:\Project coding\vibe coding\meituan-agent"
$env:LLM_MODE = "mock"        # deterministic for judging; switch to "live" if asked
python -m uvicorn agent.api:app --port 8080

# Browser
http://localhost:8080
```

Pre-flight:
- Open the page; the LLM pill should read `mock`.
- Clear `localStorage` once (`localStorage.clear()` in the console) to reset prior sessions.
- Have the demo phrases pre-loaded in a sticky note — don't type them live unless you're confident.

---

## On-camera flow (7 turns, ~90 s)

### Turn 1 — initial plan (~12 s)

**Type**: `周六和朋友三个人去三里屯玩，预算 800，想要剧本杀那种沉浸式剧情`

**Toggle** the 剧本杀 switch ON before sending.

**Narration**:
> 用户说一句话，Agent 出方案：路线 + 时间窗口 + 任务列表 + 剧本杀剧情，全套。

**Watch for**:
- Stream events flash in the thinking panel
- A 3-4 stop route renders with map + sidebar + 剧本杀 checkpoints
- Inspector: `mode: mock`, `last action: plan`, `SSE events: 10+`

---

### Turn 2 — replace (the headline trick) (~10 s)

**Type**: `第二个换一家`

**Narration**:
> 不重新规划——只改第二站。其他的 task_id、时间、地图标记都不动。

**Watch for**:
- Sidebar card #2 turns yellow, swaps name (~600 ms)
- Map marker #2 vanishes, new marker drops, lines re-draw in place
- Inspector: `last action: replace`, `patch hits: R=1`, `replan count: 0`
- **Checkpoint with old POI rewrites to the new POI's name + narrative** — this is the "剧情自适应" beat

---

### Turn 3 — remove (~8 s)

**Type**: `删掉最后那个`

**Narration**:
> 删一站，剧情里对应的章节自动消失，不会留孤魂野鬼。

**Watch for**:
- Last sidebar card turns red, fades out
- Last marker vanishes from the map
- 剧本杀 checkpoint list shrinks by exactly one
- Inspector: `last action: remove`, `patch hits: R=1 D=1`

---

### Turn 4 — insert (~10 s)

**Type**: `再加一家咖啡`

**Narration**:
> 想中间塞一杯咖啡，Agent 自己算插哪儿增量最小。

**Watch for**:
- Green card slides in at the optimal position (not always last)
- Map updates marker count, route re-runs OSRM
- Inspector: `patch hits: R=1 D=1 I=1`

---

### Turn 5 — shift time (~8 s)

**Type**: `晚一点开始`

**Narration**:
> 时间整体后移半小时，越界营业就回滚并给建议——不会闷头报错。

**Watch for**:
- All time labels animate to new values
- Inspector: `last action: shift_time`, `patch hits: ... T=1`

If the shift hits a closed window, the bot returns a softer suggestion message — that's a feature, point it out.

---

### Turn 6 — declare dislike (~8 s)

**Type**: `下次别推三里屯了`

**Narration**:
> 这是偏好声明，不动当前 plan——只在 session 里记一笔。下一次重新规划就会自动避开。

**Watch for**:
- Plan stays still
- A small "已记下：不推荐三里屯" chip appears (or a bot reply)
- Inspector: `last action: declare_dislike`, `patch hits: ... X=1`

---

### Turn 7 — confirm execution (~8 s)

**Click**: 确认执行 button

**Narration**:
> 确认之后才真正调用工具——预订、抢券、生成分享文案。前面六步都是「等审批的草稿」，零副作用。

**Watch for**:
- Task list status flips to SUCCESS
- A share-text block renders at the bottom

---

## Inspector cheat sheet (off-camera explanation if asked)

The bottom-right overlay (press `D`) shows:

| Row | What it means |
|---|---|
| `sid` | Session ID (first 8 chars) — proves we're not resetting state |
| `mode` | `mock` for offline reproducibility, `live` for real LLM |
| `last action` | Most recent action_type (replace/remove/insert/shift_time/declare_dislike/plan/replan/chat) |
| `last duration` | Server round-trip in ms |
| `patch hits` | Counters for each patch operation across the session |
| `replan count` | Times we fell through to full `run()` — should stay `0` during the demo |
| `SSE events` | Stream event count from last plan call |
| `route nodes` | Current route node count |
| `task ids` | First 3 task IDs — point out they don't change across turns 2-6 |

**Why this matters for judging**: `replan count: 0` proves the patch path is doing the work — not a hidden re-plan masquerading as a diff.

---

## Recovery moves

- **Plan didn't render** → reload page, `localStorage.clear()`, retry.
- **Replace can't find a candidate** → the bot replies "找不到合适的替换"; pick a different turn ordinal or change the category in turn 1.
- **Live mode misfires** → flip env var to `mock`, restart backend. Mock is fully scripted.
- **Map froze** → press `R` (browser refresh); the state restores from `localStorage` so the conversation continues.

---

## Recording notes

- 1080p, 30 fps, scaled browser UI to 100% so map labels stay readable.
- Capture at ≤ 2 Mb/s VBR — the map tiles compress poorly otherwise.
- Two-take strategy: first take un-narrated for clean visuals, second take voice-only over the same recording. Sync in post.
- Keep the cursor stable; don't hover map markers (popups distract).

---

## Talking points if judges ask the hard questions

> **"你怎么保证不是隐式 replan？"**
> 看 inspector 里的 `replan count` 和 `patch hits` — patch 走的是 `_try_patch` 路径，根本不调 `run()`。task_id 在 7 步演示里全程不变也是证据。

> **"剧本杀和路线怎么不会脱节？"**
> `StoryEngine.remap_after_patch` 跑在 patch 完成后，根据 change_log 同步 checkpoints —— replace 重写 POI 引用 + narrative，remove 删 checkpoint，shift_time/insert/declare_dislike 不动 story。有 9 个单元测试守这个不变量。

> **"LLM 兜底稳吗？"**
> 规则覆盖 12 条 utterance（confidence=1.0），命中不了再走 LLM（confidence=0.6）。LLM 输出经过 schema validation + coercion：action_type 白名单、time_delta_min/absolute_start/target_hint 全部类型校验。44 个单元测试守这一层。
