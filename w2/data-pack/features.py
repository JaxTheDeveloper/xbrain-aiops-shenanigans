import re

def clean_and_tokenize(text):
    text = text.lower()
    anchors = []
    if "outofmemoryerror" in text or "heap space" in text:
        anchors.append("anchor_oom")
    if "deadlock detected" in text or "lock contention" in text:
        anchors.append("anchor_deadlock")
    if "connection refused" in text or "redis connection" in text:
        anchors.append("anchor_redis_fail")
    if "certificate has expired" in text or "x509" in text:
        anchors.append("anchor_cert_expired")
        
    text = re.sub(r'\b\d+[\.\d]*m?s\b', '<duration>', text)
    text = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', '<ip>', text)
    text = re.sub(r'\b0x[0-9a-fA-F]+\b', '<hex>', text)
    text = re.sub(r'\b\d+\b', '<num>', text)
    text = re.sub(r'[^a-z\s\<\>\*]', ' ', text)
    return anchors + [w for w in text.split() if w]

def extract_features(incident: dict, incident_id: str = None) -> dict:
    logs = []
    if "log_signatures" in incident:
        logs = incident["log_signatures"]
    elif "logs" in incident:
        logs = [item["msg"] for item in incident["logs"] if "msg" in item]
        
    affected = set()
    if "affected_services" in incident:
        affected = set(incident["affected_services"])
    else:
        if "trigger_alert" in incident and "service" in incident["trigger_alert"]:
            affected.add(incident["trigger_alert"]["service"])
        if "logs" in incident:
            for item in incident["logs"]:
                if "svc" in item:
                    affected.add(item["svc"])
                    
    # extract metrics to explicitly separate db vs memory profiles
    metrics = set()
    for m in incident.get("metric_signatures", []):
        metrics.add(f"{m.get('service')}:{m.get('metric')}")
        
    trigger_rule = incident.get("trigger_alert", {}).get("rule_id", "unknown")
    
    return {
        "logs": logs,
        "affected_services": list(affected),
        "metrics": list(metrics),
        "trigger_rule": trigger_rule,
        "incident_id": incident_id or incident.get("incident_id") or incident.get("id")
    }