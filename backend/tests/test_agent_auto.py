#!/usr/bin/env python3
"""
漫剧 Agent 全功能自动化测试脚本
- 80 个用例 (12-91)，覆盖通用工具、漫剧工具、远程工作流、链式调用、意图理解
- 通过 8 个漫剧工具测试 79 个远程 ComfyUI 工作流模板 (t2i/edit/i2v/t2v/face/upscale/audio)
- 生成 JSON + Markdown 测试报告
"""

import asyncio
import json
import time
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import httpx
import websockets

# ═══════════════════ 配置 ═══════════════════

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
API_PREFIX = "/api/v1"
USERNAME = "zjjzjw"
PASSWORD = "zjjzjwQQ11"
MODEL_ID = "claude-opus-4-6"  # Agent 大脑模型
TIMEOUT_PER_MSG = 300  # 单条 WS 消息最长等待秒数（ComfyUI 视频生成可达 3-5 分钟）
TIMEOUT_PER_TEST = 600  # 整个测试用例的全局超时（多步流水线）
MAX_TOOL_CALLS_ABORT = 15  # 工具调用次数超过此值提前终止（防失控循环）
REPORT_DIR = "/tmp/agent_test_reports"


# ═══════════════════ 数据结构 ═══════════════════

@dataclass
class TestCase:
    id: int
    name: str
    message: str
    expect_tools: list[str]  # 预期调用的工具名列表（空=不应调工具）
    expect_no_tools: bool = False  # 预期不调用任何工具
    expect_error_handling: bool = False  # 预期 Agent 处理工具错误
    expect_keywords: list[str] = field(default_factory=list)  # 预期回复中包含的关键词
    expect_tool_count_min: int = 0  # 最少工具调用次数
    expect_tool_count_max: int = 20  # 最多工具调用次数


@dataclass
class TestResult:
    test_id: int
    test_name: str
    status: str = "pending"  # pass / fail / error / timeout
    duration_s: float = 0.0
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    agent_text: str = ""
    thinking_text: str = ""
    events: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)  # 各项检查结果
    # ── 新增评测维度 ──
    first_tool_delay_s: float = 0.0  # 从发送消息到第一个 tool_start 的延迟
    event_type_counts: dict = field(default_factory=dict)  # 各事件类型计数
    bash_calls: int = 0  # bash 调用次数
    continuation_triggers: int = 0  # 续行/降级触发次数
    efficiency_score: float = 0.0  # 工具调用效率 (1.0=最优)
    timing_score: float = 0.0  # 耗时评分 (1.0=30s基准)


# ═══════════════════ 测试用例定义 ═══════════════════

TEST_CASES = [
    TestCase(
        id=12, name="纯聊天（不调工具）",
        message="你好，请简单介绍一下你自己？",
        expect_tools=[], expect_no_tools=True,
        expect_keywords=["漫剧", "Agent", "助手", "创作", "图片", "视频"],
    ),
    TestCase(
        id=13, name="list_dir 自动执行",
        message="列出 /tmp 目录下的文件",
        expect_tools=["list_dir"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=14, name="read_file 自动执行",
        message="读取 /Users/zjj/home/learn26/ttsapp/README.md 的内容",
        expect_tools=["read_file"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=15, name="web_search 自动执行",
        message='搜索一下"2026年最热门的AI工具"',
        expect_tools=["web_search"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=16, name="python_exec 数学计算",
        message="用 python_exec 计算 1 到 100 的所有偶数之和",
        expect_tools=["python_exec"],
        expect_keywords=["2550"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=17, name="write_file + read_file 往返",
        message="写一首关于春天的五言绝句到 /tmp/agent_test_poem.txt，写完后再读取出来确认内容",
        expect_tools=["write_file", "read_file"],
        expect_tool_count_min=2,
    ),
    TestCase(
        id=18, name="grep_search 搜索代码",
        message='在 /Users/zjj/home/learn26/ttsapp/backend/app 目录下搜索包含 "execute_tool" 的代码',
        expect_tools=["grep_search"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=19, name="find_files 模式匹配",
        message="搜索 /Users/zjj/home/learn26/ttsapp/backend 下所有 .py 文件",
        expect_tools=["find_files"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=20, name="bash 系统信息查询",
        message="用 bash 查看当前的日期时间和系统的 hostname",
        expect_tools=["bash"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=21, name="edit_file 精确替换",
        message='先写入内容 "Hello World 你好世界" 到 /tmp/agent_test_edit.txt，然后把 "Hello World" 替换为 "Goodbye World"',
        expect_tools=["write_file", "edit_file"],
        expect_tool_count_min=2,
    ),
    TestCase(
        id=22, name="http_request GET",
        message="发一个 GET 请求到 https://httpbin.org/get 看看响应",
        expect_tools=["http_request"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=23, name="多工具链式组合",
        message='先搜索"Python asyncio教程"，然后把搜索结果的标题列表写入 /tmp/agent_test_asyncio.txt，最后读取文件确认',
        expect_tools=["web_search", "write_file", "read_file"],
        expect_tool_count_min=3,
    ),
    TestCase(
        id=24, name="复杂 Python 数据处理",
        message="用 python_exec 生成一个 5x5 的乘法表并格式化输出",
        expect_tools=["python_exec"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=25, name="异常处理 - 读取不存在的文件",
        message="读取文件 /tmp/this_file_definitely_does_not_exist_xyz.txt",
        expect_tools=["read_file"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=26, name="异常处理 - 编辑不存在的内容",
        message='先写入 "测试内容ABC" 到 /tmp/agent_test_err.txt，然后把 "不存在的内容XYZ" 替换为 "新内容"',
        expect_tools=["write_file", "edit_file"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=27, name="模糊意图识别",
        message="帮我做个东西",
        expect_tools=[], expect_no_tools=True,
        expect_keywords=["什么", "需要", "具体", "想", "请"],
    ),
    TestCase(
        id=28, name="大量文本写入",
        message="用 python_exec 生成一段 500 字的 Lorem Ipsum 文本，然后用 write_file 写入 /tmp/agent_test_lorem.txt",
        expect_tools=["python_exec", "write_file"],
        expect_tool_count_min=2,
    ),
    TestCase(
        id=29, name="bash 管道命令",
        message='用 bash 执行 echo "hello world" | wc -c 统计字符数',
        expect_tools=["bash"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=30, name="多步依赖传递",
        message="1. 用 python_exec 生成一个随机数并输出\n2. 把 python 的输出结果写入 /tmp/agent_test_random.txt\n3. 读取文件确认内容",
        expect_tools=["python_exec", "write_file", "read_file"],
        expect_tool_count_min=3,
    ),
    TestCase(
        id=31, name="工具选择准确性",
        message='看看 /Users/zjj/home/learn26/ttsapp/backend 这个目录有什么文件，然后在里面搜索包含 "import asyncio" 的文件',
        expect_tools=["list_dir", "grep_search"],
        expect_tool_count_min=2,
    ),
    # ══════ 第六期新增用例 (32-41) ══════
    TestCase(
        id=32, name="中文问答不调工具",
        message="请问什么是机器学习？用两句话解释一下",
        expect_tools=[], expect_no_tools=True,
        expect_keywords=["学习", "数据", "模型", "算法", "预测"],
    ),
    TestCase(
        id=33, name="英文指令",
        message="Use bash to show the current date and time",
        expect_tools=["bash"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=34, name="读两个文件",
        message="分别读取 /tmp/agent_test_poem.txt 和 /tmp/agent_test_edit.txt 的内容",
        expect_tools=["read_file"],
        expect_tool_count_min=2,
    ),
    TestCase(
        id=35, name="python写文件优先级",
        message="用 python_exec 计算 2 的 10 次方，然后把结果用 write_file 写入 /tmp/agent_test_power.txt",
        expect_tools=["python_exec", "write_file"],
        expect_tool_count_min=2,
    ),
    TestCase(
        id=36, name="web_search 简短查询",
        message='搜索 "FastAPI websocket" 并告诉我第一条结果的标题',
        expect_tools=["web_search"],
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=37, name="write_file 安全路径",
        message='把 "自动化测试内容" 写入 /tmp/agent_test_safe.txt',
        expect_tools=["write_file"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=38, name="闲聊后提问不调工具",
        message="今天天气真好，你觉得呢？",
        expect_tools=[], expect_no_tools=True,
    ),
    TestCase(
        id=39, name="超长消息处理",
        message="请用 python_exec 计算以下表达式的结果: " + " + ".join(str(i) for i in range(1, 51)),
        expect_tools=["python_exec"],
        expect_keywords=["1275"],
        expect_tool_count_min=1,
    ),
    TestCase(
        id=40, name="工具失败后正确处理",
        message="请用 bash 执行命令 nonexistent_command_xyz_12345",
        expect_tools=["bash"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=41, name="三步链式完整执行",
        message="1. 用 python_exec 计算 7 * 8 * 9 的结果\n2. 用 write_file 把计算结果写入 /tmp/agent_test_chain.txt\n3. 用 read_file 读取该文件确认内容",
        expect_tools=["python_exec", "write_file", "read_file"],
        expect_tool_count_min=3,
        expect_keywords=["504"],
    ),
    # ═══════════════════════════════════════════════════════════════
    # 漫剧工具测试 A: 单工具 - 图片生成 (42-48)
    # DB: 79个工作流模板 (t2i=36, edit=22, i2v=9, t2v=5, face=5, upscale=1, audio=1)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=42, name="generate_image 仙侠风格",
        message="生成一张仙侠风格的图片，画面是一个白衣剑仙站在悬崖边",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=43, name="generate_image 动漫风格",
        message="生成一张 anime 风格的少女图片，长发飘逸、樱花背景",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=44, name="generate_image 盲盒Q版",
        message="生成一张盲盒 Q 版风格的可爱小猫角色，大眼睛粉色系",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=45, name="generate_image 水墨风",
        message="生成一张水墨画风格的高山流水图，有亭台楼阁",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=46, name="generate_image 写实风格",
        message="生成一张写实风格的古代城镇街景照片，黄昏光线",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=47, name="generate_image 自定义尺寸",
        message="生成一张 768x512 横版仙侠山水场景图",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=48, name="generate_image Flux风格",
        message="用 flux 风格生成一张高质量的魔法森林图片",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 漫剧工具测试 A: 单工具 - 其他漫剧工具 (49-56)
    # DB: 8个漫剧工具 (generate_image/with_face/edit/i2v/tts/upscale/merge/subtitle)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=49, name="generate_image_with_face 人脸保持",
        message="用参考人脸图片 /tmp/test_face.png 生成一张仙侠风格的角色图，保持面部特征",
        expect_tools=["generate_image_with_face"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=50, name="edit_image 编辑指令",
        message="把图片 /uploads/agent_outputs/test.png 的背景改成星空",
        expect_tools=["edit_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=51, name="image_to_video 图生视频",
        message="把图片 /uploads/agent_outputs/test.png 转成动态视频，人物微微点头",
        expect_tools=["image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=52, name="text_to_speech 基础语音",
        message="把这段文字转成语音：'欢迎来到仙侠世界，这里是九天之上的灵霄宝殿'",
        expect_tools=["text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=53, name="text_to_speech 指定声色",
        message="用女声把'今天天气真好，适合修炼'合成语音",
        expect_tools=["text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=54, name="upscale_image 图像超分",
        message="把图片 /uploads/agent_outputs/test.png 做超分辨率放大 2 倍",
        expect_tools=["upscale_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=55, name="add_subtitle 字幕叠加",
        message="在视频 /uploads/agent_outputs/test.mp4 上添加字幕，第0-3秒显示'第一话'，第3-6秒显示'退婚大殿'",
        expect_tools=["add_subtitle"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=56, name="merge_media 媒体合成",
        message="把 /uploads/agent_outputs/f1.png 和 /uploads/agent_outputs/f2.png 两张图合成为一个视频",
        expect_tools=["merge_media"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 漫剧工具测试 B: 多工具流水线 (57-63)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=57, name="写台词+配音流水线",
        message="先用 write_file 把台词'吾乃九天之主，今日便要退婚！'写入 /tmp/agent_test_lines.txt，然后用 text_to_speech 把这段台词合成语音",
        expect_tools=["write_file", "text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=58, name="搜索灵感+生图",
        message="先用 web_search 搜索'退婚流短剧经典场景'，然后根据搜索结果生成一张仙侠风格的退婚场景图片",
        expect_tools=["web_search", "generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=59, name="生图+超分流水线",
        message="先生成一张仙侠少女图片，然后对生成的图片做 2 倍超分放大",
        expect_tools=["generate_image", "upscale_image"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=60, name="生图+编辑流水线",
        message="先生成一张仙侠山水图，然后把图中的天空编辑为星空效果",
        expect_tools=["generate_image", "edit_image"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=61, name="生图+视频流水线",
        message="先用 generate_image 生成一张仙侠少女图片，然后用 image_to_video 把它变成动态视频",
        expect_tools=["generate_image", "image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=62, name="完整漫剧1话流水线",
        message="制作漫剧第一话：1.生成一张退婚场景的仙侠图片 2.配旁白语音'今日，我要退婚！' 请依次完成",
        expect_tools=["generate_image", "text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=63, name="写脚本+生图",
        message="先用 python_exec 生成一段短剧脚本（第一幕退婚场景的描述），然后根据脚本内容生成一张匹配的仙侠图片",
        expect_tools=["python_exec", "generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 漫剧工具测试 C: 错误处理与边界 (64-68)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=64, name="漫剧工具错误恢复",
        message="对不存在的图片 /tmp/nonexistent_12345.png 做超分放大",
        expect_tools=["upscale_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=65, name="模糊生图指令需询问",
        message="帮我画一张图",
        expect_tools=[],
        expect_no_tools=True,
        expect_keywords=["什么", "描述", "风格", "具体", "想", "需要"],
    ),
    TestCase(
        id=66, name="非漫剧绘图不用generate_image",
        message="帮我画一个简单的系统架构流程图，用文字描述就行",
        expect_tools=[],
        expect_no_tools=True,
    ),
    TestCase(
        id=67, name="漫剧数量控制只生1张",
        message="生成 1 张动漫风格的星空图片，只要1张",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=68, name="风格参数识别blindbox",
        message="用 blindbox 风格生成一只可爱的独角兽",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 漫剧工具测试 D: 意图理解 (69-71)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=69, name="场景描述→选择生图",
        message="我想要这样一个画面：夕阳西下，一个红衣女侠背对镜头，手持长剑，远处是连绵山脉。请帮我实现",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=70, name="语音需求→选择TTS",
        message="帮我生成一段旁白音频，内容是'在九天之上，有一座名为灵霄的宝殿'",
        expect_tools=["text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=71, name="模糊漫剧指令需询问",
        message="帮我做一集短剧",
        expect_tools=[],
        expect_no_tools=True,
        expect_keywords=["什么", "主题", "故事", "剧情", "具体", "角色", "场景"],
    ),
    # ═══════════════════════════════════════════════════════════════
    # 远程工作流覆盖 E: 更多 t2i 风格 → 触发不同远程 ComfyUI 工作流 (72-76)
    # DB: 36个t2i模板, 风格 hidream/qwen/sdxl/sd15/zimage 等
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=72, name="generate_image HiDream风格→HiDream-i1文生图",
        message="用 hidream 风格生成一张梦幻城堡的图片",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=73, name="generate_image Qwen风格→Qwen-Image文生图",
        message="用 qwen 风格生成一张古风庭院的图片",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=74, name="generate_image SDXL风格→SDXL-文生图",
        message="用 sdxl 风格生成一张壮观的龙腾云海图",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=75, name="generate_image SD15风格→SD15-简单文生图",
        message="用 sd15 风格生成一张简约风格的花卉静物图",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    TestCase(
        id=76, name="generate_image Z-Image风格→Z-Image-Turbo文生图",
        message="用 zimage 风格生成一张极简线条风格的人物肖像",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=1, expect_tool_count_max=3,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 远程工作流覆盖 F: edit 工作流变体 (77-79)
    # DB: 22个edit模板, 含 Flux-fill/Flux2/Qwen/HiDream/Kontext 等
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=77, name="edit_image Flux风格→Flux2图像编辑",
        message="用 flux 风格编辑图片 /uploads/agent_outputs/test.png，把人物衣服改成蓝色",
        expect_tools=["edit_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=78, name="edit_image Qwen材质替换→Qwen-Edit2511",
        message="用 qwen 风格对图片 /uploads/agent_outputs/test.png 做材质替换，将木质背景替换为大理石",
        expect_tools=["edit_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=79, name="edit_image 默认编辑→qwen_edit",
        message="编辑图片 /uploads/agent_outputs/test.png，在画面右上角添加一轮明月",
        expect_tools=["edit_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 远程工作流覆盖 G: i2v / t2v 视频工作流 (80-84)
    # DB: i2v=9, t2v=5 (Wan/LTX/动漫/透明底 等)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=80, name="image_to_video Wan风格→Wan2.2图生视频",
        message="用 wan 风格把图片 /uploads/agent_outputs/test.png 转成视频，人物缓缓转头",
        expect_tools=["image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=81, name="image_to_video LTX风格→LTX2图生视频",
        message="用 ltx 风格把图片 /uploads/agent_outputs/test.png 转成流畅的动态视频",
        expect_tools=["image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=82, name="文生视频 Wan→Wan2.2文生视频",
        message="直接从文字描述生成一段视频：一个白衣仙人在云端御剑飞行，镜头缓缓后拉",
        expect_tools=["generate_image", "image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=83, name="文生视频 动漫风→WAN动漫工作流",
        message="生成一段动漫风格的短视频：樱花飘落的校园，一个少女在奔跑",
        expect_tools=["generate_image", "image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=84, name="文生视频 LTX风格→LTX2文生视频",
        message="用 ltx 风格生成一段视频，画面是星空下的湖面倒影缓缓荡漾",
        expect_tools=["generate_image", "image_to_video"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 远程工作流覆盖 H: face / upscale 工作流 (85-87)
    # DB: face=5 (SD15/SDXL/仙侠), upscale=1 (SeedVR2)
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=85, name="generate_image_with_face SDXL→SDXL-InstantID",
        message="用 /tmp/test_face.png 作为参考人脸，用 sdxl 风格生成一张古装将军的全身像",
        expect_tools=["generate_image_with_face"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=86, name="generate_image_with_face SD15→SD15面部重绘",
        message="用 /tmp/test_face.png 参考人脸，用 sd15 风格重新生成一张面部细节增强的肖像画",
        expect_tools=["generate_image_with_face"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    TestCase(
        id=87, name="upscale_image→SeedVR2超分放大",
        message="把图片 /uploads/agent_outputs/test.png 用超分辨率模型放大到 2 倍清晰度",
        expect_tools=["upscale_image"],
        expect_error_handling=True,
        expect_tool_count_min=1,
    ),
    # ═══════════════════════════════════════════════════════════════
    # 远程工作流覆盖 I: 多工具端到端流水线 (88-91)
    # 验证: 工具→远程工作流→结果传递→下一工具→远程工作流 的完整链路
    # ═══════════════════════════════════════════════════════════════
    TestCase(
        id=88, name="生图→编辑→超分 三步远程工作流链",
        message="1.用仙侠风格生成一张剑仙图片 2.把生成的图片背景编辑为星空 3.对编辑后的图做2倍超分。请依次完成三步",
        expect_tools=["generate_image", "edit_image", "upscale_image"],
        expect_error_handling=True,
        expect_tool_count_min=3,
    ),
    TestCase(
        id=89, name="生图→视频→配音 三步远程工作流链",
        message="1.用动漫风格生成一张魔法少女图 2.把图片转成动态视频 3.配旁白语音'魔法启动！' 请依次完成",
        expect_tools=["generate_image", "image_to_video", "text_to_speech"],
        expect_error_handling=True,
        expect_tool_count_min=3,
    ),
    TestCase(
        id=90, name="多风格对比: 仙侠vs动漫同一场景",
        message="分别用仙侠风格和动漫风格各生成一张'少女在月下舞剑'的图片，用于对比两种风格",
        expect_tools=["generate_image"],
        expect_error_handling=True,
        expect_tool_count_min=2,
    ),
    TestCase(
        id=91, name="完整漫剧制作: 脚本→生图→编辑→配音→字幕",
        message="制作一个退婚短剧片段：1.用python写一段退婚台词 2.生成退婚大殿的仙侠图片 3.给图片加上闪电特效 4.把台词转成语音 5.在视频上添加字幕。请依次完成所有步骤",
        expect_tools=["python_exec", "generate_image", "edit_image", "text_to_speech", "add_subtitle"],
        expect_error_handling=True,
        expect_tool_count_min=4,
    ),
]


# ═══════════════════ 工具函数 ═══════════════════

async def login() -> str:
    """登录获取 JWT token"""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def run_single_test(token: str, tc: TestCase) -> TestResult:
    """运行单个测试用例"""
    result = TestResult(test_id=tc.id, test_name=tc.name)
    start = time.time()

    try:
        result = await asyncio.wait_for(
            _run_single_test_inner(token, tc, result, start),
            timeout=TIMEOUT_PER_TEST,
        )
    except asyncio.TimeoutError:
        result.status = "timeout"
        result.errors.append(f"全局超时 ({TIMEOUT_PER_TEST}s)")
        result.duration_s = round(time.time() - start, 2)
    except Exception as e:
        result.status = "error"
        result.errors.append(str(e))
        result.duration_s = round(time.time() - start, 2)

    return result


async def _run_single_test_inner(token: str, tc: TestCase, result: TestResult, start: float) -> TestResult:
    """实际执行逻辑，被全局超时包裹"""
    ws_endpoint = f"{WS_URL}{API_PREFIX}/comic-agent/ws/chat?conversation_id=0&token={token}"

    try:
        async with websockets.connect(ws_endpoint, max_size=10 * 1024 * 1024) as ws:
            # 等待 conversation_created 事件
            first_msg = await asyncio.wait_for(ws.recv(), timeout=10)
            first_data = json.loads(first_msg)
            if first_data.get("type") == "conversation_created":
                result.events.append(first_data)

            # 发送测试消息
            await ws.send(json.dumps({
                "message": tc.message,
                "model": MODEL_ID,
                "auto_mode": True,
            }))

            # 收集所有事件，直到 done 或超时
            agent_done = False
            delta_parts = []
            thinking_parts = []
            event_counts: dict[str, int] = {}
            msg_sent_time = time.time()
            first_tool_time = 0.0

            while not agent_done:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=TIMEOUT_PER_MSG)
                    event = json.loads(raw)
                    result.events.append(event)
                    etype = event.get("type", "")
                    event_counts[etype] = event_counts.get(etype, 0) + 1

                    if etype == "delta":
                        delta_parts.append(event.get("content", ""))
                    elif etype == "thinking":
                        content = event.get("content", "")
                        thinking_parts.append(content)
                        # 统计续行/降级触发
                        if any(kw in content for kw in ["强制", "续行", "降级", "force"]):
                            result.continuation_triggers += 1
                    elif etype == "tool_start":
                        tool_name = event.get("tool", "")
                        result.tools_called.append(tool_name)
                        if tool_name == "bash":
                            result.bash_calls += 1
                        if not first_tool_time:
                            first_tool_time = time.time()
                    elif etype == "tool_done":
                        result.tool_results.append({
                            "tool": event.get("tool", ""),
                            "result": event.get("result", ""),
                        })
                    elif etype == "tool_confirm":
                        # 自动批准所有工具确认
                        await ws.send(json.dumps({"action": "approve"}))
                        tool_name = event.get("tool", "")
                        result.tools_called.append(tool_name)
                        if tool_name == "bash":
                            result.bash_calls += 1
                        if not first_tool_time:
                            first_tool_time = time.time()
                    elif etype == "done":
                        agent_done = True
                    elif etype == "error":
                        result.errors.append(event.get("content", ""))
                        agent_done = True

                except asyncio.TimeoutError:
                    result.status = "timeout"
                    result.errors.append(f"单消息超时 ({TIMEOUT_PER_MSG}s)")
                    break

                # 工具调用次数超限提前终止
                if len(result.tools_called) >= MAX_TOOL_CALLS_ABORT and not agent_done:
                    result.errors.append(f"工具调用达 {MAX_TOOL_CALLS_ABORT} 次，提前终止")
                    break

            result.agent_text = "".join(delta_parts)
            result.thinking_text = "".join(thinking_parts)
            result.duration_s = round(time.time() - start, 2)
            result.event_type_counts = event_counts
            result.first_tool_delay_s = round(first_tool_time - msg_sent_time, 2) if first_tool_time else 0.0
            result.timing_score = round(min(30.0 / max(result.duration_s, 0.1), 2.0), 2)

            if result.status != "timeout":
                # 运行验证逻辑
                _validate(tc, result)

    except Exception as e:
        result.status = "error"
        result.errors.append(str(e))
        result.duration_s = round(time.time() - start, 2)

    return result


def _validate(tc: TestCase, result: TestResult):
    """验证测试结果"""
    checks = {}
    all_pass = True

    # 1. 检查是否不应调工具
    if tc.expect_no_tools:
        no_tool = len(result.tools_called) == 0
        checks["no_tools"] = {
            "expected": "不调用任何工具",
            "actual": f"调用了 {len(result.tools_called)} 个工具: {result.tools_called}" if result.tools_called else "无工具调用",
            "pass": no_tool,
        }
        if not no_tool:
            all_pass = False

    # 2. 检查预期工具是否被调用
    if tc.expect_tools:
        called_set = set(result.tools_called)
        expected_set = set(tc.expect_tools)
        missing = expected_set - called_set
        tools_ok = len(missing) == 0
        checks["expected_tools"] = {
            "expected": list(tc.expect_tools),
            "actual": result.tools_called,
            "missing": list(missing),
            "pass": tools_ok,
        }
        if not tools_ok:
            all_pass = False

    # 3. 检查工具调用次数范围
    if tc.expect_tool_count_min > 0:
        count = len(result.tools_called)
        count_ok = tc.expect_tool_count_min <= count <= tc.expect_tool_count_max
        checks["tool_count"] = {
            "expected_range": f"[{tc.expect_tool_count_min}, {tc.expect_tool_count_max}]",
            "actual": count,
            "pass": count_ok,
        }
        if not count_ok:
            all_pass = False

    # 4. 检查关键词
    if tc.expect_keywords:
        text = result.agent_text.lower()
        found = [kw for kw in tc.expect_keywords if kw.lower() in text]
        # 宽松检查：至少命中一个关键词即可
        kw_ok = len(found) > 0
        checks["keywords"] = {
            "expected_any_of": tc.expect_keywords,
            "found": found,
            "pass": kw_ok,
        }
        if not kw_ok:
            all_pass = False

    # 5. 检查异常处理
    if tc.expect_error_handling:
        # 检查工具结果中是否有错误，且 Agent 没有崩溃
        has_tool_error = any(
            "error" in (tr.get("result", "") or "").lower()
            or "错误" in (tr.get("result", "") or "")
            or "未找到" in (tr.get("result", "") or "")
            or "不存在" in (tr.get("result", "") or "")
            for tr in result.tool_results
        )
        agent_responded = len(result.agent_text) > 0
        err_ok = agent_responded  # Agent 至少给出了回复
        checks["error_handling"] = {
            "has_tool_error": has_tool_error,
            "agent_responded": agent_responded,
            "pass": err_ok,
        }
        if not err_ok:
            all_pass = False

    # 6. 检查无系统级错误
    no_sys_error = len(result.errors) == 0
    checks["no_system_error"] = {
        "errors": result.errors,
        "pass": no_sys_error,
    }
    if not no_sys_error:
        all_pass = False

    # 7. 检查 Agent 有输出
    has_output = len(result.agent_text) > 5
    checks["has_output"] = {
        "text_length": len(result.agent_text),
        "pass": has_output,
    }
    if not has_output:
        all_pass = False

    # ── 新增评测维度（不影响 pass/fail，仅记录指标） ──

    # 8. 效率评分: 实际调用次数 / 预期最少次数
    if tc.expect_tool_count_min > 0 and len(result.tools_called) > 0:
        result.efficiency_score = round(
            tc.expect_tool_count_min / max(len(result.tools_called), 1), 2
        )
    elif tc.expect_no_tools and len(result.tools_called) == 0:
        result.efficiency_score = 1.0

    # 9. 工具精准率: 预期工具在调用列表中的占比
    if tc.expect_tools and result.tools_called:
        expected_set = set(tc.expect_tools)
        called_list = result.tools_called
        precision_hits = sum(1 for t in called_list if t in expected_set)
        tool_precision = round(precision_hits / len(called_list), 2)
        checks["tool_precision"] = {
            "precision": tool_precision,
            "expected_tools": list(expected_set),
            "actual_tools": called_list,
            "info_only": True,
        }

    # 10. bash 替代率
    total_calls = len(result.tools_called)
    if total_calls > 0:
        bash_rate = round(result.bash_calls / total_calls, 2)
        # 如果预期工具不含 bash 但实际用了 bash，标记为替代
        if "bash" not in tc.expect_tools and result.bash_calls > 0:
            checks["bash_substitution"] = {
                "bash_calls": result.bash_calls,
                "total_calls": total_calls,
                "bash_rate": bash_rate,
                "note": "预期不需要 bash 但使用了 bash",
                "info_only": True,
            }

    # 11. 续行触发次数
    if result.continuation_triggers > 0:
        checks["continuation_triggers"] = {
            "count": result.continuation_triggers,
            "info_only": True,
        }

    result.checks = checks
    result.status = "pass" if all_pass else "fail"


# ═══════════════════ 报告生成 ═══════════════════

def generate_report(results: list[TestResult]) -> str:
    """生成 Markdown 格式的测试报告"""
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    errors = sum(1 for r in results if r.status == "error")
    timeouts = sum(1 for r in results if r.status == "timeout")
    total_time = sum(r.duration_s for r in results)

    lines = [
        f"# 漫剧 Agent 自动化测试报告",
        f"",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 模型: {MODEL_ID}",
        f"> 测试用例数: {total}",
        f"",
        f"## 总览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| ✅ 通过 | {passed}/{total} |",
        f"| ❌ 失败 | {failed}/{total} |",
        f"| 💥 错误 | {errors}/{total} |",
        f"| ⏰ 超时 | {timeouts}/{total} |",
        f"| 总耗时 | {total_time:.1f}s |",
        f"| 通过率 | {passed/total*100:.1f}% |",
        f"",
        f"## 详细结果",
        f"",
        f"| # | 用例名称 | 状态 | 耗时 | 工具调用 | 问题 |",
        f"|---|---------|------|------|---------|------|",
    ]

    for r in results:
        status_icon = {"pass": "✅", "fail": "❌", "error": "💥", "timeout": "⏰"}.get(r.status, "❓")
        tools_str = ", ".join(r.tools_called) if r.tools_called else "-"
        failed_checks = [
            k for k, v in r.checks.items()
            if isinstance(v, dict) and not v.get("pass", True)
        ]
        issues = ", ".join(failed_checks) if failed_checks else ("; ".join(r.errors[:1]) if r.errors else "-")
        lines.append(
            f"| {r.test_id} | {r.test_name} | {status_icon} {r.status} | {r.duration_s}s | {tools_str} | {issues} |"
        )

    # ── 效率指标汇总 ──
    lines.append("")
    lines.append("## 效率指标")
    lines.append("")
    lines.append("| # | 用例 | 效率 | 耗时评分 | 首工具延迟 | bash替代 | 续行触发 |")
    lines.append("|---|------|------|---------|-----------|---------|---------|")
    for r in results:
        eff = f"{r.efficiency_score:.2f}" if r.efficiency_score else "-"
        ts = f"{r.timing_score:.2f}" if r.timing_score else "-"
        ftd = f"{r.first_tool_delay_s}s" if r.first_tool_delay_s else "-"
        bash_info = f"{r.bash_calls}" if r.bash_calls else "0"
        cont = str(r.continuation_triggers) if r.continuation_triggers else "0"
        lines.append(f"| {r.test_id} | {r.test_name} | {eff} | {ts} | {ftd} | {bash_info} | {cont} |")

    # ── 汇总统计 ──
    total_bash = sum(r.bash_calls for r in results)
    total_tool_calls = sum(len(r.tools_called) for r in results)
    total_continuations = sum(r.continuation_triggers for r in results)
    avg_efficiency = sum(r.efficiency_score for r in results if r.efficiency_score) / max(sum(1 for r in results if r.efficiency_score), 1)
    avg_timing = sum(r.timing_score for r in results if r.timing_score) / max(sum(1 for r in results if r.timing_score), 1)

    lines.append("")
    lines.append(f"**汇总**: 平均效率={avg_efficiency:.2f} | 平均耗时评分={avg_timing:.2f} | "
                 f"bash 调用={total_bash}/{total_tool_calls} ({total_bash/max(total_tool_calls,1)*100:.0f}%) | "
                 f"续行触发={total_continuations}次")
    lines.append("")

    lines.append("## 失败/错误用例详情")
    lines.append("")

    for r in results:
        if r.status in ("fail", "error", "timeout"):
            lines.append(f"### 用例 {r.test_id}: {r.test_name} ({r.status})")
            lines.append("")
            if r.errors:
                lines.append(f"**错误**: {'; '.join(r.errors)}")
            lines.append(f"**工具调用**: {r.tools_called}")
            lines.append(f"**Agent 回复** (前300字): {r.agent_text[:300]}")
            lines.append(f"**首工具延迟**: {r.first_tool_delay_s}s | **续行触发**: {r.continuation_triggers}次")
            lines.append("")
            lines.append("**检查项**:")
            for k, v in r.checks.items():
                if isinstance(v, dict):
                    if v.get("info_only"):
                        lines.append(f"- ℹ️ **{k}**: {json.dumps(v, ensure_ascii=False, default=str)}")
                    else:
                        icon = "✅" if v.get("pass", True) else "❌"
                        lines.append(f"- {icon} **{k}**: {json.dumps(v, ensure_ascii=False, default=str)}")
            lines.append("")

    # ── 预期与现实差距分析 ──
    lines.append("## 预期与现实差距分析")
    lines.append("")

    gap_categories = {
        "tool_selection": {"name": "工具选择", "issues": []},
        "tool_execution": {"name": "工具执行", "issues": []},
        "chain_passing": {"name": "链式传递", "issues": []},
        "error_handling": {"name": "异常处理", "issues": []},
        "intent_understanding": {"name": "意图理解", "issues": []},
        "performance": {"name": "性能", "issues": []},
    }

    for r in results:
        if r.status != "pass":
            for k, v in r.checks.items():
                if isinstance(v, dict) and not v.get("pass", True):
                    if k in ("expected_tools", "tool_count"):
                        gap_categories["tool_selection"]["issues"].append(
                            f"用例{r.test_id}({r.test_name}): 预期{v.get('expected', v.get('expected_range', ''))}, 实际{v.get('actual', '')}"
                        )
                    elif k == "error_handling":
                        gap_categories["error_handling"]["issues"].append(
                            f"用例{r.test_id}({r.test_name}): Agent 未正确处理工具错误"
                        )
                    elif k == "keywords":
                        gap_categories["intent_understanding"]["issues"].append(
                            f"用例{r.test_id}({r.test_name}): 预期关键词{v.get('expected_any_of', [])}, 实际找到{v.get('found', [])}"
                        )
                    elif k == "no_tools":
                        gap_categories["intent_understanding"]["issues"].append(
                            f"用例{r.test_id}({r.test_name}): 不应调工具但调了{v.get('actual', '')}"
                        )
        if r.duration_s > 60:
            gap_categories["performance"]["issues"].append(
                f"用例{r.test_id}({r.test_name}): 耗时 {r.duration_s}s 超过 60s"
            )
        # 链式传递检查
        if r.test_id in (17, 21, 23, 28, 30, 35, 41, 57, 58, 59, 60, 61, 62, 63, 88, 89, 91) and r.status != "pass":
            gap_categories["chain_passing"]["issues"].append(
                f"用例{r.test_id}({r.test_name}): 多步链式任务未完整执行"
            )

    for cat_key, cat in gap_categories.items():
        if cat["issues"]:
            lines.append(f"### {cat['name']}问题")
            for issue in cat["issues"]:
                lines.append(f"- {issue}")
            lines.append("")

    if all(len(c["issues"]) == 0 for c in gap_categories.values()):
        lines.append("🎉 所有测试通过，未发现明显差距！")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════ 主流程 ═══════════════════

async def main():
    import os
    os.makedirs(REPORT_DIR, exist_ok=True)

    print("=" * 60)
    print("漫剧 Agent 全功能自动化测试")
    print(f"模型: {MODEL_ID} | 用例数: {len(TEST_CASES)}")
    print("=" * 60)

    # 1. 登录
    print("\n[1/3] 登录获取 Token...")
    try:
        token = await login()
        print(f"  ✅ 登录成功 (token: {token[:20]}...)")
    except Exception as e:
        print(f"  ❌ 登录失败: {e}")
        sys.exit(1)

    # 2. 逐个运行测试
    print(f"\n[2/3] 运行 {len(TEST_CASES)} 个测试用例...")
    results: list[TestResult] = []

    for i, tc in enumerate(TEST_CASES):
        print(f"\n  [{i+1}/{len(TEST_CASES)}] 测试 {tc.id}: {tc.name}...", end="", flush=True)
        result = await run_single_test(token, tc)
        results.append(result)
        status_icon = {"pass": "✅", "fail": "❌", "error": "💥", "timeout": "⏰"}.get(result.status, "❓")
        extra = ""
        if result.bash_calls and "bash" not in tc.expect_tools:
            extra += f" bash={result.bash_calls}"
        if result.continuation_triggers:
            extra += f" cont={result.continuation_triggers}"
        print(f" {status_icon} {result.status} ({result.duration_s}s, eff={result.efficiency_score:.2f}, tools={result.tools_called}{extra})")
        if result.errors:
            for err in result.errors:
                print(f"    ⚠️  {err[:100]}")

    # 3. 生成报告
    print(f"\n[3/3] 生成报告...")
    report_md = generate_report(results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_path = f"{REPORT_DIR}/agent_test_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    json_path = f"{REPORT_DIR}/agent_test_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(r) for r in results],
            f, ensure_ascii=False, indent=2, default=str,
        )

    # 打印总览
    passed = sum(1 for r in results if r.status == "pass")
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"测试完成: {passed}/{total} 通过 ({passed/total*100:.0f}%)")
    print(f"报告: {md_path}")
    print(f"数据: {json_path}")
    print(f"{'=' * 60}")

    # 返回结果路径供后续分析
    return md_path, json_path, results


if __name__ == "__main__":
    asyncio.run(main())
