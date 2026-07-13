# FinEvidence Agent 项目计划书

## 1. 项目定位

项目名称：FinEvidence Agent

中文名称：面向财报与公开披露文件的可验证金融研究智能体

项目目标：

构建一个面向上市公司财报、SEC filings、公告和财务表格的金融研究 Agent。系统能够围绕公司经营、财务指标、风险因素和趋势变化回答问题，并输出可追溯证据、计算过程、置信度和数值一致性检查结果。

这个项目不做自动荐股，不做短期涨跌预测，不输出投资买卖建议。它的核心价值是：

1. 从公开金融文档中找到可靠证据。
2. 正确抽取和计算财务指标。
3. 降低大模型在金融问答中的幻觉和数字错误。
4. 用可量化评测证明 Agent 与算法模块的有效性。

一句话版本：

> FinEvidence Agent 是一个面向上市公司财报与 SEC filings 的可验证金融研究 Agent，支持多源检索、表格解析、财务指标计算、证据链生成与数值一致性校验。

## 2. 为什么选择这个项目

### 2.1 对目标岗位的匹配

你的目标岗位优先级是：

1. 大模型算法
2. Agent 算法
3. Agent 应用开发

FinEvidence Agent 对三类岗位都有比较清晰的展示点。

| 岗位方向 | 项目展示点 | 加分原因 |
| --- | --- | --- |
| 大模型算法 | 金融 RAG、证据 reranker、数值一致性 verifier、小模型微调/蒸馏 | 不只是调用 API，而是围绕检索、校验、训练和评测做算法改进 |
| Agent 算法 | Planner、Retriever、Table Agent、Calculator、Verifier、Report Agent | 有明确的工具调用、多步骤规划、结果校验和自修复流程 |
| Agent 应用开发 | Web Demo、引用溯源、财务报告生成、交互式问答 | 能做出可演示、可部署、业务价值明确的产品 |

### 2.2 相比其他项目的优势

相比 AI 小镇、桌面宠物、多智能体社交仿真，金融 Agent 更容易形成明确的评测闭环：

```text
问题 -> 检索证据 -> 抽取数字 -> 计算指标 -> 生成答案 -> 校验引用和数值 -> 自动评分
```

相比普通 RAG 问答，金融 Agent 更有挑战：

1. 财报文档长，结构复杂。
2. 问题经常跨年份、跨表格、跨章节。
3. 财务数字容易出现单位、币种、年份、口径错误。
4. 金融场景对证据、合规和可解释性要求更高。

相比 Coding Agent，金融 Agent 更垂直、更差异化。如果未来投递金融科技、金融 NLP、投研智能体、企业知识库、RAG 算法方向，它会更贴合业务。

## 3. 项目边界

### 3.1 第一阶段只做什么

第一版只支持公开上市公司的财报研究问答，建议从美股公司开始：

1. Apple
2. Microsoft
3. Nvidia
4. Tesla
5. Amazon

第一版只支持三类问题：

1. 事实问答：某公司某年收入、毛利、现金流是多少？
2. 趋势分析：某项指标过去三年是否上升或下降？
3. 风险识别：最新年报中主要风险因素是什么？

示例问题：

```text
Microsoft 过去三年的云业务收入增长是否放缓？
Nvidia 最新 10-K 中提到的供应链风险有哪些？
Apple 过去三年的毛利率变化趋势如何？
Tesla 最近一年经营现金流相比上一年变化多少？
Amazon 最新年报中 AWS 业务的主要增长驱动是什么？
```

### 3.2 第一阶段不做什么

为了让项目专业、合规、可评测，第一阶段明确不做：

1. 不做股票买卖建议。
2. 不做短期股价预测。
3. 不做自动交易。
4. 不做收益承诺。
5. 不抓取需要付费授权的数据。
6. 不把新闻情绪当成最终投资结论。

系统输出中应包含免责声明：

```text
本系统仅基于公开披露文件进行信息检索、指标计算和证据整理，不构成投资建议。
```

## 4. 核心问题定义

本项目要解决的问题不是“让大模型聊金融”，而是：

> 如何让大模型 Agent 在长文档、多表格、多时间周期的金融场景中，生成有证据支撑、数字一致、可验证的研究回答？

可以拆成四个子问题：

1. 金融证据检索：如何从长财报中找到真正支撑答案的段落和表格？
2. 数值推理：如何保证收入、利润、同比、毛利率、现金流等数字计算正确？
3. 幻觉抑制：如何判断回答是否被引用证据支持？
4. Agent 流程：如何让系统自动规划检索、计算、校验和报告生成步骤？

## 5. 总体技术架构

推荐架构：

```text
用户问题
  |
  v
Question Router / Planner
  |
  +-- 文本型问题 -> Text Retriever -> Evidence Reranker
  |
  +-- 表格/指标问题 -> Table Retriever -> Metric Extractor -> Calculator
  |
  +-- 风险型问题 -> Risk Section Retriever -> Risk Summarizer
  |
  v
Draft Answer Generator
  |
  v
Evidence Verifier + Numeric Verifier
  |
  v
Final Report Generator
  |
  v
答案 + 证据引用 + 计算过程 + 校验结果
```

系统分为六层：

| 层级 | 模块 | 作用 |
| --- | --- | --- |
| 数据层 | SEC filings、年报 PDF/HTML、财务表格、元数据 | 提供可追溯数据来源 |
| 解析层 | 文本切分、表格抽取、XBRL 字段解析、章节识别 | 把非结构化财报变成可检索数据 |
| 检索层 | BM25、embedding、table-aware retrieval、reranker | 找到问题相关证据 |
| Agent 层 | Planner、Retriever、Table Agent、Calculator、Verifier、Reporter | 完成多步骤金融研究任务 |
| 评测层 | QA 数据集、证据命中率、数值一致性、幻觉率 | 证明系统有效 |
| 展示层 | Streamlit/Next.js Demo、证据侧栏、计算过程面板 | 让项目可演示 |

## 6. 数据方案

### 6.1 数据来源

优先使用公开、可追溯、便于复现的数据。

| 数据源 | 用途 | 备注 |
| --- | --- | --- |
| SEC EDGAR filings | 10-K、10-Q、8-K 等公开披露文件 | 最推荐，结构相对标准 |
| 公司 Investor Relations 年报 | PDF/HTML 年报 | 可作为补充 |
| FinanceBench 样例 | 金融 QA 评测参考 | 可学习问题类型和证据标注方式 |
| 自建 QA 集 | 项目主要评测集 | 100 到 200 条即可起步 |

### 6.2 第一阶段数据范围

建议第一阶段只做 5 家公司、3 年年报：

```text
AAPL: 2023, 2024, 2025
MSFT: 2023, 2024, 2025
NVDA: 2023, 2024, 2025
TSLA: 2023, 2024, 2025
AMZN: 2023, 2024, 2025
```

如果下载和解析压力较大，可以先从 3 家公司开始：

```text
Apple, Microsoft, Nvidia
```

### 6.3 文档解析后的数据结构

文本 chunk：

```json
{
  "chunk_id": "msft_2025_10k_item1_business_0003",
  "company": "Microsoft",
  "ticker": "MSFT",
  "filing_type": "10-K",
  "fiscal_year": 2025,
  "section": "Item 1. Business",
  "text": "...",
  "source_url": "...",
  "page": 12,
  "token_count": 420
}
```

表格 chunk：

```json
{
  "table_id": "aapl_2025_10k_income_statement",
  "company": "Apple",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "statement_type": "income_statement",
  "rows": [
    {
      "metric": "Net sales",
      "period": "2025",
      "value": 391035,
      "unit": "USD millions"
    }
  ],
  "source_url": "...",
  "page": 45
}
```

证据对象：

```json
{
  "evidence_id": "ev_001",
  "claim": "Apple's gross margin increased from 2023 to 2025.",
  "supporting_chunks": ["aapl_2025_10k_income_statement", "aapl_2024_10k_income_statement"],
  "support_type": "table_calculation",
  "confidence": 0.86
}
```

## 7. Agent 设计

### 7.1 Planner Agent

职责：

1. 判断问题类型。
2. 拆分子任务。
3. 决定调用哪些工具。
4. 生成执行计划。

问题类型：

```text
fact_qa: 事实问答
metric_calc: 指标计算
trend_analysis: 趋势分析
risk_summary: 风险总结
compare_companies: 公司对比
open_research: 开放式研究
```

Planner 输出示例：

```json
{
  "question_type": "trend_analysis",
  "entities": {
    "company": "Apple",
    "ticker": "AAPL",
    "metric": "gross margin",
    "period": "2023-2025"
  },
  "steps": [
    "retrieve income statements for 2023-2025",
    "extract net sales and gross profit",
    "calculate gross margin by year",
    "compare trend",
    "verify calculations",
    "generate answer with citations"
  ]
}
```

### 7.2 Retriever Agent

职责：

1. 根据问题检索相关文本 chunk。
2. 检索相关表格 chunk。
3. 合并 BM25、embedding 和结构化字段结果。
4. 输出候选证据。

第一版检索策略：

```text
score = 0.35 * bm25_score
      + 0.35 * embedding_score
      + 0.20 * metadata_match_score
      + 0.10 * section_priority_score
```

金融文档中一些章节优先级较高：

| 问题类型 | 优先章节 |
| --- | --- |
| 业务分析 | Item 1. Business |
| 风险分析 | Item 1A. Risk Factors |
| 财务趋势 | Item 7. Management's Discussion and Analysis |
| 会计和报表 | Financial Statements |
| 法律问题 | Item 3. Legal Proceedings |

### 7.3 Table Agent

职责：

1. 识别问题需要的财务指标。
2. 从表格或 XBRL 字段中抽取数据。
3. 统一单位、币种和时间口径。
4. 生成结构化指标对象。

常见指标：

```text
Revenue / Net sales
Gross profit
Operating income
Net income
Operating cash flow
Free cash flow
Capital expenditure
Total assets
Total liabilities
Cash and cash equivalents
Gross margin
Operating margin
Net margin
Revenue growth
```

### 7.4 Calculator Agent

职责：

1. 做财务公式计算。
2. 生成可复查的计算过程。
3. 标记单位和小数位。

公式示例：

```text
gross_margin = gross_profit / revenue
operating_margin = operating_income / revenue
net_margin = net_income / revenue
revenue_growth_yoy = (revenue_t - revenue_t_minus_1) / revenue_t_minus_1
free_cash_flow = operating_cash_flow - capital_expenditure
debt_to_assets = total_liabilities / total_assets
```

输出示例：

```json
{
  "metric": "gross_margin",
  "values": [
    {
      "year": 2023,
      "formula": "gross_profit / net_sales",
      "inputs": {
        "gross_profit": 169148,
        "net_sales": 383285
      },
      "result": 0.4413,
      "display": "44.13%"
    }
  ]
}
```

### 7.5 Evidence Verifier

职责：

判断最终回答中的每个关键 claim 是否被证据支持。

Claim 类型：

```text
numeric_claim: 数字结论
trend_claim: 趋势结论
risk_claim: 风险描述
causal_claim: 原因解释
comparison_claim: 公司/年份对比
```

校验结果：

```json
{
  "claim": "Apple's gross margin increased from 2023 to 2025.",
  "status": "supported",
  "evidence_ids": ["ev_001", "ev_002"],
  "reason": "The calculated gross margin values increase year over year.",
  "confidence": 0.88
}
```

可能状态：

```text
supported: 证据支持
partially_supported: 部分支持
unsupported: 无证据支持
contradicted: 与证据矛盾
numeric_error: 数值错误
ambiguous: 证据不足或问题口径不清
```

### 7.6 Numeric Verifier

职责：

专门检查金融数字错误。

检查项：

1. 年份是否正确。
2. 单位是否正确，例如 USD millions、USD billions。
3. 币种是否正确。
4. 公式是否正确。
5. 小数点和百分比是否正确。
6. 表格行列是否取错。
7. 同比计算是否以正确年份为基准。

示例错误：

```text
把 391,035 million 写成 391,035 billion
把 0.4413 写成 4.413%
把 2024 年收入当成 2025 年收入
把 operating income 当成 net income
```

### 7.7 Report Agent

职责：

输出最终报告。

报告结构：

```text
1. 简短结论
2. 关键数字
3. 计算过程
4. 支撑证据
5. 风险和不确定性
6. Verifier 检查结果
7. 免责声明
```

回答示例格式：

```markdown
## 结论
Apple 过去三年的毛利率整体上升。

## 关键数字
| 年份 | 毛利 | 净销售额 | 毛利率 |
| --- | ---: | ---: | ---: |
| 2023 | ... | ... | ... |
| 2024 | ... | ... | ... |
| 2025 | ... | ... | ... |

## 计算过程
毛利率 = 毛利 / 净销售额。

## 证据
- Evidence 1: Apple 2025 Form 10-K, Consolidated Statements of Operations, page ...
- Evidence 2: Apple 2024 Form 10-K, Consolidated Statements of Operations, page ...

## 校验
- 数值一致性：通过
- 引用支撑度：通过
- 不确定性：低
```

## 8. 算法亮点设计

### 8.1 证据感知 RAG

普通 RAG 的问题是：模型可能检索到相关文本，但最终回答中的结论未必被证据真正支持。

本项目的改进：

1. 检索阶段保留 evidence_id。
2. 生成答案时要求每个关键 claim 绑定 evidence_id。
3. Verifier 对 claim-evidence pair 做支持性判断。
4. 不被证据支持的 claim 要删除或降级为不确定表述。

核心输出不是一段漂亮回答，而是：

```text
answer + claims + evidence + verification
```

### 8.2 Table-aware Retrieval

金融问题大量依赖表格。纯文本 embedding 容易漏掉关键数字。

改进策略：

1. 把表格转换成结构化 metric records。
2. 为每个表格生成 table summary。
3. 同时检索原始表格、表格摘要和指标字段。
4. 对指标型问题优先召回表格 chunk。

示例：

用户问：

```text
Apple 过去三年的毛利率是否上升？
```

系统应优先检索：

```text
Consolidated Statements of Operations
Net sales
Gross margin / gross profit
2023, 2024, 2025
```

而不是只检索包含 "gross margin" 的文本段落。

### 8.3 数值一致性 Verifier

大模型在金融场景中最容易犯数字错误，所以单独做 Numeric Verifier。

方法：

1. LLM 生成回答前，Calculator 先生成结构化计算结果。
2. 回答生成后，从回答中抽取所有数字 claim。
3. 用规则和计算结果逐项核对。
4. 如果不一致，让 Report Agent 重写对应片段。

可以先用规则实现，后续再训练小模型。

### 8.4 小模型微调方向

为了体现大模型算法能力，建议至少做一个小模型实验。

优先级从高到低：

1. Evidence Verifier 微调
2. Financial Reranker 微调
3. Question Router 微调
4. Numeric Error Detector 微调

推荐第一版选择 Evidence Verifier，因为它和项目主题最贴。

训练数据格式：

```json
{
  "question": "Did Microsoft's cloud revenue growth slow down over the last three years?",
  "claim": "Microsoft's cloud revenue growth slowed in the last three fiscal years.",
  "evidence": "Relevant filing snippets and table values...",
  "label": "supported"
}
```

标签：

```text
supported
partially_supported
unsupported
contradicted
numeric_error
```

训练路线：

1. 用强模型生成初始 claim-evidence-label 数据。
2. 人工抽样检查 100 到 200 条，修正标签。
3. 用 Qwen2.5-1.5B/3B、Llama 3.2 1B/3B 或同级别小模型做 LoRA。
4. 对比强模型 verifier、规则 verifier、小模型 verifier 的准确率、成本和延迟。

简历表达：

> 构建金融 claim-evidence 校验数据集，基于 LoRA 微调小模型进行证据支持性判断，在保持较低推理成本的同时提升金融回答的可验证性。

## 9. 评测设计

### 9.1 评测集规模

第一版自建 120 条问题即可：

| 类型 | 数量 | 示例 |
| --- | ---: | --- |
| 事实问答 | 30 | 某公司 2025 年收入是多少？ |
| 指标计算 | 30 | 过去三年毛利率分别是多少？ |
| 趋势分析 | 30 | 经营现金流是否持续改善？ |
| 风险总结 | 30 | 最新年报中的核心风险有哪些？ |

如果时间充裕，扩展到 200 条。

### 9.2 标注字段

每条评测数据包含：

```json
{
  "id": "qa_001",
  "company": "Microsoft",
  "ticker": "MSFT",
  "question": "How did Microsoft's cloud revenue growth change over the last three fiscal years?",
  "question_type": "trend_analysis",
  "gold_answer": "...",
  "gold_evidence": [
    {
      "source": "MSFT 2025 10-K",
      "section": "...",
      "page": 30,
      "text_or_table_ref": "..."
    }
  ],
  "gold_numbers": [
    {
      "metric": "cloud revenue",
      "year": 2025,
      "value": "...",
      "unit": "USD millions"
    }
  ]
}
```

### 9.3 指标

核心评测指标：

| 指标 | 含义 | 目标 |
| --- | --- | --- |
| Answer Accuracy | 最终答案是否正确 | 越高越好 |
| Evidence Recall | 是否召回 gold evidence | 越高越好 |
| Citation Accuracy | 引用是否真正支撑结论 | 越高越好 |
| Numeric Consistency | 数字和计算是否正确 | 越高越好 |
| Hallucination Rate | 是否出现无证据结论 | 越低越好 |
| Tool Success Rate | 工具调用是否完成 | 越高越好 |
| Cost per Query | 单次问答成本 | 越低越好 |
| Latency | 响应耗时 | 越低越好 |

### 9.4 消融实验

至少做四组对比：

```text
Baseline A: 普通 embedding RAG
Baseline B: BM25 + embedding 混合检索
Ours C: 混合检索 + table-aware retrieval
Ours D: 混合检索 + table-aware retrieval + Numeric Verifier
Ours E: 混合检索 + table-aware retrieval + Numeric Verifier + Evidence Verifier
```

预期实验表：

| 方法 | Answer Accuracy | Evidence Recall | Numeric Consistency | Hallucination Rate |
| --- | ---: | ---: | ---: | ---: |
| Embedding RAG | 待实验 | 待实验 | 待实验 | 待实验 |
| Hybrid RAG | 待实验 | 待实验 | 待实验 | 待实验 |
| Table-aware RAG | 待实验 | 待实验 | 待实验 | 待实验 |
| + Numeric Verifier | 待实验 | 待实验 | 待实验 | 待实验 |
| + Evidence Verifier | 待实验 | 待实验 | 待实验 | 待实验 |

### 9.5 Case Study

技术报告中至少写 3 个案例：

1. 普通 RAG 找错年份，Numeric Verifier 修正。
2. 模型生成了没有证据的风险结论，Evidence Verifier 拦截。
3. 纯文本检索漏掉表格，Table-aware Retrieval 找到正确财务数字。

## 10. 技术选型

### 10.1 后端

推荐：

```text
Python
FastAPI
Pydantic
SQLite/PostgreSQL
LlamaIndex 或 LangChain 可选
自定义 Agent Orchestrator
```

如果你想更偏算法和工程能力，Agent 编排可以自己写轻量版本，不必完全依赖框架。

### 10.2 检索和索引

第一版：

```text
BM25: rank-bm25 / Elasticsearch / OpenSearch
Embedding: sentence-transformers / bge / OpenAI embeddings
Vector DB: FAISS / Chroma / LanceDB
Reranker: bge-reranker / cross-encoder / API model
```

### 10.3 文档解析

```text
SEC HTML: BeautifulSoup / sec-api / companyfacts API
PDF: pdfplumber / pymupdf
表格: pandas.read_html / camelot / tabula / 自定义 HTML table parser
XBRL: sec-companyfacts / python-xbrl / edgar APIs
```

### 10.4 模型

大模型：

```text
GPT / Claude / Qwen / DeepSeek / Gemini 均可
```

小模型实验：

```text
Qwen2.5-1.5B/3B
Qwen3-1.7B/4B
Llama 3.2 1B/3B
```

训练：

```text
LoRA / QLoRA
Transformers
PEFT
TRL 可选
```

### 10.5 前端 Demo

快速路线：

```text
Streamlit
```

更正式路线：

```text
Next.js + FastAPI
```

第一版建议用 Streamlit，把精力放在算法和评测上。

## 11. 推荐目录结构

建议项目后续代码目录：

```text
fin/
  FinEvidence-Agent-项目计划书.md
  README.md
  data/
    raw/
    processed/
    eval/
  finevidence/
    __init__.py
    config.py
    data/
      sec_downloader.py
      filing_parser.py
      table_parser.py
      schema.py
    indexing/
      bm25_index.py
      vector_index.py
      hybrid_retriever.py
      table_retriever.py
      reranker.py
    agents/
      planner.py
      retriever_agent.py
      table_agent.py
      calculator_agent.py
      verifier_agent.py
      report_agent.py
      orchestrator.py
    verification/
      claim_extractor.py
      evidence_verifier.py
      numeric_verifier.py
      citation_checker.py
    evaluation/
      dataset.py
      metrics.py
      run_eval.py
      ablation.py
    training/
      build_verifier_dataset.py
      train_lora_verifier.py
      evaluate_verifier.py
    app/
      streamlit_app.py
  tests/
    test_calculator.py
    test_numeric_verifier.py
    test_retriever.py
  reports/
    experiment_report.md
    case_studies.md
```

## 12. MVP 开发路线

### 第 1 周：项目初始化与数据打通

目标：

1. 创建项目结构。
2. 下载或整理 3 家公司的 10-K。
3. 完成 HTML/PDF 文本解析。
4. 建立基础 chunk schema。

产出：

```text
可解析 10-K 文档
生成 processed chunks
能按公司、年份、章节查询文本
```

验收标准：

```text
输入 AAPL 2025 Item 1A，能返回风险章节文本
输入 MSFT 2025 income statement，能返回相关表格或表格文本
```

### 第 2 周：基础 RAG 与混合检索

目标：

1. 实现 BM25 检索。
2. 实现 embedding 检索。
3. 实现 hybrid retriever。
4. 支持按 metadata 过滤公司、年份、filing 类型。

产出：

```text
retrieve(question, ticker, year) -> evidence candidates
```

验收标准：

```text
事实型问题能召回正确章节或表格
风险型问题能优先召回 Item 1A
```

### 第 3 周：Agent 工作流

目标：

1. Planner 判断问题类型。
2. Retriever Agent 获取证据。
3. Table Agent 抽取指标。
4. Calculator Agent 计算财务指标。
5. Report Agent 输出答案。

产出：

```text
CLI 或 notebook 版本的端到端问答
```

验收标准：

```text
输入“Apple 过去三年毛利率变化如何？”
系统输出表格、计算过程、引用证据和结论
```

### 第 4 周：Verifier 与防幻觉机制

目标：

1. 实现 claim extractor。
2. 实现 evidence verifier。
3. 实现 numeric verifier。
4. 生成校验报告。

产出：

```text
answer + claims + evidence + verification report
```

验收标准：

```text
当答案数字和计算结果不一致时，系统能标记 numeric_error
当答案中出现无证据结论时，系统能标记 unsupported
```

### 第 5 周：评测集与 baseline

目标：

1. 构造 60 到 100 条初版 QA。
2. 标注 gold answer、gold evidence、gold numbers。
3. 跑普通 RAG baseline。
4. 跑 hybrid retrieval baseline。

产出：

```text
eval dataset v0.1
baseline evaluation report
```

验收标准：

```text
能输出 Answer Accuracy、Evidence Recall、Numeric Consistency、Hallucination Rate
```

### 第 6 周：算法改进与消融实验

目标：

1. 加入 table-aware retrieval。
2. 加入 Numeric Verifier。
3. 加入 Evidence Verifier。
4. 完成消融实验。

产出：

```text
ablation report
错误案例分析
```

验收标准：

```text
证明至少一个模块带来可观察提升
比如 Numeric Consistency 提升，Hallucination Rate 下降，Evidence Recall 提升
```

### 第 7 周：小模型微调或蒸馏

目标：

1. 构建 claim-evidence verifier 数据集。
2. 用强模型生成弱标注，再人工抽样修正。
3. 微调小模型或训练轻量分类器。
4. 对比小模型 verifier 与 LLM verifier。

产出：

```text
verifier training dataset
LoRA checkpoint 或分类模型
verifier evaluation report
```

验收标准：

```text
小模型能完成 supported / unsupported / numeric_error 分类
报告中包含准确率、成本、延迟对比
```

如果第 7 周时间不足，可以把小模型训练作为进阶功能，把主项目先完成。

### 第 8 周：Demo、README 与简历材料

目标：

1. 完成 Streamlit Demo。
2. 写 README。
3. 写技术报告。
4. 整理实验图表。
5. 准备简历描述和面试讲解。

产出：

```text
可运行 Demo
README
experiment_report.md
case_studies.md
resume_bullets.md
```

验收标准：

```text
面试官 3 分钟能看懂项目价值
10 分钟能看懂系统架构
30 分钟能深入聊算法、评测、失败案例和改进空间
```

## 13. Demo 设计

### 13.1 页面布局

推荐 Streamlit 页面：

```text
顶部：项目名称 + 免责声明

左侧栏：
- 公司选择
- 年份选择
- 问题类型
- 检索 top_k
- 是否启用 verifier

主区域：
- 用户问题输入框
- 最终答案
- 关键指标表
- 计算过程

右侧或下方：
- 证据片段
- 来源链接
- 页码/章节
- verifier 检查结果
- agent 执行轨迹
```

### 13.2 Demo 必须体现的亮点

1. 答案不是孤立文本，而是带证据。
2. 数字不是模型随口生成，而是由 Calculator 计算。
3. Verifier 能指出潜在错误。
4. Agent 执行轨迹可见，体现工具调用和规划能力。

### 13.3 推荐演示问题

```text
1. Apple 过去三年的毛利率变化趋势如何？请给出计算过程。
2. Microsoft 最新年报中提到的主要 AI 相关风险有哪些？
3. Nvidia 过去三年的收入增长是否加速？请引用财报证据。
4. Tesla 最新年报中经营现金流相比上一年变化多少？
5. Amazon 的 AWS 业务在最新年报中有哪些增长驱动？
```

## 14. 技术报告结构

建议最终写一篇项目技术报告，结构如下：

```text
1. Abstract
2. Problem Definition
3. Dataset
4. System Architecture
5. Method
   5.1 Hybrid Financial Retrieval
   5.2 Table-aware Retrieval
   5.3 Numeric Verifier
   5.4 Evidence Verifier
   5.5 Agent Workflow
6. Experiments
   6.1 Evaluation Setup
   6.2 Metrics
   6.3 Baselines
   6.4 Ablation Study
7. Case Studies
8. Failure Analysis
9. Limitations
10. Future Work
```

## 15. 面试讲解主线

面试时不要从“我做了一个金融问答机器人”讲起。应该这样讲：

1. 金融 RAG 最大的问题不是生成，而是证据和数字可靠性。
2. 我把问题拆成检索、表格抽取、指标计算、证据验证四个环节。
3. 我设计了 hybrid retrieval 和 table-aware retrieval 提升证据召回。
4. 我设计了 Numeric Verifier 检查年份、单位、公式和百分比。
5. 我设计了 Evidence Verifier 判断每个 claim 是否被证据支持。
6. 我构建了自评测集，做了 baseline 和消融实验。
7. 我进一步尝试用小模型蒸馏 verifier，降低成本和延迟。

三分钟版本：

> 我做的是一个可验证金融研究 Agent，不是普通股票聊天助手。它输入公司和问题，自动检索 SEC filings，抽取文本和表格证据，计算财务指标，再由 verifier 检查数字和引用是否支持结论。我构建了自评测集，比较普通 RAG、混合检索、表格增强检索和 verifier 的效果，指标包括答案准确率、证据命中率、数值一致性和幻觉率。

## 16. 简历描述

### 16.1 简历一行版

> 构建面向上市公司财报与 SEC filings 的可验证金融研究 Agent，支持多源检索、表格解析、财务指标计算、证据链生成与数值一致性校验。

### 16.2 简历详细版

> 设计并实现 FinEvidence Agent，面向上市公司 10-K/10-Q 等公开披露文件完成金融研究问答；构建 BM25 + embedding + table-aware retrieval 的混合检索系统，支持财务表格解析、指标计算和证据引用；提出 Numeric Verifier 与 Evidence Verifier，对回答中的年份、单位、公式、数值和 claim-evidence 支持关系进行校验；构建自评测集并进行消融实验，评估答案准确率、证据召回率、数值一致性和幻觉率。

### 16.3 如果完成小模型微调

> 基于强模型生成与人工校正构建金融 claim-evidence 校验数据集，使用 LoRA 微调小模型完成证据支持性判断，在保证较低成本和延迟的同时提升金融回答的可验证性。

## 17. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 财报解析复杂 | 开发时间变长 | 第一版优先解析 SEC HTML 和 pandas.read_html，PDF 作为后续 |
| 表格抽取不稳定 | 数字错误 | 优先使用结构化 XBRL/companyfacts 数据 |
| 评测集构造耗时 | 缺少实验结果 | 先做 60 条高质量 QA，再逐步扩展 |
| 小模型微调耗 GPU | 训练受限 | 先做规则 verifier 和 LLM verifier，小模型作为进阶 |
| 金融合规风险 | 项目表述不专业 | 明确不做买卖建议，只做公开信息整理和证据校验 |
| 结果不够亮眼 | 简历说服力不足 | 必须做 ablation、case study、failure analysis |

## 18. 最小可行版本

如果时间只有 2 到 3 周，做这个版本：

1. 支持 3 家公司。
2. 每家公司 2 年 10-K。
3. 支持事实问答、指标计算、风险总结。
4. 实现 hybrid retrieval。
5. 实现 Calculator。
6. 实现基础 Numeric Verifier。
7. 做 50 条评测。
8. 做 Streamlit Demo。

这个版本已经能写成一个完整项目：

> 财报 RAG + 表格计算 + 数值校验 + 可追溯证据。

## 19. 进阶版本

如果时间有 6 到 8 周，做完整版本：

1. 支持 5 到 10 家公司。
2. 支持 3 年以上历史数据。
3. 引入 table-aware retrieval。
4. 引入 Evidence Verifier。
5. 自建 120 到 200 条评测集。
6. 做完整消融实验。
7. 微调小模型 verifier。
8. 写技术报告和 Demo。

## 20. 参考资料

1. FinanceBench: A New Benchmark for Financial Question Answering  
   https://arxiv.org/abs/2311.11944

2. Finance Agent Benchmark: Benchmarking LLMs on Real-world Financial Research Tasks  
   https://arxiv.org/abs/2508.00828

3. FinRobot: An Open-Source AI Agent Platform for Financial Applications using Large Language Models  
   https://arxiv.org/abs/2405.14767

4. FinRobot: AI Agent for Equity Research and Valuation with Large Language Models  
   https://arxiv.org/abs/2411.08804

5. SEC EDGAR APIs  
   https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## 21. 最终建议

这个项目的关键不是“做一个金融聊天机器人”，而是把主题牢牢收束到：

```text
可验证金融研究 Agent
= 财报检索
+ 表格理解
+ 指标计算
+ 证据链
+ 数值校验
+ 自动评测
```

只要你能做出评测和消融实验，它就可以从普通应用项目升级为大模型算法与 Agent 算法项目。
