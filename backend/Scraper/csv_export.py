import csv
import os
from datetime import datetime


def export_to_csv(results: list[dict], target_customer: str, output_dir: str = "output") -> str:
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{target_customer}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    # Target identification brain outputs classification + score; others use niche + relevance
    use_target_id = bool(results and "classification" in results[0])
    if use_target_id:
        fieldnames = [
            "username", "source", "target_customer", "classification", "score",
            "signals_used", "uncertainties"
        ]
    else:
        fieldnames = ["username", "source", "target_customer", "niche", "relevance_score"]
    
    seen = set()
    unique_results = []
    for r in results:
        username = r.get("username", "")
        if username and username not in seen:
            seen.add(username)
            unique_results.append(r)
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in unique_results:
            if use_target_id:
                writer.writerow({
                    "username": r.get("username", ""),
                    "source": r.get("source", "unknown"),
                    "target_customer": target_customer,
                    "classification": r.get("classification", ""),
                    "score": r.get("score", ""),
                    "signals_used": " | ".join(r.get("signals_used", [])),
                    "uncertainties": " | ".join(r.get("uncertainties", [])),
                })
            else:
                writer.writerow({
                    "username": r.get("username", ""),
                    "source": r.get("source", "unknown"),
                    "target_customer": target_customer,
                    "niche": r.get("niche", ""),
                    "relevance_score": r.get("relevance", ""),
                })
    
    return filepath
