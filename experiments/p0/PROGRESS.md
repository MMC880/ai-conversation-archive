# P0 实验进度

计划：docs/P0_EXPERIMENT_PLAN.md。阶段限定：仅隔离实验，不进入 P1。

- 2026-11-03：已读取 PPT 历史独立审计与证据修正记录、本项目两份报告、产品计划、Superpowers；内置技能目录未发现 Obsidian archive Skill，已知 E:\GPT 日期目录无相关文档。旧 Skill v1.1 暂未找到，不扫描其他个人路径。
- 用户已明确不提供真实导出，本轮仅合成样本；真实导出兼容性待验收，不阻塞其余实验。
- 决定：以 Python 标准库做机制验证，不做产品技术栈决策；SQLite 保存接收字节和 pending 状态后才确认，原始文件可从接收 journal 恢复；不删除历史证据。
- 导入器：7 个合成场景 RED（14 个 assertion failures）→ GREEN 7/7；源字节、分支、未知字段、附件缺失及 ZIP 边界均有断言。
- 存储首次 GREEN 尝试失败：SQLite Connection 上下文只处理事务、不关闭连接，导致 Windows 文件占用；硬链接发布受沙箱限制。修复为明确 finally close 和 Windows 无覆盖 rename 后，6/6 通过。不是跳过或伪装通过。
- HTTP 首次实测被沙箱 WinError 10013 阻断，获自动批准后在宿主回环端口运行，6/6 通过；仅限制临时合成端点，没有修改网络配置。
- Vault 文件层先 RED 再 GREEN；沙箱中 junction 创建被拒绝，保留 SKIP。宿主全套实跑 24/24，通过 junction 逃逸拒绝用例，未打开 Obsidian。
- requesting-code-review 已启动独立只读审查。真实 Codex 实验仅新建合成临时会话，stdio 已 initialize/tools-list，等待工具调用结果；没有读取历史线程。
