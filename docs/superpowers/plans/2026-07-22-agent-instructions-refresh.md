# Agent Instructions Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用根目录唯一的标准 `AGENTS.md` 取代过时的 `agent.md`，让新 Codex 会话自动获得准确的项目规则和 prompts_4 执行协议。

**Architecture:** `AGENTS.md` 只承载仓库级工作规则，不参与应用运行时。`docs/INDEX.md` 负责文档导航，设计文档记录由“兼容双入口”改为“唯一标准入口”的用户决定。

**Tech Stack:** Markdown、Git、PowerShell、ripgrep

## Global Constraints

- 只修改文档，不修改业务代码、配置、数据库、Docker 或提示词任务正文。
- 根目录最终只保留一个 Agent 指令文件：`AGENTS.md`。
- AI 出题始终只有“出题 Agent + 审题 Agent”两层。
- 删除旧 `agent.md` 已获得用户明确授权，但删除前后都必须全局检查引用。

---

### Task 1: 更新设计决定

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-agent-instructions-design.md`

**Interfaces:**
- Consumes: 用户对标准复数文件名和删除旧文件的确认。
- Produces: 与最终结构一致的设计和验收标准。

- [x] **Step 1: 将采用方案改为唯一 `AGENTS.md`**

移除兼容入口方案，记录旧 `agent.md` 在提取有效规则后删除。

- [x] **Step 2: 更新文件职责和验收清单**

验收要求必须包括根目录不存在 `agent.md`、当前入口不再引用它、归档中的历史描述不作为活动入口。

### Task 2: 建立唯一仓库指令

**Files:**
- Create: `AGENTS.md`
- Delete: `agent.md`

**Interfaces:**
- Consumes: 当前代码、`docs/prompts_3/`、`docs/prompts_4/`、现有测试和构建命令。
- Produces: Codex 新会话自动读取的唯一项目级工作规则。

- [x] **Step 1: 创建 `AGENTS.md`**

写明项目事实、权威顺序、两层出题约束、标准工作流、跨模块安全、错误处理、验证矩阵、prompts_4 协议和 Git 规则。

- [x] **Step 2: 删除旧 `agent.md`**

确认新文件已吸收仍有效规则后删除，不保留重定向或重复入口。

### Task 3: 修复活动文档入口

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/prompts_1/06_sub_agent_tasks.md`

**Interfaces:**
- Consumes: 新的根目录 `AGENTS.md`。
- Produces: 不含失效活动链接的文档导航。

- [x] **Step 1: 替换当前入口和阅读顺序**

将 `../agent.md` 全部替换为 `../AGENTS.md`，并说明它是 AI 工作规则而不是产品提示词正文。

- [x] **Step 2: 消除早期提示词的旧权威声明**

将 `docs/prompts_1/06_sub_agent_tasks.md` 顶部改为历史方案说明，明确当前规则读取根目录 `AGENTS.md`，避免删除旧文件后仍出现伪权威引用。

### Task 4: 文档级验收

**Files:**
- Verify: `AGENTS.md`
- Verify: `docs/INDEX.md`
- Verify: `docs/superpowers/specs/2026-07-22-agent-instructions-design.md`

**Interfaces:**
- Consumes: Tasks 1-3 的最终文件。
- Produces: 唯一性、引用、链接和差异证据。

- [x] **Step 1: 验证唯一性和残留引用**

Run: `Get-ChildItem -File -Filter '*agent*.md'; rg -n --hidden --glob '!/.git/**' 'agent\.md' .`

Expected: 根目录只显示 `AGENTS.md`；活动文档不再引用旧文件，若归档历史记录仍出现则明确属于历史事实。

- [x] **Step 2: 验证 Markdown 相对链接**

运行仓库内 Markdown 链接检查脚本，确认本次修改文件中的相对目标均存在。

- [x] **Step 3: 验证内容约束和 Git 差异**

Run: `rg -n '出题 Agent|审题 Agent|prompts_4|内部浏览器|Conventional Commits' AGENTS.md; git diff --check; git status --short`

Expected: 所有核心规则均可定位，`git diff --check` 退出码为 0，差异只包含计划内文档。
