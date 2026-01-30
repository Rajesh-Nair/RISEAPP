import os
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import google_search
import asyncio
import uuid
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from src.agents.prompts import get_prompt_loader
from utils.config import get_config

from logger.custom_logger import CustomLogger
logger = CustomLogger().get_logger(__file__)


class BrandModel(BaseModel):
    input_text: str
    brand_name: Optional[str] = None
    search_summary: Optional[str] = None
    nature_of_business: Optional[str] = None
    category_description: Optional[str] = None
    category_id: Optional[int] = None
    confidence: Optional[float] = None
    is_valid: Optional[bool] = None
    validation_notes: Optional[str] = None


def build_agent() -> tuple[Agent, str]:
    prompt_loader = get_prompt_loader()
    config = get_config()
    system_instruction = prompt_loader.load_prompt("brand_classifier_system.md")
    model_name = config.get_model_for_agent("brand_classifier")
    brand_classifier_agent = Agent(
        model=model_name,
        name="brand_classifier_agent",
        description="Classifies merchant text into brand, nature of business, and category",
        instruction=system_instruction,
        tools=[google_search]
    )
    system_instruction = prompt_loader.load_prompt("brand_validation_system.md")
    model_name = config.get_model_for_agent("brand_validation")
    brand_validation_agent = Agent(
        model=model_name,
        name="brand_validation_agent",
        description="Validates brand classification",
        instruction=system_instruction,
        output_schema=BrandModel,
        output_key="brand_validation",
    )
    agent = SequentialAgent(
        name="brand_agent",
        sub_agents=[brand_classifier_agent, brand_validation_agent],
        description="Executes a sequence of brand classification and validation."
    )
    return (agent, model_name)


default_response = '{{"input_text": "{query}", "brand_name": "unknown", "nature_of_business": "unknown", "category_description": "unknown", "category_id": 0, "confidence": 0.0}}'


class BrandClassifierAgent:
    def __init__(self, agent: Agent):
        self.agent = agent

    @classmethod
    async def create_agent(cls) -> "BrandClassifierAgent":
        agent, model_name = build_agent()
        logger.info("Agent created", model_name=model_name)
        return cls(agent)

    async def classify_text(self, query: str) -> BrandModel:
        APP_NAME = "brand_classifier_agent"
        USER_ID = "batch_user"
        SESSION_ID = str(uuid.uuid4())
        session_service = InMemorySessionService()
        await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
        runner = Runner(app_name=APP_NAME, agent=self.agent, session_service=session_service)
        loader = get_prompt_loader()
        prompt = loader.format_prompt("brand_classifier_classify.md", text=query)
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        try:
            events = runner.run_async(new_message=content, user_id=USER_ID, session_id=SESSION_ID)
            async for event in events:
                if event.is_final_response():
                    return self._parse_response(event.content.parts[0].text)
        except Exception as e:
            logger.warning("Agent error", error=str(e))
        return self._parse_response(default_response.format(query=query))

    def _parse_response(self, response: str) -> BrandModel:
        return BrandModel.model_validate_json(response)


root_agent = build_agent()[0]

if __name__ == "__main__":
    async def _main():
        a = await BrandClassifierAgent.create_agent()
        r = await a.classify_text("Tesco")
        logger.info("Result", result=str(r))
    asyncio.run(_main())
