# FactStack

[English](README.md) | [中文](README_zh.md)

**面向技术文档的证据优先 RAG 问答系统**

FactStack 是一个专为技术文档和 Runbook 设计的检索增强生成（RAG）系统。它优先提供**基于证据的答案和引用**，并内置**拒答逻辑**来处理证据不足的情况。

## 核心特性

- 📚 **证据优先回答**: 所有答案都基于检索到的文档，并带有明确的引用标记
- 🚫 **拒答逻辑**: 当证据不足时，系统会明确拒绝回答，避免幻觉
- 🔍 **混合检索**: 结合向量搜索（语义）和 BM25（关键词）以获得更好的召回率
- 🌐 **跨语言检索**: 支持用中文提问英文文档，采用双通道检索
- 📊 **重排序**: 多阶段管道，通过重排序提高精确度
- 📝 **完整追踪**: 为每次查询生成 JSONL 追踪日志，记录管道各阶段的时间
- 🧪 **内置评测**: 评测框架，包含召回率、引用精确度和拒答准确率等指标
- 🔧 **可配置提示词**: 多种提示词配置，适用于不同场景

## 快速开始

### 安装

```bash
# 克隆并安装
pip install -r requirements.txt
pip install -e .
```

### 一键演示（无需 API Key）

FactStack 内置 DummyLLM，可以在没有 OpenAI API Key 的情况下运行完整管道：

```bash
# 1. 导入文档
python -m factstack.ingest --docs ./docs --persist ./db

# 2. 提问
python -m factstack.ask --db ./db --question "如何排查 Kubernetes 中的 CrashLoopBackOff？"

# 3. 运行评测
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml
```

### 使用 OpenAI API

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your-key-here

python -m factstack.ask --db ./db --question "部署服务的步骤是什么？"
```

### 自定义模型

```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o
export EMBEDDING_MODEL=text-embedding-3-large
export OPENAI_API_KEY=your-key-here

python -m factstack.ask --db ./db --question "如何回滚部署？"
```

## 项目结构

```
factstack/
├── docs/                      # 示例技术文档
├── prompts/
│   ├── base.yaml             # 默认提示词配置
│   └── strict.yaml           # 更严格的拒答配置
├── artifacts/                 # 生成的输出（追踪日志、答案）
├── src/factstack/
│   ├── config.py             # 配置管理
│   ├── ingest.py             # 文档导入 CLI
│   ├── ask.py                # 问答 CLI
│   ├── eval.py               # 评测 CLI
│   ├── pipeline/
│   │   ├── chunking.py       # 文档分块
│   │   ├── embeddings.py     # 嵌入向量生成
│   │   ├── vector_store.py   # ChromaDB 向量存储
│   │   ├── bm25_store.py     # BM25 关键词索引
│   │   ├── rerank.py         # 重排序逻辑
│   │   ├── assemble.py       # 上下文组装
│   │   └── refusal.py        # 拒答/不确定性逻辑
│   ├── llm/
│   │   ├── base.py           # LLM 接口
│   │   ├── openai_llm.py     # OpenAI 实现
│   │   ├── dummy_llm.py      # 无 API 测试
│   │   └── schemas.py        # Pydantic 输出模式
│   └── observability/
│       └── tracer.py         # 管道追踪
└── tests/
    └── eval_set.yaml         # 评测用例
```

## 使用指南

### 文档导入

```bash
# 基本导入
python -m factstack.ingest --docs ./docs --persist ./db

# 自定义分块设置
python -m factstack.ingest --docs ./docs --persist ./db --chunk-size 600 --chunk-overlap 100
```

### 提问

```bash
# 基本提问
python -m factstack.ask --db ./db --question "如何回滚部署？"

# 使用不同的提示词配置
python -m factstack.ask --db ./db --question "..." --prompt strict

# 输出 JSON 格式
python -m factstack.ask --db ./db --question "..." --json

# 自定义 top-k 检索数量
python -m factstack.ask --db ./db --question "..." --topk 10
```

### 评测

```bash
# 运行评测套件
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml

# 使用严格提示词
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml --prompt strict

# 自定义输出位置
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml --output ./results.json
```

## 输出格式

### 答案结构

每个答案包含：

```json
{
  "answer": "带有 [C1]、[C2] 引用的答案",
  "citations": [
    {"chunk_id": "...", "source": "file.md", "text": "...", "score": 0.85}
  ],
  "confidence": 0.75,
  "missing_info": ["需要的额外上下文"],
  "reasoning": "答案推导的解释",
  "is_refusal": false,
  "refusal_reason": null
}
```

### 追踪格式（JSONL）

每次查询会在 `artifacts/` 目录生成追踪文件：

```json
{"ts": "...", "run_id": "abc123", "stage": "vector_search", "input_summary": "...", "output_summary": "5 results", "latency_ms": 45.2, "ok": true}
{"ts": "...", "run_id": "abc123", "stage": "rerank", "input_summary": "...", "output_summary": "3 results", "latency_ms": 120.5, "ok": true}
```

## 添加新文档

1. 将 Markdown 或 TXT 文件添加到 `./docs/`
2. 重新运行导入：`python -m factstack.ingest --docs ./docs --persist ./db`
3. 索引将使用新文档重建

## 添加评测用例

编辑 `tests/eval_set.yaml`：

```yaml
cases:
  - question: "你的测试问题"
    expected_sources:
      - "document_name"  # 源路径的部分匹配
    expected_answer_contains:
      - "预期关键词"
    difficulty: medium  # easy/medium/hard
    should_refuse: false  # 如果应该拒答则为 true
```

## 评测指标

- **Recall@K**: 是否检索到预期的源文档？
- **Citation Precision**: 引用是否来自预期的源文档？
- **Answer Groundedness**: 答案是否包含引用？
- **Refusal Accuracy**: 系统在应该拒答时是否拒答？

## 配置

### 环境变量

- `LLM_PROVIDER`: `openai` 或 `dummy`（默认：`dummy`）
- `LLM_MODEL`: LLM 使用的模型（默认：`gpt-4o-mini`）
- `EMBEDDING_MODEL`: 嵌入向量使用的模型（默认：`text-embedding-3-small`）
- `OPENAI_API_KEY`: 使用 OpenAI 时必需

使用自定义模型的示例：
```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o
export EMBEDDING_MODEL=text-embedding-3-large
export OPENAI_API_KEY=your-key-here

python -m factstack.ask --db ./db --question "如何部署服务？"
```

### 提示词配置

- `base.yaml`: 通用场景的平衡配置
- `strict.yaml`: 更高的拒答阈值，更严格的引用要求

## 设计原则

1. **无证据不回答**: 每个声明都必须有检索到的文档块支持
2. **明确的不确定性**: 当证据不足时，系统会明确表示
3. **完整可追踪**: 每个管道阶段都有日志记录，便于调试
4. **评测驱动**: 内置评测确保长期质量

## 跨语言检索

### 问题描述

当用中文（或其他 CJK 语言）提问英文文档时，传统 RAG 系统往往会失败，原因包括：

1. **嵌入空间不匹配**: 中文查询的嵌入向量与英文文档嵌入向量对齐不佳
2. **关键词不匹配**: BM25/关键词搜索在查询和文档使用不同语言时失效

这会导致非常低的相关性得分（如 ~0.01），即使存在相关文档也会触发拒答。

### 解决方案：双通道检索

FactStack 实现了双通道检索方案：

1. **查询语言检测**: 自动检测查询是否包含 CJK 字符
2. **查询翻译**: 将非英文查询翻译为检索友好的英文关键词
3. **双通道检索**: 使用原始查询和翻译后的查询并行搜索
4. **多路召回合并**: 合并两个通道的结果，按 chunk_id 去重
5. **统一重排序**: 对合并后的结果进行重排序

### 使用示例

**中文提问英文文档：**

```bash
# 用中文提问
python -m factstack.ask --db ./db --question "如何回滚部署？"

# 输出：
# QueryLang=zh, CrossLingual=True, Translation=rule
# 翻译后的查询："rollback deploy deployment"
# 引用来自 deployment_runbook.md
```

**关闭跨语言检索：**

```bash
python -m factstack.ask --db ./db --question "如何回滚部署？" --cross-lingual off
```

**控制翻译模式：**

```bash
# 使用 LLM 翻译（需要 API key）
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode llm

# 使用基于规则的词典翻译（无需 API key）
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode rule

# 关闭翻译
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode off
```

### CLI 参数

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--cross-lingual` | `on`, `off` | `on` | 启用双通道检索 |
| `--translate` | `on`, `off` | `on` | 启用查询翻译 |
| `--translation-mode` | `llm`, `rule`, `off` | `llm` | 翻译方法 |
| `--topk` | 整数 | 8 | 每个检索通道的文档块数 |
| `--rerank-topk` | 整数 | 5 | 重排序后的文档块数 |

### 翻译模式

- **`llm`**: 使用配置的 LLM 进行翻译（最佳质量，需要 API key）
- **`rule`**: 使用内置中英词典（无需 API key，可离线使用）
- **`off`**: 完全关闭翻译

当设置 `--translation-mode llm` 但没有可用的 API key 时，系统会自动降级到 `rule` 模式。

### 跨语言追踪字段

追踪日志包含跨语言检索的额外字段：

```json
{"stage": "language_detect", "metadata": {"query_language": "zh", "needs_translation": true}}
{"stage": "query_translate", "metadata": {"original_query": "如何回滚部署？", "translated_query": "rollback deploy deployment", "translation_mode": "rule"}}
{"stage": "dual_retrieval", "metadata": {"original_query": "...", "translated_query": "...", "total_candidates": 12, "multi_channel_hits": 3}}
```

### 多指标拒答

拒答逻辑使用多个指标而非仅依赖最高分数：

- **Top-N 平均分**: 前 5 个文档块的平均分数
- **高质量证据数量**: 超过质量阈值的文档块数量
- **覆盖率**: 相关结果在前几名中的占比
- **跨语言加成**: 当使用翻译时采用更宽松的阈值

这可以防止在跨语言检索通过翻译通道找到相关文档时出现误拒答。

## 许可证

MIT
