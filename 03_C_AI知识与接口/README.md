# 京遇 C AI后端与文化知识初始化

实际工程：D:\JingYu\03_C_AI知识与接口。仅完成2026-11-05工作：本地启动、八景模板、5条天坛候选事实、最小关键词检索、模拟接口和测试。无真实模型调用、完整RAG、多轮会话、语音、数字人、手账生成。

## 运行

在PowerShell中：

```powershell
Set-Location -LiteralPath 'D:\JingYu\03_C_AI知识与接口'
.\scripts\start.ps1
```

若PowerShell执行策略限制脚本，可直接运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查 http://127.0.0.1:8000/health；八景表 /spots；接口说明 /docs；停止按Ctrl+C。仅本机访问。普通启动日志输出至终端；验收运行日志保存在logs，若需要落盘可用PowerShell重定向到本工程logs。切勿用系统python别名，它当前指向Windows商店。

## 测试与检索

```powershell
$env:TEMP = "$PWD\tmp"
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp\pytest
.\.venv\Scripts\python.exe scripts\search_sample.py 蓝瓦 --include-unreviewed
```

候选检索返回TT_QND_003及真实登记来源ID；这只是离线检索，不是模型回答。去掉--include-unreviewed返回空列表，因为当前5条均待人工审校。未知问题返回空列表，不伪造记录。

## 目录

app/ 数据模型、数据读取、最小接口；data/ 八景表、来源表、facts_SPOTID.json与空白事实模板；docs/ 合同、选型、验收、原文提取；examples/ 明确标记的模拟JSON；tests/ 自动化测试；scripts/ 启动及离线检索；logs/ 真实运行记录；tmp/ 临时数据；.cache/ D盘pip缓存；.venv/ D盘虚拟环境。

项目根目录按v6建00_产品规范、01_A_视觉资产、02_B_前端代码、03_C_AI知识与接口、04_交互测试、05_最终提交；A/B目录仅为空目录，未写入代码或视觉资产。共享规范目录仅保存两份原始文件副本。PDF中C目录的排版空格按用户给定精确路径处理，不另建带空格目录。

## 重建环境

使用已核实的Python3.12安装器命令py -3.12；在本工程下创建.venv。安装前将TEMP、TMP设为本工程tmp，PIP_CACHE_DIR设为本工程.cache\pip。以 requirements.lock.txt 安装本次确切版本（含测试依赖）。requirements.in与requirements-dev.in记录依赖意图。D盘环境依赖电脑上的Python3.12基础解释器；不声称已经复制为可跨机运行的Python发行包。跨机需按文档重建虚拟环境。

.env.example仅示例；可复制为.env，但当前版本忽略模型配置且始终不调用模型。密钥不得进入代码、日志、示例或版本库；.gitignore已排除.env、虚拟环境、日志和缓存。今天未建立团队Git仓库、未创建远程仓库、未提交任何密钥。不要在聊天中发送密钥。

文件依据、版本差异、实测记录与后续建议见docs/初始化验收.md；技术路线与付费服务尚待用户确认。

首次或跨机重建可运行 `.\scripts\bootstrap.ps1`，它会将临时目录与pip缓存定向D盘并按锁文件安装。当前初始化机器已完成安装，无需重复。
