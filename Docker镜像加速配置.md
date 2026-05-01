# Docker 镜像加速器配置指南

## 问题说明
当前无法从 Docker Hub 拉取镜像，出现网络超时错误。需要配置镜像加速器。

## 解决方案：配置 Docker Desktop 镜像加速

### 方法 1：通过 Docker Desktop 界面配置（推荐）

1. 打开 **Docker Desktop**
2. 点击右上角的 **设置图标（齿轮）**
3. 选择 **Docker Engine**
4. 在 JSON 配置中添加以下内容：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev",
    "https://dockerpull.org",
    "https://dockerhub.icu"
  ]
}
```

5. 点击 **Apply & Restart** 应用并重启 Docker

### 方法 2：手动编辑配置文件

编辑 Docker daemon 配置文件：

```bash
# 创建或编辑配置文件
nano ~/.docker/daemon.json
```

添加以下内容：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev",
    "https://dockerpull.org",
    "https://dockerhub.icu"
  ]
}
```

保存后重启 Docker Desktop。

## 可用的国内镜像加速器列表

| 镜像源 | 地址 | 说明 |
|--------|------|------|
| DaoCloud | https://docker.m.daocloud.io | 稳定可靠 |
| 1Panel | https://docker.1panel.live | 开源面板提供 |
| Rat.dev | https://hub.rat.dev | 社区维护 |
| DockerPull | https://dockerpull.org | 公共服务 |
| DockerHub ICU | https://dockerhub.icu | 备用源 |

## 验证配置

配置完成后，运行以下命令验证：

```bash
# 查看 Docker 配置
docker info | grep -A 10 "Registry Mirrors"

# 测试拉取镜像
docker pull redis:7-alpine
```

## 配置完成后的操作

配置镜像加速器并重启 Docker 后，返回项目目录运行：

```bash
cd /Users/zjj/home/learn26/ttsapp
docker-compose up -d
```

## 故障排查

### 如果仍然无法拉取镜像

1. **检查网络连接**
   ```bash
   ping docker.m.daocloud.io
   ```

2. **尝试其他镜像源**
   - 从列表中选择其他镜像源
   - 可以配置多个镜像源作为备份

3. **检查 Docker 状态**
   ```bash
   docker info
   docker version
   ```

4. **重启 Docker Desktop**
   - 完全退出 Docker Desktop
   - 重新启动应用

### 临时解决方案：使用代理

如果镜像加速器也无法使用，可以配置 HTTP 代理：

```json
{
  "proxies": {
    "http-proxy": "http://proxy.example.com:8080",
    "https-proxy": "http://proxy.example.com:8080"
  }
}
```

## 注意事项

⚠️ **重要提示**：
- 配置修改后必须重启 Docker Desktop 才能生效
- 镜像加速器可能会定期更新，如果某个源失效，请尝试其他源
- 建议配置多个镜像源以提高可用性
