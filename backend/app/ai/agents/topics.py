"""Agent 3a: group decision-related dialogue acts into topics and normalize option names."""

from pydantic import BaseModel

from app.ai.agents.extract import render_context
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct, MeetingContext
from app.ai.domain.timefmt import fmt_ts
from app.ai.llm import LLMClient, load_prompt

TOPIC_ACTS = {
    Act.PROPOSE,
    Act.SUPPORT,
    Act.OBJECT,
    Act.AMEND,
    Act.DECIDE,
    Act.REJECT,
    Act.DEFER,
    Act.REOPEN,
}


class TopicSpec(BaseModel):
    topic_id: str
    question: str


class Alias(BaseModel):
    alias: str
    canonical: str


class Assignment(BaseModel):
    act_id: str
    topic_id: str
    option: str | None = None


class TopicsOutput(BaseModel):
    topics: list[TopicSpec]
    aliases: list[Alias]  # tên gọi khác -> tên chuẩn ("Mongo" -> "MongoDB")
    assignments: list[Assignment]


def _render_acts(acts: list[DialogueAct]) -> str:
    return "\n".join(
        f"{a.id} | {fmt_ts(a.start)} | {a.speaker} | {a.act.value} | {a.option or ''} | {a.quote}"
        for a in acts
    )


async def assign_topics(
    llm: LLMClient, ctx: MeetingContext, acts: list[DialogueAct], prompt_version: str
) -> tuple[list[TopicSpec], list[DialogueAct]]:
    topic_acts = [a for a in acts if a.act in TOPIC_ACTS]
    if not topic_acts:
        return [], list(acts)
    system = load_prompt("topics", prompt_version) + "\n\n" + render_context(ctx)
    out = await llm.structured(
        agent="topics", system=system, user=_render_acts(topic_acts), schema=TopicsOutput
    )
    topic_ids = {t.topic_id for t in out.topics}
    aliases = {x.alias: x.canonical for x in out.aliases}
    known = {a.id for a in topic_acts}
    chosen: dict[str, Assignment] = {}
    for asg in out.assignments:
        if asg.act_id in known and asg.topic_id in topic_ids:
            chosen[asg.act_id] = asg
    result: list[DialogueAct] = []
    for a in acts:
        pick = chosen.get(a.id)
        if pick is None:
            result.append(a)
            continue
        option = pick.option if pick.option is not None else a.option
        if option is not None:
            option = aliases.get(option, option)
        result.append(a.model_copy(update={"topic_id": pick.topic_id, "option": option}))
    return out.topics, result
