import json
from config.targets import get_target_config

BATCH_SIZE = 10


class OllamaBrain:
    def __init__(self, target_customer: str, model: str = "llama3:8b"):
        if model.startswith("gpt-"):
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=0.1)
        elif model.startswith("claude-"):
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model=model, temperature=0.1)
        else:
            from langchain_ollama import OllamaLLM
            self.llm = OllamaLLM(model=model, temperature=0.1)
        self.target_customer = target_customer
        self.config = get_target_config(target_customer)
        
        if not self.config:
            raise ValueError(f"Unknown target customer: {target_customer}")
    
    def _build_prompt(self, users: list[dict]) -> str:
        user_list = "\n".join([
            f"- @{u['username']} ({u.get('source', 'unknown')})"
            for u in users
        ])
        
        niches = ", ".join(self.config["niches"])
        
        return f"""Analyze these Instagram accounts for {self.config['name']} target market.

ACCOUNTS TO ANALYZE:
{user_list}

INSTRUCTIONS:
1. For EACH account above, decide if it's relevant to {self.config['name']}
2. Remove only clear spam/bots (random strings, suspicious patterns)
3. Keep all accounts that COULD be relevant
4. Classify each kept account into a niche
5. Rate relevance 1-10

VALID NICHES: {niches}

IMPORTANT: Return ALL accounts that could be relevant. Do not truncate.

OUTPUT FORMAT (JSON array only, no other text):
[{{"username": "x", "niche": "y", "relevance": 8}}]

Return [] only if ALL accounts are spam/bots."""

    def _filter_batch(self, users: list[dict]) -> list[dict]:
        if not users:
            return []
        
        prompt = self._build_prompt(users)
        
        try:
            response = self.llm.invoke(prompt)
            start = response.find("[")
            end = response.rfind("]") + 1
            
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except Exception as e:
            print(f"    Batch error: {e}")
        
        return []
    
    def filter_accounts(self, users: list[dict]) -> list[dict]:
        if not users:
            return []
        
        # Build user map for source info lookup
        user_map = {u["username"]: u for u in users}
        
        # Process in batches to avoid token limits
        all_filtered = []
        total_batches = (len(users) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in range(0, len(users), BATCH_SIZE):
            batch = users[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            print(f"    Processing batch {batch_num}/{total_batches} ({len(batch)} accounts)...")
            
            filtered = self._filter_batch(batch)
            all_filtered.extend(filtered)
        
        # Deduplicate and merge source info
        seen = set()
        final_results = []
        
        for item in all_filtered:
            username = item.get("username", "").lstrip("@")
            if not username or username in seen:
                continue
            
            seen.add(username)
            
            # Merge source info from original data
            if username in user_map:
                item["source"] = user_map[username].get("source", "unknown")
                item["source_hashtag"] = user_map[username].get("source_hashtag", "")
                item["target_customer"] = self.target_customer
            
            final_results.append(item)
        
        # Sort by relevance
        final_results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        
        return final_results


def analyze_accounts(users: list[dict], target_customer: str, model: str = "llama3:8b") -> list[dict]:
    if not users:
        return []
    
    # Deduplicate input
    seen = set()
    unique_users = []
    for u in users:
        if u["username"] not in seen:
            seen.add(u["username"])
            unique_users.append(u)
    
    print(f"  Analyzing {len(unique_users)} unique accounts...")
    
    brain = OllamaBrain(target_customer=target_customer, model=model)
    return brain.filter_accounts(unique_users)
