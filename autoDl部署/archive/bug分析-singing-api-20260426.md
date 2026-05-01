# Bug 分析报告 — Singing API 两个 Bug

**日期**: 2026-04-26  
**涉及文件**:
- `backend/app/api/v1/singing.py`
- `backend/app/core/singer_client.py`
- `backend/.env`（配置根因）

---

## Bug 1：`POST /api/v1/singing/transcribe` 返回 500

### 现象

```
Request URL  : POST http://localhost:3000/api/v1/singing/transcribe
Status Code  : 500 Internal Server Error
```

### 根本原因

`singing.py:158` 中的 `singing_transcription` 函数**没有 try-except**，当 Singer Gradio 服务不可达时，异常直接向上传播，FastAPI 将其转化为 500：

```python
# singing.py:136~170（当前代码）
@router.post("/transcribe")
async def singing_transcription(...):
    ...
    prompt_meta, target_meta = await singer_client.transcribe(  # ← 无 try-except！
        prompt_audio_bytes=prompt_content,
        ...
    )
    return JSONResponse({...})
```

调用链：

```
singing_transcription()
  → singer_client.transcribe()           # singer_client.py:52
    → self.call("/transcription_function")  # gradio_client.py:71
      → _get_client()
        → Client("http://127.0.0.1:7862")  # .env: SOUL_SINGER_SPACE
          → [Errno 61] Connection refused  ← Singer SSH 隧道未建立
              ↑ 异常一路冒泡 → FastAPI → 500
```

对比：`/svs` 端点把实际调用放在 `process_svs_task` 后台任务里，该函数有完整的 try-except（`singing.py:81`），所以不会 500，而是把错误存入数据库。

### 解决方案

在 `singing_transcription` 中添加 try-except，捕获连接异常并返回 HTTP 502（上游不可达）：

```python
# 修改后（待审核）
@router.post("/transcribe")
async def singing_transcription(...):
    ...
    try:
        prompt_meta, target_meta = await singer_client.transcribe(
            prompt_audio_bytes=prompt_content,
            target_audio_bytes=target_content,
            prompt_lyric_lang=prompt_lyric_lang,
            target_lyric_lang=target_lyric_lang,
            prompt_vocal_sep=prompt_vocal_sep,
            target_vocal_sep=target_vocal_sep,
        )
    except Exception as e:
        logger.error(f"Singer transcribe 失败: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Singer 服务不可达，请检查 SSH 隧道是否已建立: {e}",
        )
    return JSONResponse({
        "prompt_metadata": base64.b64encode(prompt_meta).decode() if prompt_meta else None,
        "target_metadata": base64.b64encode(target_meta).decode() if target_meta else None,
    })
```

---

## Bug 2：SVS Task 23 失败 —— `error_message: "[Errno 61] Connection refused"`

### 现象

```json
{
  "id": 23,
  "task_type": "singing_svs",
  "status": "failed",
  "error_message": "[Errno 61] Connection refused"
}
```

### 根本原因

**两层原因叠加**：

#### 第一层：Singer 本地 SSH 隧道未建立

`.env` 第 50 行：
```
SOUL_SINGER_SPACE=http://127.0.0.1:7862
```

注释说明了依赖：
```
# Singer: V100 实例, Gradio, 需 SSH 隧道 (ssh -CNg -L 7862:127.0.0.1:6006 autodl-singer)
```

Singer 指向本地 `127.0.0.1:7862`，这是 SSH 隧道的本地端口。如果隧道未建立，任何连接都会被操作系统直接拒绝，产生 `[Errno 61] Connection refused`（macOS 的 ECONNREFUSED）。

#### 第二层：`/svs` 端点没有前置健康检查，盲目创建注定失败的任务

```python
# singing.py:173~230（当前代码）
@router.post("/svs")
async def singing_voice_synthesis(...):
    # ← 没有检查 Singer 是否可达
    prompt_path, prompt_url = await _save_upload(...)   # 文件已写入磁盘
    ...
    task = SoulTask(status=SoulTaskStatus.pending, ...)  # 任务已入库
    db.add(task); await db.commit()

    background_tasks.add_task(process_svs_task, ...)    # 后台任务提交
    return SVSResponse(task_id=task.id, status="pending")  # ← 返回成功给前端！
```

端点返回"成功"（HTTP 200）后，后台任务才尝试连接 Singer，立即失败，任务变为 `failed`。  
结果：**用户看到"任务已创建"但紧接着看到"失败"**，体验极差，且浪费了文件上传和数据库写入。

### 解决方案

#### 操作层面（立即可用）

建立 Singer SSH 隧道：

```bash
# 在本地 Mac 上执行，保持终端不关闭（或加 -f 后台运行）
ssh -CNg -L 7862:127.0.0.1:6006 autodl-singer &

# 验证连通性
curl -s http://127.0.0.1:7862/ | head -5
```

#### 代码层面（待审核）

在 `/svs` 端点创建任务前，做 Singer 健康预检：

```python
# 修改后（待审核）
@router.post("/svs", response_model=SVSResponse)
async def singing_voice_synthesis(...):
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    # ← 新增：前置健康检查，避免创建注定失败的任务
    if not await singer_client.health_check():
        raise HTTPException(
            status_code=503,
            detail="Singer 服务不可达，请先建立 SSH 隧道: ssh -CNg -L 7862:127.0.0.1:6006 autodl-singer",
        )

    prompt_path, prompt_url = await _save_upload(prompt_audio, ".wav")
    target_path, target_url = await _save_upload(target_audio, ".wav")
    # ... 后续不变
```

---

## 对比总结

| | Bug 1 | Bug 2 |
|---|---|---|
| **端点** | `POST /transcribe`（同步） | `POST /svs`（异步任务） |
| **表现** | HTTP 500 | 任务 status=failed |
| **直接原因** | 缺少 try-except | Singer SSH 隧道未建立 |
| **代码缺陷** | `singing_transcription` 无异常处理 | `/svs` 无前置健康检查 |
| **操作修复** | 启动 SSH 隧道后即可用 | 启动 SSH 隧道后即可用 |
| **代码修复** | 加 try-except → 返回 502 | 加 `health_check()` → 返回 503 |

---

## 待审核项

- [ ] Bug 1 修复：`singing.py:158` 添加 try-except（代码已在本文件中给出）
- [ ] Bug 2 修复：`singing.py:200` 添加 `health_check()` 前置检查（代码已在本文件中给出）
- [ ] 操作确认：Singer SSH 隧道启动命令已验证可用

> **注意**：两个 Bug 的共同触发条件是 Singer 隧道未建立。代码修复完成后，表现将从"神秘 500 / 静默失败"变为"明确的 503 + 提示操作步骤"。
