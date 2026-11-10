# 京遇 AI 后端与可信知识增强

当前阶段：2026-11-10。项目名称与分工见[项目根README](../README.md)和[职责边界](../00_产品规范/项目现状与职责边界_20261110.md)。本文是当前运行入口，整理前README保存在[历史副本](docs/history/README_阶段整理前_20261110.md)。

## 已完成与边界

FastAPI + Pydantic、本地JSON知识管理、确定性关键词检索、来源关联与争议记录、人工审核过滤、模型生成、程序检查、独立模型核验、最多一次修订、来源查询已经实现。先运行普通检索，不引入LightRAG/GraphRAG。

目前5条天坛候选事实中，仅 `TT_QND_003` 的收窄表述和原文 `TT_QND_003_E01` 获准发布。来源批准只覆盖明确证据和用途，其余事实/片段仍待审；不是语料库全部完成。

DeepSeek Flash已在首题“祈年殿的蓝瓦是什么时候改的？”完成两次成功请求（生成、独立核验）；此前一次402失败另记。实际原文、响应、耗时与费用估算见[真实实测报告](docs/首题真实测试结果_20261110.md)。模型核验不代替人工审核、不保证绝对正确；当前没有其他问题的真实验收结论。

本轮离线检查 **78 passed，1 warning**；真实厂商调用0次，详见[本地检查记录](docs/records/20261110/工程整理与同步/本地检查.json)。多轮记忆、ASR/TTS、数字人、手账生成、上传和业务存储未由本后端实现。`/journal/draft`仍为501预留接口。

## 运行与跨机重建

先进入本后端目录；以下均以该目录为工作目录，不依赖作者机器的固定盘符。Windows建议Python3.12，独立环境通过 `scripts/bootstrap.ps1` 重建，并安装 `requirements.lock.txt` 锁定依赖。已有 `.venv` 时无需重建。初始化脚本会定向本工程临时目录和缓存；不要复用其他项目环境。

```powershell
# 在仓库根目录执行一次
Set-Location -LiteralPath './03_C_AI知识与接口'
# 首次环境初始化；已有环境请跳过
.\scripts\bootstrap.ps1
# 运行本机服务
.\scripts\start.ps1
```

启动脚本监听 `127.0.0.1:8000`；健康检查 `/health`，交互合同 `/docs`，OpenAPI `/openapi.json`。如需直接启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

模型配置由 `.env.example` 复制至本机 `.env` 后填写。不要覆盖已有 `.env`，不要输出文件全文或提交密钥。环境变量优先于 `.env`，修改后重启服务。`model_ready`只表示配置齐全，不代表已真实调用。真实问答会消耗厂商额度，需要按本次约定范围执行，历史未用额度不自动授权新测试。

## 离线测试与检索

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:MODEL_PROVIDER = 'disabled'
$env:MODEL_API_KEY = ''
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\search_sample.py 蓝瓦
# 仅用于资料整理，不能用于正式回答放行
.\.venv\Scripts\python.exe scripts\search_sample.py 蓝瓦 --include-unreviewed
```

测试使用ScriptedModel/httpx.MockTransport及本机HTTP，网络保护禁止模型厂商访问；不将离线fixture批准当正式批准。上述环境变量关闭当前终端模型配置；如之后需要真实服务，请在新的终端按本机 `.env` 启动，不要将禁用配置误认为模型失效。

## 目录

| 路径 | 内容 |
|---|---|
| app/ | 接口、模型结构、JSON读取、问答流程与模型适配 |
| data/ | 八景模板、事实/来源/原文、审核记录、事件与争议关系；不得自动回写模型纠错 |
| docs/ | [统一索引](docs/README.md)、当前合同、schema及技术说明 |
| docs/reviews/ | 人工审读稿、证据整理和必要历史，当前审核以正式数据与明确批准范围为准 |
| docs/integration/ | [数字人对接说明](docs/integration/京遇%20AI%20后端—数字人接口对接说明.md)、fetch、独立页面与脱敏历史快照 |
| docs/records/ | 精选离线/真实测试证据、费用说明，见[索引](docs/records/README.md) |
| docs/history/ | 旧接口合同与整理前README；不是当前行为说明 |
| examples/ | 明确标记mock的旧前端fixture，不是当前真实响应 |
| tests/、scripts/ | 自动测试、启动、离线检索和需要明确范围的真实验收脚本 |
| logs/、tmp/、.cache/、.venv/ | 本机产物，除既有固定测试基准外不提交 |

## 接口与下一步

复用 `GET /health`、`GET /spots`、`POST /chat`、`GET /sources/{source_id}`，详见[合同0.2](docs/接口合同_0.2.md)。知识接口没有用户鉴权；默认仅允许localhost/127.0.0.1的5173前端跨域来源。分机监听、精确前端origin和网络可达性先按[对接说明](docs/integration/京遇%20AI%20后端—数字人接口对接说明.md)确认。

数字人显示与播报可复用通过全部检查后的 `answer`；失败不播放候选。数字人成员负责其实际SDK、语音和播放接口，前端集成来源展示、停止旧播报和新问题状态。下一批天坛知识见[最多五项补充草案](docs/天坛下一批语料任务_20261110.md)，不自动标为已审。
