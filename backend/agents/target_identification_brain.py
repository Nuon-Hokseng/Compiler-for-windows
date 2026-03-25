"""
Target Customer Identification Brain for Instagram.

Analyzes profiles only. Does NOT perform any actions (follow, like, message).
Reasons, scores, and classifies users based on incomplete/noisy data.
Prioritizes accuracy and precision over coverage or speed.
"""

import json
import re

# Process fewer profiles per call for higher quality reasoning
BATCH_SIZE = 5

TARGET_DEFINITION_PROMPT = """You are a Target Customer Identification Brain for Instagram.
You do NOT perform any actions such as follow, like, or message.
You ONLY analyze profiles and decide whether they match the ideal target customer.
Your job is to reason, score, and classify Instagram users based on incomplete and noisy data.
Accuracy and precision are more important than coverage or speed.

━━━━━━━━━━━━━━━━━━━━━━
TARGET CUSTOMER DEFINITION
━━━━━━━━━━━━━━━━━━━━━━
• Age: 18–29 (highest priority: early 20s)
• Work status:
  - Full-time workers preferred
  - Students acceptable ONLY if part-time job signals exist
• Occupation:
  - Non-IT only (factory, nurse, caregiver, logistics, transport, service work)
• Location:
  - Japan ONLY. Target customers must be located in Japan.
  - Within Japan: prefer rural or regional areas over major cities (e.g. prefer 地方 over 東京・大阪)
• Mindset:
  - Likely to aspire to side jobs, remote work, or freelance income
• Account type:
  - Private (locked) accounts are acceptable

━━━━━━━━━━━━━━━━━━━━━━
HARD EXCLUSIONS (INSTANT REJECT)
━━━━━━━━━━━━━━━━━━━━━━
• Located outside Japan (non-Japan = instant NON-TARGET)
• Age 60+
• High school students
• Full-time housewives
• Explicit disability-focused accounts

━━━━━━━━━━━━━━━━━━━━━━
DISCOVERY CONTEXT
━━━━━━━━━━━━━━━━━━━━━━
Profiles are discovered from followers of:
• Large lifestyle or car-related accounts
• Regional / low-ranked university club or circle accounts
• Regional hair removal or cosmetic surgery clinic accounts

━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS SIGNALS
━━━━━━━━━━━━━━━━━━━━━━
Use all available signals:
• Japan location: bio in Japanese, area codes (03=Tokyo, 06=Osaka, etc.), prefecture/city names, Japanese text, discovery from Japanese accounts
• Profile photo (age, lifestyle, work cues)
• Bio text (numbers like "02", "03", locations, job hints)
• Recent posts (work environment, commute, daily routine)
• Captions and comments
• Followers/following context when explicit info is missing

Make probabilistic inferences when data is incomplete.

━━━━━━━━━━━━━━━━━━━━━━
SCORING MODEL (0–100)
━━━━━━━━━━━━━━━━━━━━━━
Age likelihood (18–29, prefer early 20s): 0–30
Work status & lifestyle: 0–25
Occupation type (non-IT): 0–15
Location (Japan only; within Japan prefer regional over urban): 0–15
Side-job aspiration signals: 0–15

━━━━━━━━━━━━━━━━━━━━━━
INTERPRETATION RULES
━━━━━━━━━━━━━━━━━━━━━━
• Japan location is required; if clearly outside Japan or no Japan signals, score as NON-TARGET
• Prefer early 20s over late 20s
• Prefer working adults over students
• Prefer regional over metropolitan (within Japan)
• Prefer non-IT over IT
• When uncertain, lower the score rather than guessing high
• Favor false negatives over false positives

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT CLASSIFICATION
━━━━━━━━━━━━━━━━━━━━━━
Classify each profile into ONE of:
- IDEAL TARGET (Score ≥ 80)
- POSSIBLE TARGET (Score 65–79)
- NON-TARGET (Score < 65 or excluded)

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━
For EACH profile, output exactly:

CLASSIFICATION: IDEAL TARGET | POSSIBLE TARGET | NON-TARGET
SCORE: XX / 100
SIGNALS USED:
- Signal 1
- Signal 2
- (more if applicable)
UNCERTAINTIES:
- Uncertainty 1 (or "None" if none)

Separate each profile with a line: ---
"""


class TargetIdentificationBrain:
    """Analyzes Instagram profiles and classifies them as IDEAL TARGET, POSSIBLE TARGET, or NON-TARGET."""

    def __init__(self, model: str = "claude-3-haiku-20240307"):
        if model.startswith("gpt-"):
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=0.1)
        elif model.startswith("claude-"):
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model=model, temperature=0.1)
        else:
            raise ValueError(f"Unsupported local model: {model}")
            

    def _build_profile_block(self, user: dict) -> str:
        """Format a single user's available data for the prompt."""
        username = user.get("username", "").lstrip("@")
        source = user.get("source", "unknown")
        source_hashtag = user.get("source_hashtag", "")
        parts = [f"Username: @{username}", f"Discovery source: {source}"]
        if source_hashtag:
            parts.append(f"Source context: {source_hashtag}")
        if user.get("bio"):
            parts.append(f"Bio: {user['bio']}")
        if user.get("post_summary"):
            parts.append(f"Post/content summary: {user['post_summary']}")
        if user.get("profile_notes"):
            parts.append(f"Notes: {user['profile_notes']}")
        return "\n".join(parts)

    def _build_batch_prompt(self, users: list[dict]) -> str:
        """Build the full prompt for a batch of profiles."""
        profile_blocks = "\n\n".join(
            f"Profile {i+1}:\n{self._build_profile_block(u)}"
            for i, u in enumerate(users)
        )
        return f"""{TARGET_DEFINITION_PROMPT}

━━━━━━━━━━━━━━━━━━━━━━
PROFILES TO ANALYZE
━━━━━━━━━━━━━━━━━━━━━━

{profile_blocks}

Analyze each profile above. Use discovery context and any signals to reason. When data is incomplete, be conservative and lower the score.
Output in the mandatory format for each profile, separated by --- ."""

    def _parse_single_response(self, text: str) -> list[dict]:
        """Parse one batch response into list of classification dicts."""
        # Split by --- to get per-profile blocks
        raw_blocks = re.split(r"\n---\s*\n", text.strip())
        results = []
        for block in raw_blocks:
            block = block.strip()
            if not block or block.lower().startswith("profile"):
                continue
            classification = None
            score = None
            signals = []
            uncertainties = []
            current = None
            for line in block.split("\n"):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if line_stripped.upper().startswith("CLASSIFICATION:"):
                    classification = line_stripped.split(":", 1)[1].strip().upper()
                    if "IDEAL" in classification:
                        classification = "IDEAL TARGET"
                    elif "POSSIBLE" in classification:
                        classification = "POSSIBLE TARGET"
                    else:
                        classification = "NON-TARGET"
                elif line_stripped.upper().startswith("SCORE:"):
                    match = re.search(r"(\d+)\s*/\s*100", line_stripped)
                    if match:
                        score = int(match.group(1))
                elif line_stripped.upper().startswith("SIGNALS USED:"):
                    current = "signals"
                elif line_stripped.upper().startswith("UNCERTAINTIES:"):
                    current = "uncertainties"
                elif current == "signals" and line_stripped.startswith("-"):
                    signals.append(line_stripped.lstrip("-").strip())
                elif current == "uncertainties" and line_stripped.startswith("-"):
                    unc = line_stripped.lstrip("-").strip()
                    if unc and unc.lower() != "none":
                        uncertainties.append(unc)
            if classification is not None:
                results.append({
                    "classification": classification,
                    "score": score if score is not None else 0,
                    "signals_used": signals,
                    "uncertainties": uncertainties,
                })
        return results

    def _filter_batch(self, users: list[dict]) -> list[dict]:
        """Run the brain on one batch and return enriched results with username/source."""
        if not users:
            return []
        prompt = self._build_batch_prompt(users)
        try:
            response = self.llm.invoke(prompt)
            parsed = self._parse_single_response(response)
            # Attach username and source to each result by index
            for i, res in enumerate(parsed):
                if i < len(users):
                    res["username"] = users[i].get("username", "").lstrip("@")
                    res["source"] = users[i].get("source", "unknown")
                    res["source_hashtag"] = users[i].get("source_hashtag", "")
            return parsed
        except Exception as e:
            print(f"    Batch error: {e}")
            # Return minimal NON-TARGET for each user in batch on error
            return [
                {
                    "username": u.get("username", "").lstrip("@"),
                    "source": u.get("source", "unknown"),
                    "source_hashtag": u.get("source_hashtag", ""),
                    "classification": "NON-TARGET",
                    "score": 0,
                    "signals_used": [],
                    "uncertainties": [str(e)],
                }
                for u in users
            ]

    def classify_accounts(self, users: list[dict]) -> list[dict]:
        """Classify each profile into IDEAL TARGET, POSSIBLE TARGET, or NON-TARGET."""
        if not users:
            return []
        user_map = {u.get("username", "").lstrip("@"): u for u in users}
        all_results = []
        total_batches = (len(users) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, len(users), BATCH_SIZE):
            batch = users[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            print(f"    Analyzing batch {batch_num}/{total_batches} ({len(batch)} profiles)...")
            batch_results = self._filter_batch(batch)
            all_results.extend(batch_results)
        # Ensure every username appears exactly once
        seen = set()
        final = []
        for r in all_results:
            username = r.get("username", "")
            if not username or username in seen:
                continue
            seen.add(username)
            if username in user_map:
                r["source"] = user_map[username].get("source", "unknown")
                r["source_hashtag"] = user_map[username].get("source_hashtag", "")
            r["target_customer"] = "ideal"
            final.append(r)
        # Sort: IDEAL first, then POSSIBLE, then NON-TARGET; within same class by score desc
        order = {"IDEAL TARGET": 0, "POSSIBLE TARGET": 1, "NON-TARGET": 2}
        final.sort(key=lambda x: (order.get(x.get("classification", ""), 2), -(x.get("score") or 0)))
        return final


def classify_target_accounts(
    users: list[dict],
    model: str = "claude-3-haiku-20240307",
) -> list[dict]:
    """
    Entry point: classify profiles using the Target Customer Identification Brain.

    Each user dict can have: username, source, source_hashtag, and optionally
    bio, post_summary, profile_notes for richer analysis.
    """
    if not users:
        return []
    seen = set()
    unique = []
    for u in users:
        uname = u.get("username", "").lstrip("@")
        if uname and uname not in seen:
            seen.add(uname)
            unique.append(u)
    print(f"  Target identification: analyzing {len(unique)} unique profiles...")
    brain = TargetIdentificationBrain(model=model)
    return brain.classify_accounts(unique)
