# AgentFlow 工具清单（迁移参考）

> 共 **40 个内置工具** + **80+ 别名** + **MCP 动态工具**  
> 源码位置：`backend/app/tools/`

---

## 架构概览

```
BaseTool (base.py)          ← 抽象基类
  ├── name / description / category / risk_level
  ├── input_schema           ← OpenAI Function Calling 格式
  └── run(arguments) → dict  ← 异步执行

ToolRegistry (registry.py)  ← 统一注册中心
  ├── register_defaults()    ← 启动时注册所有内置工具
  ├── register_mcp_tools()   ← 动态注册 MCP 外部工具
  ├── execute(name, args)    ← 执行（含别名自动解析）
  └── _TOOL_ALIASES          ← 80+ LLM 幻觉别名映射
```

迁移时需保留 `BaseTool` 接口和 `ToolRegistry.execute()` 的别名解析逻辑。

---

## 一、Shell & 执行（builtin.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 1 | `bash` | BashTool | 执行 Shell 命令 | high | `command`, `timeout?`, `working_dir?` |
| 2 | `python_exec` | PythonExecTool | 执行 Python 代码 | high | `code`, `timeout?` |
| 3 | `multi_bash` | MultiBashTool | 并发执行多条命令 | high | `commands[]` |

**安全机制**：
- `bash` 内置危险命令黑名单（`rm -rf /`, `mkfs`, fork bomb 等）
- `python_exec` 在 `/tmp` 下执行，自动检测新生成文件并返回 URL
- 两者均支持输出截断（防 token 爆炸）

**常见别名**：`shell` / `run_python` / `execute_code` / `terminal` / `cmd` → 自动映射

---

## 二、文件系统（builtin.py + advanced_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 4 | `read_file` | ReadFileTool | 读取文件内容 | low | `path`, `offset?`, `limit?` |
| 5 | `write_file` | WriteFileTool | 写入文件（自动创建目录） | medium | `path`, `content` |
| 6 | `edit_file` | EditFileTool | str_replace 精确替换 | medium | `path`, `old_string`, `new_string` |
| 7 | `insert_file_line` | InsertFileLineTool | 指定行号前插入 | medium | `path`, `line`, `content` |
| 8 | `undo_edit` | UndoEditTool | 撤销最近一次编辑 | medium | `path` |
| 9 | `list_dir` | ListDirTool | 列出目录内容 | low | `path`, `max_depth?` |
| 10 | `find_files` | FindFilesTool | glob 模式搜索文件 | low | `pattern`, `base_dir?`, `max_results?` |
| 11 | `grep_search` | GrepSearchTool | 正则搜索文件内容 | low | `query`, `path`, `includes?` |
| 12 | `zip_files` | ZipFilesTool | 打包为 ZIP | medium | `paths[]`, `output_path` |
| 13 | `image_read` | ImageReadTool | 图片→Base64 | low | `path` |
| 14 | `pdf_read` | PdfReadTool | 提取 PDF 文字 | low | `path`, `max_pages?` |
| 15 | `notebook_read` | NotebookReadTool | 读 Jupyter Notebook | low | `path` |
| 16 | `notebook_edit` | NotebookEditTool | 编辑 Notebook Cell | medium | `path`, `cell_index`, `new_source`, `mode?` |

**编辑工具链路**：`read_file` → `edit_file` → `undo_edit`（支持撤销）

**常见别名**：`cat_file` / `view` / `create_file` / `str_replace_editor` / `ls` / `grep` / `glob` → 自动映射

---

## 三、网络（builtin.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 17 | `web_search` | WebSearchTool | 网络搜索（含天气自动路由） | low | `query` |
| 18 | `web_fetch` | WebFetchTool | 获取网页纯文本 | low | `url`, `max_chars?` |
| 19 | `http_request` | HttpRequestTool | 通用 HTTP 请求 | medium | `url`, `method?`, `headers?`, `body?`, `timeout?` |

**特殊逻辑**：
- `web_search` 自动识别天气查询，调用实时天气 API
- `web_fetch` 自动去除 HTML 标签，返回纯文本

**常见别名**：`google_search` / `search` / `curl` / `fetch` / `browse` / `scrape` → 自动映射

---

## 四、数据库（data_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 | 依赖 |
|---|--------|-----|------|------|----------|------|
| 20 | `mysql_query` | MySQLQueryTool | 执行 MySQL SQL | high | `sql`, `host?`, `port?`, `user?`, `password?`, `database?` | pymysql |
| 21 | `mysql_schema` | MySQLSchemaTool | 查看表结构 | low | `database?`, `table?` | pymysql |
| 22 | `redis_cmd` | RedisCmdTool | 执行 Redis 命令 | medium | `command`, `args?`, `uri?` | redis |
| 23 | `sqlite_query` | SQLiteQueryTool | 查询 SQLite | medium | `db_path`, `sql` | sqlite3 |
| 24 | `milvus_search` | MilvusSearchTool | Milvus 向量搜索 | low | `collection`, `query_vector`, `top_k?` | pymilvus |

**连接管理**：MySQL/Redis 自动读取 `MYSQL_*` / `REDIS_*` 环境变量，参数可省略。

---

## 五、Office 文档（data_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 | 依赖 |
|---|--------|-----|------|------|----------|------|
| 25 | `excel_read` | ExcelReadTool | 读 Excel | low | `path`, `sheet?` | openpyxl |
| 26 | `excel_write` | ExcelWriteTool | 写 Excel | medium | `path`, `data`, `sheet?` | openpyxl |
| 27 | `word_read` | WordReadTool | 读 Word .docx | low | `path` | python-docx |
| 28 | `word_write` | WordWriteTool | 写 Word .docx | medium | `path`, `content[]` | python-docx |
| 29 | `ppt_read` | PPTReadTool | 读 PowerPoint | low | `path` | python-pptx |
| 30 | `ppt_write` | PPTWriteTool | 写 PowerPoint | medium | `path`, `slides[]` | python-pptx |
| 31 | `md_to_html` | MdToHtmlTool | Markdown→HTML | low | `content` | markdown |

---

## 六、版本控制（advanced_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 32 | `git` | GitTool | Git 操作 | medium | `action` (diff/log/status/add/commit/push/pull/branch), `args?` |

---

## 七、系统信息（advanced_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 33 | `env_info` | EnvInfoTool | OS/Python/CPU/内存/已装包 | low | 无 |
| 34 | `process_list` | ProcessListTool | 进程列表（可过滤） | low | `filter?` |

---

## 八、图表渲染（diagram_tool.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 | 依赖 |
|---|--------|-----|------|------|----------|------|
| 35 | `draw_diagram` | DrawDiagramTool | 渲染图表为图片 | low | `type` (mermaid/plantuml/graphviz/...), `source` | Kroki 服务 |

**支持格式**：mermaid, plantuml, graphviz/dot, blockdiag, seqdiag, actdiag, nwdiag, c4plantuml, excalidraw, ditaa

---

## 九、Agent 专用工具（agent_tools.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 36 | `create_memory` | CreateMemoryTool | 持久化记忆（跨会话） | low | `content`, `type?`, `tags?` |
| 37 | `list_memories` | ListMemoriesTool | 检索已保存记忆 | low | `type?`, `keyword?`, `limit?` |
| 38 | `create_task` | CreateTaskTool | 创建任务追踪 | low | `title`, `description?`, `steps?` |
| 39 | `update_task` | UpdateTaskTool | 更新任务状态 | low | `task_id`, `status`, `result?` |

---

## 十、效率工具（builtin.py）

| # | 工具名 | 类 | 说明 | 风险 | 核心参数 |
|---|--------|-----|------|------|----------|
| 40 | `todo` | TodoTool | 读写任务列表 | low | `action` (read/write), `todos?` |

---

## 别名映射表（迁移重点）

LLM 经常输出非标准工具名，`_TOOL_ALIASES` 做自动映射。迁移时务必保留。

| 别名类别 | 示例别名 | 映射目标 |
|---------|---------|---------|
| Python 执行 | `run_python`, `execute_code`, `jupyter`, `python` | → `python_exec` |
| Shell 执行 | `shell`, `terminal`, `cmd`, `computer` | → `bash` |
| 文件读取 | `cat_file`, `view`, `open_file`, `load_file` | → `read_file` |
| 文件写入 | `create_file`, `save_file`, `new_file` | → `write_file` |
| 文件编辑 | `str_replace_editor`, `str_replace`, `modify_file` | → `edit_file` |
| 网络搜索 | `google_search`, `search`, `bing_search` | → `web_search` |
| URL 获取 | `fetch_url`, `browse`, `scrape`, `open_url` | → `web_fetch` |
| 文件搜索 | `grep`, `search_files`, `code_search` | → `grep_search` |
| 目录列表 | `ls`, `dir`, `listdir` | → `list_dir` |
| HTTP 请求 | `curl`, `fetch`, `api_call`, `post_request` | → `http_request` |
| 文件存在检查 | `file_exists`, `path_exists` | → `bash`（自动构造 test 命令） |
| 复合文件操作 | `file_operations` | → 分派到 read/write/bash |

完整映射见 `registry.py` 中 `_TOOL_ALIASES` 字典（约 80 条）。

---

## MCP 动态工具

通过 `config/mcp_servers.yaml` 配置外部 MCP 工具服务器，运行时自动注册。

```yaml
servers:
  - name: my_server
    command: npx
    args: ["-y", "@my/mcp-server"]
```

注册后工具名格式：`mcp_{server_name}_{tool_name}`

---

## 依赖汇总（迁移时需安装）

| 包名 | 用途 | 必装 |
|------|------|------|
| httpx | HTTP 请求 / 网页获取 | ✅ |
| pymysql | MySQL 工具 | 按需 |
| redis | Redis 工具 | 按需 |
| openpyxl | Excel 读写 | 按需 |
| python-docx | Word 读写 | 按需 |
| python-pptx | PPT 读写 | 按需 |
| markdown | Markdown→HTML | 按需 |
| pymilvus | Milvus 向量搜索 | 按需 |
| PyPDF2 / pdfplumber | PDF 提取 | 按需 |
| Pillow | 图片处理 | 按需 |

---

## 迁移核心检查清单

- [ ] 复制 `base.py`（BaseTool 抽象基类）
- [ ] 复制 `builtin.py`（15 个基础工具）
- [ ] 复制 `data_tools.py`（12 个数据/文档工具）
- [ ] 复制 `advanced_tools.py`（9 个高级工具）
- [ ] 复制 `agent_tools.py`（4 个 Agent 工具）
- [ ] 复制 `diagram_tool.py`（1 个图表工具）
- [ ] 复制 `registry.py`（注册中心 + 别名映射）
- [ ] 确认目标环境 Python 依赖已安装
- [ ] 配置环境变量（`MYSQL_*`, `REDIS_*` 等）
- [ ] 如需 MCP，配置 `mcp_servers.yaml`
- [ ] 如需图表，部署 Kroki 服务
