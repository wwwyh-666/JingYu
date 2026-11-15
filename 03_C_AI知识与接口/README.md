# 京遇 AI 后端与可信知识增强（C 模块）

当前阶段：2026-11-15 阶段性归档。项目总览见[项目根README](../README.md)与[职责边界](../00_产品规范/项目现状与职责边界_20261110.md)；整理前的旧版README保存在[docs/history](docs/history/README_阶段整理前_20261110.md)。

本模块负责：知识问答后端、可信知识库（事实/来源/原文证据/人工审核）、DeepSeek Flash 真实问答、程序检查与独立模型核验、来源追溯。**不负责**：前端页面、数字人渲染、ASR/TTS、手账生成、用户体系。

## 1. 当前能力与进度

| 项 | 状态 |
|---|---|
| 八景点可信知识库 | 8 个景点；18 条事实（16 批准 + 2 条天坛待审）；25 条证据（20 批准）；16 条来源（13 批准）；16 份审核记录 |
| 问答链路 | 检索 → 生成 → 程序检查 → 独立模型核验 → 发布/拒答；失败可修订 1 次（单题最多 4 次模型请求） |
| 模型 | DeepSeek 官方 `deepseek-flash`，非流式、非思考模式、temperature=0 |
| 离线自动化测试 | **185 passed, 0 failed**（2026-11-15，`MODEL_PROVIDER=disabled`，0 次厂商调用） |
| 真实模型问答 | 第一轮八景 8 题：**6/8**；随后修复 Q2/Q8 检索并复测，两题均通过 |
| 数字人接口联调 | **未进行**（SDK/语音接口未交付，本文不作完成结论） |

三个阶段的区别（不要混写）：离线测试 185 项 ≠ 8/8 真实问答 ≠ 数字人联调完成。详见[测试与验收汇总](docs/C模块_测试与验收汇总_20261115.md)。

## 2. 技术栈

- FastAPI + Pydantic v2（`extra='forbid'`，加载即校验）
- 本地 JSON 知识库（`data/`），多文件合并加载，无数据库
- 确定性关键词检索（keywords + query_aliases 词面匹配，无向量/图谱）
- DeepSeek Flash（httpx 直连，非流式，无 SDK、无隐藏重试）
- pytest（脚本模型 + httpx.MockTransport + 本机 HTTP，网络保护禁止访问厂商）

## 3. 核心功能

1. `POST /chat`：单轮问答，回答由通过检查的 claims 拼接，附事实 ID、逐句证据、来源、原文与核验判定。
2. `GET /sources/{source_id}`：查看来源及其当前可发布原文。
3. `GET /health`、`GET /spots`：自检与景点清单。
4. 门禁：事实、来源、证据、来源白名单、URL、scope 全部通过才发布；否则返回明确的 `error_code`（200/502/503/504）。
5. 审计：每次请求写 `logs/qa/qa-{answer_id}.json`，含检索、候选、问题码、核验、Token 用量，密钥自动脱敏。

## 4. 目录结构

| 路径 | 内容 |
|---|---|
| `app/` | `main.py` 路由与启动；`models.py` Schema；`repository.py` 加载/门禁/检索；`qa.py` 问答流水线；`model_client.py` 模型适配 |
| `data/` | `spots.json`、`sources.json`、`facts_{SPOT}.json`、`evidence_{SPOT}.json`、`reviews_{fact_id}.json`、天坛争议事件表 |
| `tests/` | 共 8 个 Python 文件：`conftest.py`（共享 fixture，无用例）+ 7 个 `test_*.py`；185 项用例分布在 7 个测试文件 |
| `scripts/` | `bootstrap.ps1` 建环境、`start.ps1` 启动、`search_sample.py` 离线检索、`accept_first_qa.py` 真实验收客户端、`inspect_conflict.py` 争议查看 |
| `docs/` | [文档索引](docs/README.md)：架构、知识库、接口、测试、交接、历史报告、候选材料、对接示例 |
| `docs/integration/` | [数字人对接说明](docs/integration/京遇%20AI%20后端—数字人接口对接说明.md)、`chat-client.mjs`、`chat-demo.html` |
| `docs/candidate/` | 候选证据包（**未入库**，不代表正式知识） |
| `examples/` | 明确标注 mock 的旧前端示例，不是当前真实响应 |
| `logs/`、`tmp/`、`.venv/` | 本机产物，默认不提交；**唯一例外**：`logs/TT_revision_unchanged_before.json` 是 `test_tiantan_revision.py` 使用的正式基线快照，已被 Git 跟踪（`.gitignore` 中显式豁免），必须随成果提交 |

## 5. 环境配置

```powershell
Set-Location -LiteralPath './03_C_AI知识与接口'
.\scripts\bootstrap.ps1          # 首次；已有 .venv 可跳过
# .env 只在不存在时创建；已填好 API Key 的 .env 永远不会被覆盖
if (-not (Test-Path -LiteralPath '.env')) {
  Copy-Item -LiteralPath '.env.example' -Destination '.env'
} else {
  Write-Host '.env 已存在，跳过初始化（保留已有 API Key 配置）'
}
```

`.env` 关键项（**密钥只在后端，不提交、不输出**）：

```text
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-flash
MODEL_BASE_URL=https://api.deepseek.com
MODEL_API_KEY=（仅本机填写）
MODEL_TIMEOUT_SECONDS=30
MODEL_MAX_OUTPUT_TOKENS=1600
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

环境变量优先于 `.env`；修改后重启服务。`model_ready=true` 只代表配置齐全，不代表已真实调用。

## 6. 本地启动

```powershell
.\scripts\start.ps1        # 监听 127.0.0.1:8000
# 或直接：
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- 健康检查 `/health`；交互文档 `/docs`；OpenAPI `/openapi.json`。
- 未配置模型时 `/chat` 返回 503 `MODEL_NOT_CONFIGURED`，不会伪装成回答。

## 7. 测试方法

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:MODEL_PROVIDER = 'disabled'
$env:MODEL_API_KEY = ''
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider   # 期望 185 passed
.\.venv\Scripts\python.exe scripts\search_sample.py 祈谷       # 离线检索，不调模型
```

真实问答会消耗厂商额度，必须按明确授权范围执行；离线测试中的 fixture 批准不代表正式批准。

## 8. API 文档入口

| 内容 | 入口 |
|---|---|
| 接口速查（请求/响应/拒答/联调） | [docs/C模块_API接口与联调说明_20261115.md](docs/C模块_API接口与联调说明_20261115.md) |
| 数字人正式对接合同 | [docs/integration/京遇 AI 后端—数字人接口对接说明.md](docs/integration/京遇%20AI%20后端—数字人接口对接说明.md) |
| 接口合同 0.2 | [docs/接口合同_0.2.md](docs/接口合同_0.2.md) |
| 在线 | `http://127.0.0.1:8000/docs`、`/openapi.json` |

## 9. 重要技术文档索引

| 文档 | 用途 |
|---|---|
| [C模块_AI后端架构与技术实现说明_20261115.md](docs/C模块_AI后端架构与技术实现说明_20261115.md) | 架构、流水线、门禁、错误码、审计 |
| [C模块_八景可信知识库说明_20261115.md](docs/C模块_八景可信知识库说明_20261115.md) | 三层数据、哈希、审核、白名单、状态、数量 |
| [C模块_API接口与联调说明_20261115.md](docs/C模块_API接口与联调说明_20261115.md) | 路由、字段、成功判定、异常、调用要点 |
| [C模块_测试与验收汇总_20261115.md](docs/C模块_测试与验收汇总_20261115.md) | 185 项离线测试、两轮真实问答、Token 与费用 |
| [C模块_阶段性交接说明_20261115.md](docs/C模块_阶段性交接说明_20261115.md) | 给组长/组员：能做什么、怎么跑、还差什么 |
| [2026-11-15_八景知识库正式入库与统一验收报告.md](docs/2026-11-15_八景知识库正式入库与统一验收报告.md) | 知识入库证据 |
| [2026-11-15_八景真实模型问答验收报告.md](docs/2026-11-15_八景真实模型问答验收报告.md) | 第一轮 6/8 证据 |
| [2026-11-15_八景检索问题最小修复报告.md](docs/2026-11-15_八景检索问题最小修复报告.md) | Q2/Q8 修复过程 |
| [2026-11-15_Q2_Q8检索修复后真实问答复测报告.md](docs/2026-11-15_Q2_Q8检索修复后真实问答复测报告.md) | 复测通过证据 |
| [docs/README.md](docs/README.md) | 全部文档索引（含历史材料） |

## 10. 边界与下一步

- 已完成：知识库、检索、真实问答链路、程序检查/核验/修订、来源追溯、离线回归。
- 未完成：数字人端到端联调（ASR/TTS/播报）、前端集成、8/8 同轮真实回归、多轮记忆、鉴权限流、流式输出、手账生成。
- 历史材料（天坛 003/004/005 审读、候选包、旧合同、实测记录）全部保留在 `docs/` 下，不因归档删除。

维护约定：正式结论以 `data/`、`tests/` 与实际运行记录为准；文档中的"历史状态"按日期阅读，不用旧结论覆盖新状态。
