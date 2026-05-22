# NovelWritingAgent

本项目是一个本地运行的小说写作 AI 工作台，包含作品管理、章节写作、大纲规划、角色管理、世界观、拆书分析和统一项目助手。

## 本地开发

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 打包 Windows 可执行程序

在项目根目录运行：

```powershell
.\build-exe.bat
```

生成文件：

```text
release\NovelWritingAgent.exe
release\update.json
```

## 自动更新

exe 启动时会自动检查 GitHub 最新 Release。默认仓库：

```text
teangtang1122/NovelWritingAgent
```

发布新版本时，在 GitHub Release 中上传：

```text
NovelWritingAgent.exe
sha256.txt
```

如果检测到 Release 版本号高于本地版本，程序会下载新的 exe，退出当前进程后自动替换并重启。普通用户不需要安装 git、Python、Node.js 或 npm。

可选环境变量：

```text
NOVEL_AGENT_DISABLE_UPDATE=1
NOVEL_AGENT_UPDATE_REPO=owner/repo
NOVEL_AGENT_UPDATE_MANIFEST_URL=https://example.com/update.json
NOVEL_AGENT_GITHUB_TOKEN=...
```

`NOVEL_AGENT_UPDATE_MANIFEST_URL` 的优先级高于 GitHub Release API，适合私有分发或自建更新清单。
