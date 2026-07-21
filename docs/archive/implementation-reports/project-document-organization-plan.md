# Project Documentation Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all architecture findings into one HTML report and organize formal project documentation without changing executable code, configuration, databases, Docker data, or local test artifacts.

**Architecture:** Keep the existing runtime tree intact and treat documentation as a separate, navigable information architecture. Add one documentation index, archive three tracked historical text assets with Git-aware moves, and create one consolidated HTML review from the three existing local reports.

**Tech Stack:** Markdown, HTML/CSS, Git, PowerShell, existing Docker Compose services, Codex in-app browser.

## Global Constraints

- Only `.md`, `.html`, and `.patch` files may be created, moved, or modified.
- Do not modify files under `backend/`, `frontend/src/`, `nginx/`, `sql/`, or `docker-data/`.
- Do not modify `.env`, Docker Compose, Makefile, package manifests, lockfiles, or Git ignore rules.
- Do not delete any file.
- Preserve `agent.md` at the project root because project prompt documentation references it.
- Preserve `sql/report.md` because the question-bank task brief references its current path.
- Preserve the original ignored reports under `test/`.
- Stop immediately if a target archive path already exists or if a moved file has an unknown consumer.

---

### Task 1: Add the documentation navigation page

**Files:**
- Create: `docs/INDEX.md`
- Reference: `agent.md`
- Reference: `docs/prompts_1/06_sub_agent_tasks.md`
- Reference: `docs/prompts_2/question-bank/00-task-brief.md`

**Interfaces:**
- Consumes: the existing document directories and their current authority relationships.
- Produces: one stable human navigation page for all project documentation.

- [ ] **Step 1: Verify all navigation targets exist**

Run:

```powershell
$targets = @(
  'agent.md',
  'docs/advises',
  'docs/prompts_1',
  'docs/prompts_2',
  'docs/prompts_3',
  'sql/report.md'
)
$targets | ForEach-Object { if (-not (Test-Path -LiteralPath $_)) { throw "Missing: $_" } }
```

Expected: exit code `0`, with no missing-target error.

- [ ] **Step 2: Create the navigation page**

The page must contain these sections and meanings:

```markdown
# 项目文档导航

## 当前入口
- `../agent.md`：项目提示词体系的顶层入口。
- `prompts_3/`：当前学习平台重构与功能实现设计。

## 产品与历史设计
- `advises/`：产品构想、竞品分析与改进建议。
- `prompts_1/`：初始产品、架构、数据模型、测试与验收设计。
- `prompts_2/`：历史题库方案，仅作历史参考；当前 AI 出题采用两层出题/审题设计。

## 审查与归档
- `reviews/project-optimization-summary.html`：合并后的架构、安全、交付与产品优化报告。
- `archive/implementation-reports/`：历史实施报告与本次整理设计/计划。
- `archive/patches/`：不再参与运行的历史补丁。

## 保留在原位置的资料
- `../sql/report.md`：题库生成验收报告，保留原路径以维持 prompts_2 引用。
- `../test/`：本地验收截图、日志和原始审查报告；该目录被 Git 忽略。
```

- [ ] **Step 3: Validate navigation links and changed file type**

Run:

```powershell
rg -n 'agent\.md|prompts_1|prompts_2|prompts_3|project-optimization-summary|sql/report\.md' docs/INDEX.md
git diff --name-only | ForEach-Object { if ([IO.Path]::GetExtension($_) -notin '.md','.html','.patch') { throw "Non-text change: $_" } }
```

Expected: all navigation categories appear; no non-text change error.

- [ ] **Step 4: Commit the navigation page**

```powershell
git add -- docs/INDEX.md
git commit -m "docs: add project documentation index"
```

Expected: one commit containing only `docs/INDEX.md`.

---

### Task 2: Archive tracked historical text assets

**Files:**
- Move: `.superpowers/sdd/task-2-report.md` → `docs/archive/implementation-reports/question-pipeline-report.md`
- Move: `.superpowers/sdd/task-3-report.md` → `docs/archive/implementation-reports/question-persistence-report.md`
- Move: `frontend/patches/task5-learning-integration.patch` → `docs/archive/patches/task5-learning-integration.patch`

**Interfaces:**
- Consumes: three tracked historical text assets with no runtime imports.
- Produces: a single archive location that separates history from executable source.

- [ ] **Step 1: Recheck references and target collisions**

Run:

```powershell
$moves = @{
  '.superpowers/sdd/task-2-report.md' = 'docs/archive/implementation-reports/question-pipeline-report.md'
  '.superpowers/sdd/task-3-report.md' = 'docs/archive/implementation-reports/question-persistence-report.md'
  'frontend/patches/task5-learning-integration.patch' = 'docs/archive/patches/task5-learning-integration.patch'
}
foreach ($source in $moves.Keys) {
  if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
  if (Test-Path -LiteralPath $moves[$source]) { throw "Target exists: $($moves[$source])" }
}
rg -n 'task-2-report|task-3-report|task5-learning-integration\.patch' . -g '!frontend/node_modules/**' -g '!.git/**' -g '!docker-data/**'
```

Expected: only the plan/design references these paths; no runtime consumer appears.

- [ ] **Step 2: Move the files with Git**

Run:

```powershell
New-Item -ItemType Directory -Force -Path 'docs/archive/patches' | Out-Null
git mv -- '.superpowers/sdd/task-2-report.md' 'docs/archive/implementation-reports/question-pipeline-report.md'
git mv -- '.superpowers/sdd/task-3-report.md' 'docs/archive/implementation-reports/question-persistence-report.md'
git mv -- 'frontend/patches/task5-learning-integration.patch' 'docs/archive/patches/task5-learning-integration.patch'
```

Expected: three Git moves; no file content change.

- [ ] **Step 3: Update documentation references to archived paths**

Modify only these Markdown files if their old paths occur:

- `docs/INDEX.md`
- `docs/archive/implementation-reports/project-document-organization-design.md`
- `docs/archive/implementation-reports/project-document-organization-plan.md`

Use the new archive paths shown in the Files section. Do not edit runtime files.

- [ ] **Step 4: Verify exact content preservation**

Run:

```powershell
git diff --summary
git diff --check
git diff --name-only | ForEach-Object { if ([IO.Path]::GetExtension($_) -notin '.md','.html','.patch') { throw "Non-text change: $_" } }
```

Expected: three renames plus Markdown reference updates; no whitespace or non-text errors.

- [ ] **Step 5: Commit the archive moves**

```powershell
git add -- docs/INDEX.md docs/archive/implementation-reports docs/archive/patches .superpowers/sdd frontend/patches
git commit -m "docs: archive historical implementation artifacts"
```

Expected: a documentation-only commit.

---

### Task 3: Create the consolidated optimization report

**Files:**
- Create: `docs/reviews/project-optimization-summary.html`
- Read only: `test/architecture-review-20260721-215458.html`
- Read only: `test/architecture-review-crosscut-20260721-220244.html`
- Read only: `test/architecture-review-critical-20260721-221429.html`

**Interfaces:**
- Consumes: all independent findings from the three local HTML reports.
- Produces: one responsive, standalone review document and the stable target linked by `docs/INDEX.md`.

- [ ] **Step 1: Verify all source reports exist and enumerate their findings**

Run:

```powershell
$reports = @(
  'test/architecture-review-20260721-215458.html',
  'test/architecture-review-crosscut-20260721-220244.html',
  'test/architecture-review-critical-20260721-221429.html'
)
$reports | ForEach-Object { if (-not (Test-Path -LiteralPath $_)) { throw "Missing report: $_" } }
$reports | ForEach-Object { "$_ : $(([regex]::Matches((Get-Content -LiteralPath $_ -Raw), '<article class=')).Count) candidate cards" }
```

Expected: all three files exist and each reports candidate cards.

- [ ] **Step 2: Build one standalone HTML report**

The report must contain these non-duplicated findings:

1. public question-answer exposure;
2. unsafe admin access control;
3. destructive administrative changes and missing audit trail;
4. backup and recovery;
5. answer submission transaction concurrency;
6. canonical learning dimensions and question catalog access;
7. versioned schema migration;
8. authentication session and account principal revocation;
9. traffic protection and AI resource budgets;
10. runtime readiness;
11. delivery verification and real browser E2E;
12. operational diagnostics and AI run tracing;
13. permanently pending generation jobs;
14. frontend PracticeSession;
15. frontend TutorConversation;
16. LearningContractAdapter and LearningJourney;
17. spaced repetition and wrong-book scheduling;
18. Learning Read Model performance;
19. Admin Backoffice maintainability;
20. student data governance;
21. client availability, PWA, and accessibility.

Each finding must include priority, recommendation strength, file evidence, problem, impact, recommendation, and a before/after visual. The report must clearly state that this documentation-only task does not implement the recommendations.

- [ ] **Step 3: Validate the HTML structure**

Run:

```powershell
$report = 'docs/reviews/project-optimization-summary.html'
$html = Get-Content -LiteralPath $report -Raw
if (-not $html.Contains('<!doctype html>')) { throw 'Missing doctype' }
if (-not $html.Contains('Top recommendation')) { throw 'Missing top recommendation' }
if (([regex]::Matches($html, 'data-finding=')).Count -ne 21) { throw 'Expected 21 findings' }
if (-not ($html.Contains('Before') -and $html.Contains('After'))) { throw 'Missing diagrams' }
```

Expected: exit code `0` and exactly 21 findings.

- [ ] **Step 4: Open and inspect through the Codex in-app browser**

Open the absolute report path, inspect desktop and narrow viewport rendering, and confirm:

- navigation and priority filters are usable;
- text does not overflow cards;
- the report shows all 21 findings;
- the implementation order is visible;
- there are no browser console errors caused by the document.

- [ ] **Step 5: Commit the consolidated report**

```powershell
git add -- docs/reviews/project-optimization-summary.html
git commit -m "docs: consolidate project optimization review"
```

Expected: one HTML-only commit.

---

### Task 4: Prove runtime code was not affected

**Files:**
- Verify only: all changes since commit `5955b5f`
- Modify: none

**Interfaces:**
- Consumes: the completed documentation-only changes.
- Produces: evidence that no executable/configuration file changed and the existing application still builds and tests.

- [ ] **Step 1: Enforce the changed-file allowlist**

Run:

```powershell
$changed = git diff --name-only 5955b5f..HEAD
$invalid = $changed | Where-Object { [IO.Path]::GetExtension($_) -notin '.md','.html','.patch' }
if ($invalid) { $invalid; throw 'Executable or configuration file changed' }
$changed
```

Expected: only `.md`, `.html`, and `.patch` paths.

- [ ] **Step 2: Verify links and old paths**

Run:

```powershell
rg -n 'task-2-report|task-3-report|frontend/patches/task5-learning-integration\.patch' docs agent.md README.md
git diff --check 5955b5f..HEAD
```

Expected: no stale old path outside historical mapping descriptions; no whitespace errors.

- [ ] **Step 3: Run backend regression tests**

Run:

```powershell
docker compose exec -T backend pytest -q
docker compose exec -T backend python -m compileall -q app
```

Expected: all backend tests pass and compileall exits `0`.

- [ ] **Step 4: Run the frontend production build**

Run:

```powershell
docker compose exec -T frontend npm run build
```

Expected: Next.js production build exits `0`.

- [ ] **Step 5: Check containers and logs**

Run:

```powershell
docker compose ps
docker compose logs --since 10m backend frontend nginx-gateway
```

Expected: application containers are running/healthy and logs contain no new startup or request errors caused by the documentation work.

- [ ] **Step 6: Final Git verification**

Run:

```powershell
git status --short --branch
git log -5 --oneline --decorate
```

Expected: clean worktree, documentation commits visible, current branch ahead of remote until pushed.
