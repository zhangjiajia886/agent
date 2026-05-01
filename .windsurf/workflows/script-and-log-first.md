---
description: 脚本优先与日志优先执行规范
---
# 脚本优先与日志优先执行规范

适用场景：
- 远程服务器部署
- 安装依赖
- 模型下载
- 服务启动
- 长时间运行任务
- 需要反复排查的问题

## 核心规则

1. 所有可能运行超过 10 秒的任务，优先写成脚本文件，再执行。
2. 不直接在终端里拼接超长命令，尤其是 `ssh '...'` 内嵌大量逻辑的形式。
3. 每个脚本必须有明确日志文件，日志路径必须提前说明。
4. 启动脚本后，必须立即给出：
   - 启动命令
   - 日志文件路径
   - 查看日志命令
   - 查看进程命令
   - 预期下一条日志大概何时出现
5. 任何长任务都不能让用户“傻等”，必须提供至少一种进度观察方式：
   - `tail -f` 日志
   - 查看输出文件大小
   - 查看目标目录大小
   - 查看进程状态
   - 查看阶段性标记日志
6. 如果日志因为进度条刷新机制看不到变化，必须明确说明原因，并改成可观察方案。
7. 若任务失败，必须第一时间说明：
   - 最后执行到哪条命令
   - 卡在哪个文件/包/阶段
   - 是网络、权限、磁盘、版本还是脚本逻辑问题
8. 对同一任务的修复，优先修改已有脚本，不重复发明新的散乱命令。
9. 所有关键动作完成后，要同步更新记录文档，至少包含：
   - 实际执行的命令
   - 当前状态
   - 卡点
   - 下一步建议
10. 如果用户说“继续”，默认执行顺序为：
   - 先检查已有脚本和日志
   - 再修改脚本
   - 再执行脚本
   - 再汇报日志

## 标准执行模板

### 1. 先生成脚本

示例：

```bash
~/install_xxx.sh
~/deploy_xxx.sh
~/watch_xxx.sh
```

### 2. 再启动脚本

示例：

```bash
nohup bash ~/install_xxx.sh > ~/logs/install_xxx.log 2>&1 &
```

### 3. 立即返回观察方式

必须至少返回以下内容：

```bash
# 看日志
ssh autodl 'tail -30 ~/logs/install_xxx.log'

# 持续看日志
ssh autodl 'tail -f ~/logs/install_xxx.log'

# 看进程
ssh autodl 'ps aux | grep install_xxx | grep -v grep'
```

### 4. 如果 tail 看不到实时进度

改用辅助脚本或替代观察方式，例如：

```bash
# 看下载文件大小
ls -lh /tmp/*.whl

# 看目录体积增长
du -sh /root/autodl-tmp/envs/env-name/lib/python3.10/site-packages/

# 看阶段日志
tail -50 ~/logs/install_xxx.log
```

## 输出要求

每次执行后都必须明确回答以下 5 个问题：

1. 现在执行到什么步骤了？
2. 最后执行的命令是什么？
3. 日志文件在哪里？
4. 当前是正常运行、卡住还是失败？
5. 下一步准备做什么？

## 长脚本必须通过文件执行（核心强制规则）

**适用条件**：`run_command` 中 shell 命令超过 3 行，或包含 heredoc / 多重管道 / 嵌套引号时，必须：

1. **先用 `write_to_file` 写成 `.sh` 文件**（路径建议 `/tmp/xxx.sh` 或工程目录下的 `scripts/`）
2. **再用 `run_command` 执行该文件**：`bash /tmp/xxx.sh`
3. **禁止直接把长逻辑内嵌在 `run_command` 的 CommandLine 参数里**

正确示范：
```
Step 1: write_to_file → /tmp/batch_test.sh  (写脚本)
Step 2: run_command   → bash /tmp/batch_test.sh  (执行)
```

错误示范（禁止）：
```
run_command → "for i in ...; do curl ...; done && ..."  ← 直接内嵌长命令
```

## 禁止事项

- 不要让用户长时间等待却没有日志路径
- 不要只说“正在执行”而不给观察方式
- 不要频繁换脚本名，除非架构变化
- 不要在失败后继续盲试而不先定位失败点
- 不要把关键结论只留在聊天里而不写入记录文件
- **不要把超过 3 行的 shell 逻辑直接写在 run_command 的 CommandLine 里**

## 远程部署推荐命名

- `clone_repos.sh`
- `install_torch_debug.sh`
- `install_envs.sh`
- `start_all.sh`
- `watch_progress.sh`

日志推荐目录：

- `~/logs/clone.log`
- `~/logs/torch_debug.log`
- `~/logs/install_envs.log`
- `~/logs/flashhead.log`
- `~/logs/podcast.log`
- `~/logs/singer.log`

## 结论

后续遇到部署、安装、下载、启动服务等任务，默认优先遵守本规范：

**先脚本，后执行；先日志，后等待；先观察，后判断。**
