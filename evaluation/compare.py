#***********************************************
#      Filename: compare.py
#   Description: DeepResearch vs DeepSeek V4 Flash 对比评测脚本
#***********************************************

"""
用法:
    python -m evaluation.compare

功能:
    1. 读取 results/ 下已有的 DeepResearch 报告
    2. 用相同研究问题 + 实时网络搜索调用 DeepSeek V4 Flash，生成 Baseline 回答
    3. 用 Qwen 作为独立裁判，结合事实核查搜索结果，对两份回答分别做多维度打分
    4. 输出 evaluation/results.md 对比报告

前置条件:
    export DEEPSEEK_API_KEY=your_deepseek_api_key
"""

import os
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from tavily import TavilyClient

# ===== 配置 =====

# DEEPSEEK_API_KEY = 
# DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
# DEEPSEEK_MODEL = "deepseek-chat"  # V4 Flash 模型名，如与实际不同请修改

# TAVILY_API_KEY = 
# TAVILY_BASE_URL = "https://api.tavily.com"

# CACHE_FILE = Path(__file__).parent / "cache.json"


# ===== 评测任务定义 =====

@dataclass
class EvalTask:
    """一个评测任务：研究问题 + 已有报告路径"""
    id: str
    topic: str
    report_path: str
    brief_question: str  # 发给 DeepSeek 的问题


EVAL_TASKS = [
    EvalTask(
        id="nvidia_gpu",
        topic="英伟达（NVIDIA）最新 GPU 调研报告",
        report_path="results/output_report_sample_1.md",
        brief_question="请详细调研 NVIDIA（英伟达）截至 2026 年 3 月的最新 GPU 产品线，包括数据中心（Blackwell 系列）、消费级（GeForce RTX 50 系列）、专业工作站（RTX PRO 系列）。要求列出具体型号、关键规格（显存、功耗、性能指标）、发布时间、适用场景，并给出信息来源。",
    ),
    EvalTask(
        id="agent_memory_v1",
        topic="个性化记忆（Memory）能力调研报告",
        report_path="results/output_report_sample_2.md",
        brief_question="请详细调研当前主流 AI Agent / 大模型系统中的个性化记忆（Memory）功能如何实现，包括短期记忆（会话内上下文管理）和长期记忆（跨会话偏好/事实存储）的技术方案、架构设计、写入/检索/更新/遗忘机制，以及不同框架（LangGraph、AutoGen、Letta 等）的实现差异。",
    ),
    EvalTask(
        id="agent_memory_v2",
        topic="AI Agent 个性化记忆功能工程落地与技术演进深度调研报告",
        report_path="results/output_report_sample_3.md",
        brief_question="请以 2026 年为基准，深度调研 AI Agent 框架中短期记忆与长期记忆的实现范式、技术路线差异（向量数据库 vs 结构化数据库 vs 模型内化 vs 混合架构）、关键工程因素（延迟、一致性、隐私合规、可解释性）、商业化产品部署模式（Gong、Notion AI、Cohere 等），以及未来 18-36 个月的演进方向。",
    ),
]


# ===== 评分模型 =====

class ReportScore(BaseModel):
    """单份报告的多维度评分"""
    comprehensiveness: int = Field(description="全面性 (0-10): 是否覆盖了问题的关键方面")
    accuracy: int = Field(description="准确性 (0-10): 事实是否正确，有无编造或过时信息")
    depth: int = Field(description="深度 (0-10): 分析是否有深度，是否提供了对比和权衡")
    structure: int = Field(description="结构 (0-10): 组织是否清晰，逻辑是否严密")
    sourcing: int = Field(description="信息来源 (0-10): 有无可靠来源引用，信息是否可验证")
    summary: str = Field(description="一句话评价该报告")


class ComparisonResult(BaseModel):
    """两份报告的对比结果"""
    report_a: ReportScore  # DeepResearch
    report_b: ReportScore  # DeepSeek
    winner: str = Field(description="'a' 表示 DeepResearch 胜出, 'b' 表示 DeepSeek 胜出, 'tie' 表示平局")
    overall_summary: str = Field(description="一句话总结对比结论")


def _get_tavily_client() -> TavilyClient:
    """获取 Tavily 搜索客户端"""
    return TavilyClient(api_key=TAVILY_API_KEY, api_base_url=TAVILY_BASE_URL)


def search_web(query: str, max_results: int = 5) -> str:
    """执行 Tavily 网络搜索，返回格式化的搜索结果"""
    client = _get_tavily_client()
    result = client.search(
        query=query,
        max_results=max_results,
        include_raw_content=False,
        topic="general",
    )
    if not result.get("results"):
        return "未找到搜索结果。"

    parts = []
    for i, r in enumerate(result["results"], 1):
        parts.append(f"来源 {i}: {r['title']}\nURL: {r['url']}\n摘要: {r['content']}")
    return "\n\n---\n\n".join(parts)


async def _search_and_generate_for_deepseek(question: str) -> str:
    """先执行网络搜索获取最新信息，再将搜索结果作为上下文提供给 DeepSeek 生成回答"""
    # 用问题本身作为搜索query
    print("  [搜索] 正在执行网络搜索...")
    search_results = await asyncio.to_thread(search_web, question, max_results=5)
    print(f"  [搜索] 获取到搜索结果 ({len(search_results)} 字符)")

    # 将搜索结果作为上下文提供给 DeepSeek
    enhanced_prompt = f"""请根据以下搜索结果，生成一份详尽、结构化、有事实依据的研究报告。

=== 最新搜索结果 ===
{search_results}

=== 研究问题 ===
{question}

请基于以上搜索结果撰写报告。如果搜索结果中的信息不充分，可以补充你的知识，但应优先使用搜索结果中的信息。请在报告中引用来源。
"""
    return await call_deepseek(enhanced_prompt)


# ===== DeepSeek Baseline 生成 =====

async def call_deepseek(question: str) -> str:
    """调用 DeepSeek V4 Flash 生成回答"""
    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    response = await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": "你是一位专业的研究助手。请根据用户的问题生成一份详尽、结构化、有事实依据的研究报告。请列出具体数据、技术细节和来源。"},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=32768,
    )
    return response.choices[0].message.content


# ===== 加载已有报告 =====

def load_existing_report(path: str) -> str:
    """加载已有的 DeepResearch 报告"""
    project_root = Path(__file__).parent.parent
    full_path = project_root / path
    if not full_path.exists():
        raise FileNotFoundError(f"报告文件不存在: {full_path}")
    return full_path.read_text(encoding="utf-8")


# ===== Baseline 缓存 =====

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ===== LLM-as-Judge 对比评分 =====

JUDGE_SYSTEM_PROMPT = """你是一位严格、客观的研究质量评估专家。你的任务是对比两份针对同一研究问题的报告，分别对每份报告进行多维度独立打分。

评分维度 (每项 0-10 分):
- comprehensiveness (全面性): 是否覆盖了问题的关键方面
- accuracy (准确性): 事实是否正确，有无编造或过时信息 — 请结合事实核查结果判断
- depth (深度): 分析是否有深度，是否提供了对比和权衡，而非泛泛而谈
- structure (结构): 组织是否清晰，逻辑是否严密
- sourcing (信息来源): 有无可靠来源引用，信息是否可验证

评判原则:
- 长不等于好。填充内容多的报告应给低分
- 短不等于差。精准覆盖核心要点的报告应给高分
- 有明确来源引用和可验证信息的报告得分更高
- 明确标注不确定性或缺口的报告应获得准确性加分
- 报告中与事实核查结果一致的信息应加分，矛盾的信息应扣分

请分别给报告 A 和报告 B 打分，并指出哪个整体更好。以 JSON 格式返回。"""

JUDGE_USER_PROMPT = """研究问题: {topic}

=== 事实核查参考 ===
{fact_check_results}

--- 报告 A (DeepResearch 多智能体系统) ---
{report_a}

--- 报告 B (DeepSeek V4 Flash 带搜索) ---
{report_b}

请分别给两份报告独立打分，并指出哪个整体更好。在准确性维度上，请特别关注报告中的关键事实是否与事实核查结果一致。"""


class FactCheckClaims(BaseModel):
    """从报告中提取的关键事实声明"""
    claims: List[str] = Field(description="从报告中提取的 3-5 条关键事实声明，每条声明应简洁且可搜索")


async def _extract_claims(report: str) -> List[str]:
    """从报告中提取关键事实声明用于搜索验证"""
    short = report[:8000]
    extractor = ChatOpenAI(
        model="qwen-plus-2025-12-01",
        openai_api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0,
        max_tokens=1024,
    ).with_structured_output(FactCheckClaims)

    try:
        result = await extractor.ainvoke([
            SystemMessage(content="从以下研究报告中提取 3-5 条关键事实声明，每条声明应简洁可搜索（如具体型号、价格、发布时间、技术参数等），方便后续通过搜索引擎验证真伪。"),
            HumanMessage(content=short),
        ])
        return result.claims[:5]
    except Exception:
        return []


async def _fact_check(topic: str, report_a: str, report_b: str) -> str:
    """对两份报告中的关键事实执行网络搜索验证"""
    print("  [事实核查] 正在提取关键声明...")
    claims_a = await _extract_claims(report_a)
    claims_b = await _extract_claims(report_b)

    # 合并去重
    all_claims = list(dict.fromkeys(claims_a + claims_b))[:8]
    if not all_claims:
        return "未能从报告中提取到关键事实声明，无法进行事实核查。"

    print(f"  [事实核查] 提取到 {len(all_claims)} 条关键声明，正在搜索验证...")
    check_results = []

    for claim in all_claims:
        query = f"{topic} {claim}"
        try:
            search_result = await asyncio.to_thread(search_web, query, max_results=3)
            check_results.append(f"声明: {claim}\n搜索结果:\n{search_result}")
        except Exception as e:
            check_results.append(f"声明: {claim}\n搜索失败: {e}")

    return "\n\n---\n\n".join(check_results)


async def judge_comparison(
    topic: str,
    report_a: str,
    report_b: str,
) -> ComparisonResult:
    """用 Qwen 作为裁判，结合事实核查结果对两份报告进行对比评分"""
    # 先进行事实核查搜索
    fact_check_results = await _fact_check(topic, report_a, report_b)
    print(f"  [事实核查] 完成 ({len(fact_check_results)} 字符)")

    max_len = 10000
    a_truncated = report_a[:max_len] + "\n...(已截断)" if len(report_a) > max_len else report_a
    b_truncated = report_b[:max_len] + "\n...(已截断)" if len(report_b) > max_len else report_b
    fc_truncated = fact_check_results[:12000] + "\n...(已截断)" if len(fact_check_results) > 12000 else fact_check_results

    judge = ChatOpenAI(
        model="qwen-plus-2025-12-01",
        openai_api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0,
        max_tokens=4096,
    ).with_structured_output(ComparisonResult)

    return await judge.ainvoke([
        SystemMessage(content=JUDGE_SYSTEM_PROMPT),
        HumanMessage(content=JUDGE_USER_PROMPT.format(
            topic=topic,
            fact_check_results=fc_truncated,
            report_a=a_truncated,
            report_b=b_truncated,
        )),
    ])


# ===== 结果汇总 =====

@dataclass
class EvalResult:
    task_id: str
    topic: str
    deepseek_word_count: int
    deepresearch_word_count: int
    dr_comprehensiveness: int
    ds_comprehensiveness: int
    dr_accuracy: int
    ds_accuracy: int
    dr_depth: int
    ds_depth: int
    dr_structure: int
    ds_structure: int
    dr_sourcing: int
    ds_sourcing: int
    dr_summary: str
    ds_summary: str
    winner: str
    overall_summary: str


def generate_markdown_report(results: list[EvalResult]) -> str:
    """生成 Markdown 格式的对比报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = len(results)

    dims = ["comprehensiveness", "accuracy", "depth", "structure", "sourcing"]
    dim_names_zh = {
        "comprehensiveness": "全面性",
        "accuracy": "准确性",
        "depth": "深度",
        "structure": "结构",
        "sourcing": "信息来源",
    }

    # 计算各维度平均值
    dr_avg = {d: 0.0 for d in dims}
    ds_avg = {d: 0.0 for d in dims}
    dr_wins = ds_wins = ties = 0

    for r in results:
        for d in dims:
            dr_avg[d] += getattr(r, f"dr_{d}")
            ds_avg[d] += getattr(r, f"ds_{d}")
        if r.winner == "a":
            dr_wins += 1
        elif r.winner == "b":
            ds_wins += 1
        else:
            ties += 1

    for d in dims:
        dr_avg[d] /= n
        ds_avg[d] /= n

    md = f"""# DeepResearch vs DeepSeek V4 Flash 对比评测报告

生成时间: {now}

评测方法: 用相同研究问题分别调用 DeepResearch（多智能体迭代系统）和 DeepSeek V4 Flash（带实时网络搜索），再由独立裁判 LLM（Qwen）结合事实核查搜索结果对两份报告进行多维度评分。

---

## 总体结果

| 维度 | DeepResearch (多智能体) | DeepSeek V4 Flash (带搜索) | 领先 |
|------|------------------------|-------------------------|------|
"""

    for d in dims:
        dr_val = f"{dr_avg[d]:.1f}"
        ds_val = f"{ds_avg[d]:.1f}"
        lead = "DeepResearch" if dr_avg[d] > ds_avg[d] else ("DeepSeek" if ds_avg[d] > dr_avg[d] else "平")
        md += f"| {dim_names_zh[d]} | {dr_val} | {ds_val} | {lead} |\n"

    md += f"\n**胜出统计**: DeepResearch {dr_wins}/{n} | DeepSeek {ds_wins}/{n} | 平局 {ties}/{n}\n"

    md += "\n---\n\n## 逐项对比\n\n"

    for r in results:
        winner_label = {"a": "DeepResearch", "b": "DeepSeek V4 Flash", "tie": "平局"}.get(r.winner, "DeepResearch")
        md += f"""### {r.topic}

| 维度 | DeepResearch | DeepSeek V4 Flash (带搜索) |
|------|-------------|------------------|
| 全面性 | {r.dr_comprehensiveness} | {r.ds_comprehensiveness} |
| 准确性 | {r.dr_accuracy} | {r.ds_accuracy} |
| 深度 | {r.dr_depth} | {r.ds_depth} |
| 结构 | {r.dr_structure} | {r.ds_structure} |
| 信息来源 | {r.dr_sourcing} | {r.ds_sourcing} |
| 字数 | {r.deepresearch_word_count:,} | {r.deepseek_word_count:,} |

**胜出方**: {winner_label}

> DeepResearch: {r.dr_summary}
>
> DeepSeek: {r.ds_summary}

> **总结**: {r.overall_summary}

---

"""

    return md


# ===== 主流程 =====

def get_dashscope_api_key() -> str:
    """获取 DashScope API Key，优先从环境变量，其次从 config.yml 读取"""
    if os.environ.get("DASHSCOPE_API_KEY"):
        return os.environ["DASHSCOPE_API_KEY"]
    config_path = Path(__file__).parent.parent / "config.yml"
    if config_path.exists():
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        api_key = config.get("stages", {}).get("prod", {}).get("cognition", {}).get("openai", {}).get("api_key", "")
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key
            return api_key
    return ""


async def run_evaluation():
    """执行完整的评测流程"""
    print("=" * 60)
    print("  DeepResearch vs DeepSeek V4 Flash 对比评测")
    print("=" * 60)

    if not DEEPSEEK_API_KEY:
        print("\n错误: 未设置 DEEPSEEK_API_KEY 环境变量")
        print("请运行: export DEEPSEEK_API_KEY=your_deepseek_api_key")
        return

    dashscope_key = get_dashscope_api_key()
    if dashscope_key:
        print("  [OK] DashScope API Key 已就绪（用于裁判 LLM）")

    cache = load_cache()
    results = []

    for task in EVAL_TASKS:
        print(f"\n--- [{task.id}] {task.topic} ---")

        # 1. 获取 DeepSeek Baseline 回答（带搜索 + 缓存）
        cache_key = f"deepseek_search_{task.id}"
        if cache_key in cache:
            print("  [缓存] DeepSeek Baseline（含搜索）已缓存，跳过调用")
            deepseek_report = cache[cache_key]
        else:
            print("  [DeepSeek] 正在搜索并生成 Baseline 回答...")
            deepseek_report = await _search_and_generate_for_deepseek(task.brief_question)
            cache[cache_key] = deepseek_report
            save_cache(cache)
            print(f"  [DeepSeek] 生成完毕 ({len(deepseek_report)} 字符)")

        # 2. 加载已有 DeepResearch 报告
        print("  [DeepResearch] 加载已有报告...")
        deepresearch_report = load_existing_report(task.report_path)
        print(f"  [DeepResearch] 加载完毕 ({len(deepresearch_report)} 字符)")

        # 3. 裁判打分
        print("  [Judge] 正在对比评分...")
        score = await judge_comparison(task.topic, deepresearch_report, deepseek_report)
        print(f"  [Judge] 评分完毕: winner={score.winner}")
        print(f"           DeepResearch 总分={score.report_a.comprehensiveness + score.report_a.accuracy + score.report_a.depth + score.report_a.structure + score.report_a.sourcing}")
        print(f"           DeepSeek 总分={score.report_b.comprehensiveness + score.report_b.accuracy + score.report_b.depth + score.report_b.structure + score.report_b.sourcing}")

        # 4. 记录结果
        result = EvalResult(
            task_id=task.id,
            topic=task.topic,
            deepseek_word_count=len(deepseek_report),
            deepresearch_word_count=len(deepresearch_report),
            dr_comprehensiveness=score.report_a.comprehensiveness,
            ds_comprehensiveness=score.report_b.comprehensiveness,
            dr_accuracy=score.report_a.accuracy,
            ds_accuracy=score.report_b.accuracy,
            dr_depth=score.report_a.depth,
            ds_depth=score.report_b.depth,
            dr_structure=score.report_a.structure,
            ds_structure=score.report_b.structure,
            dr_sourcing=score.report_a.sourcing,
            ds_sourcing=score.report_b.sourcing,
            dr_summary=score.report_a.summary,
            ds_summary=score.report_b.summary,
            winner={"report_a": "a", "report_b": "b", "a": "a", "b": "b", "tie": "tie"}.get(score.winner, "a"),
            overall_summary=score.overall_summary,
        )
        results.append(result)

    # 5. 输出汇总报告
    report_md = generate_markdown_report(results)
    output_path = Path(__file__).parent / "results.md"
    output_path.write_text(report_md, encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"  评测完成! 结果已保存到: {output_path}")
    print(f"{'=' * 60}")
    print(f"\n{report_md}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
