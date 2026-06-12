# in case i need to directly implement something, or with constants
# say, louvine, or PC.
# PS: i just realised those are done with networkx
import math

# tok retrieval
from collections import defaultdict
from features import clean_and_tokenize, extract_features

def similarity(a: dict, b: dict) -> float:
    tokens_a = []
    for msg in a.get("logs", []):
        tokens_a.extend(clean_and_tokenize(msg))
        
    tokens_b = []
    for msg in b.get("logs", []):
        tokens_b.extend(clean_and_tokenize(msg))
        
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    
    if not set_a and not set_b:
        log_sim = 1.0
    elif not set_a or not set_b:
        log_sim = 0.0
    else:
        anchors_a = {t for t in set_a if t.startswith("anchor_")}
        anchors_b = {t for t in set_b if t.startswith("anchor_")}
        if anchors_a or anchors_b:
            anchor_match = len(anchors_a & anchors_b) / len(anchors_a | anchors_b) if (anchors_a and anchors_b) else 0.0
            base_match = len(set_a & set_b) / len(set_a | set_b)
            log_sim = 0.8 * anchor_match + 0.2 * base_match
        else:
            log_sim = len(set_a & set_b) / len(set_a | set_b)
            
    services_a = set(a.get("affected_services", []))
    services_b = set(b.get("affected_services", []))
    svc_sim = len(services_a & services_b) / len(services_a | services_b) if (services_a or services_b) else 1.0
    
    metrics_a = set(a.get("metrics", []))
    metrics_b = set(b.get("metrics", []))
    metric_sim = len(metrics_a & metrics_b) / len(metrics_a | metrics_b) if (metrics_a or metrics_b) else 1.0
    
    rule_sim = 1.0 if a.get("trigger_rule") == b.get("trigger_rule") else 0.0
    
    return 0.4 * log_sim + 0.2 * svc_sim + 0.2 * metric_sim + 0.2 * rule_sim

def retrieve_and_vote(query: dict, history: list[dict], top_k: int = 3) -> dict:
    scores = []
    for hist_inc in history:
        hist_feat = extract_features(hist_inc)
        score = similarity(query, hist_feat)
        scores.append((score, hist_inc))
        
    scores.sort(key=lambda x: x[0], reverse=True)
    max_score = scores[0][0] if scores else 0.0
    top_candidates = scores[:top_k]
    
    top_3_neighbors = [inc.get("id") or inc.get("incident_id") for _, inc in top_candidates]
    
    votes = defaultdict(float)
    total_score = sum(s for s, _ in top_candidates) if top_candidates else 1.0
    if total_score == 0.0:
        total_score = 1.0
        
    for score, inc in top_candidates:
        rc_class = inc.get("root_cause_class", "unknown")
        votes[rc_class] += score / total_score
        
    action_stats = defaultdict(lambda: defaultdict(list))
    for inc in history:
        rc_class = inc.get("root_cause_class", "unknown")
        mttr = inc.get("mttr_minutes", 60)
        outcome = inc.get("outcome", "success")
        success_score = 1.0 if outcome == "success" else (0.5 if outcome == "partial" else 0.0)
        for act in inc.get("actions_taken", []):
            action_stats[act][rc_class].append((success_score, mttr))
            
    serializable_stats = {}
    for act, classes in action_stats.items():
        serializable_stats[act] = {}
        for rc_class, records in classes.items():
            avg_success = sum(r[0] for r in records) / len(records)
            avg_mttr = sum(r[1] for r in records) / len(records)
            serializable_stats[act][rc_class] = {
                "avg_success": avg_success,
                "avg_mttr": avg_mttr
            }

    return {
        "max_similarity": max_score,
        "root_cause_distribution": dict(votes),
        "action_stats": serializable_stats,
        "top_3_neighbors": top_3_neighbors,
        "consensus_score": max_score,
        "incident_id": query.get("incident_id")
    }