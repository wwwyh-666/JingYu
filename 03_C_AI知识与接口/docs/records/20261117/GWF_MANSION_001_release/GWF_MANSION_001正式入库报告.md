# GWF_MANSION_001 正式入库报告

日期：2026-11-17 ｜ 审核人：王宇涵 ｜ 决定：批准入库（方案A，保留原始单条E01）

## 1. 审核人及审核日期

- 审核人：王宇涵（京遇团队成员、知识库与后端算法负责人，身份沿用 data/reviews_TT_QND_003.json 既有登记）
- 审核日期：2026-11-17
- 审核依据：2026-11-17 专项复核报告（仓库外 C:/Users/Public/GWF_MANSION_001复核_20261117/）与人工审核材料包（仓库外 C:/Users/Public/GWF_MANSION_001_人工审核材料_20261117/）
- 用户在 2026-11-17 聊天指令中逐项确认八项审核清单并明确批准；证据处理方案A（保留原始单条E01，不拆分、不改quote与SHA256）由用户确定

## 2. 正式批准决定

- release_status：approved（事实GWF_MANSION_001、证据GWF_MANSION_001_E01）
- statement保持用户确认的收窄版（保存较为完整并向公众开放），不恢复最高级断言
- 向公众开放仅指恭王府博物馆历史介绍文章中的描述，不构成2026年实时开放状态证明
- 整页未批准（whole_webpage_approved=false）；仅批准accepted_text与对应evidence_ids

## 3. 四个文件修改明细

- data/facts_GWF.json：追加GWF_MANSION_001（+38行，纯新增；字段结构沿用002惯例，query_aliases由候选query_examples逐字映射，source_evidence按002结构补建并标明第1段两句连续；notes保留历史暂缓原文并追加2026-11-17审核说明）
- data/evidence_GWF.json：追加GWF_MANSION_001_E01（+17行，纯新增；quote/locator/quote_sha256/usage逐字沿用候选值；note保留候选原文并追加方案A说明与时间边界）
- data/sources.json：SRC_GWF_PGM_001.approved_evidence_ids追加GWF_MANSION_001_E01（+2/-1行；-1为E02行加逗号的格式变化，内容不变；来源名称/URL/主体/状态等其余字段未动）
- data/reviews_GWF_MANSION_001.json：新建独立审核记录（沿用reviews_GWF_MANSION_002.json结构；含七项审核意见、方案A理由、时间边界、历史暂缓差异未还原说明）

## 4. 入库前后数据数量对比

| 项目 | 入库前(实测) | 入库后(实测) |
|---|---:|---:|
| Fact总数 | 18 | 19 |
| Approved Fact | 16 | 17 |
| Evidence总数 | 25 | 26 |
| Approved Evidence | 20 | 21 |
| Source总数 | 16 | 16（复用，未新建） |
| Review记录 | 16 | 17 |

## 5. E01原始quote与SHA256复核

- quote逐字未变（与候选包evidences记录及quote_hashes.json三方逐字一致）
- SHA256：cb5e2827d14fa91df73b8d6cb947afc05bdc53236bc472295a65e150d2d66296（入库后复算一致）
- locator原样：正文第1段第1句及其后“1982年”句

## 6. GWF_MANSION_002未修改的证明

- git diff显示facts_GWF.json与evidence_GWF.json全部为纯新增行（+38/+17），无任何删除或修改行
- 独立检查：002 fact（text/reviewer/reviewed_at/source_evidence）与002两条evidence（review_status=approved、reviewed_at=2026-11-15）逐字段一致
- sources.json中002的两条approved_evidence_ids完整保留

## 7. 测试结果（MODEL_PROVIDER=disabled，厂商调用0次）

- 6 failed, 229 passed（此前基线235全过）
- 6项失败全部为守卫型基线断言拦截本轮授权变更，非数据错误：
  1. test_repository_loads_all_eight_spots：GWF计数守卫1（现2）
  2-3. test_natural_question_hits_expected_fact[GWF×2]：002两条query首位断言（001因keywords恭王府+王府匹配得分2>1居首；002仍在[:3]命中；同景点多命中为旧库既有模式，HEAD基线已有14处）
  4. test_all_evidence_hashes_and_whitelists_consistent：末尾001不存在守卫（其哈希复算、白名单、evidence_is_publishable检查全部通过）
  5. test_exact_formal_evidence_inventory_and_hashes：全库evidence==25守卫（现26）
  6. test_other_data_unchanged：facts_GWF.json文件SHA快照过期
- 按任务书指示未修改任何测试基线，待用户另行授权更新

## 8. Git状态

- 分支feature/c-ai-backend，HEAD=dc01c27646b9c4c6e4cdfe56475342f1b8b59580（=origin，ahead/behind 0/0）
- 本轮修改5个文件（data四文件+本报告），未执行任何git写操作
- GWF_MANSION_002、其他景点数据、业务代码、检索算法、Prompt、.env、C类保留文件均未触碰

## 9. 尚存来源时间局限

- 向公众开放为2014年报刊文章官网转载（页面2017-10-17更新）中的历史描述，不构成2026年实时开放状态证明
- 历史暂缓原因（1996/2008年句、措辞差异）与2026-11-17官网实测不符，成因尚未完全还原；历史记录已保留
- 本轮未做第三方存档（Wayback）比对