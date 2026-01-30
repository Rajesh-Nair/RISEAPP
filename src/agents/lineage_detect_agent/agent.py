"""Lineage detection agent: match internal doc chunks to external (regulatory) chunks."""

import asyncio
import json
import re
import uuid
from typing import List, Tuple

from google.adk.agents import Agent
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from pydantic import BaseModel

from src.agents.prompts import get_prompt_loader
from utils.config import get_config
from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)


class LineageMatchModel(BaseModel):
    external_chunk_ids: List[str] = []
    confidence: float | None = None


def _build_candidates_block(candidates: List[Tuple[str, str]]) -> str:
    lines = []
    for eid, text in candidates:
        preview = (text or "")[:800].strip()
        lines.append(f"- external_chunk_id: {eid}\n  text: {preview}")
    return "\n\n".join(lines) if lines else "(none)"


def build_lineage_agent() -> Agent:
    loader = get_prompt_loader()
    cfg = get_config()
    model_name = cfg.get_model_for_agent("lineage_detect")
    system = loader.load_prompt("lineage_detect_system.md")
    return Agent(
        model=model_name,
        name="lineage_detect_agent",
        description="Maps internal policy chunks to external regulatory chunks",
        instruction=system,
    )


root_agent = build_lineage_agent()


async def detect_lineage(
    internal_chunk: str,
    candidates: List[Tuple[str, str]],
) -> LineageMatchModel:
    """Run lineage agent: internal chunk + (external_chunk_id, text) candidates -> matches."""
    if not candidates:
        return LineageMatchModel(external_chunk_ids=[], confidence=None)
    loader = get_prompt_loader()
    prompt = loader.format_prompt(
        "lineage_detect_match.md",
        internal_chunk=internal_chunk[:4000],
        candidates_block=_build_candidates_block(candidates),
    )
    app = "lineage_detect_agent"
    uid = "batch_user"
    sid = str(uuid.uuid4())
    session = InMemorySessionService()
    await session.create_session(app_name=app, user_id=uid, session_id=sid)
    runner = Runner(app_name=app, agent=root_agent, session_service=session)
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    try:
        events = runner.run_async(new_message=content, user_id=uid, session_id=sid)
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                raw = event.content.parts[0].text
                return _parse_lineage_response(raw)
    except Exception as e:
        logger.warning("Lineage agent error", error=str(e))
    return LineageMatchModel(external_chunk_ids=[], confidence=None)


def _parse_lineage_response(raw: str) -> LineageMatchModel:
    raw = raw.strip()
    m = re.search(r"\{[^{}]*\"external_chunk_ids\"[^{}]*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        d = json.loads(raw)
        ids = d.get("external_chunk_ids") or []
        if not isinstance(ids, list):
            ids = [str(ids)] if ids else []
        ids = [str(x) for x in ids]
        conf = d.get("confidence")
        if conf is not None:
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = None
        return LineageMatchModel(external_chunk_ids=ids, confidence=conf)
    except Exception as e:
        logger.warning("Parse lineage response failed", raw=raw[:200], error=str(e))
    return LineageMatchModel(external_chunk_ids=[], confidence=None)


if __name__ == "__main__":
    async def _main():
        r = await detect_lineage(
            "This policy sets model risk standards.",
            [("1_0", "Model risk management policy scope.")],
        )
        logger.info("Result", result=r.model_dump())

    asyncio.run(_main())
