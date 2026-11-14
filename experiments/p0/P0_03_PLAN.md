# P0-03 导出候选模型验证计划

日期2026-11-03。授权：本轮用户指令、DEVELOPMENT_MASTER_PLAN §5 P0-03、PRD FR-01–04/AT-01/03及ENGINEERING_LESSONS。P0-02已由用户确认审计通过。仅合成数据；真实格式WAITING_REAL_SAMPLE；不进入P0-04/P1。

执行：使用Superpowers writing-plans/test-driven-development，主Agent按executing-plans顺序实施，最后做一次有界独立代码审查和完成前验证。用户已授权自主技术选择，故不重复设计确认；原工程非Git仓库，不init/worktree/commit，不清理唯一证据。

## 目标、设计和边界

保留原17个实验源文件及历史测试/报告。新模块复用importer.inspect_export/safe_name、storage.exclusive_bytes/sandbox_path；增加严格JSON和候选字段审查、原件checkpoint与可重试报告。不开发完整导入器、产品schema或队列。JSON输入显式指定类型，在内存包装ZIP以复用旧解析器；包装不是原始文件，原JSON独立保留/hash。

官方帮助确认ZIP聊天历史、conversations.json/可能编号JSON，但本次打开的页面没有给完整字段/附件/分支schema。本实验的mapping/current_node/author/content/attachments.path全部是合成候选假设，不声称官方字段已验证；不使用ChatGPT隐藏API，也不下载公开个人聊天样本。

## 文件与步骤

1. 已有资产哈希快照、公开来源摘要；只读现有主计划/PRD/经验/实验和31测试证据，不重跑旧全套。
2. 新建p003_fixtures.py（复用fixtures素材）与test_export_validation.py；先RED，针对严格JSON、所有角色/分支/未知内容、直接JSON、重复、CRC/资源预算、恢复行为。
3. 新建export_validation.py：inspect_candidate(data, kind='zip')、preserve_and_validate(data, root, kind='zip')、resume(root, digest, kind='zip')。只写p0/runs的原始hash对象与成功报告；失败保留受限原件且不产生成功报告。预算沿用旧2MB/50项，仅实验值。
4. 新建p003_demo.py；保存两个合成对话、含编辑分支/未知角色/代码/附件的样本、JSON与分块样本、损坏输入和结果清单。相同字节幂等；进程在原件落盘后异常退出可重开重试，不声称硬件断电恢复。
5. 用既有run_evidence.py记录新测试RED/GREEN、demo；有新变更/审查发现才补测，不重跑无变化的HTTP/Vault/Codex旧套件。给独立审查者精确新文件/边界，不读取私人日志。
6. 生成docs/handoff/P0-03_CHATGPT_EXPORT_VALIDATION.md，写实际结果、覆盖、失败与未验；核对所有旧字节不变。完成后停止等待审计。

## Review Focus

- 未识别结构不报真实兼容；原ZIP/JSON字节不可被标准化覆盖。
- message.id相同不应把两个图节点合并；重复会话ID明确拒绝并保留原件，不擅自语义合并。
- 未知角色/块保留，时间未知不推断，非有限数/重复JSON键不能静默丢信息。
- 原件已保留不等于解析已成功；失败不留成功清单；重试和报告冲突不覆盖用户数据。
- ZIP成员不解压，恶意输入也只保留受限原件；报告输出/恢复路径也必须被同一runs边界限制。

## 执行记录/决定

- 首次15个新测试RED→GREEN后独立审查发现数值float精度、JSON包装附件、DEFLATE异常和空附件类型缺口。新增失败回归后修复，旧17源文件不动。
- Ruling：不能无损往返的JSON小数不转换为字符串或近似值，而明确拒绝为UNSUPPORTED_NUMERIC_PRECISION，并保留输入原字节。只是本轮候选解析器能力限制，不判断官方输入不合法。
- 限范围复核发现极小指数触发DecimalException，再先RED后归一异常；最终20新测试通过。不重跑原31测试或其他阶段套件。
