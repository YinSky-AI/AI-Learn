# 项目文档导航

本页用于快速定位项目中的正式设计、当前实施依据、历史方案和验收资料。业务代码仍位于 `backend/` 与 `frontend/src/`，文档整理不会改变程序路径。

## 当前入口

- [`../agent.md`](../agent.md)：项目提示词体系的顶层入口。
- [`prompts_3/`](prompts_3/)：当前已实施功能的设计依据，包含两层 AI 出题、四角色辅导、错题本、游戏化、行为报告、知识图谱、PWA 和竞赛系统。
- [`prompts_4/README.md`](prompts_4/README.md)：基于优化报告拆分的尚未实施优化待办包；提示词已编写，不代表功能已经实施。
- [`reviews/project-optimization-summary.html`](reviews/project-optimization-summary.html)：合并后的架构、安全、交付、性能和产品优化报告。

## 产品与历史设计

- [`advises/`](advises/)：产品构想、竞品分析与改进建议。
- [`prompts_1/`](prompts_1/)：初始产品、架构、数据模型、测试与验收设计。
- [`prompts_2/`](prompts_2/)：历史题库方案，仅作历史参考；当前 AI 出题以 `prompts_3` 的两层出题/审题设计为准。

## 审查与归档

- [`reviews/`](reviews/)：项目级架构审查、风险清单与优化建议。
- [`archive/implementation-reports/`](archive/implementation-reports/)：历史实施报告，以及本次目录整理的设计和实施计划。
- [`archive/patches/`](archive/patches/)：已经退出日常开发流程、仅供追溯的历史补丁。

## 保留在原位置的资料

- [`../sql/report.md`](../sql/report.md)：题库生成验收报告。该路径被 `prompts_2` 引用，因此继续保留。
- `../test/`：本地验收截图、测试日志和原始架构审查报告。该目录被 Git 忽略，不作为正式文档入口。
- `../docker-data/`：本地 Docker Desktop 虚拟磁盘，不属于项目文档，不得作为普通文件移动或删除。

## 文档使用顺序

1. 先阅读根目录 `agent.md` 了解项目总体目标和提示词入口。
2. 新功能和当前实现以 `prompts_3/` 为主要设计依据。
3. 产品方向参考 `advises/`，早期背景参考 `prompts_1/`。
4. `prompts_2/` 只用于理解历史题库方案，不恢复其中已经废弃的复杂 Agent 分层。
5. 开始下一轮重构前，先查看合并优化报告中的优先级和依赖关系。
