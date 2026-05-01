# 漫剧 Agent 全功能测试用例

> 测试目标：验证 Agent 的 19 个工具、审批机制、计划续执行、路径传递等核心能力
> 前置条件：后端 8000 + 前端 3000 启动，选择一个 Agent 模型（如 claude-sonnet-4-6）

---

## 工具安全分类一览

| 分类       | 工具名称                                                       | 执行方式     |
|------------|---------------------------------------------------------------|-------------|
| **自动执行** | `read_file`, `list_dir`, `find_files`, `grep_search`, `web_search`, `web_fetch` | 无需确认，直接执行 |
| **需确认**   | `write_file`, `edit_file`, `bash`, `python_exec`, `http_request`, `generate_image`, `generate_image_with_face`, `edit_image`, `image_to_video`, `upscale_image`, `text_to_speech`, `merge_media`, `add_subtitle` | 弹出黄色确认卡，用户点「批准执行」后才执行 |

---

## 测试用例 1: 自动执行 vs 需确认

### 输入
```
帮我完成以下任务：先用 web_search 搜索"退婚流短剧"的流行元素，然后把搜索结果要点写入一个文件 search_result.md，最后根据要点生成一张退婚场景的仙侠风格图片。
```

### 预期行为
| 步骤 | Agent 动作 | 预期 UI |
|------|-----------|---------|
| 1 | 输出简短计划（2-3行） + 调用 `web_search` | ✅ 自动执行，不弹确认卡 |
| 2 | 调用 `write_file` 写入搜索结果 | ⚠️ **弹黄色确认卡**，显示文件名和内容预览 |
| 3 | 调用 `generate_image` 生成仙侠图 | ⚠️ **弹黄色确认卡**，显示 prompt 和风格 |
| 4 | 输出总结 | 聊天区展示生成的图片 |

### 验证点
- [ ] `web_search` 无确认卡（AUTO_APPROVE_TOOLS 生效）
- [ ] `write_file` 有确认卡
- [ ] `generate_image` 有确认卡
- [ ] 批准后工具正常执行，结果正确返回

---

## 测试用例 2: 拒绝执行

### 输入
```
帮我生成一张赛博朋克风格的城市夜景图片
```

### 操作
- 当 `generate_image` 确认卡弹出时，**点击「❌ 拒绝」**

### 预期行为
- Agent 收到 "用户拒绝执行" 反馈
- Agent 输出文字说明已取消/被拒绝，询问是否需要调整
- **不崩溃，不卡死**

### 验证点
- [ ] 拒绝后 Agent 正常响应
- [ ] Agent 不会重复尝试被拒绝的操作
- [ ] 对话可以正常继续

---

## 测试用例 3: 多步骤链式任务（路径传递）

### 输入
```
生成一张仙侠风格的退婚宴会场景图片，然后把这张图片转成动态视频，最后给视频配上旁白"三年之约已到，今日退婚！"
```

### 预期行为
| 步骤 | Agent 动作 | 关键验证 |
|------|-----------|---------|
| 1 | 调用 `generate_image` | 确认卡弹出，批准后生成图片 |
| 2 | 调用 `image_to_video`，`source_image` 使用上一步的 `image_path` | **绝对路径传递正确**（非 /uploads/... URL） |
| 3 | 调用 `text_to_speech`，文本为旁白 | 确认卡弹出，批准后生成音频 |

### 验证点
- [ ] Agent 使用 `image_path`（绝对路径）而非 `image_url` 作为下一步输入
- [ ] 三个工具依次弹出确认卡
- [ ] 每步结果正确链接到下一步

---

## 测试用例 4: 只读工具全自动（无确认卡）

### 输入
```
帮我看看当前目录下有哪些文件，然后读取 README.md 的内容
```

### 预期行为
| 步骤 | Agent 动作 | 预期 UI |
|------|-----------|---------|
| 1 | 调用 `list_dir` | ✅ 自动执行 |
| 2 | 调用 `read_file` 读取 README.md | ✅ 自动执行 |

### 验证点
- [ ] 全程无确认卡弹出
- [ ] 文件列表和内容正确展示

---

## 测试用例 5: 计划续执行机制

### 输入
```
帮我完成一个复杂任务：
1. 写一个 Python 脚本计算 1 到 100 的质数
2. 用 python_exec 执行这个脚本
3. 把结果写入 primes.txt
```

### 预期行为
- 如果 Agent 只输出文字计划而不调用工具 → 系统自动注入续执行提示 + `tool_choice=required`
- 聊天区应出现 "🔄 检测到计划未执行，强制 Agent 调用工具..." 提示
- Agent 随后被强制调用工具开始执行

### 验证点
- [ ] 不会出现"光说不做"的情况
- [ ] 如果触发续执行，thinking 区域有提示
- [ ] 最终所有步骤完成

---

## 测试用例 6: Shell 命令执行

### 输入
```
帮我用 bash 查看当前系统的 Python 版本和磁盘使用情况
```

### 预期行为
| 步骤 | Agent 动作 | 预期 UI |
|------|-----------|---------|
| 1 | 调用 `bash` (command: `python --version`) | ⚠️ 弹确认卡 |
| 2 | 调用 `bash` (command: `df -h`) | ⚠️ 弹确认卡 |

### 验证点
- [ ] bash 命令需要确认
- [ ] 命令执行结果正确返回
- [ ] 不会执行危险命令（如 rm -rf）

---

## 测试用例 7: Python 代码执行

### 输入
```
用 python_exec 帮我计算一下斐波那契数列的前 20 项
```

### 预期行为
- `python_exec` 确认卡弹出，显示代码内容
- 批准后执行，返回计算结果

### 验证点
- [ ] 确认卡中可以看到将要执行的代码
- [ ] 执行结果正确
- [ ] 超时保护生效（默认 60s）

---

## 测试用例 8: 图片编辑

### 前置
先执行测试用例 3 生成一张图片

### 输入
```
把刚才生成的图片修改为夜晚场景，增加月亮和星空
```

### 预期行为
- Agent 调用 `edit_image`，使用之前图片的路径
- 确认卡弹出，显示编辑指令

### 验证点
- [ ] Agent 正确引用上下文中的图片路径
- [ ] edit_image 确认卡显示编辑内容
- [ ] 编辑结果展示

---

## 测试用例 9: 文件编辑（精确替换）

### 前置
先执行测试用例 1 生成 search_result.md

### 输入
```
读取 search_result.md，把里面的"退婚流"替换为"逆袭流"
```

### 预期行为
| 步骤 | Agent 动作 | 预期 UI |
|------|-----------|---------|
| 1 | 调用 `read_file` | ✅ 自动执行 |
| 2 | 调用 `edit_file` | ⚠️ 弹确认卡，显示 old_string 和 new_string |

### 验证点
- [ ] read_file 自动执行
- [ ] edit_file 需确认，替换内容清晰可见
- [ ] 替换正确执行

---

## 测试用例 10: HTTP 请求

### 输入
```
帮我发一个 GET 请求到 https://httpbin.org/get 看看返回什么
```

### 预期行为
- `http_request` 确认卡弹出
- 返回 httpbin 的响应数据

### 验证点
- [ ] http_request 需要确认
- [ ] 响应数据正确展示

---

## 测试用例 11: 端到端短剧生成（终极测试）

### 输入
```
生成一个退婚流小说开头场景的短视频：
- 场景描述：豪门宴会厅，男主角站在大厅中央，冷漠地宣读退婚书
- 需要：一张仙侠风格的场景图 → 转成 5 秒动态视频 → 配上旁白音频
```

### 预期行为
| 步骤 | Agent 动作 | 确认 |
|------|-----------|------|
| 1 | 简要计划 + 调用 `generate_image` | ⚠️ 确认 |
| 2 | 调用 `image_to_video`（用上步 image_path） | ⚠️ 确认 |
| 3 | 调用 `text_to_speech`（生成旁白） | ⚠️ 确认 |
| 4 | 输出总结，展示所有生成物 | 图片+视频+音频 |

### 验证点
- [ ] 三步链式工具调用全部成功
- [ ] 路径传递正确
- [ ] 所有媒体在聊天中正确预览
- [ ] Agent 不卡死、不空转

---

## 通用验证项

### 审批机制
- [ ] 黄色确认卡正确显示工具名称和参数
- [ ] 点「✅ 批准执行」后工具开始执行
- [ ] 点「❌ 拒绝」后 Agent 收到反馈并正常继续
- [ ] 超时 5 分钟自动拒绝
- [ ] 按钮点击后变为「已批准」/「已拒绝」状态

### 计划续执行
- [ ] Agent 输出计划无工具调用时触发强制续执行
- [ ] thinking 区域显示 "🔄 检测到计划未执行" 提示
- [ ] 续执行后 Agent 正确调用工具

### 路径传递
- [ ] generate_image 返回 image_path（绝对路径）
- [ ] image_to_video 使用绝对路径作为 source_image
- [ ] Agent 不会误用 /uploads/... URL 作为工具输入

### 异常处理
- [ ] 工具执行失败时 Agent 给出错误说明
- [ ] WebSocket 断开重连不影响审批队列
- [ ] 达到最大轮次（10轮）时生成最终摘要

---

## 测试用例 12: 纯聊天（不调工具）

### 输入
```
你好，请简单介绍一下你自己？
```

### 预期行为
- Agent 直接友好回复，**不调用任何工具**
- 回复中应提及自己是"漫剧 Agent"或类似角色名

### 验证点
- [ ] 无 tool_start / tool_done 事件
- [ ] delta 事件输出纯文字回复
- [ ] 回复内容合理（含角色介绍）

---

## 测试用例 13: list_dir 自动执行

### 输入
```
列出 /tmp 目录下的文件
```

### 预期行为
- Agent 调用 `list_dir`，path 参数为 `/tmp`
- 自动执行，无确认卡

### 验证点
- [ ] list_dir 无确认卡（AUTO_APPROVE_TOOLS 生效）
- [ ] 返回文件列表

---

## 测试用例 14: read_file 自动执行

### 输入
```
读取 /Users/zjj/home/learn26/ttsapp/README.md 的内容
```

### 预期行为
- Agent 调用 `read_file`，自动执行
- 返回文件内容

### 验证点
- [ ] read_file 自动执行
- [ ] 内容正确返回

---

## 测试用例 15: web_search 自动执行

### 输入
```
搜索一下"2026年最热门的AI工具"
```

### 预期行为
- Agent 调用 `web_search`，自动执行
- 返回搜索结果摘要

### 验证点
- [ ] web_search 自动执行
- [ ] 搜索结果正确展示

---

## 测试用例 16: python_exec 数学计算

### 输入
```
用 python_exec 计算 1 到 100 的所有偶数之和
```

### 预期行为
- Agent 调用 `python_exec`，执行 Python 代码
- 确认卡弹出（auto_mode 下自动批准）
- 返回结果 2550

### 验证点
- [ ] python_exec 被调用
- [ ] 计算结果正确（2550）

---

## 测试用例 17: write_file + read_file 往返

### 输入
```
写一首关于春天的五言绝句到 /tmp/agent_test_poem.txt，写完后再读取出来确认内容
```

### 预期行为
| 步骤 | Agent 动作 | 预期 |
|------|-----------|------|
| 1 | 调用 `write_file` | 写入诗句 |
| 2 | 调用 `read_file` | 读回确认 |

### 验证点
- [ ] write_file 成功执行
- [ ] read_file 自动执行
- [ ] 读回内容与写入内容一致

---

## 测试用例 18: grep_search 搜索代码

### 输入
```
在 /Users/zjj/home/learn26/ttsapp/backend/app 目录下搜索包含 "execute_tool" 的代码
```

### 预期行为
- Agent 调用 `grep_search`，自动执行
- 返回匹配结果

### 验证点
- [ ] grep_search 自动执行
- [ ] 结果包含 tool_executor.py 和 agent_runner.py 的匹配行

---

## 测试用例 19: find_files 模式匹配

### 输入
```
搜索 /Users/zjj/home/learn26/ttsapp/backend 下所有 .py 文件
```

### 预期行为
- Agent 调用 `find_files`，pattern 为 `**/*.py`
- 自动执行，返回文件列表

### 验证点
- [ ] find_files 自动执行
- [ ] 结果包含 .py 文件列表

---

## 测试用例 20: bash 系统信息查询

### 输入
```
用 bash 查看当前的日期时间和系统的 hostname
```

### 预期行为
- Agent 调用 `bash`，执行 date 和 hostname 命令
- 需确认（auto_mode 下可自动批准只读命令）

### 验证点
- [ ] bash 命令执行成功
- [ ] 返回日期和 hostname 信息

---

## 测试用例 21: edit_file 精确替换

### 输入
```
先写入内容 "Hello World 你好世界" 到 /tmp/agent_test_edit.txt，然后把 "Hello World" 替换为 "Goodbye World"
```

### 预期行为
| 步骤 | Agent 动作 | 预期 |
|------|-----------|------|
| 1 | 调用 `write_file` | 写入原始内容 |
| 2 | 调用 `edit_file` | old_string="Hello World", new_string="Goodbye World" |

### 验证点
- [ ] write_file 成功
- [ ] edit_file 确认卡弹出，替换正确
- [ ] 文件内容变为 "Goodbye World 你好世界"

---

## 测试用例 22: http_request GET

### 输入
```
发一个 GET 请求到 https://httpbin.org/get 看看响应
```

### 预期行为
- Agent 调用 `http_request`，method=GET
- 确认卡弹出，返回 httpbin 响应

### 验证点
- [ ] http_request 需确认
- [ ] 响应包含 status_code 200

---

## 测试用例 23: 多工具链式组合

### 输入
```
先搜索"Python asyncio教程"，然后把搜索结果的标题列表写入 /tmp/agent_test_asyncio.txt，最后读取文件确认
```

### 预期行为
| 步骤 | Agent 动作 | 工具类型 |
|------|-----------|---------|
| 1 | `web_search` | ✅ 自动 |
| 2 | `write_file` | ⚠️ 确认 |
| 3 | `read_file` | ✅ 自动 |

### 验证点
- [ ] 三个工具依次调用
- [ ] web_search 自动执行
- [ ] write_file 需确认
- [ ] read_file 自动执行
- [ ] 文件内容包含搜索结果

---

## 测试用例 24: 复杂 Python 数据处理

### 输入
```
用 python_exec 生成一个 5x5 的乘法表并格式化输出
```

### 预期行为
- Agent 调用 `python_exec`，执行乘法表代码
- 返回格式化的乘法表

### 验证点
- [ ] python_exec 执行成功
- [ ] 输出包含正确的乘法表

---

## 测试用例 25: 异常处理 - 读取不存在的文件

### 输入
```
读取文件 /tmp/this_file_definitely_does_not_exist_xyz.txt
```

### 预期行为
- Agent 调用 `read_file`
- 工具返回错误信息
- Agent 向用户说明文件不存在

### 验证点
- [ ] Agent 不崩溃
- [ ] Agent 给出文件不存在的错误说明
- [ ] 对话可以正常继续

---

## 测试用例 26: 异常处理 - 编辑不存在的内容

### 输入
```
先写入 "测试内容ABC" 到 /tmp/agent_test_err.txt，然后把 "不存在的内容XYZ" 替换为 "新内容"
```

### 预期行为
- write_file 成功
- edit_file 返回错误（old_string 不存在）
- Agent 向用户说明替换失败

### 验证点
- [ ] Agent 正确处理 edit_file 错误
- [ ] 不重复调用失败的操作
- [ ] 给出合理的错误说明

---

## 测试用例 27: 模糊意图识别

### 输入
```
帮我做个东西
```

### 预期行为
- Agent 不应直接调用工具
- 应询问用户具体需求

### 验证点
- [ ] 无工具调用
- [ ] Agent 提出反问或请求更多信息

---

## 测试用例 28: 大量文本写入

### 输入
```
用 python_exec 生成一段 500 字的 Lorem Ipsum 文本，然后用 write_file 写入 /tmp/agent_test_lorem.txt
```

### 预期行为
| 步骤 | Agent 动作 |
|------|-----------|
| 1 | `python_exec` 生成文本 |
| 2 | `write_file` 写入文件 |

### 验证点
- [ ] python_exec 成功生成文本
- [ ] write_file 成功写入
- [ ] 文件字节数 > 0

---

## 测试用例 29: bash 管道命令

### 输入
```
用 bash 执行 echo "hello world" | wc -c 统计字符数
```

### 预期行为
- Agent 调用 `bash`，执行管道命令
- 返回字符计数结果（12）

### 验证点
- [ ] bash 执行管道命令成功
- [ ] stdout 包含字符计数

---

## 测试用例 30: 多步依赖传递

### 输入
```
1. 用 python_exec 生成一个随机数并输出
2. 把 python 的输出结果写入 /tmp/agent_test_random.txt
3. 读取文件确认内容
```

### 预期行为
| 步骤 | Agent 动作 | 关键验证 |
|------|-----------|---------|
| 1 | `python_exec` | 生成随机数 |
| 2 | `write_file` | 使用 python 输出的数字 |
| 3 | `read_file` | 验证内容 |

### 验证点
- [ ] 三步链式执行
- [ ] Agent 正确传递 python 输出结果到 write_file
- [ ] 文件内容包含随机数

---

## 测试用例 31: 工具选择准确性

### 输入
```
看看 /Users/zjj/home/learn26/ttsapp/backend 这个目录有什么文件，然后在里面搜索包含 "import asyncio" 的文件
```

### 预期行为
| 步骤 | Agent 动作 | 工具类型 |
|------|-----------|---------|
| 1 | `list_dir` | ✅ 自动 |
| 2 | `grep_search` 或 `find_files` | ✅ 自动 |

### 验证点
- [ ] Agent 选择正确的工具
- [ ] 两个工具都自动执行（均为 L0）
- [ ] 搜索结果正确
