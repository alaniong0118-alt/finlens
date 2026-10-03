# FinLens Evidence-Grounded Financial Q&A MVP — Final Verification

验收日期：2026-10-04（Asia/Macau）。当前状态：非 secret 验收保持通过；本轮密钥 exists；真实 OpenAI 请求额度不足（诊断 HTTP 429 / insufficient_quota / credit_balance_exhausted），真实回答及 claim audit 尚未完成。

## 1. Files changed

此前非 secret 里程碑的修改记录（本轮仅更新两份 reports，没有修改应用代码）：

- `backend/app/filing_search_service.py`：保留完整问题用于 embedding；词法匹配去除限定的问句外壳，增加 revenue/net sales 与 revenue growth/net sales increased 别名，保留时间、数字及否定条件。
- `backend/app/evidence_policy.py`：收紧中等语义分的放行条件，阻止临床试验负例误命中普通财务段落。
- `backend/app/answer_service.py`：明确禁止 hold、target price 和 portfolio allocation 建议，补充对应检查。
- `backend/tests/test_rag.py`、`backend/tests/test_rag_database.py`：增加上述实际缺口的回归测试，补充真实 SDK 对 mock HTTP 401/429/500 的错误映射检查。
- `backend/scripts/evaluate_rag.py`：动态发现 filing，使用五个完整问题及正式 API 路由，记录实际模型调用尝试、来源、错误和耗时。
- `backend/reports/rag_evaluation.json`：保存真实数据库检索、正式接口结果、lineage、浏览器与工程验收记录。
- `backend/requirements.txt`：记录代码已经使用、环境已经安装的 BeautifulSoup 依赖，没有升级依赖。
- `backend/README.md`、根目录 `README.md`：同步 scoring、evidence、评估和运行说明。
- 本验收报告。

本轮没有修改 frontend 源码、数据库结构或历史 migration。

## 2. Architecture verified

| 层 | 验证状态 |
|---|---|
| Browser → Next.js | 实际生产页面加载、输入、loading、错误与 insufficient 状态通过 |
| Next.js → FastAPI | 同源代理实际 HTTP 检查通过 |
| Company / filing selection | 数据来自现有 API；AAPL 有一个已索引 filing，Visa 未索引状态正确 |
| Hybrid Retrieval | 实际 DB 检索，company + accession scope 检查通过 |
| Evidence Policy | 五个相关问题 sufficient；临床试验负例 insufficient 且不调用 provider |
| Context | DB chunks、SOURCE/END SOURCE 边界、去重、长度限制保留 |
| Real LLM | blocked：credit_balance_exhausted；5 个问题均 HTTP 502，上游诊断 HTTP 429 |
| Claim Validation | 自动测试通过，真实模型语义正确性未验证 |
| Citations → SEC | 21 条候选引用的数据库 lineage 通过；官方 filing index 与主文档可访问 |

正式 endpoint 保持：`POST /companies/{ticker}/filings/{accession_number}/answer`。

请求保持：`{"question":"What drove revenue growth?","limit":5}`。

Response 保持 ticker、company_name、accession_number、question、answer、claims、citations、evidence_status、model 及 insufficient_evidence。

## 3. Backend verification（此前通过，未重复运行）

- 全量 `python -m pytest -q`：**41 passed / 0 failed / 0 skipped**；44 个 subtests 通过。
- 使用项目 `.venv/Scripts/python.exe`，Python 3.14.7。
- 本轮 Python 文件的 `py_compile`：通过。
- `from app.main import app`：通过。
- FastAPI 已在 `127.0.0.1:8001` 启动。
- 实际本地 HTTP smoke 共 20 项通过，记录于 JSON 的 `local_http_verification`。
- `/healthz`、`/dbz`、`/companies`、AAPL sources、keyword search、semantic search、context：HTTP 200。
- 五个 sufficient 问题的 answer：HTTP 503 / `LLM_UNAVAILABLE`，符合未配置 key 的行为。
- 临床试验负例的 answer：HTTP 200 / insufficient。
- AAPL accession 放入 Visa scope、不存在的 accession：context citations 均为空。
- 旧财务 API、sources 和检索兼容性在 regression tests 中通过。
- provider 测试使用 mock，包含 citation、恶意 SOURCE、空/未知 citation、重复 citation、refusal、incomplete、timeout、401、429、500。没有把这些记录成 real LLM。

## 4. Frontend verification（此前通过，未重复运行）

- `npm test`：**6 passed / 0 failed**。
- `npm run lint`：通过。
- `npm run build`：通过，Next.js 15.5.27 未升级。
- 生产服务器：`http://127.0.0.1:3001`。
- 实际浏览器通过：页面加载，company selector，AAPL filing selector，Visa 无索引状态，question，Ask，loading，缺 key 提示，insufficient 状态。
- 受控后端停机时观察到实际 HTTP 500 的错误提示。后续后端已恢复。
- 成功的真实回答、claim 卡片及从真实回答点击 SEC 链接：**尚未通过；当前 provider API 额度不足**。对应 API 客户端与引用映射的自动测试使用 mock，不能替代真实验收。
- Frontend 链接直接使用 API 的 `citation.sec_url`，不自行构造。

运行期间发现 dev 和 build 共用 `.next` 导致缺失模块。停止开发进程、重新 build、启动 production server 后解决。最初两次启动被执行策略拒绝；最新授权后的本机启动已成功，当前不再是 blocker。

复现生产运行：先停止同目录的 Next.js dev 进程，然后在 frontend 执行：

```powershell
$env:FINLENS_API_BASE_URL='http://127.0.0.1:8001'
npm run build
npm run start -- --hostname 127.0.0.1 --port 3001
```

## 5. Database

| 项目 | 实际值 |
|---|---:|
| companies | 10 |
| financial_facts | 3,251 |
| filing_chunks | 37 |
| 非空 embeddings | 37 |
| embedding dimension | 384 |
| pgvector extension | 0.8.7 |

Docker `finlens-postgres` / `pgvector/pgvector:pg16` 健康。chunk 与 embedding 在完整回归及评估前后的逐行 fingerprint 一致。本轮没有 ingest、数据库写入、embedding 重建、表删除或 volume 操作。

## 6. Alembic

- `alembic current`：`d7b834408ba8 (head)`。
- `alembic check`：`No new upgrade operations detected.`
- 没有新增或修改 migration。

## 7. AAPL filing actually used

通过当前 `GET /companies/AAPL/sources` 动态发现并选择：

- ticker：AAPL
- company：Apple Inc.
- CIK：0000320193
- accession：0000320193-26-000020
- form：10-Q
- filed：2026-07-31
- 主文档：aapl-20260627.htm
- [数据库 SEC filing URL](https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index.html)

官方 index 的公司、accession、form、filed 和主文档名已核对。只做来源查看，没有重新 ingest。

## 8. Required five-query real evaluation

动态选择当前 AAPL 已索引 filing：`0000320193-26-000020`，不是硬编码。五个请求通过现有正式 POST /answer 路由（FastAPI TestClient transport）真实调用 OpenAI SDK。没有 mock provider response。实际送出的 SOURCE blocks、检索分数、metadata、model、effort 和耗时已写入 JSON。

| Question | Retrieval Evidence | Retrieved Chunks | HTTP | Latency ms | Result |
|---|---|---|---:|---:|---|
| What drove revenue growth? | sufficient | chunk_0017, chunk_0018, chunk_0016, chunk_0019, chunk_0006 | 502 | 2791.67 | UPSTREAM_FAILURE |
| What were the main drivers of services revenue? | sufficient | chunk_0018, chunk_0006, chunk_0028, chunk_0033, chunk_0029 | 502 | 1733.11 | UPSTREAM_FAILURE |
| What was the gross margin? | sufficient | chunk_0018, chunk_0001, chunk_0026, chunk_0016, chunk_0015 | 502 | 693.91 | UPSTREAM_FAILURE |
| What supply constraints were discussed? | sufficient | chunk_0015, chunk_0026, chunk_0027, chunk_0028, chunk_0016 | 502 | 2288.01 | UPSTREAM_FAILURE |
| How did artificial intelligence affect the business? | sufficient | chunk_0033, chunk_0019, chunk_0027, chunk_0032, chunk_0013 | 502 | 1111.14 | UPSTREAM_FAILURE |

五个请求均未返回模型 answer、claims 或 used citation IDs。sufficient 仅表示检索证据状态。一个受影响问题的诊断重试确认 provider HTTP 429 / insufficient_quota / credit_balance_exhausted。未继续批量重试。

## 9. Insufficient evidence test

问题：`What clinical trial results did Apple report?`

- 本轮正式 answer 路由返回 HTTP 200。
- `evidence_status=insufficient`，`insufficient_evidence=true`。
- 实际 provider SDK 调用增量：**0**。
- claims 与 citations 均为 []。
- answer：The filing evidence retrieved does not provide enough support to answer this question.

## 10. Real LLM

- OPENAI_API_KEY：exists；未输出、记录或回显密钥。
- 配置模型：`gpt-6-astra`；reasoning effort：`medium`。未取得成功响应，不能报告为成功响应模型确认。
- 真实 SDK 尝试：6（五个必测问题 + 一次诊断重试）；成功回答：0。
- 五个正式 endpoint 请求：HTTP 502 / UPSTREAM_FAILURE。
- 安全诊断：RateLimitError / provider HTTP 429 / insufficient_quota / credit_balance_exhausted。
- 当前 blocker 是 API 可用余额不足；上一轮 invalid_api_key 不再是当前诊断结论。
- 未改应用代码、模型或架构；未重跑 frontend build 与完整 regression。

## 11. Citation lineage audit

对五个问题的全部 21 条 candidate citation，核对：

`source_id → SOURCE text → chunk_id → 指定 company/accession 的 DB row → metadata → SEC URL`。

全部 metadata 与数据库一致，SOURCE 文本与对应 chunk 一致，URL 为数据库存储的官方 `www.sec.gov` 地址。JSON 保留每条检查结果和完整 candidate context。

官方 [主文档](https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm) 可访问；已对照 Services 原因、毛利表及 AI 披露的相应段落。逐条 DB lineage 通过不代表模型 claim 语义通过。

## 12. Claim audit

实际请求的 SOURCE blocks 已记录，但没有成功生成模型回答，因此本轮没有 factual claims 可评级。

- SUPPORTED：not_run。
- PARTIALLY_SUPPORTED：not_run。
- NOT_SUPPORTED：not_run。
- unsupported claims：未评估，不能视为已验证为 0。

保留 citation → SOURCE block → DB chunk → accession → official SEC URL 的 metadata 和实际输入，未将 lineage 记录冒充为 claim 语义审计。取得真实回答后仍须逐条核对数字、百分比、quarter/year、fiscal period、YoY/sequential、因果与公司主体。

## 13. Retrieval / evidence / validation issues discovered

1. **问句外壳干扰 lexical scoring**：毛利和 Services 完整问句误判 insufficient。已修复限定问句 normalization，并测试保留时间与否定条件。
2. **Revenue / net sales 词汇差异**：旧 top-k 遗漏直接解释增长原因的段落。已加入限定财务别名，实际 Services 原因段落 chunk_0018 排第一。
3. **Evidence false positive**：临床试验问题仅凭 ~0.40 的语义分放行。已收紧为 S≥0.60 可独立通过，或 S≥0.40 且 L≥0.10；其他原分支保留。指定负例现已稳定拒绝。
4. **运行缓存冲突**：生产 build 与运行中的 dev 共用 `.next`。通过停止 dev、构建后使用 production server 解决并记录运行顺序。
5. **依赖声明缺失**：BeautifulSoup 已使用且已安装，但未写入 requirements。已补齐声明，没有升级。

没有发现新的 citation identity/schema 拒绝逻辑故障。当前 evidence 仍是单 filing 的启发式规则，不构成对所有未来问题的语义正确性保证。

## 14. Evaluation report

本轮只更新 `backend/reports/rag_evaluation.json` 和本报告。此前通过的非 secret 工程、浏览器、数据库及官方 SEC 来源验收记录保留，没有重新运行。JSON 包含五个真实 SDK 尝试、实际 sent_source_context、检索分数及 chunks、HTTP 与 latency、安全诊断和负例。

- 实际 provider 尝试：true；成功回答：0。
- claim audit：not_run_no_model_answer。
- 负例：HTTP 200 / insufficient / provider calls 0。
- 应用代码修改：无；完整 regression/build：未重跑。

## 15. Remaining blockers

当前唯一外部 blocker：**credit_balance_exhausted**。一次诊断请求收到 OpenAI HTTP 429 / insufficient_quota / credit_balance_exhausted。需要为该 API key 所属的 API 项目/账户恢复可用额度。无需在聊天中发送密钥。

Implementation and non-secret-dependent verification are complete; real LLM acceptance is blocked by exhausted OpenAI API credits (HTTP 429 / insufficient_quota).

五个成功真实回答和 claim-by-claim audit 尚未完成，不能宣称 MVP fully verified。
