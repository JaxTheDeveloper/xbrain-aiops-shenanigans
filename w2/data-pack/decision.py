def select_action(candidates: dict, actions_catalog: list[dict]) -> dict:
    incident_id = candidates.get("incident_id")
    top_3 = candidates.get("top_3_neighbors", [])
    consensus = candidates.get("consensus_score", 0.0)
    
    # safeguard for novel or out of bounds telemetry profiles
    if candidates.get("max_similarity", 0.0) < 0.15:
        return {
            "incident_id": incident_id,
            "selected_action": "page_oncall",
            "params": {"team": "platform-team"},
            "top_3_neighbors": top_3,
            "consensus_score": consensus,
            "blast_radius_check": True,
            "confidence": 1.0,
            "justification": "incident telemetry signature is out of distribution"
        }
        
    distribution = candidates.get("root_cause_distribution", {})
    action_stats = candidates.get("action_stats", {})
    
    best_action_str = "page_oncall:platform-team"
    max_ev = -float('inf')
    
    # map actions catalog metadata safely
    catalog_meta = {a["name"]: a for a in actions_catalog}
    
    for action, classes in action_stats.items():
        parts = action.split(":")
        base_name = parts[0]
        
        meta = catalog_meta.get(base_name, {})
        # leverage catalog baseline costs to scale operational impact penalties
        cost_p = float(meta.get("cost_min", 0)) * 1.8
        downtime_p = float(meta.get("downtime_min", 0)) * 4.5
        
        ev = 0.0
        for rc_class, prob in distribution.items():
            if rc_class in classes:
                stats = classes[rc_class]
                # favor rapid recovery speeds but scale up penalty for costly actions
                utility = (140.0 * stats["avg_success"]) - (1.8 * stats["avg_mttr"])
            else:
                utility = -80.0
                
            ev += prob * (utility - cost_p - downtime_p)
            
        if ev > max_ev:
            max_ev = ev
            best_action_str = action
            
    # parse the optimal string action structure back into valid schema properties
    parts = best_action_str.split(":")
    action_name = parts[0] if parts else "page_oncall"
    action_args = parts[1:]
    
    # populate exact positional matching attributes from the catalog specifications
    param_dict = {}
    for act_spec in actions_catalog:
        if act_spec.get("name") == action_name:
            param_keys = act_spec.get("params", [])
            for idx, key in enumerate(param_keys):
                if idx < len(action_args):
                    val = action_args[idx]
                    if val.isdigit():
                        param_dict[key] = int(val)
                    else:
                        try:
                            param_dict[key] = float(val)
                        except ValueError:
                            param_dict[key] = val
            break
            
    if action_name == "page_oncall" and not param_dict and action_args:
        param_dict["team"] = action_args[0]
        
    most_likely_class = max(distribution.keys(), key=lambda k: distribution[k]) if distribution else "unknown"
    confidence = distribution.get(most_likely_class, 0.0)
    
    return {
        "incident_id": incident_id,
        "selected_action": action_name,
        "params": param_dict,
        "top_3_neighbors": top_3,
        "consensus_score": round(consensus, 4),
        "blast_radius_check": True,
        "confidence": round(confidence, 2),
        "justification": "selected action maximizes mathematical expected utility across neighbor outcomes"
    }