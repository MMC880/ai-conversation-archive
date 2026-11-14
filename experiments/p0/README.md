# P0 隔离实验

这些是合成数据的机制验证，不是完整应用，也不能证明真实 ChatGPT 导出兼容。无需安装第三方依赖；使用 Python 3.12.10 / SQLite 3.49.1。产品语言仍未由这些实验决定。

## 运行

在 `E:\GPT\AI-Conversation-Archive\experiments\p0`：

```powershell
python -X utf8 run_evidence.py suite -- python -X utf8 -m unittest discover -v
python -X utf8 run_evidence.py demo -- python -X utf8 demo.py
```

回环 HTTP 和 Windows junction 测试需要宿主允许相应操作；受限沙箱可能 WinError 10013 或 SKIP。看完整结果与 skipped，不只看 exit0。临时 HTTP server 使用随机 127.0.0.1 端口，测试结束关闭。

Codex 可选验证（启动新的合成 CLI 会话并使用现有登录，会调用模型）：

```powershell
python -X utf8 run_evidence.py codex -- python -X utf8 run_codex_probe.py
```

仅进程参数启用 stdio probe，使用 `--ignore-user-config --no-daemon`，不编辑用户配置，不读取历史会话。协议探针只实现此实验所需最小方法，不能作为生产 MCP server 使用。自动判断同时检查 wire、完成工具结果和 SQLite 中接收字节，范围永远为 partial。

## 文件与数据

- `fixtures.py` / `importer.py`：合成 ZIP、多分支、未知字段、附件和异常输入；仅识别自定义测试方言，不是经真实样本校准的解析器。
- `storage.py`：SQLite 单事务接收 journal、按原始字节哈希去重、追加快照、无覆盖原始文件发布与恢复；无外部消息队列依赖。
- `hub.py`：实验 HTTP 接口；令牌、来源、Host、预算、schema 和请求 framing 检查；不是生产 HTTP server。
- `vault_projection.py`：将来源消息放入长度足够的 literal fence，原样展示而不激活源 Markdown 外部嵌入。富 Markdown 阅读渲染后置；控制的附件链接单独生成。
- `mcp_probe.py` / `run_codex_probe.py` / `probe_result.py`：协议探针、真实 CLI 调用、回执验收。
- `test_*.py`：行为测试；测试临时目录仅位于 `runs/`，临时测试数据自动清理。
- `runs/demo-*`：可打开检查的合成 ZIP、inspection、journal、raw 和独立 `test-vault`，不属于现有 Obsidian Vault。
- `runs/codex-*`：新建合成会话的 wire/client/result。首轮继承 MCP 初始化问题已记录；旧结果不代表最终隔离验收。
- `evidence/`：逐次命令、退出码和完整 stdout/stderr，保留 RED、失败、SKIP、修复与最终结果。

## 已知界限

幂等按输入字节 hash，尚未验证 JSON 排版差异、跨来源合并或完整版本谱系。pending 时 SQLite journal 是待生成 L0 文件的持久 spool，完成后 raw 可独立回读重建索引；这只是候选机制，不是对产品原始存储架构的最终决策。

异常退出测试在已提交事务后 `os._exit(73)`，不等于真实硬件断电。无覆盖发布与文件 fsync 不提供已测过的硬件写缓存保证。仅提供文件级 Vault 回读，没有打开 Obsidian，也没有测试 MV3 或 ChatGPT 实际 DOM。报告中这些保持待验收。
