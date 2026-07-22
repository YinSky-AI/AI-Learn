# Prompts 4 Optimization Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert all 21 findings in `docs/reviews/project-optimization-summary.html` into a navigable, safety-constrained Vibe Coding prompt package under `docs/prompts_4/`.

**Architecture:** Three shared documents define usage, global guardrails, and dependency order. Each HTML finding maps one-to-one to a priority-specific Markdown prompt that contains current evidence, scope, staged execution, coupling checks, tailored acceptance criteria, and a fixed evidence report. `docs/INDEX.md` exposes the package without changing the status of `prompts_3`.

**Tech Stack:** Markdown, PowerShell validation, Git.

## Global Constraints

- Modify only Markdown files under `docs/`.
- Do not modify backend, frontend, Docker, database, CI, environment, or generated files.
- Do not delete or move any existing file.
- Preserve the two-layer question generation constraint: one generation Agent and one review Agent.
- Every task prompt must require investigation before implementation and must treat HTML line references as candidates to re-verify.
- UI tasks must require internal-browser interaction, console inspection, responsive checks, and screenshot evidence.
- Database tasks must require backup, isolated migration/restore verification, rollback evidence, and explicit target checks.
- User-facing errors must be plain text and must not expose stack traces, SQL, secrets, or internal objects.

---

### Task 1: Create package navigation and shared rules

**Files:**
- Create: `docs/prompts_4/README.md`
- Create: `docs/prompts_4/00-global-execution-rules.md`
- Create: `docs/prompts_4/01-implementation-order.md`

**Interfaces:**
- Consumes: the scope and structure defined in `docs/prompts_4/02-prompt-package-design.md`.
- Produces: shared rules referenced by every P0, P1, and P2 task prompt.

- [ ] **Step 1: Write README navigation**

Create a README that clearly says the package is an implementation backlog, not proof that the features already exist. Include links to the global rules, implementation order, design, all three priority folders, and a 21-item progress checklist.

- [ ] **Step 2: Write exact global execution rules**

Cover project-instruction discovery, clean-scope checks, investigation-first behavior, TDD, deletion approval, cross-layer coupling, error normalization, secret handling, database safety, Docker rebuild rules, internal-browser screenshot acceptance, logs, regression tests, Git scope review, and a fixed final evidence report.

- [ ] **Step 3: Write dependency-driven implementation order**

Document this recommended sequence: delivery baseline → backup/recovery → schema migration → question-answer isolation and admin authentication → administrative protection and account principal → learning dimensions and answer transaction → readiness, budget, and diagnostics → generation jobs and review scheduling → frontend session/conversation/contract/availability → measured performance, backoffice, and governance. Include a table of tasks that must not edit shared models or configuration concurrently.

- [ ] **Step 4: Validate shared documents**

Run:

```powershell
rg -n "提示词已编写|并不代表功能已经实施|内部浏览器|截图|数据库|回滚|出题 Agent|审题 Agent" docs/prompts_4/*.md
git diff --check
```

Expected: all safety concepts are present and `git diff --check` prints no errors.

- [ ] **Step 5: Commit shared documents**

```powershell
git add -- docs/prompts_4/README.md docs/prompts_4/00-global-execution-rules.md docs/prompts_4/01-implementation-order.md
git commit -m "docs: add prompts 4 execution framework"
```

### Task 2: Create eight P0 prompts

**Files:**
- Create: `docs/prompts_4/P0/01-question-access.md`
- Create: `docs/prompts_4/P0/02-access-control.md`
- Create: `docs/prompts_4/P0/03-administrative-change.md`
- Create: `docs/prompts_4/P0/04-backup-and-recovery.md`
- Create: `docs/prompts_4/P0/05-answer-submission-transaction.md`
- Create: `docs/prompts_4/P0/06-learning-dimensions-and-question-catalog.md`
- Create: `docs/prompts_4/P0/07-schema-migration.md`
- Create: `docs/prompts_4/P0/08-delivery-verification.md`

**Interfaces:**
- Consumes: `docs/prompts_4/00-global-execution-rules.md`, `docs/prompts_4/01-implementation-order.md`, and HTML findings 1–8.
- Produces: eight independently executable P0 Vibe Coding prompts.

- [ ] **Step 1: Map finding evidence one-to-one**

Each prompt must preserve its finding number, candidate files, problem, impact, recommended boundary, and benefit while explicitly requiring the executor to re-check current code.

- [ ] **Step 2: Add task-specific safety and acceptance**

Require the following distinguishing evidence: public DTO response checks for Question Access; cookie/session/CSRF/authorization tests for Access Control; recovery and audit checks for Administrative Change; real `pg_dump` plus isolated restore for Backup & Recovery; idempotency/concurrency/rollback tests for Answer Submission; canonical value and multi-database routing tests for Learning Dimensions; upgrade/downgrade and clean-database tests for Schema Migration; backend, frontend, contract, browser, PWA, Docker, and artifact checks for Delivery Verification.

- [ ] **Step 3: Validate all P0 prompts**

Run:

```powershell
$files = Get-ChildItem docs/prompts_4/P0 -Filter *.md
if ($files.Count -ne 8) { throw "Expected 8 P0 prompts, found $($files.Count)" }
foreach ($file in $files) {
  $text = Get-Content -Raw -Encoding UTF8 $file.FullName
  foreach ($heading in @('任务定位','当前证据','开始前调查','允许修改范围','禁止操作','分阶段执行','跨模块耦合检查','错误处理要求','验收标准','最终报告格式')) {
    if (-not $text.Contains($heading)) { throw "$($file.Name) missing $heading" }
  }
}
git diff --check
```

Expected: eight files, all ten sections present, no whitespace errors.

- [ ] **Step 4: Commit P0 prompts**

```powershell
git add -- docs/prompts_4/P0
git commit -m "docs: add critical prompts 4 tasks"
```

### Task 3: Create nine P1 prompts

**Files:**
- Create: `docs/prompts_4/P1/09-account-principal.md`
- Create: `docs/prompts_4/P1/10-traffic-protection-and-ai-budget.md`
- Create: `docs/prompts_4/P1/11-runtime-readiness.md`
- Create: `docs/prompts_4/P1/12-operational-diagnostics.md`
- Create: `docs/prompts_4/P1/13-generation-job.md`
- Create: `docs/prompts_4/P1/14-practice-session.md`
- Create: `docs/prompts_4/P1/15-tutor-conversation.md`
- Create: `docs/prompts_4/P1/16-learning-contract-and-journey.md`
- Create: `docs/prompts_4/P1/17-review-scheduler.md`

**Interfaces:**
- Consumes: shared rules and HTML findings 9–17.
- Produces: nine independently executable P1 Vibe Coding prompts.

- [ ] **Step 1: Map findings and preserve current architecture constraints**

Keep Question Generation at exactly two Agents. Do not let Generation Job reintroduce a multi-Agent hierarchy. Separate JSON/SSE transport adapters from TutorConversation behavior, and separate source adapters from PracticeSession state transitions.

- [ ] **Step 2: Add tailored acceptance evidence**

Cover token revocation and disabled users; atomic rate windows and AI input/cost budgets; liveness/readiness dependency failures; correlated run IDs and redaction; job idempotency, leasing, retries, and terminal states; three practice sources and state-machine tests; buffered SSE, cancellation, persistence, and explicit unavailable state; DTO validation and loading/empty/error separation; deterministic scheduler cases and migration rollback.

- [ ] **Step 3: Validate all P1 prompts**

Run the same ten-section validation as Task 2 with `docs/prompts_4/P1` and an expected count of 9. Also run:

```powershell
rg -n "出题 Agent.*审题 Agent|两层|内部浏览器|截图" docs/prompts_4/P1
git diff --check
```

Expected: nine files; the Generation Job prompt preserves the two-Agent rule; all UI prompts require browser evidence.

- [ ] **Step 4: Commit P1 prompts**

```powershell
git add -- docs/prompts_4/P1
git commit -m "docs: add high-value prompts 4 tasks"
```

### Task 4: Create four P2 prompts

**Files:**
- Create: `docs/prompts_4/P2/18-learning-read-model.md`
- Create: `docs/prompts_4/P2/19-admin-backoffice.md`
- Create: `docs/prompts_4/P2/20-student-data-governance.md`
- Create: `docs/prompts_4/P2/21-client-availability.md`

**Interfaces:**
- Consumes: shared rules and HTML findings 18–21.
- Produces: four independently executable P2 Vibe Coding prompts.

- [ ] **Step 1: Add evidence-first constraints**

Learning Read Model must measure query count and latency before optimization. Admin Backoffice must deepen business modules rather than mechanically split files. Student Data Governance must stop for confirmed jurisdiction, age range, retention policy, and user-right requirements before coding. Client Availability must define explicit UI states and accessible interaction behavior.

- [ ] **Step 2: Add tailored acceptance evidence**

Require before/after query evidence and cache invalidation tests; route/service contract regression and admin browser flows; data inventory plus export/anonymization/deletion audit checks without legal conclusions; online/offline/update/install flows, keyboard operation, screen-reader announcements, responsive views, console logs, and screenshots.

- [ ] **Step 3: Validate all P2 prompts**

Run the ten-section validation against `docs/prompts_4/P2` with an expected count of 4, followed by `git diff --check`.

- [ ] **Step 4: Commit P2 prompts**

```powershell
git add -- docs/prompts_4/P2
git commit -m "docs: add evolutionary prompts 4 tasks"
```

### Task 5: Update project index and verify the complete package

**Files:**
- Modify: `docs/INDEX.md`
- Verify: `docs/prompts_4/**/*.md`

**Interfaces:**
- Consumes: all package documents from Tasks 1–4.
- Produces: one discoverable, complete prompt package with no code changes.

- [ ] **Step 1: Add prompts_4 to current documentation entry points**

Link `prompts_4/README.md` and describe it as the unimplemented optimization backlog derived from the HTML report. Keep `prompts_3` described as the current implemented design basis.

- [ ] **Step 2: Validate counts and one-to-one mapping**

Run:

```powershell
$p0 = @(Get-ChildItem docs/prompts_4/P0 -Filter *.md)
$p1 = @(Get-ChildItem docs/prompts_4/P1 -Filter *.md)
$p2 = @(Get-ChildItem docs/prompts_4/P2 -Filter *.md)
if ($p0.Count -ne 8 -or $p1.Count -ne 9 -or $p2.Count -ne 4) { throw "Priority count mismatch" }
$ids = @($p0 + $p1 + $p2 | ForEach-Object { [int]$_.BaseName.Substring(0,2) } | Sort-Object)
if (($ids -join ',') -ne ((1..21) -join ',')) { throw "Finding ID mismatch: $($ids -join ',')" }
```

Expected: no exception.

- [ ] **Step 3: Validate links and required content**

Resolve every relative Markdown link under `docs/prompts_4`, verify every task references the global rules, and scan for unfinished placeholder language. The command must exit non-zero when any unfinished marker is found.

- [ ] **Step 4: Audit scope**

Run:

```powershell
git diff --check
$changed = git diff --name-only HEAD~4..HEAD
$invalid = $changed | Where-Object { $_ -notmatch '^docs/.+\.md$' }
if ($invalid) { throw "Non-document changes: $($invalid -join ', ')" }
git status --short
```

Expected: no whitespace errors, no non-Markdown changes, clean status after final commit.

- [ ] **Step 5: Commit navigation**

```powershell
git add -- docs/INDEX.md
git commit -m "docs: link prompts 4 optimization backlog"
```
