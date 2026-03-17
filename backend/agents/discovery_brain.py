"""
Discovery Brain (AI #1) — Instagram Search Strategy Generator.

Converts user targeting intent into a structured Instagram discovery plan.
Uses OpenAI gpt-4.1-mini with low temperature for deterministic output.
Does NOT perform any scraping or actions.
"""

import json
import re

DISCOVERY_SYSTEM_PROMPT = """You generate precise Instagram scraping plans.

Convert the user's target into high-intent discovery signals.

Rules:
- Prefer narrow, high-intent terms
- Include Japanese variants when relevant
- Avoid broad generic hashtags
- If job-related intent, prioritize hiring signals
- Be conservative with quantity but creative with angles
- When targeting Japan, prioritize regional/niche Japanese hashtags
- Target followers of popular accounts, not the accounts themselves
- Focus on communities where young working adults gather:
  car enthusiasts, regional communities, beauty/lifestyle, university clubs
- Include both English and Japanese hashtags when Japan is relevant
- Think about where 18-29 year old non-IT workers spend time on Instagram

Return JSON only:
{
  "search_queries": [],
  "hashtags": [],
  "bio_keywords": [],
  "caption_keywords": [],
  "japanese_keywords": [],
  "seed_accounts": [],
  "priority_order": []
}"""

DISCOVERY_PLAN_KEYS = {
    "search_queries",
    "hashtags",
    "bio_keywords",
    "caption_keywords",
    "japanese_keywords",
    "seed_accounts",
    "priority_order",
}


class DiscoveryBrain:
    """Generates an Instagram discovery plan from user intent."""

    def __init__(self, model: str = "llama3:8b", temperature: float = 0.3):
        if model.startswith("gpt-"):
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=temperature)
        elif model.startswith("claude-"):
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model=model, temperature=temperature)
        else:
            from langchain_community.chat_models import ChatOllama
            self.llm = ChatOllama(model=model, temperature=temperature)

    def generate_plan(
        self,
        target_interest: str,
        optional_keywords: list[str] | None = None,
        max_profiles: int = 50,
    ) -> dict:
        """
        Convert user intent into a structured discovery plan.

        Returns dict with keys: search_queries, hashtags, bio_keywords,
        caption_keywords, japanese_keywords, seed_accounts, priority_order.
        """
        kw_str = ", ".join(optional_keywords) if optional_keywords else "(none)"
        user_msg = (
            f"Target: {target_interest}\n"
            f"Keywords: {kw_str}\n"
            f"Country: Japan\n"
            f"Generate plan."
        )

        messages = [
            {"role": "system", "content": DISCOVERY_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = self.llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)

        return self._parse_plan(raw)

    def _parse_plan(self, raw: str) -> dict:
        """Extract and validate JSON plan from LLM response."""
        # Try to find JSON block in response
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            raise ValueError(f"Discovery Brain returned no JSON: {raw[:200]}")

        try:
            plan = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Discovery Brain returned invalid JSON: {e}")

        # Ensure all required keys exist with correct types
        for key in DISCOVERY_PLAN_KEYS:
            if key not in plan:
                plan[key] = []
            elif not isinstance(plan[key], list):
                plan[key] = [plan[key]] if plan[key] else []

        return plan


def generate_discovery_plan(
    target_interest: str,
    optional_keywords: list[str] | None = None,
    max_profiles: int = 50,
    model: str = "gpt-4.1-mini",
) -> dict:
    """
    Entry point: generate an Instagram discovery plan from user intent.

    Returns a dict with search_queries, hashtags, bio_keywords,
    caption_keywords, japanese_keywords, seed_accounts, priority_order.
    """
    brain = DiscoveryBrain(model=model)
    return brain.generate_plan(target_interest, optional_keywords, max_profiles)
