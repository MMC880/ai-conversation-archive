# P0 隔离技术验证计划

日期：2026-11-03。依据：已验收产品计划、PROJECT_RESEARCH_REPORT.md、本轮授权及用户明确要求仅用合成聊天样本。

执行中新增基线：docs/PRD.md v1.0 已完整读取；它负责产品功能和验收，原产品计划继续负责 P0–P7 顺序。逐项对照未发现实质需求冲突；不重启已完成实验。已有实验只是对应 FR/NFR 的机制证据，不代表真实产品 AT 验收已完成。详见 docs/PRD_ALIGNMENT.md 和最终验证报告。

执行采用 Superpowers writing-plans → 顺序执行 → TDD → systematic-debugging → 独立审查 → verification-before-completion。用户已授权自主规划和普通技术选择，故无需逐项设计确认；不自动 commit，不创建全局配置，不改变 P0–P7。

## 范围和实现选择

- 新建 `experiments/p0/`，使用现有 Python 3.12 标准库 unittest、sqlite3、http.server、zipfile、hashlib、subprocess，避免安装依赖。它是一次性机制实验，不锁定产品语言为 Python。
- 所有样本、数据库、日志、测试 Vault 和 MCP payload 均合成，写入本项目的实验子目录。
- 不读取私人会话记录，不调用现有 Obsidian MCP，不修改真实 Vault，不启动 Tunnel，不修改上游。
- 真实 ChatGPT 格式兼容性为 WAITING_REAL_SAMPLE；Obsidian 实际打开/渲染与网页 DOM/MV3 端到端验证单独列出，不用文件层测试替代。

## 任务与验收

1. 经验整理：读取已知 PPT 项目报告/独立审计/现行与过期机器证据；有证据才写“已验证”，旧报告与本次复核分开。旧 Obsidian Skill v1.1 仅在已知技能与工程文档中定位，找不到就记录。
2. 合成导出机制：`fixtures.py` 生成多轮、中文、代码、分支、附件、未知内容、异常 ZIP；`test_importer.py` 先测试分支保留/顺序、缺失标记、重复文件/越界/大小/损坏拒绝，再实现 `importer.py`。预期：原 ZIP 不变，未知数据不丢；不声称真实导出兼容。
3. 原始存储和幂等：`test_storage.py` 验证并发重复、变化追加、重启恢复、损坏文件检测与异常中断，再实现 `storage.py`。以 SQLite 单事务先保存接收字节和 pending 状态，再投影原始文件；每个确认接收必须能恢复。
4. 接收安全：`test_hub.py` 通过真实回环 HTTP 验证令牌、Origin、Host、Content-Type、请求预算、路径字段拒绝和持久确认，再实现 `hub.py`。凭据不入日志；拒绝请求不落盘；不宣称生产服务器已就绪。
5. 测试 Vault：`test_vault.py` 验证中文/代码块/附件链接回读、重复导出不覆盖、外部修改冲突、路径/链接逃逸拒绝，再实现 `vault_projection.py`。不调用 Obsidian；文件层与客户端层分开。
6. Codex：`mcp_probe.py` 暴露一个只接收显式合成 payload 的 stdio 工具；先用本地 JSON-RPC 测试，再以单次进程配置接入真实 Codex CLI，保留 wire 和客户端事件。只观察本次新建合成会话，严禁读取历史会话。失败保留且不伪装为通过。
7. 输出 ENGINEERING_LESSONS.md、P0_VALIDATION_REPORT.md、README、逐次命令/退出码/完整测试日志及文件哈希；独立审查实验与结论，修复确认的问题后重跑相关测试及全套。

## Review Focus

真实样本缺失不能变成兼容通过；分支不能扁平化冒充完整历史；未授权请求不能先落盘；确认返回必须在持久事务之后；源数据不能被投影覆盖；SQLite 与文件分步提交必须可恢复；测试 Vault 目录不能借 symlink/junction 逃逸；MCP 工具参数不能被称为完整会话捕获。

## 证据约定

每次测试都使用 `run_evidence.py <label> -- <argv...>`，保留时间、工作目录、原始 argv、退出码、stdout/stderr。RED 与 GREEN 分开保留。阶段状态与重大决定记录在 `experiments/p0/PROGRESS.md`；不删除失败日志。
