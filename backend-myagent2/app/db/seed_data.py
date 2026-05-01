"""
Built-in seed data for skills, prompts, and tools.
Called on startup to UPSERT default records.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


BUILTIN_SKILLS = [
    {
        "id": "skill_code_review",
        "name": "code-review",
        "description": "代码审查：分析代码质量、安全漏洞、性能问题，并提出改进建议",
        "category": "development",
        "content": "你是一位资深代码审查专家。请仔细审查以下代码，从以下几个维度进行分析：\n1. **代码质量**：可读性、命名规范、代码组织\n2. **潜在 Bug**：逻辑错误、边界条件、空值处理\n3. **安全性**：SQL注入、XSS、敏感信息泄露\n4. **性能**：时间复杂度、内存使用、数据库查询优化\n5. **最佳实践**：设计模式、SOLID原则\n\n请用 Markdown 格式输出，按严重程度排序。",
        "is_builtin": 1,
        "tags": '["code", "review", "development"]',
        "argument_hint": "粘贴要审查的代码",
        "when_to_use": "需要审查代码质量时",
    },
    {
        "id": "skill_sql_expert",
        "name": "sql-expert",
        "description": "SQL专家：根据自然语言生成SQL查询，支持MySQL/PostgreSQL/SQLite",
        "category": "data",
        "content": "你是 SQL 查询专家，精通 MySQL、PostgreSQL 和 SQLite。\n用户会用自然语言描述需求，你需要：\n1. 生成正确的 SQL 查询语句\n2. 解释查询逻辑\n3. 注意 SQL 注入防护\n4. 考虑查询性能（索引使用、避免全表扫描）\n\n输出格式：先给出 SQL 代码块，再解释。",
        "is_builtin": 1,
        "tags": '["sql", "database", "data"]',
        "argument_hint": "描述你需要的查询",
        "when_to_use": "需要编写或优化SQL查询时",
    },
    {
        "id": "skill_translate",
        "name": "translate",
        "description": "翻译专家：中英日韩多语言互译，保持专业术语准确性",
        "category": "writing",
        "content": "你是专业的多语言翻译专家，精通中文、英文、日文、韩文。\n翻译原则：\n1. 准确传达原文含义，不添加也不遗漏信息\n2. 使用目标语言的自然表达方式\n3. 专业术语保持一致性\n4. 如有歧义，提供多种翻译并说明区别\n\n如果用户没有指定目标语言，中文翻译为英文，其他语言翻译为中文。",
        "is_builtin": 1,
        "tags": '["translate", "language", "writing"]',
        "argument_hint": "输入要翻译的文本",
        "when_to_use": "需要翻译文本时",
    },
    {
        "id": "skill_summarize",
        "name": "summarize",
        "description": "智能摘要：提炼长文本核心要点，生成结构化摘要",
        "category": "writing",
        "content": "你是文本摘要专家。请分析以下内容并生成结构化摘要：\n\n## 输出格式\n1. **一句话总结**（不超过50字）\n2. **核心要点**（3-5个要点，每个不超过30字）\n3. **关键数据**（如有数字、日期等关键信息）\n4. **详细摘要**（200字以内的完整摘要）\n\n保持客观中立，不添加个人观点。",
        "is_builtin": 1,
        "tags": '["summarize", "writing", "analysis"]',
        "argument_hint": "粘贴要摘要的长文本",
        "when_to_use": "需要快速了解长文本要点时",
    },
    {
        "id": "skill_explain_code",
        "name": "explain-code",
        "description": "代码解释：逐行解析代码逻辑，适合学习和理解复杂代码",
        "category": "development",
        "content": "你是编程教学专家。请用清晰易懂的方式解释以下代码：\n\n1. **总体功能**：这段代码做了什么\n2. **逐行解析**：关键行的作用\n3. **数据流**：数据是如何流动和变换的\n4. **设计模式**：用了什么设计模式或算法\n5. **改进建议**：如何让代码更好\n\n用通俗的语言，避免过于专业的术语。如果有复杂概念，用类比来解释。",
        "is_builtin": 1,
        "tags": '["code", "explain", "learning"]',
        "argument_hint": "粘贴要解释的代码",
        "when_to_use": "需要理解一段代码的工作原理时",
    },
    {
        "id": "skill_api_designer",
        "name": "api-design",
        "description": "API设计师：设计RESTful API，生成OpenAPI规范文档",
        "category": "development",
        "content": "你是 API 设计专家，精通 RESTful 设计规范。\n根据用户描述的业务需求，输出：\n1. **API 端点列表**（HTTP方法 + 路径 + 简述）\n2. **请求/响应示例**（JSON格式）\n3. **数据模型**（TypeScript interface 或 JSON Schema）\n4. **认证方式**建议\n5. **分页、过滤、排序**规范\n\n遵循 REST 最佳实践，URL 使用复数名词，正确使用 HTTP 状态码。",
        "is_builtin": 1,
        "tags": '["api", "design", "rest"]',
        "argument_hint": "描述业务需求",
        "when_to_use": "需要设计新的API接口时",
    },
    {
        "id": "skill_debug",
        "name": "debug",
        "description": "调试助手：分析错误日志和堆栈信息，定位Bug根因",
        "category": "development",
        "content": "你是资深调试专家。请分析以下错误信息：\n\n分析步骤：\n1. **错误类型**：识别错误类别（语法、运行时、逻辑、配置等）\n2. **根因分析**：找到问题的根本原因\n3. **修复方案**：给出具体的修复代码\n4. **预防措施**：如何避免类似问题再次发生\n5. **相关知识**：相关的技术背景知识\n\n如果信息不足，列出需要补充的信息。",
        "is_builtin": 1,
        "tags": '["debug", "error", "troubleshoot"]',
        "argument_hint": "粘贴错误日志或堆栈信息",
        "when_to_use": "遇到Bug需要排查时",
    },
    {
        "id": "skill_data_analysis",
        "name": "data-analysis",
        "description": "数据分析：分析数据集，发现模式和趋势，生成洞察报告",
        "category": "data",
        "content": "你是数据分析专家。请分析提供的数据并生成洞察报告：\n\n## 分析维度\n1. **数据概览**：数据量、字段、类型\n2. **统计特征**：均值、中位数、分布\n3. **趋势发现**：时间趋势、周期性\n4. **异常检测**：离群值、缺失值\n5. **关联分析**：变量间的相关性\n6. **可视化建议**：推荐的图表类型\n7. **业务洞察**：数据背后的业务含义\n\n用数据说话，给出具体数字和百分比。",
        "is_builtin": 1,
        "tags": '["data", "analysis", "insight"]',
        "argument_hint": "粘贴数据或描述数据集",
        "when_to_use": "需要分析数据并提取洞察时",
    },
]


BUILTIN_PROMPTS = [
    {
        "id": "prompt_system_default",
        "name": "默认助手",
        "description": "通用智能助手系统提示词",
        "type": "system",
        "content": "你是一个专业、友好的AI助手。请用清晰、准确的语言回答用户的问题。\n如果不确定答案，请诚实说明。回答时注意：\n1. 结构清晰，善用列表和标题\n2. 代码使用 Markdown 代码块\n3. 重要信息加粗标注",
        "is_builtin": 1,
        "tags": '["default", "general"]',
    },
    {
        "id": "prompt_cot",
        "name": "思维链推理",
        "description": "引导模型进行逐步推理",
        "type": "system",
        "content": "请一步一步地思考这个问题。\n\n对于每一步：\n1. 明确当前步骤要解决什么\n2. 列出相关的已知信息\n3. 进行推理\n4. 得出该步骤的结论\n\n最后给出完整的答案。",
        "is_builtin": 1,
        "tags": '["reasoning", "chain-of-thought"]',
    },
    {
        "id": "prompt_strict_json",
        "name": "严格JSON输出",
        "description": "强制模型只输出合法JSON",
        "type": "system",
        "content": "你是一个 JSON 生成器。你必须：\n1. 只输出合法的 JSON，不要有任何其他文字\n2. 不要用 Markdown 代码块包裹\n3. 确保所有字符串正确转义\n4. 数字不要用引号括起来\n5. 布尔值使用 true/false",
        "is_builtin": 1,
        "tags": '["json", "structured-output"]',
    },
    {
        "id": "prompt_tech_writer",
        "name": "技术文档写作",
        "description": "专业技术文档写作风格",
        "type": "system",
        "content": "你是技术文档写作专家，遵循以下规范：\n1. 使用主动语态和第二人称（\"你\"）\n2. 段落简短，每段不超过3-4句\n3. 使用编号列表表示步骤，无序列表表示选项\n4. 代码示例必须可运行\n5. 术语首次出现时给出解释\n6. 添加必要的注意事项和警告\n7. 保持一致的格式和术语",
        "is_builtin": 1,
        "tags": '["writing", "documentation", "technical"]',
    },
    {
        "id": "prompt_few_shot",
        "name": "Few-shot 示例模板",
        "description": "通过示例引导模型输出格式",
        "type": "user",
        "content": "请按照以下示例的格式回答：\n\n示例输入：{示例1输入}\n示例输出：{示例1输出}\n\n示例输入：{示例2输入}\n示例输出：{示例2输出}\n\n实际输入：{用户输入}\n实际输出：",
        "is_builtin": 1,
        "tags": '["few-shot", "template"]',
    },
    {
        "id": "prompt_role_play",
        "name": "角色扮演框架",
        "description": "定义AI角色的身份、能力和行为边界",
        "type": "system",
        "content": "## 角色设定\n- **身份**：{角色名称}\n- **专业领域**：{领域描述}\n- **经验年限**：{N}年\n\n## 能力范围\n- 擅长：{列出擅长领域}\n- 不涉及：{列出不回答的领域}\n\n## 回答风格\n- 语气：{专业/友好/幽默}\n- 格式：{结构化/对话式}\n- 示例：{是否包含示例}\n\n## 行为准则\n1. 始终保持角色一致性\n2. 不确定时承认局限\n3. 适当引用权威来源",
        "is_builtin": 1,
        "tags": '["role-play", "persona", "template"]',
    },
    {
        "id": "prompt_mcp_server",
        "name": "MCP 服务器",
        "description": "MCP 服务器相关问题",
        "type": "system",
        "content": "你是 MCP 服务器专家。请回答以下问题：\n\n1. **服务器配置**：如何配置 MCP 服务器\n2. **插件管理**：如何安装和管理插件\n3. **用户管理**：如何管理用户和权限\n4. **性能优化**：如何优化服务器性能\n5. **故障排查**：如何排查常见故障",
        "is_builtin": 1,
        "tags": '["mcp", "server", "management"]',
    },
    {
        "id": "prompt_knowledge_base",
        "name": "知识库",
        "description": "知识库相关问题",
        "type": "system",
        "content": "你是知识库专家。请回答以下问题：\n\n1. **知识库创建**：如何创建知识库\n2. **知识库管理**：如何管理知识库\n3. **知识库搜索**：如何搜索知识库\n4. **知识库更新**：如何更新知识库\n5. **知识库共享**：如何共享知识库",
        "is_builtin": 1,
        "tags": '["knowledge", "base", "management"]',
    },
]


BUILTIN_MCP_SERVERS = [
    {
        "id": "mcp_template_filesystem",
        "name": "filesystem-template",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/zjj/home/claudecode/myagent2"],
        "env": {},
        "auto_start": 0,
        "status": "disconnected",
        "tools_count": 0,
        "tools": [],
    },
    {
        "id": "mcp_template_github",
        "name": "github-template",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        "auto_start": 0,
        "status": "disconnected",
        "tools_count": 0,
        "tools": [],
    },
    {
        "id": "mcp_template_fetch",
        "name": "fetch-template",
        "command": "npx",
        "args": ["-y", "@kazuph/mcp-fetch"],
        "env": {},
        "auto_start": 0,
        "status": "disconnected",
        "tools_count": 0,
        "tools": [],
    },
]


BUILTIN_KNOWLEDGE_BASES = [
    {
        "id": "kb_template_local_docs",
        "name": "本地文档目录模板",
        "description": "适合导入本地 Markdown、TXT、PDF 文档目录作为知识库",
        "type": "file",
        "config": {
            "source": "preset",
            "path": "./docs",
            "recursive": True,
            "extensions": ["md", "txt", "pdf"],
            "chunk_strategy": "markdown",
        },
        "doc_count": 0,
        "status": "template",
    },
    {
        "id": "kb_template_api_docs",
        "name": "API 文档抓取模板",
        "description": "适合抓取 Swagger、OpenAPI 或静态 API 文档站点",
        "type": "url",
        "config": {
            "source": "preset",
            "seed_urls": ["https://example.com/docs"],
            "crawl_depth": 2,
            "include_patterns": ["/docs", "/api"],
            "chunk_strategy": "html_sections",
        },
        "doc_count": 0,
        "status": "template",
    },
    {
        "id": "kb_template_project_notes",
        "name": "项目说明知识模板",
        "description": "适合整理项目背景、约束、规范、术语等文本型知识",
        "type": "text",
        "config": {
            "source": "preset",
            "content_template": "# 项目背景\n\n# 业务目标\n\n# 技术约束\n\n# 术语表\n",
            "chunk_strategy": "plain_text",
        },
        "doc_count": 0,
        "status": "template",
    },
]


BUILTIN_WORKFLOWS = [
    {
        "id": "wf_template_quick_qa",
        "name": "快速问答工作流",
        "description": "适合新用户直接发起一次标准问答流程",
        "status": "active",
        "tags": ["preset", "qa", "beginner"],
        "definition": {
            "variables": {
                "user_query": {"type": "string", "description": "用户输入的问题"},
                "answer": {"type": "string", "description": "模型输出答案"}
            },
            "nodes": [
                {
                    "id": "start_1",
                    "type": "start",
                    "position": {"x": 280, "y": 40},
                    "data": {"label": "开始", "outputs": ["user_query"]}
                },
                {
                    "id": "llm_1",
                    "type": "llm",
                    "position": {"x": 260, "y": 180},
                    "data": {
                        "label": "生成回答",
                        "systemPrompt": "你是专业、友好的 AI 助手。",
                        "userPromptTemplate": "请回答：{{user_query}}",
                        "model": "default",
                        "temperature": 0.7,
                        "topP": 1,
                        "maxTokens": 1200,
                        "enableTools": False,
                        "allowedTools": [],
                        "outputFormat": "markdown",
                        "outputVariable": "answer"
                    }
                },
                {
                    "id": "end_1",
                    "type": "end",
                    "position": {"x": 280, "y": 340},
                    "data": {"label": "结束", "outputs": ["answer"]}
                }
            ],
            "edges": [
                {"id": "e_start_llm", "source": "start_1", "target": "llm_1", "animated": True},
                {"id": "e_llm_end", "source": "llm_1", "target": "end_1", "animated": True}
            ]
        },
    },
    {
        "id": "wf_template_skill_router",
        "name": "技能路由工作流",
        "description": "先进入技能节点，再汇总结果返回，适合演示技能型编排",
        "status": "draft",
        "tags": ["preset", "skill", "router"],
        "definition": {
            "variables": {
                "user_query": {"type": "string", "description": "用户需求"},
                "skill_result": {"type": "string", "description": "技能输出结果"}
            },
            "nodes": [
                {
                    "id": "start_1",
                    "type": "start",
                    "position": {"x": 300, "y": 40},
                    "data": {"label": "开始", "outputs": ["user_query"]}
                },
                {
                    "id": "skill_1",
                    "type": "skill",
                    "position": {"x": 280, "y": 180},
                    "data": {
                        "label": "代码解释技能",
                        "skillId": "skill_explain_code",
                        "skillName": "explain-code",
                        "sourceType": "builtin",
                        "contextMode": "",
                        "argsTemplate": "{{user_query}}",
                        "modelOverride": "",
                        "allowedTools": [],
                        "whenToUse": "需要解释代码时",
                        "migrationStatus": "",
                        "outputVariable": "skill_result"
                    }
                },
                {
                    "id": "end_1",
                    "type": "end",
                    "position": {"x": 300, "y": 340},
                    "data": {"label": "结束", "outputs": ["skill_result"]}
                }
            ],
            "edges": [
                {"id": "e_start_skill", "source": "start_1", "target": "skill_1", "animated": True},
                {"id": "e_skill_end", "source": "skill_1", "target": "end_1", "animated": True}
            ]
        },
    },
]


async def seed_builtin_data(db) -> None:
    """Seed built-in skills, prompts into the database (UPSERT)."""
    now = datetime.now(timezone.utc).isoformat()

    # Cleanup legacy incorrect preset records
    await db.execute("DELETE FROM mcp_servers WHERE id IN (?, ?)", ("mcp_server_default", "mcp_server_custom"))
    await db.execute("DELETE FROM knowledge_bases WHERE id IN (?, ?)", ("knowledge_base_default", "knowledge_base_custom"))

    # Seed skills
    for s in BUILTIN_SKILLS:
        await db.execute(
            """INSERT OR REPLACE INTO skills
               (id, name, description, category, content, is_builtin, tags, argument_hint, when_to_use, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM skills WHERE id = ?), ?), ?)""",
            (s["id"], s["name"], s["description"], s["category"], s["content"],
             s["is_builtin"], s["tags"], s.get("argument_hint", ""), s.get("when_to_use", ""),
             s["id"], now, now),
        )

    # Seed prompts
    for p in BUILTIN_PROMPTS:
        await db.execute(
            """INSERT OR REPLACE INTO prompts
               (id, name, description, type, content, is_builtin, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM prompts WHERE id = ?), ?), ?)""",
            (p["id"], p["name"], p["description"], p["type"], p["content"],
             p["is_builtin"], p["tags"],
             p["id"], now, now),
        )

    # Seed MCP templates
    for server in BUILTIN_MCP_SERVERS:
        await db.execute(
            """INSERT OR REPLACE INTO mcp_servers
               (id, name, command, args, env, auto_start, status, tools_count, tools, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM mcp_servers WHERE id = ?), ?), ?)""",
            (
                server["id"],
                server["name"],
                server["command"],
                json.dumps(server["args"]),
                json.dumps(server["env"]),
                server["auto_start"],
                server["status"],
                server["tools_count"],
                json.dumps(server["tools"]),
                server["id"],
                now,
                now,
            ),
        )

    # Seed knowledge base templates
    for kb in BUILTIN_KNOWLEDGE_BASES:
        await db.execute(
            """INSERT OR REPLACE INTO knowledge_bases
               (id, name, description, type, config, doc_count, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM knowledge_bases WHERE id = ?), ?), ?)""",
            (
                kb["id"],
                kb["name"],
                kb["description"],
                kb["type"],
                json.dumps(kb["config"]),
                kb["doc_count"],
                kb["status"],
                kb["id"],
                now,
                now,
            ),
        )

    # Seed workflow presets
    for wf in BUILTIN_WORKFLOWS:
        await db.execute(
            """INSERT OR REPLACE INTO workflows
               (id, name, description, definition, status, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM workflows WHERE id = ?), ?), ?)""",
            (
                wf["id"],
                wf["name"],
                wf["description"],
                json.dumps(wf["definition"]),
                wf["status"],
                json.dumps(wf["tags"]),
                wf["id"],
                now,
                now,
            ),
        )

    await db.commit()
