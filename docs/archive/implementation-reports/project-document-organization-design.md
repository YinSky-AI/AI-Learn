# 项目目录与文档安全整理设计

## 目标

在不修改业务代码、不移动本地运行数据、不删除任何文件的前提下，整理项目中的正式目录与文档，使提示词、产品建议、架构审查、历史实施报告和历史补丁具有清晰归属。

## 整理范围

本次仅处理 Git 已跟踪的正式文档与历史文本资产：

- 合并现有三份架构审查报告；
- 增加文档总导航；
- 归档两个历史实施报告；
- 归档一个已经应用过的历史补丁；
- 更新因移动而受影响的文档引用。

本次明确不处理：

- `backend/` 业务代码；
- `frontend/src/` 业务代码；
- `docker-data/` 中的 Docker 虚拟磁盘；
- `sql/` 中被 Git 忽略的题库生成中间产物；
- `test/` 中的本地验收截图、日志和原始架构报告；
- `.superpowers/` 中被 Git 忽略的运行过程文件；
- `frontend/.tmp-tdd-unknown/`；
- 任何删除操作。

## 目标结构

```text
docs/
├─ INDEX.md
├─ advises/
├─ prompts_1/
├─ prompts_2/
├─ prompts_3/
├─ reviews/
│  └─ project-optimization-summary.html
└─ archive/
   ├─ implementation-reports/
   │  ├─ project-document-organization-design.md
   │  ├─ question-pipeline-report.md
   │  └─ question-persistence-report.md
   └─ patches/
      └─ task5-learning-integration.patch
```

## 文件映射

| 当前文件 | 整理后文件 | 处理方式 |
|---|---|---|
| `.superpowers/sdd/task-2-report.md` | `docs/archive/implementation-reports/question-pipeline-report.md` | Git 重命名 |
| `.superpowers/sdd/task-3-report.md` | `docs/archive/implementation-reports/question-persistence-report.md` | Git 重命名 |
| `frontend/patches/task5-learning-integration.patch` | `docs/archive/patches/task5-learning-integration.patch` | Git 重命名 |
| `test/architecture-review-20260721-215458.html` | `docs/reviews/project-optimization-summary.html` | 与另外两份报告合并后新建 |
| `test/architecture-review-crosscut-20260721-220244.html` | 同上 | 合并来源，原文件保留 |
| `test/architecture-review-critical-20260721-221429.html` | 同上 | 合并来源，原文件保留 |

## 文档导航设计

`docs/INDEX.md` 作为唯一的文档导航页，说明：

- `agent.md` 是项目提示词体系的顶层入口，继续保留在项目根目录；
- `docs/prompts_1/` 是初始产品、架构与验收设计；
- `docs/prompts_2/` 是历史题库方案，仅作为历史参考；
- `docs/prompts_3/` 是当前学习平台重构与功能设计；
- `docs/advises/` 保存产品构想和竞品分析；
- `docs/reviews/` 保存合并后的架构与风险审查；
- `docs/archive/` 保存不再参与运行、但仍有追溯价值的实施报告和补丁；
- `sql/report.md` 继续留在原路径，因为 `docs/prompts_2/question-bank/00-task-brief.md` 明确引用它。

## 合并报告设计

`docs/reviews/project-optimization-summary.html` 将三份现有报告合并为一个可独立打开的 HTML，按优先级组织：

1. P0 Critical：公开题库答案、后台访问控制、不可恢复删除、备份恢复；
2. P0：答题事务、学习维度与题库访问、Schema Migration、生产配置与交付验收；
3. P1 High：账号撤销、永久 pending 任务、AI 成本预算、运行就绪、可观测性；
4. P1：前端练习会话、辅导会话、读取性能、后台管理、数据治理、PWA 与可访问性；
5. 推荐实施顺序和“不在本次整理中修改业务代码”的范围说明。

每个候选保留问题、文件证据、影响、建议与推荐强度。报告使用响应式布局，并在生成后由本机浏览器打开检查。

## 安全与错误处理

- 所有移动仅作用于明确列出的三个 Git 已跟踪文件；
- 移动前重新读取文件并确认目标不存在；
- 不覆盖同名文件；
- 如果引用检查发现未知消费者，停止相应移动并保留原位置；
- 不操作 `.env`、数据库文件、Docker 虚拟磁盘、截图或未跟踪题库数据；
- 不执行任何删除命令。

## 验收标准

- `docs/INDEX.md` 能正确导航所有正式文档类别；
- 合并 HTML 包含三份报告中的全部独立问题，且浏览器打开无明显布局错误；
- 三个历史文件被 Git 识别为重命名或等价移动；
- 原有 `agent.md` 与 `sql/report.md` 引用仍有效；
- 全局引用搜索不包含已失效的旧路径；
- `git diff --check` 通过；
- 前端构建与后端测试保持通过；
- Git 变更中不包含业务代码、环境文件、本地数据或删除操作。

## 删除候选

本设计不授权删除。盘点中发现的疑似重复 Next.js 路由、临时 TDD 文件、历史生成中间产物和 Docker 数据，只记录为未来候选；如需处理，必须重新列出精确影响范围并取得用户确认。
