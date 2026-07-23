# FinEvidence Agent 大模型算法计划书

## 1. 当前阶段

FinEvidence Agent 目前已经完成了确定性端到端 pipeline：

```text
SEC filings
  -> 财报文本和表格解析
  -> text_chunks.jsonl + table_chunks.jsonl + metric_records.jsonl
  -> BM25 / vector / hybrid retrieval
  -> planner + retriever + table agent + calculator
  -> rule report
  -> numeric / evidence / citation verification
  -> ablation evaluation
```

项目现在也已经有了可选的大模型报告生成层：

```text
确定性证据 + 确定性计算结果
  -> LLMReportAgent
  -> 带引用的最终回答
  -> verifier 检查
```

第一次 DeepSeek smoke experiment 说明大模型接口已经跑通。但是 `full_agent_llm_report`
也暴露出一个问题：大模型在组织答案时可能引入措辞错误、口径混淆或引用错误。

所以，下一阶段不应该简单地把所有模块都接上大模型，而应该一次只接一个 LLM 模块，
然后用消融实验证明这个模块到底有没有带来提升。

## 2. 核心原则

每一个接入 LLM 的模块都必须回答一个实验问题：

```text
这个模块是否能提升某个可量化指标，同时不损害 numeric consistency、
citation accuracy 和 tool success？
```

不要在同一次实验里同时改 planner、reranker、reporter 和 verifier。否则如果指标提升，
你不知道是谁带来的；如果指标下降，也不知道是谁拖了后腿。

这个项目要展示的是算法实验闭环，而不是简单 API 拼装。

## 3. LLM 模块优先级

| 优先级 | 模块 | LLM 的作用 | 原因 |
| ---: | --- | --- | --- |
| 1 | LLM Evidence Verifier | 判断 claim 是否被 evidence 支持 | 最贴合项目主题，也能为后续小模型 verifier 训练提供数据 |
| 2 | LLM Reranker | 对候选证据重新排序 | 可以在生成前提高证据质量 |
| 3 | LLM Planner | 判断问题类型，抽取实体、年份、指标 | 可以减少 routing 和 metric extraction 错误 |
| 4 | LLM Table Metric Mapper | 处理表格行名和指标名的歧义 | 适合解决财报术语和标准指标之间的映射问题 |
| 5 | LLM Report Repair | 只重写 verifier 失败的回答片段 | 让大模型生成更安全，而不是完全相信初稿 |

`CalculatorAgent` 应该继续保持确定性。财务公式、百分比、同比变化这些都应该由代码计算，
不应该让大模型自己算。

## 4. 实验路线

### EXP-002: LLM ReportAgent

当前状态：已经实现第一版，需要跑完整实验和失败分析。

目标：

```text
只让 LLM 负责把确定性证据和确定性计算结果写成自然语言答案。
```

假设：

```text
LLM report generation 可以提升 risk_summary 和 trend_analysis 的回答质量，
同时不降低 numeric consistency 和 citation accuracy。
```

运行命令：

```bash
python3 -B -m finevidence.evaluation.ablation \
  --dataset data/eval/qa_v0_1.jsonl \
  --modes full_agent full_agent_llm_report \
  --top-k 5 \
  --records \
  --output reports/ablation_v0_1_llm_report.json
```

核心指标：

| 指标 | 预期方向 |
| --- | --- |
| answer_accuracy | 提升 |
| evidence_recall | 基本不变 |
| numeric_consistency | 基本不变 |
| citation_accuracy | 不下降，最好提升 |
| hallucination_rate | 不上升，最好下降 |
| tool_success_rate | 基本不变 |

失败分析清单：

| 失败类型 | 需要检查什么 |
| --- | --- |
| 数字措辞错误 | LLM 是否把 gross profit amount 和 gross margin percentage 混淆 |
| 缺少引用 | LLM 是否使用了数字但没有加 citation marker |
| 无证据结论 | LLM 是否加入了 evidence 中不存在的业务解释 |
| JSON/schema 失败 | 模型是否没有返回合法 JSON |
| 过度总结 | 风险总结是否漏掉 gold answer 中要求的关键点 |

交付物：

```text
reports/ablation_v0_1_llm_report.json
reports/experiment_report.md 中的 EXP-002 部分
reports/case_studies.md 中至少一个 LLM 成功案例和一个 LLM 失败案例
```

### EXP-003: LLM Evidence Verifier

目标：

```text
使用强模型判断每个 claim 是否被检索到的 evidence 和 citation 支持。
```

这是最重要的大模型算法步骤，因为它直接对应项目的核心目标：

```text
降低金融问答中的幻觉和无证据结论。
```

输入格式：

```json
{
  "question": "...",
  "answer": "...",
  "claim": "...",
  "evidence": [
    {
      "id": "AAPL_2025_10K_table_0014",
      "text": "...",
      "rows": []
    }
  ],
  "calculations": []
}
```

输出格式：

```json
{
  "label": "supported",
  "confidence": 0.86,
  "supporting_evidence_ids": ["AAPL_2025_10K_table_0014"],
  "reason": "The evidence contains the cited net sales and gross profit values.",
  "suggested_fix": ""
}
```

标签集合：

```text
supported
partially_supported
unsupported
contradicted
numeric_error
ambiguous
```

实现任务：

| 任务 | 文件 |
| --- | --- |
| 添加 verifier prompt 和 JSON schema | `finevidence/llm/prompts.py` |
| 添加 `LLMEvidenceVerifier` | `finevidence/verification/llm_evidence_verifier.py` |
| 在 `VerifierAgent` 中加入可选 LLM 模式 | `finevidence/agents/verifier_agent.py` |
| 在 ablation 中加入对应模式 | `finevidence/evaluation/ablation.py` |
| 用 fake LLM client 写测试 | `tests/test_llm_evidence_verifier.py` |

建议的 ablation modes：

```text
full_agent
full_agent_llm_report
full_agent_llm_verifier
full_agent_llm_report_llm_verifier
```

评测指标：

| 指标 | 作用 |
| --- | --- |
| citation_accuracy | 判断 citation 是否真正支持 claim |
| hallucination_rate | 判断 unsupported claim 是否被发现 |
| tool_success_rate | 判断 LLM verifier 是否稳定运行 |
| cost_per_query | 统计 LLM verification 的成本 |
| latency | 判断 verification 延迟是否可接受 |

交付物：

```text
reports/ablation_v0_1_llm_verifier.json
reports/experiment_report.md 中的 EXP-003 部分
data/eval/verifier_cases_v0_1.jsonl
```

### EXP-004: LLM Reranker

目标：

```text
使用 LLM 或 reranker model 对检索到的 text/table evidence candidates 重新排序。
```

LLM reranker 不应该替代原有检索。原有 BM25、vector、hybrid retrieval 负责召回候选证据，
LLM reranker 只负责对 top candidates 重新排序。

输入格式：

```json
{
  "question": "...",
  "candidates": [
    {
      "id": "...",
      "ticker": "AAPL",
      "fiscal_year": 2025,
      "section": "Item 1A. Risk Factors",
      "text_preview": "..."
    }
  ]
}
```

输出格式：

```json
{
  "ranked_ids": ["...", "..."],
  "rationales": {
    "...": "This candidate directly discusses supply chain risk."
  }
}
```

实现任务：

| 任务 | 文件 |
| --- | --- |
| 添加 LLM reranker prompt/schema | `finevidence/llm/prompts.py` |
| 添加可选 LLM reranker class | `finevidence/indexing/reranker.py` |
| 在 retriever agent 中加入 `--reranker llm` 或 mode flag | `finevidence/agents/retriever_agent.py` |
| 在 ablation 中加入 LLM reranker 模式 | `finevidence/evaluation/ablation.py` |

建议的 ablation modes：

```text
hybrid_retrieval
hybrid_reranked
hybrid_llm_reranked
full_agent
full_agent_llm_reranked
```

评测指标：

| 指标 | 预期变化 |
| --- | --- |
| evidence_recall | 提升 |
| answer_accuracy | 如果证据召回是瓶颈，应提升 |
| citation_accuracy | 如果证据质量更好，应提升 |
| latency | 会变差，需要记录 |
| cost_per_query | 会变差，需要记录 |

接受标准：

```text
只有当 evidence_recall 或 answer_accuracy 的提升足以抵消额外 latency 和 API cost 时，
才保留 LLM reranker。
```

### EXP-005: LLM Planner

目标：

```text
使用 LLM 判断 question type，并抽取 ticker、fiscal year、metrics、period range 和 tools。
```

LLM planner 应该是可选模式。原来的 deterministic planner 要继续作为 fallback。

输入格式：

```json
{
  "question": "Did Apple's gross margin improve from 2023 to 2025?",
  "default_ticker": "AAPL",
  "default_fiscal_year": 2025
}
```

输出格式：

```json
{
  "question_type": "trend_analysis",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "periods": [2023, 2024, 2025],
  "requested_metrics": ["gross_profit", "revenue"],
  "requested_calculations": ["gross_margin"],
  "tools": ["retriever_agent", "table_agent", "calculator_agent"]
}
```

实现任务：

| 任务 | 文件 |
| --- | --- |
| 添加 LLM planner prompt/schema | `finevidence/llm/prompts.py` |
| 添加 `LLMPlannerAgent`，或者在 PlannerAgent 内加入 mode | `finevidence/agents/planner.py` |
| 在 orchestrator 中加入 planner mode | `finevidence/agents/orchestrator.py` |
| 在 ablation 中加入 planner mode | `finevidence/evaluation/ablation.py` |

评测指标：

| 指标 | 预期提升 |
| --- | --- |
| answer_accuracy | trend/fact 问题上升 |
| tool_success_rate | 如果 planner 修复 routing，应提升 |
| numeric_consistency | 如果 metric extraction 更准，应提升 |

风险：

```text
LLM planner 可能错误推断用户没有明确提供的 ticker 或 year。
所以 CLI 显式传入的 ticker/year 必须拥有更高优先级。
```

### EXP-006: LLM Table Metric Mapper

目标：

```text
只用 LLM 处理 ambiguous metric-name mapping，不让 LLM 做计算。
```

示例问题：

```text
问题问 revenue。
表格行可能写成 net sales、total net sales、revenues、sales and other operating revenue。
```

输入格式：

```json
{
  "question_metric": "revenue",
  "candidate_rows": [
    "Net sales",
    "Cost of sales",
    "Gross margin"
  ],
  "table_context": "Consolidated Statements of Operations"
}
```

输出格式：

```json
{
  "selected_row": "Net sales",
  "canonical_metric": "revenue",
  "confidence": 0.93,
  "reason": "Net sales is Apple's revenue line item in this statement."
}
```

实现任务：

| 任务 | 文件 |
| --- | --- |
| 添加 metric mapper prompt/schema | `finevidence/llm/prompts.py` |
| 添加可选 metric mapper | `finevidence/agents/table_agent.py` |
| 为 ambiguous row labels 添加测试 | `tests/test_table_agent.py` |

接受标准：

```text
修复已知 table extraction failures，同时不降低 metric_calc accuracy。
```

## 5. Verifier Dataset 计划

LLM Evidence Verifier 不只是一个线上模块，它还应该为后续小模型训练生成数据。

### 5.1 数据来源

使用下面两类 pipeline 的预测结果：

```text
full_agent
full_agent_llm_report
```

对每个 answer：

```text
answer -> claim_extractor -> claim-evidence pairs -> LLM verifier label
```

### 5.2 数据格式

```json
{
  "id": "verifier_v0_1_0001",
  "question": "What was Apple gross margin in 2025?",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "claim": "Apple's gross margin for fiscal year 2025 was 46.91%.",
  "evidence": [
    {
      "id": "AAPL_2025_10K_table_0014",
      "text": "..."
    }
  ],
  "label": "supported",
  "label_source": "llm",
  "model": "deepseek-v4-pro",
  "confidence": 0.91,
  "needs_human_review": false
}
```

### 5.3 人工审核策略

第一版不需要人工标注所有样本。优先审核最有价值的部分：

| 优先级 | 样本类型 |
| ---: | --- |
| 1 | LLM verifier 低置信度样本 |
| 2 | rule verifier 和 LLM verifier 判断不一致的样本 |
| 3 | 包含 numeric_error 的样本 |
| 4 | trend claims |
| 5 | risk summary claims |

目标：

```text
v0.1 阶段人工审核 100 到 200 条 claim-evidence examples。
```

## 6. 小模型训练计划

小模型训练应该放在 LLM verifier baseline 跑通之后。

候选模型：

```text
Qwen2.5-1.5B/3B
Qwen3-1.7B/4B
Llama 3.2 1B/3B
```

训练目标：

```text
Input: question + claim + evidence
Output: supported / partially_supported / unsupported / contradicted / numeric_error
```

建议文件：

| 文件 | 作用 |
| --- | --- |
| `finevidence/training/build_verifier_dataset.py` | 构建 claim-evidence-label JSONL |
| `finevidence/training/train_lora_verifier.py` | 训练 LoRA 或 QLoRA verifier |
| `finevidence/training/evaluate_verifier.py` | 对比 rule verifier、LLM verifier 和 small-model verifier |

评测维度：

| 维度 | 对比对象 |
| --- | --- |
| accuracy | rule verifier vs LLM verifier vs small model |
| hallucination detection | unsupported claim detection |
| numeric error detection | numeric_error label accuracy |
| latency | 每个 claim 的响应时间 |
| cost | API 成本 vs 本地模型成本 |

## 7. 技术报告写作计划

最终技术报告不能只展示分数，还要解释每个模块为什么重要。

必须包含的章节：

```text
1. 问题定义
2. 数据和解析 pipeline
3. 检索架构
4. Agent workflow
5. Verifier 设计
6. LLM 模块设计
7. 评测集
8. 消融实验
9. 失败分析
10. 小模型 verifier 实验
11. 局限性和未来工作
```

至少写三个 case studies：

| 案例 | 目的 |
| --- | --- |
| Numeric error caught | 展示 NumericVerifier 的价值 |
| Unsupported claim caught | 展示 EvidenceVerifier 的价值 |
| Table-aware retrieval success | 展示表格检索的价值 |
| LLM report failure | 展示为什么需要 verifier/fallback |

## 8. 近期行动顺序

建议按下面顺序推进：

1. 先 commit 当前 LLM report 和 dotenv 工作。
2. 在 `qa_v0_1.jsonl` 上跑完整 EXP-002。
3. 把 EXP-002 结果写进 `reports/experiment_report.md`。
4. 检查失败的 `full_agent_llm_report` 样本。
5. 加强 LLM report prompt 和 citation rules。
6. 实现 EXP-003 LLM Evidence Verifier。
7. 构建 `data/eval/verifier_cases_v0_1.jsonl`。
8. 等 verifier dataset 稳定后，再开始小模型 verifier 训练。

## 9. 建议 commit messages

当前 LLM report 和 dotenv 工作：

```text
feat(llm): add provider-neutral report generation
```

这份详细计划书：

```text
docs: add llm algorithm experiment plan
```

后续 LLM Evidence Verifier：

```text
feat(verification): add llm evidence verifier
```

后续 LLM reranker：

```text
feat(indexing): add llm evidence reranker
```
