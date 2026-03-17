"""
Qualification Brain (AI #2) — Strict Lead Qualification Scorer.

Scores Instagram profiles against the target definition.
Conservative: prefers false negatives over false positives.
Returns structured JSON with scores, confidence, and reasoning.
Uses OpenAI gpt-4.1-mini with temperature=0 for deterministic output.
"""

import json
import re

BATCH_SIZE = 5
QUALIFICATION_SYSTEM_PROMPT = """You are a lead qualifier for a Japanese-market side-job recruitment campaign.

Your goal is to identify potential target customers: young working adults in Japan
who might be interested in side jobs or remote freelance work.

Be LENIENT — include profiles when uncertain. False positives are acceptable;
false negatives are costly.

SCORING (max 100):
- Age signals (18-29, early 20s ideal): 0-25
  Birth year hints in bio ("03","04","99"), university/専門学校 mentions,
  young lifestyle content, graduation year references
- Work/occupation signals (non-IT blue-collar preferred): 0-25
  Factory/工場, nurse/看護師, caregiver/介護, logistics/運送,
  transport, part-time/バイト/パート, 社会人, 正社員, any working adult
- Location signals (rural/regional Japan preferred): 0-20
  Regional city names, prefecture mentions, dialect usage,
  rural lifestyle indicators, small-town references
- Side-job/income interest signals: 0-15
  副業, お金, 稼ぐ, remote work, financial aspiration,
  mentions of wanting extra income, interest in freelance
- General engagement/activity: 0-15
  Active account, posts regularly, normal social media user

QUALIFICATION RULES:
- is_target = true if total_score >= 35
- If at least 1-2 positive signals exist → qualify as target
- When uncertain or insufficient info → lean toward INCLUDE
- Private/locked accounts: score based on available info (profile image, bio, name)
  If bio/name suggest a young Japanese working adult → qualify
- Japanese-language profiles are a strong positive signal

HARD EXCLUSIONS (is_target = false regardless of score):
- Clearly 60+ years old (明らかに60歳以上)
- Full-time housewife with 主婦 as primary identity
- High school student (高校生)
- Corporate/brand/business accounts (企業アカウント)

Return JSON only:
{
  "is_target": boolean,
  "total_score": number,
  "scores": {
    "age": number,
    "work_lifestyle": number,
    "occupation": number,
    "location": number,
    "side_job_signal": number
  },
  "confidence": "low" | "medium" | "high",
  "reasoning": ""
}"""


PROFILE_TEMPLATE = """Profile:
Username: {username}
Bio: {bio}
Name: {full_name}
Followers: {followers}

Captions:
{captions}

Comments:
{comments}

Evaluate."""


class QualificationBrain:
    """Scores and qualifies Instagram profiles against target criteria."""

    def __init__(self, model: str = "llama3:8b", temperature: float = 0):
        if model.startswith("gpt-"):
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=temperature)
        elif model.startswith("claude-"):
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model=model, temperature=temperature)
        else:
            from langchain_community.chat_models import ChatOllama
            self.llm = ChatOllama(model=model, temperature=temperature)

    def qualify_profiles(self, profiles: list[dict]) -> list[dict]:
        """
        Score each profile and return enriched results.

        Each profile dict should have: username, bio, full_name,
        followers_count, recent_captions, recent_comments.

        Returns list of dicts with original data + qualification results.
        """
        if not profiles:
            return []

        results: list[dict] = []
        total_batches = (len(profiles) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(profiles), BATCH_SIZE):
            batch = profiles[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            print(f"    Qualifying batch {batch_num}/{total_batches} ({len(batch)} profiles)...")

            for profile in batch:
                result = self._qualify_single(profile)
                results.append(result)

        # Sort by total_score descending
        results.sort(key=lambda x: -(x.get("total_score") or 0))
        return results

    def _qualify_single(self, profile: dict) -> dict:
        """Score a single profile."""
        prompt_text = self._build_profile_prompt(profile)

        messages = [
            {"role": "system", "content": QUALIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ]

        try:
            response = self.llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_response(raw)

            # Merge qualification data with profile data
            return {
                "username": profile.get("username", ""),
                "full_name": profile.get("full_name", ""),
                "bio": profile.get("bio", ""),
                "followers_count": profile.get("followers_count", 0),
                "following_count": profile.get("following_count", 0),
                "profile_image_url": profile.get("profile_image_url", ""),
                "detected_language": profile.get("detected_language", ""),
                "discovery_source": profile.get("discovery_source", ""),
                **parsed,
            }

        except Exception as e:
            print(f"    Qualification error for @{profile.get('username', '?')}: {e}")
            return {
                "username": profile.get("username", ""),
                "full_name": profile.get("full_name", ""),
                "bio": profile.get("bio", ""),
                "followers_count": profile.get("followers_count", 0),
                "following_count": profile.get("following_count", 0),
                "profile_image_url": profile.get("profile_image_url", ""),
                "detected_language": profile.get("detected_language", ""),
                "discovery_source": profile.get("discovery_source", ""),
                "is_target": False,
                "total_score": 0,
                "scores": {
                    "age": 0,
                    "work_lifestyle": 0,
                    "occupation": 0,
                    "location": 0,
                    "side_job_signal": 0,
                },
                "confidence": "low",
                "reasoning": f"Error: {e}",
            }

    def _build_profile_prompt(self, profile: dict) -> str:
        """Build a minimal token-efficient prompt for one profile."""
        captions = profile.get("recent_captions", [])
        comments = profile.get("recent_comments", [])

        # Truncate for token efficiency
        captions_text = "\n".join(c[:300] for c in captions[:5]) if captions else "(none)"
        comments_text = "\n".join(c[:200] for c in comments[:10]) if comments else "(none)"

        bio = (profile.get("bio") or "")[:300]
        full_name = (profile.get("full_name") or "")[:100]

        return PROFILE_TEMPLATE.format(
            username=profile.get("username", ""),
            bio=bio if bio else "(none)",
            full_name=full_name if full_name else "(none)",
            followers=profile.get("followers_count", 0),
            captions=captions_text,
            comments=comments_text,
        )

    def _parse_response(self, raw: str) -> dict:
        """Parse JSON qualification response from LLM."""
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return {
                "is_target": False,
                "total_score": 0,
                "scores": {
                    "age": 0,
                    "work_lifestyle": 0,
                    "occupation": 0,
                    "location": 0,
                    "side_job_signal": 0,
                },
                "confidence": "low",
                "reasoning": "Failed to parse LLM response",
            }

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {
                "is_target": False,
                "total_score": 0,
                "scores": {
                    "age": 0,
                    "work_lifestyle": 0,
                    "occupation": 0,
                    "location": 0,
                    "side_job_signal": 0,
                },
                "confidence": "low",
                "reasoning": "Invalid JSON from LLM",
            }

        # Normalize and validate
        scores = data.get("scores", {})
        total = sum(
            scores.get(k, 0)
            for k in ["age", "work_lifestyle", "occupation", "location", "side_job_signal"]
        )

        return {
            "is_target": data.get("is_target", total >= 35),
            "total_score": data.get("total_score", total),
            "scores": {
                "age": scores.get("age", 0),
                "work_lifestyle": scores.get("work_lifestyle", 0),
                "occupation": scores.get("occupation", 0),
                "location": scores.get("location", 0),
                "side_job_signal": scores.get("side_job_signal", 0),
            },
            "confidence": data.get("confidence", "low"),
            "reasoning": data.get("reasoning", ""),
        }


def qualify_profiles(
    profiles: list[dict],
    model: str = "gpt-4.1-mini",
) -> list[dict]:
    """
    Entry point: qualify Instagram profiles using the Qualification Brain.

    Each profile dict should contain: username, bio, full_name,
    followers_count, recent_captions, recent_comments.

    Returns list of dicts sorted by total_score DESC, each with:
    is_target, total_score, scores, confidence, reasoning + original profile data.
    """
    if not profiles:
        return []
    print(f"  Qualification Brain: scoring {len(profiles)} profiles...")
    brain = QualificationBrain(model=model)
    return brain.qualify_profiles(profiles)


def make_inline_qualifier(model: str = "llama3:8b") -> callable:
    """
    Create a reusable single-profile qualifier function for inline use.

    Returns a callable: profile_dict -> scored_dict
    Used by ProfileScraper for the scrape → qualify → store loop.
    """
    brain = QualificationBrain(model=model)

    def _qualify_one(profile: dict) -> dict:
        return brain._qualify_single(profile)

    return _qualify_one
