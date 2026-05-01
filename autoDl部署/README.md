# AutoDL 部署目录说明

## 目录结构

```
autoDl部署/
├── scripts/          # ✅ 最终有效脚本（D03机 / RTX 5090）
├── docs/             # 📖 当前有效文档
└── archive/          # 🗂️ 历史参考（只读）
```

---

## scripts/ — 恢复用脚本

| 脚本 | 作用 | 执行顺序 |
|---|---|---|
| `download_models_d03.sh` | 三模型并行下载（~20GB）| Step 1 |
| `install_envs_d03.sh` | 安装 env-flashhead + env-podcast（串行）| Step 2 |
| `install_fh_requirements.sh` | FlashHead 依赖安装（被 install_envs_d03 调用）| — |
| `install_podcast.sh` | Podcast 依赖安装（被 install_envs_d03 调用）| — |
| `start_all_d03.sh` | 启动 FlashHead(6006) + Podcast(6008) | Step 3 |

**快速恢复（数据盘为空时）：**
```bash
scp scripts/download_models_d03.sh autodl-9050:~/
scp scripts/install_envs_d03.sh autodl-9050:~/
ssh autodl-9050 'bash ~/download_models_d03.sh'     # Step 1: ~40min
ssh autodl-9050 'bash ~/install_envs_d03.sh'        # Step 2: ~30min
ssh autodl-9050 'bash ~/start_all.sh'               # Step 3: 立即
```

---

## docs/ — 当前有效文档

| 文档 | 内容 |
|---|---|
| `数据盘丢失恢复手册.md` | 为什么丢失 / 如何预防 / 一键恢复 |
| `模型恢复计划.md` | 分阶段恢复详细步骤 |
| `260426新卡研究.md` | D03机（RTX 5090）配置与地址信息 |
| `前端全流程测试.md` | 前端各模块测试步骤 |
| `使用教程.md` | 服务使用说明 |

---

## archive/ — 历史参考

| 文档 | 内容 |
|---|---|
| `真实记录执行的所有命令.md` | 部署全过程命令记录（最重要的历史参考）|
| `autodl部署重大问题.md` | 遇到的问题与解决方案 |
| `bug分析-singing-api-20260426.md` | Singing API bug 分析 |
| `gpu选择方案研究.md` | GPU 选型研究 |
| `迁移到A100实施方案.md` | A100 迁移方案（未执行）|
| `部署实施计划.md` | 原始部署计划 |
| `分析这台服务都所有基本信息.md` | 实例基本信息分析 |
