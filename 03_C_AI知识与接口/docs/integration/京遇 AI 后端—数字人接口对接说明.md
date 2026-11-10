# 京遇 AI 后端—数字人接口对接说明

核对日期：2026-11-10。依据当前 `feature/c-ai-backend` 工作区源码与当晚 21:09 首题成功记录整理。本次仅新增对接材料和独立示例，不改应用逻辑、知识数据或人工审核记录，未调用模型。

## 1. 对接结论与职责

现有知识接口已经可以直接对接，**无需新增数字人专用问答接口**。

文字问题或用户确认后的 ASR 识别文字 → `POST /chat` → 等待完整回答与核验结束 → 前端显示 `answer` 和来源 → 将通过检查的 `answer` 交给数字人成员的 TTS/播报组件。

- 知识后端负责检索、生成、引用/对象检查、独立模型核验、最多一次修订与来源查询。
- 前端负责提问入口、麦克风权限、录音上传、识别文字确认、回答/来源显示及调用播报组件。
- 数字人成员负责 ASR、TTS、二维角色、字幕、播放/停止/重播及状态切换。其语音接口的地址、请求体和音频格式需要另行约定；**本知识后端没有实现 `/speech/transcribe` 或 `/speech/synthesize`**。
- 前端不直接连接 DeepSeek，不携带模型密钥，不自行生成或补写文化事实。

本次已经验证的事实范围只有 `TT_QND_003` 对应的获批收窄表述与 `TT_QND_003_E01`。不表示全部天坛语料或整张来源网页获批。

## 2. 地址、请求与返回

### 2.1 主接口

| 项目 | 当前实现 |
|---|---|
| 方法、路径 | `POST /chat` |
| 本机标准启动地址 | `http://127.0.0.1:8000/chat`；以服务实际启动地址为准 |
| 请求/响应格式 | `application/json`，UTF-8；一次返回完整 JSON，不是流式或音频接口 |
| 鉴权 | 当前应用接口没有用户鉴权；不需要 Authorization 或 Cookie |
| 在线结构说明 | 服务启动后的 `/docs` 与 `/openapi.json`；当前源码是本说明核对依据 |

首题实测使用本机 HTTP 服务的同一 `/chat` 路由。保存的成功记录没有存储该次临时监听端口，不能将上表的标准 8000 端口写成当时实测端口。

| 请求字段 | 必填/默认 | 约束与用途 |
|---|---|---|
| `spot_id` | 必填 | `TT/GG/ZGL/YHY/JS/GWF/YHG/ZYM`；当前首题使用 `TT`，不意味着其他景点已有可发布内容 |
| `question` | 必填 | 1—2000 字符；语音也先转成用户确认后的文字 |
| `object_id` | 可省略，null | 最长100字符；本题建议 `TT_QND`，约束建筑对象 |
| `period` | 可省略，null | 最长200字符；按登记时期字符串精确过滤，不是自然语言年代解析；本题建议不传 |
| `request_id` | 可省略，后端生成 | 1—100字符；建议每次新问题生成唯一值，返回时回显；不具备幂等或去重扣费能力 |
| `session_id` | 可省略，null | 最长100字符；当前仅回显，没有多轮记忆 |
| `turn_id` | 可省略，1 | 整数1—1000；当前仅回显 |

字符串会去除首尾空白，额外未知字段会被拒绝。不要发送 `audio`、`tts_text`、模型名或密钥。参数错误通常返回 HTTP 422。

### 2.2 首题真实请求及完整响应（历史快照）

以下直接提取自 `docs/records/20261110/首题真实测试/完整实际记录.json` 的 `cases[0]`；不是模拟响应，也不是本轮重新调用结果。仅将审读人姓名替换为 `[团队自审人姓名已脱敏]`，保留字段、证据、运行编号和实际耗时/用量。对应独立 JSON 文件可以直接交给队友核对结构。

请求：

```json
{
  "spot_id": "TT",
  "object_id": "TT_QND",
  "question": "祈年殿的蓝瓦是什么时候改的？",
  "request_id": "058101f1-4408-4eca-b8ed-7816b61d8b09-normal"
}
```

HTTP 200 完整响应：

```json
{
  "spot_id": "TT",
  "session_id": null,
  "turn_id": 1,
  "answer": "据天坛公园《祈年殿》介绍，1751年（清乾隆十六年），大享殿统一改为蓝瓦，并更名为祈年殿。",
  "fact_ids": [
    "TT_QND_003"
  ],
  "citations": [
    {
      "source_id": "SRC_TT_OFFICIAL_QND_001",
      "title": "祈年殿",
      "url": "https://tiantanpark.cn/scenic_spot_list/detail/1254.html",
      "evidence_ids": [
        "TT_QND_003_E01"
      ]
    }
  ],
  "confidence_flag": "supported",
  "check_status": "passed",
  "is_mock": false,
  "model_called": true,
  "request_id": "058101f1-4408-4eca-b8ed-7816b61d8b09-normal",
  "answer_id": "589e70da-bc84-4a07-a0ce-7be59da6b378",
  "evidence": [
    {
      "evidence_id": "TT_QND_003_E01",
      "fact_id": "TT_QND_003",
      "spot_id": "TT",
      "object_id": "TT_QND",
      "period": "清·乾隆十六年（1751）",
      "source_id": "SRC_TT_OFFICIAL_QND_001",
      "url": "https://tiantanpark.cn/scenic_spot_list/detail/1254.html",
      "quote": "1751年 (清·乾隆十六年)，统一改为蓝瓦，并更名“祈年殿”",
      "locator": "页面标题祈年殿下的建筑介绍段；搜索1751年；段中由该年份开始、至更名的分句",
      "quote_sha256": "21c5e0f8df59c3d760d744595dec95dede2ba229bdffc0f4929b45b6040cd608",
      "usage": "answer",
      "note": "直接表述年份、改瓦和更名；主证据",
      "review_status": "approved",
      "reviewer": "[团队自审人姓名已脱敏]",
      "reviewed_at": "2026-11-10"
    }
  ],
  "claims": [
    {
      "claim_id": "c1",
      "text": "据天坛公园《祈年殿》介绍，1751年（清乾隆十六年），大享殿统一改为蓝瓦，并更名为祈年殿。",
      "fact_id": "TT_QND_003",
      "spot_id": "TT",
      "object_id": "TT_QND",
      "period": "清·乾隆十六年（1751）",
      "evidence_ids": [
        "TT_QND_003_E01"
      ]
    }
  ],
  "verification": {
    "status": "supported",
    "judgments": [
      {
        "claim_id": "c1",
        "verdict": "supports",
        "evidence_ids": [
          "TT_QND_003_E01"
        ],
        "explanation": "证据原文明确记载1751年（清乾隆十六年）统一改为蓝瓦并更名“祈年殿”，与claim的年份、改瓦、更名内容一致，且对象为祈年殿/大享殿，未扩大范围。"
      }
    ],
    "revision_count": 0
  },
  "evidence_review_status": "approved",
  "error_code": null,
  "metrics": {
    "elapsed_ms": 4736.675,
    "retrieval_ms": 0.141,
    "calls": [
      {
        "phase": "generate",
        "started_at": "2026-11-10T21:09:19.617572+08:00",
        "elapsed_ms": 2143.161,
        "configured_model": "deepseek-flash",
        "actual_model": "deepseek-flash",
        "status": "success",
        "usage": {
          "prompt_tokens": 731,
          "completion_tokens": 94,
          "total_tokens": 825,
          "prompt_tokens_details": {
            "cached_tokens": 0
          },
          "prompt_cache_hit_tokens": 0,
          "prompt_cache_miss_tokens": 731
        },
        "error_code": null
      },
      {
        "phase": "verify",
        "started_at": "2026-11-10T21:09:21.762378+08:00",
        "elapsed_ms": 2584.357,
        "configured_model": "deepseek-flash",
        "actual_model": "deepseek-flash",
        "status": "success",
        "usage": {
          "prompt_tokens": 845,
          "completion_tokens": 88,
          "total_tokens": 933,
          "prompt_tokens_details": {
            "cached_tokens": 0
          },
          "prompt_cache_hit_tokens": 0,
          "prompt_cache_miss_tokens": 845
        },
        "error_code": null
      }
    ]
  }
}
```

此次真实生成和独立核验各1次，共2次模型请求，无修订；HTTP 往返 4740.989 ms。后端耗时、两次模型耗时和厂商用量见上面的 `metrics`，其中总输入1576 token、总输出182 token、总计1758 token。两次模型核验不能保证绝对正确，历史成功也不保证下一次结果完全一致。

### 2.3 前端字段映射

| 需要的内容 | 直接复用的字段 | 使用方式 |
|---|---|---|
| 用户回答 | `answer` | 显示最终回答；失败时也可能是边界说明，需要结合状态判断 |
| 数字人播报文本 | **`answer`** | 当前没有 `speech_text`/`tts_text`；通过下文播报条件后，原样交给 TTS，保留来源限定与年份，不擅自改写 |
| 字幕 | `answer` | 可显示整句；当前没有逐字/逐句时间戳或音素口型数据，由播报组件负责同步 |
| 事实卡 ID | `fact_ids[]`；逐句关联见 `claims[].fact_id` | 本题 `TT_QND_003`；不是原文编号，也没有独立事实详情查询接口 |
| 来源 ID | `citations[].source_id`、`evidence[].source_id` | 本题 `SRC_TT_OFFICIAL_QND_001` |
| 原文片段 ID | `citations[].evidence_ids[]`、`claims[].evidence_ids[]`、`evidence[].evidence_id` | 本题 `TT_QND_003_E01` |
| 原文与定位 | `evidence[].quote / locator / url / quote_sha256` | 来源面板展示原文、页面内定位与链接；哈希用于原文一致性检查，不代表内容必然正确 |
| 程序检查/整体流程 | `check_status`、`error_code` | 正常为 `passed`、null；不能只看 HTTP 200 |
| 模型核验 | `verification.status` 与 `judgments[]` | 正常为 `supported`；逐条 `verdict` 为 `supports`，另有 `contradicts/insufficient_evidence`；`revision_count` 记录修订次数 |
| 人工审核 | `evidence_review_status`、`evidence[].review_status/reviewer/reviewed_at` | 正常为 `approved`；来源审核记录通过下述来源接口取得。回答本身并非人工逐条批准 |
| 模拟/真实标记 | `is_mock`、`model_called` | 此历史成功为 false、true；这两个值单独不足以说明核验通过 |
| 追踪与用量 | `request_id`、`answer_id`、`metrics` | 联调故障定位；不要将内部用量和核验解释作为播报文本 |

人工批准和自动核验分别保存；不要在界面写“教师审核”“保证正确”或把 `verification.status=supported` 当成人工审校。当前 `/chat` 不单独返回事实卡完整审核记录，但发布前后端已检查事实、关联来源与原文的批准状态。无需为了数字人重建审核接口。

### 2.4 查看原文来源

`GET /sources/SRC_TT_OFFICIAL_QND_001`。无需请求体，不会触发模型。成功为 `{ "source": { ... }, "evidence": [ ... ] }`，完整历史成功快照见同目录 `真实首题.source.sanitized.json`。

`source` 包含 `source_id/title/institution/url/accessed_on/published_on/locator/review_status/reviewer/reviewed_at/approved_evidence_ids`；`evidence` 使用上面响应中的原文对象结构。只能返回当前符合可发布条件的原文。来源或原文状态变化后可返回404，不能因历史快照曾成功就继续当成当前批准资料。

来源接口可能包含同一来源其他已批准片段；显示“本次依据”时应与本次 `citations[].evidence_ids` 求交集，不把整个网页当成本题依据。本次 `answer`、`claims`、原文之间的对应关系已足够供前端展示。

## 3. 可直接运行的 fetch 示例

同目录 `chat-client.mjs` 提供 `askJingyu()` 与 `getSource()`。只有主动调用函数才发请求；导入文件不会调用模型。成功返回 `{ displayText, speechText, canSpeak, response, requestId }`。

在前端项目中复制该文件并调用：

```javascript
import { askJingyu, getSource } from './chat-client.mjs';

// 例如放在用户点击“发送”的事件中；不要在页面加载时自动调用。
const controller = new AbortController();
try {
  const result = await askJingyu({
    baseUrl: 'http://127.0.0.1:8000', // 分机时换成知识后端电脑的局域网地址
    question: '祈年殿的蓝瓦是什么时候改的？',
    spotId: 'TT', objectId: 'TT_QND', signal: controller.signal,
  });
  document.querySelector('#answer').textContent = result.displayText;
  if (result.canSpeak) {
    // 将 result.speechText 传给队友实际交付的播报组件。
    // 此处不假设队友已经实现某个 speak() 或 /speech 接口。
    console.log('可播报文本：', result.speechText);
    const citation = result.response.citations[0];
    const source = await getSource('http://127.0.0.1:8000', citation.source_id);
    console.log('本次来源详情：', source);
  }
} catch (error) {
  // 先停止旧音频；不得自动重试 /chat，也不播报失败候选。
  console.error(error.code ?? error.name, error.message);
}
```

无需现有前端的独立演示页面为 `chat-demo.html`：通过本机静态服务器在 `http://127.0.0.1:5173/chat-demo.html` 打开，点击发送才能调用后端；页面只展示可交给组件的播报文本，不假装已接入 TTS。不要直接双击以 `file://` 打开，`null` 来源不在允许的跨域来源中。

供联调成员使用的启动方式（先进入后端根目录；本轮没有执行）：

```powershell
# 知识后端电脑；脚本监听本机 127.0.0.1:8000
.\scripts\start.ps1

# 另一个终端：只托管示例页面，不调用模型
& '.\.venv\Scripts\python.exe' -m http.server 5173 --bind 127.0.0.1 --directory '.\docs\integration'
```

数字人成员电脑若没有该 Python 环境，可用自己的前端开发服务器托管这几个文件。页面发送时仍需确保知识后端可达且跨域配置匹配。

播报条件：HTTP 成功、`error_code===null`、`is_mock===false`、`model_called===true`、`check_status==='passed'`、`confidence_flag==='supported'`、`evidence_review_status==='approved'`、`verification.status==='supported'`，且存在事实、逐句声明、来源和原文。示例已检查这些条件并校验请求标识与景点。前端检查服务于展示和播报控制，不能替代后端审核与核验。

切换景点或新问题开始时，停止旧音频并使旧请求结果失效；可通过 AbortController 取消等待，配合递增序号防止旧结果覆盖新页面。取消浏览器请求不保证取消后端或模型执行，可能仍产生用量。重播应复用已取得的回答/音频，不要重新调用 `/chat`。不要自动重试；每次新问答可能触发生成、核验和一次修订后的重新核验，最多4次模型请求。

## 4. 跨域、鉴权与分机联调

当前源码默认以及本机 `.env` 中的 `CORS_ORIGINS` 均为：

```text
http://localhost:5173,http://127.0.0.1:5173
```

- 允许业务方法 GET、POST，请求头 Content-Type；中间件处理跨域预检 OPTIONS。未启用携带凭证，示例显式 `credentials:'omit'`。
- 不要使用 `mode:'no-cors'`；浏览器会使响应不可读。不要添加不存在的前端鉴权头。模型密钥只在后端 `.env` 中，不进浏览器、录音或TTS请求。
- 允许的是**前端页面地址的 origin（协议+主机+端口，无路径）**，不是知识后端地址。例如前端从 `http://192.168.1.20:5173` 打开，该 origin 才应加入后端 `CORS_ORIGINS`；设置后重启后端。运行进程环境变量可能覆盖 `.env`，联调时以实际进程为准。
- 当前标准启动脚本只监听 `127.0.0.1`，另一台电脑无法访问。分机联调需另行让知识后端监听可达的局域网地址（如 `0.0.0.0:8000`），前端 `baseUrl` 填后端电脑的真实局域网 IP，不填 `0.0.0.0`，也不填另一台电脑自己的 localhost。检查双方网络与入站端口可达；本轮没有修改监听地址、防火墙或配置。
- 当前接口没有用户鉴权、限流和应用级幂等控制；联调范围按团队约定网络管理，不作为已完成的公网服务。跨域限制不是鉴权。

`GET /health` 只检查服务与配置，不调用模型；`model_ready=true` 不代表本次真实生成或核验成功。建议先用它排查连接，再由获准的联调操作触发问答。本轮没有启动服务或执行线上问答。

## 5. 异常处理与数字人状态

| 情况 | 当前 HTTP / 状态 | 前端与数字人处理 |
|---|---|---|
| 正常发布 | 200，`passed` + `supported` | 显示 `answer`、来源；再调用播报组件 |
| 无可发布证据 | 200，`NO_PUBLISHABLE_EVIDENCE` | 显示边界说明；不播放文化回答，不让其他模型补齐 |
| 景点/对象不符 | 200，`SCOPE_MISMATCH` | 提示确认景点对象，不自动换范围再次提问 |
| 程序检查不通过 | 200，`PROGRAM_CHECK_FAILED` | 不播报候选；显示后端返回说明 |
| 核验结构无效/不支持 | 200，`VERIFICATION_OUTPUT_INVALID` 或 `VERIFICATION_NOT_SUPPORTED` | 不将失败候选当最终回答；不自动重试 |
| 知识校验失败/执行中证据变更 | 200，`KNOWLEDGE_DATA_INVALID` 或 `EVIDENCE_CHANGED_DURING_REQUEST` | 停止播报，交后端定位 |
| 未配置模型/传输失败 | 503，`MODEL_NOT_CONFIGURED` 或 `MODEL_TRANSPORT_ERROR` | 不按成功响应处理，保留错误码供联调 |
| 模型超时 | 504，`MODEL_TIMEOUT` | 停止等待动画，不自动重试 |
| 厂商错误、解析失败、截断等 | 502，`MODEL_HTTP_*`、`MODEL_INVALID_*`、`MODEL_INCOMPLETE_OUTPUT` 等 | 不发布候选，不向用户暴露密钥或厂商内部错误体 |
| 请求结构错误 | 422，FastAPI `detail` 数组 | 修正参数；此响应不是 ChatResponse，不直接访问 answer |
| 来源不可发布 | 404，`detail.code=SOURCE_NOT_PUBLISHABLE` | 来源面板提示暂不可查看，不用历史截图代替当前来源状态 |
| 网络/CORS/非JSON/未处理服务故障 | fetch抛错，或其他状态/响应体 | 停止等待/播报，提供简短提示；不假设每个异常都有相同 JSON 结构 |

加载中应为“正在检索与核验”等等待状态；接口不是流式，不存在应先播报的已验证片段。`verification.status` 可为 `not_run/supported/contradicts/insufficient_evidence/failed`，只有 supported 可进入正常播报；`confidence_flag` 是离散标签，不是概率。

当前没有单独播报字段。**最小方案是零后端改动，复用 answer。**若后续确实需要不同于显示文本的读音处理，可先讨论增加可空 `speech_text`（仅在最终通过后填入、失败时为 null）；这只是建议，本轮未实施，也不应删除来源限定或改变文化事实。音频 URL、声音选择、时间戳、停止和重播接口由数字人成员交付，不在当前知识接口内臆造约定。

## 6. 本轮核对依据与交付边界

- `app/main.py`：实际路由、HTTP 状态映射、CORS 与启动初始化。
- `app/models.py`：请求约束、完整响应及来源结构。
- `app/qa.py`：发布前审核过滤、生成/检查/独立核验、修订与失败返回。
- `app/repository.py`：事实/来源/原文三层审核及来源片段白名单。
- `app/model_client.py`：非流式请求、超时及错误映射，无隐藏重试。
- `scripts/start.ps1`：标准本机监听地址；`scripts/accept_first_qa.py`：实际测试客户端使用 `/chat` 和来源查询的方式。
- `docs/records/20261110/首题真实测试/完整实际记录.json`：本说明历史请求/响应、真实耗时和用量的出处。

接口说明整理时只做静态源码调查、历史记录提取与文档/示例离线检查。没有执行新的问答，没有运行全套付费验收，没有扩大正式发布事实，也没有改审核结论。示例通过离线语法/结构核对不等于已完成跨电脑、ASR、TTS 或数字人播报联调。
