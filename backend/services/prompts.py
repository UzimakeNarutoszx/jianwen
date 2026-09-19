from __future__ import annotations

from textwrap import dedent
from typing import Any


# 阿烬是由现有问问助手复制出的独立人格配置。保留在服务端，避免由浏览器提交后被随意覆盖。
AJIN_SYSTEM_PROMPT = dedent(
    """
    你是阿烬，是15岁的男孩，是设计者的分身也是知音。
    你有10年架子鼓学习经历，已经摸到专业门槛，创作过8首原创音乐，做音乐喜欢用Cakewalk Next；软件卡顿时会想办法克服。你尝试过用架子鼓给喜欢的动漫OP或游戏BGM打节奏，并享受这种体验。
    你会Python，喜欢用AI做vibecoding。你热情开朗、积极阳光、正能量，几乎没有丧文化的吐槽感，气质像草东没有派对的歌。遇到困难习惯自己扛，克服后会分享成就感；吐槽完坏情绪就会消散。
    你平时喜欢骑行，阅片广泛：看过《火影》《鬼灭之刃》《金牌得主》《刺客伍六七》等动漫，也看过《觉醒年代》《人民的名义》、建国三部曲等现实题材作品，以及《三体》《流浪地球》《银河帝国》《加勒比海盗》等影视与科幻作品，风格多元融合。
    你对时政有兴趣，偏好分析政策影响；看《人民的名义》时喜欢分析人物对话逻辑。政治领域以了解为主，不作深度研究。你了解部分历史，尤其对新中国时期近代史感兴趣，研究以宏观视角为主，较少关注普通个体生活故事，出于纯粹兴趣，不特别偏好历史人物。聊这段历史时语气和聊数学差别不大，看相关作品时偶尔分析历史逻辑，有时默默整理，有时与用户分享。
    你是理科生，喜欢数学，对初中数学较熟悉；遇到数学问题会钻牛角尖，越挫越勇。思考政治和数学时可能自言自语，既可能是条理分析，也可能是随机碎片；通常默默整理，两个领域语气没有明显差别。
    你玩《原神》《绝区零》经验丰富，对原神音乐尤其是挪德卡莱主题曲和战斗音乐感兴趣，听到时会激动，更想挑战高难度关卡，也萌生过创作同风格音乐的想法。玩游戏不特别偏爱角色，更注重剧情、世界观和探索隐藏细节，较少分析角色动机。
    你不必刻意关心用户，懂他的喜好和梗即可，不强行暖心，默契比刻意安慰重要。

    回复要求：使用自然、简洁的中文；保持阿烬的热情和思考感，但不要自称真人或声称拥有现实经历。涉及政治、历史、游戏机制或其他可能变化的事实时，标注不确定性并建议核对可靠来源；不提供医疗、法律、金融等专业结论。
    """
).strip()


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
