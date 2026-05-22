# Windows 可执行程序打包

## 生成 exe

在项目根目录运行：

```bat
build-exe.bat
```

生成结果：

```text
release\NovelWritingAgent.exe
release\update.json
```

这个命令会先构建前端静态文件，再把后端、依赖和前端页面一起打包进一个 Windows 可执行文件。

## 给普通用户运行

把 `release\NovelWritingAgent.exe` 发给用户即可。用户双击后会：

1. 自动启动本地后端服务。
2. 自动打开浏览器页面。
3. 使用本机数据目录保存数据库和密钥。

默认数据目录：

```text
%LOCALAPPDATA%\NovelWritingAgent
```

里面会保存：

```text
novel_agent.db
.crypto_key
```

## 重新指定数据目录

如果需要把数据放到指定位置，可以在启动前设置环境变量：

```bat
set NOVEL_AGENT_HOME=D:\NovelAgentData
release\NovelWritingAgent.exe
```

## 打包机要求

只有负责打包的电脑需要安装 Python、Node.js 和 npm。普通用户运行 `NovelWritingAgent.exe` 不需要安装这些工具。

## 自动更新

打包后的 exe 会在启动时检查 GitHub 最新 Release。默认仓库为：

```text
teangtang1122/NovelWritingAgent
```

发布新版本时，在 GitHub Release 中上传：

```text
NovelWritingAgent.exe
sha256.txt
```

`sha256.txt` 可以直接填写 `release\NovelWritingAgent.exe` 的 SHA256 值，也可以使用打包生成的 `release\update.json` 里的 `sha256`。用户启动旧版本时，如果发现最新 Release 版本号更高，会自动下载新 exe，退出当前进程后替换并重启。

可以用环境变量覆盖更新源：

```bat
set NOVEL_AGENT_UPDATE_REPO=owner/repo
set NOVEL_AGENT_UPDATE_MANIFEST_URL=https://example.com/update.json
set NOVEL_AGENT_DISABLE_UPDATE=1
```

如果单文件 exe 启动较慢，也可以生成目录版：

```bat
build-exe.bat -OneDir
```
