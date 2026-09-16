# 🤖 Hermes Rules for Web Performance Analyser
**DO NOT READ, EDIT, OR CHANGE unless explicitly told to do so by the user.**
**Created:** 2026-07-04
**Last update:** 2026-08-26

This file is the **single source of truth** for visual design decisions.
Hermes MUST follow these rules when modifying any HTML/CSS file.

---

## 🔒 PROTECTED PALETTE — DO NOT CHANGE

These colors are **PERMANENT** and must **NOT** be changed unless the user
explicitly says "เปลี่ยนสี" or "change color of X" with specific values.

### Approved Colors (Frozen)
```css
--blue-accent:    #1a73e8;   /* Links, buttons, primary CTA */
--charcoal-text:  #333333;   /* Body text — NEVER pure black */
--amber-warning:  #d97706;   /* Warnings, medium alerts */
--green-success:  #16a34a;   /* Success, low alerts */
--red-critical:   #dc2626;   /* Critical errors */
--slate-100:      #f1f5f9;   /* Card backgrounds */
--slate-50:       #fafbfc;   /* Page background */
--slate-400:      #94a3b8;   /* Muted text, labels */
--slate-200:      #e2e8f0;   /* Borders, dividers */
```

### Forbidden Patterns
- ❌ Pure black (`#000` / `black`) — use `#333333` instead
- ❌ Pure white (`#fff` / `white`) — use `#fafbfc` or `#f1f5f9`
- ❌ Neon colors (electric blue, hot pink, lime green)
- ❌ Gradient backgrounds (heavy/modern gradients only, no rainbow)
- ❌ High-saturation colors that look gimmicky

### Rule
> "Before changing ANY color in this project,
> ASK the user for the new color value first."

---

## 📐 PROTECTED LAYOUT — DO NOT RESTRUCTURE

### Existing Layout Structure (Frozen)
Page has this exact order:
```
<header>
  <h1>title</h1>
  <p>subtitle</p>
</header>

<section class="input-row">
  <input type="text">
  <button>analyze</button>
</section>

<section class="results">
  <!-- Agent cards, Lighthouse scores, Alerts -->
</section>
```

### Existing Grid System (Frozen)
```css
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.lh-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
```

### Forbidden Layout Changes
- ❌ Move `<header>` below `<results>`
- ❌ Change `grid-template-columns` formula
- ❌ Replace `display: grid` with `flexbox` (or vice versa)
- ❌ Add new sections without permission
- ❌ Remove existing sections without permission

### Allowed Edits
- ✓ `padding` values (with same ratio)
- ✓ `font-size` (up to 10% change)
- ✓ `border-radius` (keep similar)
- ✓ Add MORE cards/items (don't remove)

---

## 🇹🇭 LANGUAGE RULES

This project uses Thai as primary language.
Hermes responses in PHP/CLI: **Thai only**
HTML page text: **English** (analyser is technical tool)

When user says "เปลี่ยนสี", understand they mean **HEX CHANGE**, not theme change.

---

## ⚠️ BEFORE-EDIT CHECKLIST (Hermes must verify)

Before modifying ANY file:
1. ☐ Have you read this entire HERMES_RULES.md?
2. ☐ Is the change about COLORS?  → STOP, ASK FIRST
3. ☐ Is the change about LAYOUT?  → STOP, ASK FIRST
4. ☐ Is the change about FUNCTIONALITY? → OK to proceed
5. ☐ Will the change be REVERSIBLE? → OK (must keep backup)

---

## 🔧 BACKUP POLICY

**MANDATORY:** Before editing ANY HTML/CSS file:
1. Create backup:
2. Confirm backup exists in `backups/` directory
3. THEN proceed with edits

**MANDATORY:** After edits:
- Show user a diff or screenshot (if browser tool available)
- Ask "ชอบไหม?" — don't assume success

---

## 📁 PROTECTED FILES — ASK BEFORE EDITING

| File | Why Protected |
|------|---------------|
| `html/index.html` | Visual identity — design system |
| `html/*.css` (if exists) | Same as HTML |
| `config/agents.yaml` | AI behavior — user-tuned |

### Allowed to Edit Without Asking
- `src/ai_client.py` (with new feature request)
- `src/storage.py` (with backup first)
- `src/alerts.py` (with backup first)
- `scripts/*.sh` (utilities)
- `db/webperf.db` (data only)
- `logs/*.log` (just create, don't modify)
- `data/csv/`, `data/json/`, `reports/` (output only)

---

## 🎯 CORRECT USER REQUEST PATTERNS

### Good — Hermes will do this:
- "ปรับปรุง AI analysis logic ใน `src/ai_client.py`"
- "Add new export format ใน reports/"
- "Fix PostgreSQL error ใน database agent"
- "Update Lighthouse threshold"
- "เปลี่ยน font-family จาก 'Segoe UI' เป็น 'Inter'"

### Needs Confirmation — Hermes will ASK first:
- "ปรับสีเว็บให้สวยขึ้น"  → ASK: สีอะไร เป็นอะไร
- "ปรับ layout"  → ASK: ส่วนไหน อย่างไร
- "ออกแบบใหม่หมด"  → ASK: theme/style/รายละเอียด
- "ทำให้ทันสมัย"  → ASK: แนวไหน (gradient? flat? minimal?)
- "Fix display issue"  → ASK: bug ที่ไหน อย่างไร

---

## 🎨 EMERGENCY RESTORE

If user says "ย้อนกลับ" or "ไม่ชอบ" or "wrong":
1. DON'T ARGUE — just restore
2. List available backups:
   ```bash
   ls -la backups/*.tar.gz
   ```
3. Show user the options
4. Restore chosen backup
5. Confirm with user before doing destructive changes

---

## 📝 VERSION HISTORY

| Date | Change | Author |
|------|--------|--------|
| 2026-07-04 | Initial ruleset | Hermes Agent |
| 2026-07-04 | Color palette lock | Hermes Agent |
| 2026-07-04 | Layout freeze | Hermes Agent |
| 2026-07-05 | Env + Dev/Test workflow + Backup naming | Hermes Agent |

---

## 🖥️ PROJECT ENVIRONMENT (FROZEN)

| Item | Value |
|------|-------|
| Project folder | `/home/ipds/Hermes-Prj/chk-a` |
| Dev machine | Ubuntu on WSL, IP `172.20.14.199` |
| Test machine | Ubuntu on Virtual Box, IP `192.168.56.122` |
| All project files | MUST live under `/home/ipds/Hermes-Prj/chk-a` |

> Any file outside this project folder is OUT OF SCOPE.

---

## 🔐 HASH VERIFICATION (MANDATORY before any "same file?" claim)

Always verify identity with a hash — never trust filename, size, or mtime alone.

```bash
# On dev
md5sum <file>
sha256sum <file>
```


**Rule:** Two files are "the same" only when their hash output is byte-identical.
If hash differs, treat as different file → do NOT proceed, re-transfer.

---

## 💡 PROACTIVE SUGGESTIONS (ALWAYS ON)

Hermes is expected to **think ahead** for the user, not just react.

When working on a task, if Hermes notices ANY related improvement opportunity
beyond what the user explicitly asked for — Hermes MUST surface it as a
suggestion, not silently apply it.

### Examples (suggestion may apply)
- "ตอนนี้แก้ X แล้ว ขอเสนอเพิ่มเรื่อง Y ที่เกี่ยวข้องด้วย เหมาะไหม?"
- "พบว่า code ส่วนนี้มี hardcoded value N ครั้ง ถ้าทำเป็น config น่าจะดีกว่า สนใจไหม?"
- "ขอเสนอ refactor เล็กๆ ตรง Z ที่ช่วยให้ maintain ง่ายขึ้น ทำไปพร้อมกันได้"
- "มี edge case ที่อาจ break — ขอเสนอเพิ่ม test case นี้ด้วย"

### Rule
> "ถ้ามีข้อเสนออื่นใด ให้บอก ให้เสนอได้"
> Surface ideas, alternative approaches, related improvements — let the user decide.
> DO NOT silently change things outside the explicit request scope.

### Logging (MANDATORY)
> When a suggestion is made, Hermes MUST log it to a **separate log file**
> at `logs/suggestions.log` (one entry per suggestion, with timestamp + reasoning).
> This creates a persistent suggestion backlog the user can review later.

```
YYYY-MM-DD HH:MM:SS | SUGGESTION | <what was suggested> | <reason/justification>
```

---

## ⏱️ AUTONOMOUS DECISION TIMEOUT (2 minutes)

When Hermes asks the user a **decision-requiring question** (e.g. clarifying
intent, choosing between options, approving a destructive change) and the user
does NOT respond within approximately **2 minutes**:

1. ✅ Hermes MUST pick the most reasonable default itself
2. ✅ State the decision explicitly: "เนื่องจากไม่มีการตอบสนองภายใน 2 นาที ฉันเลือกแนวทาง X เพราะ Y"
3. ✅ Continue with the chosen approach
4. ❌ Hermes MUST NOT block and wait forever
5. ❌ Hermes MUST NOT abandon the task

### Reasonable-default rule
- Choose the option that is **safest**, **most reversible**, and **most aligned
  with HERMES_RULES.md protected values** (palette, layout, scope).
- If multiple options are equally reasonable, prefer the **smallest / least
  invasive** change.

### Applies to
- Choice between equivalent implementation approaches
- Selecting default values for new config fields
- Naming decisions for new files/symbols
- Picking one of several test scenarios

### Does NOT apply to
- Irreversible destructive operations (still ASK even after timeout)
- Anything that would violate protected palette / layout / scope rules
- Anything the user explicitly said "ask first"

### Logging (MANDATORY)
> When Hermes makes an autonomous decision after the 2-minute timeout,
> it MUST also log the decision to `logs/decisions.log` (one entry per decision).

```
YYYY-MM-DD HH:MM:SS | AUTONOMOUS_DECISION | <decision made> | <reason/justification> | <options considered>
```

---

## ⚡ FINAL RULE
**When in doubt, ASK the user. NEVER assume.**
This matches user's stated preference: "สงสัยประเด็นใดให้ถาม ข้องใจเรื่องใดให้ถาม ห้ามตัดสินใจเอง"

---

## 🕐 TIME REFERENCE RULE
**Always use local time** for all timestamps, logs, and time references.
- Format: `YYYY-MM-DD HH:MM:SS` (local timezone)
- This applies to: logs/suggestions.log, logs/decisions.log, backup filenames, cron schedules, and all user-facing time displays

---

## 🔄 CACHE BUSTER VERSION BUMP RULE (MANDATORY)
**Every time ANY frontend asset (HTML, CSS, JS, Worker) is modified and deployed, the cache buster query parameter MUST be incremented.**

### When to Bump
- ✅ Any edit to `html/js/*.js` (including `app.js`, `benchmark.js`)
- ✅ Any edit to `html/css/*.css` (including `style.css`)
- ✅ Any edit to `html/index.html`
- ✅ Any edit to `workers/*.js` (including `benchmark-worker.js`)

### How to Bump
1. **Format:** `YYYYMMDDHHMM` (local time, 24-hour)
2. **Location:** Worker URL in `html/js/app.js` → `initWorker()` method
3. **Example:** `new Worker('/workers/benchmark-worker.js?v=202608261000')`

### Workflow
```bash
# 1. Edit files
# 2. Bump cache buster in app.js (worker URL)
# 3. Sync to deployment
rsync -av html/ /var/www/chk-a/
# 4. Verify in browser (hard refresh: Ctrl+Shift+R+F5)
```

### Rule
> "No deployment without cache buster bump — stale assets break benchmark runs."

---

## 🔍 PRE-EDIT SCAN RULE (MANDATORY)
**Before editing ANY code, the Agent MUST scan the entire project structure** to understand all related functions, dependencies, and patterns.

### Required Steps:
1. **Search for all relevant files** using `grep`, `search_files`, or `read_file`
2. **Map the call graph**: understand how functions call each other
3. **Identify all touch points**: config files, tests, utilities, shared modules
4. **Document findings** before writing any fix

### Forbidden:
- ❌ Guessing file locations or function names
- ❌ Starting edits without full context scan
- ❌ Assuming the bug is isolated to one file

---

## 🧪 TEST-FIRST DEVELOPMENT RULE (MANDATORY)
**Never fix code without a failing test first.**

### Workflow:
1. **Write a Unit Test** that reproduces the bug (test MUST fail initially)
2. **Run the test** → confirm it fails (RED)
3. **Write the fix** → run test again
4. **Test passes** (GREEN) → fix is verified
5. **Run ALL existing tests** → must pass 100%

### If no existing tests:
- Read the original working function
- Create an **Automated Test** that captures current correct behavior
- Store it in the test suite for future regression protection

---

## ♻️ EXTEND OVER MODIFY RULE
**Prefer extending (adding new) over modifying (changing existing) core system files.**

### Allowed:
- ✅ New files, new functions, new classes, new config options
- ✅ Wrapper/adapter patterns
- ✅ Feature flags for new behavior

### Forbidden unless absolutely necessary:
- ❌ Changing signatures of existing public functions
- ❌ Modifying core logic in place
- ❌ Deleting/renaming existing exports

### If modification is unavoidable:
1. Create backup first
2. Keep old behavior accessible (e.g., via config flag)
3. Add deprecation path

---

## 🔄 ZERO-REGRESSION LOOP RULE
**An edit cycle is ONLY complete when:**
1. ✅ New feature works (manual + automated verification)
2. ✅ **ALL existing tests pass 100%** (zero failures, zero new flaky tests)

### If ANY old test fails:
1. **STOP immediately**
2. **Rollback** to the last known-good commit (pre-edit state)
3. Re-analyze the approach
4. Try a different fix that doesn't break existing behavior

### No exceptions:
- "It's just one test" → ROLLBACK
- "The test was wrong anyway" → FIX THE TEST FIRST, then re-apply fix
- "We'll fix it later" → ROLLBACK NOW

---

## 📋 CHANGELOG MANDATORY UPDATE RULE
**Every file modification MUST be recorded in `CHANGELOG.md` immediately after the change.**

### Required Information for Each Entry:
- **Date and Time** — Local timezone (Asia/Bangkok +07), format: `YYYY-MM-DD HH:MM:SS`
- **File Path** — Relative to project root (e.g., `src/agents/resolver_agent.py`)
- **Change Type** — One of: `Added`, `Changed`, `Fixed`, `Removed`, `Security`
- **Description** — Brief summary of what changed and why

### Entry Format:
```markdown
- **YYYY-MM-DD HH:MM:SS** — `path/to/file.ext` — Type: Description
```

### When to Log:
- ✅ Creating a new file
- ✅ Modifying an existing file (code, config, docs, tests, scripts)
- ✅ Deleting a file
- ✅ Moving/renaming a file (log as Removed + Added)
- ✅ Any change to `HERMES_RULES.md` itself

### Where to Add:
- Under the `[Unreleased]` section at the top of `CHANGELOG.md`
- If `[Unreleased]` doesn't exist, create it

### Example:
```markdown
## [Unreleased]

### Changed
- **2026-09-07 10:30:45** — `src/agents/resolver_agent.py` — Fixed: DNS timeout handling for IPv6 addresses
- **2026-09-07 10:31:12** — `config/config.yaml` — Changed: Increased resolver timeout from 5s to 10s
```

### Rule:
> "No commit without CHANGELOG entry — every change must be traceable."

