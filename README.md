# DeepResearch

**多智能体深度研究系统** 
基于 LangGraph 的自动化 AI 研究助手 · 对抗式质量审查 · Self-Evolution 迭代

---

## 目录

- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [工作流程](#工作流程)
- [智能体设计](#智能体设计)
- [LLM 评估体系](#llm-评估体系)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [示例输出](#示例输出)

---

## 核心特性

- **多层嵌套图架构** — 主流水线→Supervisor 循环子图→Researcher 搜索子图的三层设计，支持复杂任务的多轮迭代
- **六类专业化 Agent** — Supervisor / Research / Draft / Evaluator / Red Team / Writer，各司其职协同完成研究全流程
- **并行搜索调度** — Supervisor 动态拆解子任务，最多 3 个 Research Agent 并行执行迭代式网络搜索（搜索→反思→再搜索）
- **分层模型路由** — 按 Agent 复杂度分配不同量级模型，在保障关键节点推理能力的同时显著降低整体调用成本
- **三段式 Prompt 装配** — base + phase + dynamic 解耦设计，将全局行为约束、阶段职责契约与动态上下文注入分离
- **对抗式质量审查** — Red Team 从攻击者视角审查逻辑漏洞与事实盲区，最多 3 轮批评+PASS/FAIL 机制
- **self-Evolution 评估** — Evaluator 全面性/准确性/连贯性三维打分，低于 6.0 自动触发质量门控驱动重新规划
- **完整评测体系** — 自建 LLM-as-Judge 5 维度评分 + 事实核查模块，综合性平均分 9.3 vs DeepSeek V4 Flash 7.6

---

## 系统架构

```
用户输入 (Query)
    │
    ▼
┌─────────────────────┐
│   Draft Agent       │  生成研究简报 + 报告初稿
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│              Supervisor Agent                    │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Think   │  │ Dispatch x3  │  │  Refine   │  │
│  │  Tool    │  │ (并行研究)    │  │  Report   │  │
│  └──────────┘  └──────┬───────┘  └─────┬─────┘  │
│                       │                 │        │
│          ┌────────────▼──────┐    ┌─────▼─────┐  │
│          │ Research Agent x3 │    │ Evaluator │  │
│          │  (网络搜索+压缩)   │    │  (评分)    │  │
│          └───────────────────┘    └─────┬─────┘  │
│                                        │        │
│                                  ┌─────▼─────┐  │
│                                  │ Red Team  │  │
│                                  │ (对抗审查) │  │
│                                  └───────────┘  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────┐
│  Final Report Gen   │  综合所有研究发现，输出最终报告
└─────────────────────┘
```

---

## 工作流程

整个研究过程分为 4 个阶段，通过 LangGraph 的有向图编排：

**Stage 1 — 研究简报生成**

用户输入研究问题后，Draft Agent 将模糊的需求转化为结构化的研究简报（research brief），明确调研方向、关注重点和注意事项。

**Stage 2 — 报告初稿生成**

基于研究简报，Draft Agent 快速生成一份报告初稿（draft report），作为后续迭代优化的起点。

**Stage 3 — 监督式迭代研究**（核心循环）

Supervisor Agent 进入迭代循环：

1. **策略反思** — 通过 Think Tool 分析当前进展，识别研究盲区
2. **任务分解** — 将待研究主题拆解为并行子任务（最多 3 个 Research Agent 同时工作）
3. **并行搜索** — Research Agent 执行迭代式网络搜索（搜索 → 反思 → 再搜索），并对结果进行压缩
4. **报告优化** — 根据新发现修正报告草稿
5. **质量评估** — Evaluator Agent 对报告打分（全面性 / 准确性 / 连贯性，各 0-10 分）
6. **对抗审查** — Red Team Agent 以批评者视角审查报告的逻辑漏洞和盲区（最多 3 轮）
7. **自我纠正** — 未解决的批评意见会作为 System Message 注入到下一轮 Supervisor 对话中

当质量达标或达到最大迭代次数时，循环结束。

**Stage 4 — 最终报告生成**

Writer Agent 综合研究简报、所有研究发现和报告初稿，输出最终的 Markdown 研究报告。

---

## 智能体设计

| Agent | 职责 | 关键特性 | 推荐模型量级 |
|-------|------|---------|-------------|
| **Supervisor** | 总协调者，负责任务分解与调度 | 去噪算法、动态上下文注入、质量驱动迭代、多轮 replan-dispatch 循环 | 大 |
| **Research Agent** | 执行网络搜索和信息提取 | 迭代式搜索（搜索→反思→再搜索）、结果压缩、并行调度 | 中 |
| **Draft Agent** | 生成研究简报和报告初稿 | 结构化输出（Pydantic schema）、需求模糊性解析 | 中 |
| **Red Team** | 对抗式质量审查 | 最多 3 轮批评、PASS/FAIL 机制、未解决意见注入 System Message | 大 |
| **Evaluator** | 多维度报告评分 | 全面性/准确性/连贯性三维打分、self-evolution 触发条件判断 | 中 |
| **Writer** | 最终报告生成 | 整合所有研究发现、格式化 Markdown 输出 | 中 |

---

## LLM 评估体系

### 评测框架概述

DeepResearch 采用自建的 **LLM-as-Judge** 评测框架，结合事实核查模块对研究报告进行客观、可验证的多维度评分。评测流程如下：

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│ 研究问题    │ ──▶ │ DeepResearch │ ──▶ │            │     │            │
│ (Query)     │     │ + Baseline   │ ──▶ │ LLM Judge  │ ──▶ │ 对比报告   │
└─────────────┘     └──────────────┘     │ (Qwen)      │     │ (Markdown) │
         │                      │        └─────┬───────┘     └────────────┘
         │                      │              │
         │              ┌───────▼────────┐     │
         │              │ 事实核查模块   │     │
         │              │ Tavily 搜索验证 │◀────┘
         │              └────────────────┘
         │                    │
         └────────────────────┘
       相同研究问题输入
```

### 5 维度评分标准

| 维度 | 英文名 | 评分说明 |
|------|--------|---------|
| **全面性** | comprehensiveness | 是否覆盖了问题的关键方面，有无遗漏核心要点 |
| **准确性** | accuracy | 事实是否正确，有无编造或过时信息（结合事实核查结果） |
| **深度** | depth | 分析是否有深度，是否提供了对比和权衡，而非泛泛而谈 |
| **结构** | structure | 组织是否清晰，逻辑是否严密，章节划分是否合理 |
| **信息来源** | sourcing | 有无可靠来源引用，信息是否可验证 |

### 评判原则

- **长不等于好** — 填充内容多的报告应给低分
- **短不等于差** — 精准覆盖核心要点的报告应给高分
- **来源至上** — 有明确来源引用和可验证信息的报告得分更高
- **诚实加分** — 明确标注不确定性或缺口的报告应获得准确性加分
-  **事实一致** — 报告中与事实核查结果一致的信息应加分，矛盾的信息应扣分

### 评测基准

| 指标 | DeepResearch | DeepSeek V4 Flash (带搜索) | 领先幅度 |
|------|--------------|--------------------------|---------|
| 全面性 | 9.5 | 7.9 | +20% |
| 准确性 | 9.3 | 8.0 | +16% |
| 深度 | 9.3 | 8.2 | +11% |
| 结构 | 8.9 | 8.6 | +4% |
| 信息来源 | **9.7** | 5.3 | **+83%** |
| **综合平均分** | **9.3** | **7.6** | **+22%** |

> 💡 **信息来源可靠性领先近 1.8 倍** — DeepResearch 的多智能体协作模式在来源引用和信息可验证性上表现突出。

### 运行评测

```bash
# 设置 DeepSeek API Key（用于生成 Baseline）
export DEEPSEEK_API_KEY=your_deepseek_api_key

# 运行评测脚本
python -m evaluation.compare
```

评测结果将保存至 `evaluation/results.md`。

---

## 快速开始

### 环境要求

- Python 3.11+
- Jupyter Notebook / JupyterLab

### 安装步骤

**1. 克隆项目**

```bash
git clone <your-repo-url>
cd DeepResearch
```

**2. 安装依赖**

```bash
pip install -r requirements.txt
```

**3. 配置环境变量**

```bash
cp env.example .env
```

编辑 `.env`，填入 LangSmith 配置（可选，用于可观测性追踪）：

```env
LANGCHAIN_TRACING_V2=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=your_project_name
```

**4. 配置模型和搜索 API**

编辑 `config.yml`，填入你的 API 配置：

```yaml
stages:
  prod:
    cognition:
      openai:
        base_url: https://your-api-endpoint
        api_key: your-api-key
        default_model: gpt-4o-mini
```

> 需要配置 OpenAI 兼容的 API（支持自定义 base_url）和 Tavily Search API。

**5. 运行**

在 Jupyter 中打开 `run.ipynb`，按顺序执行所有 Cell 即可。

单次研究任务大约需要 **10-20 分钟** 完成。

---

## 配置说明

所有配置集中在 `config.yml`，采用层级结构：

### LLM 配置

```yaml
cognition:
  openai:
    base_url: http://xxx          # OpenAI 兼容 API 地址
    api_key: sk-xxxx              # API Key
    default_model: gpt-5.4-mini   # 默认模型
    temperature: 0                # 温度参数
    timeout_seconds: 600          # 超时时间
```

### 搜索配置

```yaml
search:
  backend: tavily
  tavily:
    api_key: tvly-dev-xxxx        # Tavily API Key
    max_results: 3                # 单次搜索返回结果数
    topic: general                # 搜索主题: general / news / finance
    include_raw_content: true     # 是否包含原始网页内容
```

### Agent 角色配置

每个 Agent 可以指定不同的模型：

```yaml
roles:
  supervisor:
    backend: openai
    handle: gpt-5.4-nano         # Supervisor 使用的模型
  red_team:
    backend: openai
    handle: gpt-5.4-mini         # Red Team 使用的模型（建议用更强的模型）
  researcher_main:
    handle: gpt-5.4-nano         # Research Agent 主模型
  researcher_summarizer:
    handle: gpt-5.4-nano         # 网页内容摘要模型
  researcher_compressor:
    handle: gpt-5.4-nano         # 研究结果压缩模型
  writer:
    handle: gpt-5.4-nano         # 最终报告生成模型
  draft:
    handle: gpt-5.4-nano         # 简报和初稿生成模型
  evaluator:
    handle: gpt-5.4-nano         # 质量评估模型
```

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_researcher_iterations` | 15 | Supervisor 最大迭代次数 |
| `max_concurrent_researchers` | 3 | 最大并行 Research Agent 数量 |
| `min_need_repair_score` | 6.0 | 低于此分数触发质量修复提醒 |
| `MAX_CRITIC` | 3 | Red Team 最大批评轮数 |

---

## 项目结构

```
DeepResearch/
├── config.yml                          # 全局配置文件
├── requirements.txt                    # Python 依赖
├── env.example                         # 环境变量模板
├── run.ipynb                           # 主执行 Notebook
├── deep_research/                      # 核心源码
│   ├── __init__.py
│   ├── agent_builder.py               # 主工作流图构建
│   ├── llm.py                         # LLM 客户端初始化
│   ├── logging.py                     # 日志配置
│   ├── utils.py                       # 工具函数
│   ├── agents/                        # 智能体实现
│   │   ├── supervisor.py             # Supervisor Agent + 子图
│   │   ├── research_agent.py         # Research Agent
│   │   ├── red_team_agent.py         # Red Team Agent
│   │   ├── evaluator_agent.py        # Evaluator Agent
│   │   └── draft_agent.py            # Draft Agent
│   ├── prompts/                       # 提示词模板
│   │   ├── research_brief.py         # 研究简报生成提示词
│   │   ├── draft_report.py           # 初稿生成提示词
│   │   ├── research_agent.py         # Research Agent 提示词
│   │   ├── research_denoise.py       # Supervisor 去噪算法提示词
│   │   ├── red_team.py               # Red Team 提示词
│   │   ├── draft_evaluator.py        # 评估提示词
│   │   ├── final_report.py           # 最终报告提示词
│   │   └── ...                       # 其他辅助提示词
│   ├── states/                        # 状态定义 (Pydantic Schema)
│   │   ├── supervisor.py             # Supervisor 状态
│   │   ├── research.py               # Research Agent 状态
│   │   ├── draft.py                  # 主工作流状态
│   │   ├── quality.py                # 质量评分记录
│   │   ├── critique.py               # 对抗审查记录
│   │   └── eval_result.py            # 评估结果
│   ├── tools/                         # 工具函数
│   │   ├── tool.py                   # 搜索/反思/精修工具
│   │   └── search_factory.py         # 搜索后端工厂
│   └── providers/                     # 搜索提供商
│       └── customsearch.py           # 自定义搜索后端
└── results/                           # 输出报告目录
    ├── output_report_sample_1.md     # 示例报告 1
    └── output_report_sample_2.md     # 示例报告 2
```

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| **Agent 框架** | LangGraph | 有向图编排多智能体工作流，支持子图和循环 |
| **LLM 集成** | LangChain + LangChain OpenAI | 统一 LLM 调用接口，结构化输出 |
| **数据验证** | Pydantic V2 | 状态管理、Schema 定义、结构化解析 |
| **网络搜索** | Tavily API | 高质量网页搜索和原始内容提取 |
| **可观测性** | LangSmith | LLM 调用追踪、调试、性能分析 |
| **执行环境** | Jupyter Notebook | 交互式运行和结果展示 |
| **终端渲染** | Rich | Markdown 报告终端渲染 |
| **评测裁判** | Qwen (DashScope) | LLM-as-Judge 独立评分 |

