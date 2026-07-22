# P1-11：运行就绪（Runtime Readiness）

将本文件完整交给编码 AI 执行。HTML 只作候选证据；先读当前代码、部署配置、测试和 `AGENTS.md`。

## 任务定位

- 优先级 P1；风险高（故障服务被误判健康）。区分 liveness 与 readiness，并让 Compose、网关和监控消费同一真实可用性边界。
- 非目标：不把每个外部服务都变成启动阻塞项，不伪造静态 200，不进行无关 Docker 重构。

## 当前证据

- Finding 11 候选为 `backend/app/main.py:241-260`、`nginx/nginx.conf:210-215`、`docker-compose.yml:76-127`：后端 health 可能无条件 healthy、Nginx 为静态 200，编排不等待真实依赖。
- 建议 readiness 聚合数据库、Redis、必需配置和必要下游，liveness 只反映进程可响应；必须复核服务实际依赖。

## 开始前调查

1. 阅读应用生命周期、依赖初始化、Compose healthcheck/depends_on、Nginx upstream、环境配置、监控调用和现有 smoke 测试。
2. 列出每个依赖对 liveness/readiness 的影响、超时、缓存和故障语义；确认哪些 provider 是可降级而非必需。
3. 记录运行目标的 host、environment、数据库名称；不能在未知环境执行破坏性检查。

## 允许修改范围

- 可修改健康端点、依赖探针、健康 DTO、Nginx/Compose healthcheck、启动日志和针对性的测试；保持已有公开端点兼容或给迁移路径。
- 若涉及数据库 schema，先备份并在独立测试库验证迁移和回滚；单纯健康检查不应擅自变更数据。

## 禁止操作

- 禁止把 readiness 与 liveness 混为一个永远 200 的端点、在探针中输出连接串/异常、或用 sleep 假装依赖健康。
- 禁止删除容器、卷、数据库或无授权更改生产部署策略。

## 分阶段执行

1. 复核依赖图和消费者；2. 设计状态、超时及降级矩阵；3. 先写依赖成功/失败测试；4. 最小实施端点和编排；5. 重建容器并验收。

## 跨模块耦合检查

- 检查 DB、Redis、配置、AI 预算、Nginx、Compose、CI、路由和环境变量的一致性；确认健康检查不会连接错数据库。
- 与 P1-10/P1-12 对齐：预算/诊断依赖故障的状态、日志和 run ID 不能产生互相矛盾的健康结论。

## 错误处理要求

- readiness 失败返回稳定、纯文本或安全状态码契约，不返回堆栈、SQL、主机名、密钥或完整下游响应。
- 日志保留脱敏依赖名、耗时、错误类别和关联 ID；超时/部分失败遵循设计的降级或拒绝策略。

## 验收标准

- 自动化测试与真实容器 smoke 分别证明：进程存活时 liveness 正常；DB、Redis、必需配置各自故障时 readiness 明确失败；可降级依赖符合声明行为。
- Compose 只在真实 readiness 后标为可用，Nginx 不再以静态 200 掩盖上游失败；修改应用/编排后执行 `docker compose up -d --build`，检查 `docker ps`、日志和 Docker Desktop。
- 检查成功/故障恢复、超时上界、健康 DTO 脱敏、构建和 `git diff --check`。

## 最终报告格式

报告状态、文件和探针矩阵、Finding 11 复核、测试与容器命令输出、`docker ps`/日志/Docker Desktop 证据、数据库目标与隔离迁移证据（如适用）、提交 SHA、残余依赖风险和人工部署步骤。
