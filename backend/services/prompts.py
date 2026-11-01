from __future__ import annotations

from textwrap import dedent
from typing import Any


# 阿烬是由现有问问助手复制出的独立人格配置。保留在服务端，避免由浏览器提交后被随意覆盖。
AJIN_SYSTEM_PROMPT = "你是阿烬，一个虚构的学习助手。用简洁中文讨论技术、阅读与公共议题；区分事实和观点，不声称拥有真人身份或现实经历，不确定时提示核实来源。"


ASK_SYSTEM_PROMPT = dedent(
    """
    你是「见闻」的问问助手，专门回答政策、新闻、公共议题和年轻人的现实问题。

    规则：
    - 优先用清楚、克制、直接的中文回答。
    - 先区分事实、解释和观点，再给结论。
    - 涉及具体政策、数据、新闻时，尽量提示来源或依据入口。
    - 不确定时明确说明不确定，不要编造。
    - 不替代法律、投资、医疗等专业判断。
    - 不做煽动性判断，不输出极端立场。
    - 默认围绕用户当前上下文回答；如果超出上下文，先说明再扩展。
    """
).strip()


ASK_CONTEXT_TEMPLATE = dedent(
    """
    当前上下文：
    {context}

    要求：
    - 当前上下文可能包含“全站文章资料库”和“当前关联文章”。
    - 回答前先阅读全站文章资料库；如果存在当前关联文章，优先围绕当前关联文章回答。
    - 如果用户的问题明显超出上下文，说明你将切换到更宽泛的问答范围。
    - 回答保持简洁，必要时用条目拆分。
    """
).strip()


ARTICLE_CONTEXT_TEMPLATE = dedent(
    """
    文章上下文：
    标题：{title}
    来源：{sources}
    三句话总结：
    1. {summary_1}
    2. {summary_2}
    3. {summary_3}
    正文要点：
    {key_points}
    """
).strip()


FOLLOW_UP_USER_TEMPLATE = dedent(
    """
    请基于以上上下文回答这个问题：
    {question}
    """
).strip()


def build_article_context(
    *,
    title: str,
    sources: str,
    summary: list[str],
    key_points: list[str] | None = None,
) -> str:
    items = list(summary[:3]) + [""] * max(0, 3 - len(summary))
    return ARTICLE_CONTEXT_TEMPLATE.format(
        title=title,
        sources=sources,
        summary_1=items[0],
        summary_2=items[1],
        summary_3=items[2],
        key_points="\n".join(f"- {point}" for point in (key_points or [])) or "- 无",
    )


def build_context_block(context: str | dict[str, Any]) -> str:
    if isinstance(context, str):
        return context.strip()

    parts: list[str] = []
    for key, value in context.items():
        if value is None:
            continue
        if isinstance(value, list):
            rendered = "\n".join(f"- {item}" for item in value) or "- 无"
        else:
            rendered = str(value)
        parts.append(f"{key}：{rendered}")
    return "\n".join(parts).strip()


def build_ask_messages(
    question: str,
    *,
    context: str | dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": ASK_SYSTEM_PROMPT}]

    if context:
        messages.append(
            {
                "role": "system",
                "content": ASK_CONTEXT_TEMPLATE.format(context=build_context_block(context)),
            }
        )

    for item in history or []:
        role = item.get("role", "user")
        content = item.get("content", "").strip()
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question.strip()})
    return messages


def build_ajin_messages(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build messages for the cloned 阿烬 agent."""
    messages: list[dict[str, str]] = [{"role": "system", "content": AJIN_SYSTEM_PROMPT}]
    for item in history or []:
        role = item.get("role", "user")
        content = item.get("content", "").strip()
        if content and role in {"user", "assistant"}:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question.strip()})
    return messages
