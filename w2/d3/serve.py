import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent
W2_ROOT = ROOT.parent
D1_ROOT = W2_ROOT / 'd1'
D2_ROOT = W2_ROOT / 'd2'

app = FastAPI(title='AIOps RCA Service', version='0.1.0')

SEVERITY_ORDER = {'warn': 0, 'crit': 1}


class Alert(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: str
    value: float
    threshold: float
    labels: dict[str, Any] = Field(default_factory=dict)


class IncidentRequest(BaseModel):
    alerts: list[Alert]


class ClusterResponse(BaseModel):
    cluster_id: str | None = None
    services: list[str] = Field(default_factory=list)
    root_cause: str | None = None
    confidence: float | None = None


class IncidentResponse(BaseModel):
    clusters: list[ClusterResponse] = Field(default_factory=list)
    root_cause: dict[str, Any] | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    similar_incidents: list[str] = Field(default_factory=list)
    method: str = 'graph+tfidf'


service_graph: nx.DiGraph | None = None
cluster_summary: dict[str, Any] | None = None
incident_history: list[dict[str, Any]] = []


def _load_json(path: Path) -> Any:
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def _load_assets() -> None:
    global service_graph, cluster_summary, incident_history
    service_definition = _load_json(D1_ROOT / 'dataset' / 'services.json')
    service_graph = build_service_graph(service_definition)
    cluster_summary = _load_json(D1_ROOT / 'results' / 'cluster_summary.json')
    incident_history = _load_json(D2_ROOT / 'dataset' / 'incidents_history.json')


def build_service_graph(definition: dict) -> nx.DiGraph:
    graph = nx.DiGraph()
    for node in definition.get('services', []) + definition.get('stores', []):
        graph.add_node(node['name'], **node)
    for edge in definition.get('edges', []):
        graph.add_edge(edge['from'], edge['to'], **{k: v for k, v in edge.items() if k not in ['from', 'to']})
    return graph


def fingerprint(alert: dict) -> str:
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"


def dedup(alerts: list) -> tuple[list, dict]:
    fp_map: dict[str, list] = defaultdict(list)
    seen: dict[str, dict] = {}
    for alert in sorted(alerts, key=lambda item: item['ts']):
        fp = fingerprint(alert)
        fp_map[fp].append(alert['id'])
        if fp not in seen:
            seen[fp] = alert
    return list(seen.values()), dict(fp_map)


def session_groups(alerts: list, gap_sec: int = 120) -> list:
    if not alerts:
        return []
    sorted_alerts = sorted(alerts, key=lambda item: item['ts'])
    groups = [[sorted_alerts[0]]]
    for alert in sorted_alerts[1:]:
        last_ts = datetime.fromisoformat(groups[-1][-1]['ts'].replace('Z', '+00:00'))
        current_ts = datetime.fromisoformat(alert['ts'].replace('Z', '+00:00'))
        if (current_ts - last_ts).total_seconds() <= gap_sec:
            groups[-1].append(alert)
        else:
            groups.append([alert])
    return groups


def topology_group(alerts: list, graph: nx.DiGraph) -> list:
    alert_services = {alert['service'] for alert in alerts}
    subgraph = graph.subgraph(alert_services).to_undirected()
    by_service: dict[str, list] = defaultdict(list)
    for alert in alerts:
        by_service[alert['service']].append(alert)
    result = []
    for component in nx.connected_components(subgraph):
        group = []
        for svc in component:
            group.extend(by_service[svc])
        result.append(group)
    return result


def correlate(alerts: list, graph: nx.DiGraph, gap_sec: int = 120) -> list:
    deduped, fp_all_ids = dedup(alerts)
    sessions = session_groups(deduped, gap_sec=gap_sec)
    clusters = []
    for session_idx, session_alerts in enumerate(sessions):
        for group_idx, group in enumerate(topology_group(session_alerts, graph)):
            fps = sorted({fingerprint(alert) for alert in group})
            all_ids = sorted(aid for fp in fps for aid in fp_all_ids.get(fp, []))
            clusters.append({
                'cluster_id': f'c-{session_idx:03d}-{group_idx:03d}',
                'alert_count': len(all_ids),
                'services': sorted({alert['service'] for alert in group}),
                'time_range': [min(alert['ts'] for alert in group), max(alert['ts'] for alert in group)],
                'max_severity': max((alert['severity'] for alert in group), key=lambda item: SEVERITY_ORDER.get(item, 0)),
                'fingerprints': fps,
                'alert_ids': all_ids,
            })
    return clusters


def build_cluster_query(cluster: dict) -> str:
    services_text = ' '.join(cluster.get('services', []))
    fingerprint_text = ' '.join(cluster.get('fingerprints', []))
    severity_text = cluster.get('max_severity', '')
    return ' '.join([services_text, fingerprint_text, severity_text]).strip()


def incident_text(incident: dict) -> str:
    parts = [incident.get('root_cause_class', '')] + incident.get('affected_services', [])
    parts += incident.get('log_signatures', [])
    metric_text = [' '.join([metric.get('service', ''), metric.get('metric', ''), metric.get('delta', '')]) for metric in incident.get('metric_signatures', [])]
    trace_text = [' '.join([trace.get('from', ''), trace.get('to', ''), str(trace.get('p99_deviation_ratio', ''))]) for trace in incident.get('trace_signatures', [])]
    return ' '.join(parts + metric_text + trace_text).strip()


def normalize_scores(scores: dict) -> dict:
    if not scores:
        return {}
    max_value = max(scores.values())
    min_value = min(scores.values())
    if max_value == min_value:
        return {key: 1.0 for key in scores}
    return {key: (value - min_value) / (max_value - min_value) for key, value in scores.items()}


def score_graph_candidates(graph: nx.DiGraph, cluster: dict) -> list[tuple[str, float]]:
    cluster_services = cluster.get('services', [])
    graph_scores = {service: graph.in_degree(service) + graph.out_degree(service) for service in cluster_services}
    graph_norm = normalize_scores(graph_scores)
    fp_counts = Counter(fp.split('|')[0] for fp in cluster.get('fingerprints', []))
    severity_weights = {'warn': 1.0, 'crit': 2.0}
    temporal_scores = {service: 0.0 for service in cluster_services}
    for fp in cluster.get('fingerprints', []):
        service_name, metric_name, severity = fp.split('|')
        temporal_scores[service_name] += 1.0 * severity_weights.get(severity, 1.0)
    temporal_norm = normalize_scores(temporal_scores)
    combined = {service: 0.55 * graph_norm.get(service, 0.0) + 0.45 * temporal_norm.get(service, 0.0) for service in cluster_services}
    return sorted(combined.items(), key=lambda item: item[1], reverse=True)[:3]


def build_tfidf_retriever(incidents: list[dict]) -> tuple[TfidfVectorizer, Any, list[dict]]:
    texts = [incident_text(incident) for incident in incidents]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix, incidents


def retrieve_similar_incidents(query: str, vectorizer: TfidfVectorizer, matrix: Any, incidents: list[dict], top_k: int = 3) -> list[tuple[dict, float]]:
    if not query.strip():
        return []
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, matrix)[0] if matrix.shape[0] > 0 else []
    ranked = sorted(list(enumerate(sims)), key=lambda item: item[1], reverse=True)[:top_k]
    return [(incidents[idx], float(score)) for idx, score in ranked if score > 0.0]


_load_assets()


@app.middleware('http')
async def add_latency_header(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers['X-Response-Time-Ms'] = str(elapsed_ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={'detail': exc.errors()})


@app.get('/healthz')
async def healthz() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/readyz')
async def readyz() -> dict[str, Any]:
    checks = {
        'status': 'ready' if (service_graph is not None and cluster_summary is not None and incident_history) else 'not-ready',
        'graph_loaded': service_graph is not None,
        'cluster_summary_loaded': cluster_summary is not None,
        'history_loaded': bool(incident_history),
    }
    if checks['status'] != 'ready':
        raise HTTPException(status_code=503, detail=checks)
    return checks


@app.post('/incident', response_model=IncidentResponse)
async def incident(request: IncidentRequest) -> IncidentResponse:
    if not request.alerts:
        raise HTTPException(status_code=422, detail='alerts must not be empty')

    alerts = [alert.model_dump() for alert in request.alerts]
    clusters = correlate(alerts, service_graph, gap_sec=120)
    if not clusters:
        raise HTTPException(status_code=400, detail='unable to form clusters from alerts')

    vectorizer, incident_matrix, incidents = build_tfidf_retriever(incident_history)
    cluster_results = []
    for cluster in clusters:
        graph_top3 = score_graph_candidates(service_graph, cluster)
        top_service = graph_top3[0][0] if graph_top3 else cluster['services'][0]
        query = build_cluster_query(cluster)
        similar = retrieve_similar_incidents(query, vectorizer, incident_matrix, incidents, top_k=3)
        top_sim = similar[0][1] if similar else 0.0
        max_graph_score = graph_top3[0][1] if graph_top3 else 0.0
        severity_score = 1.0 if cluster.get('max_severity') == 'crit' else 0.5
        confidence = round(min(1.0, 0.35 * max_graph_score + 0.55 * top_sim + 0.1 * severity_score), 2)
        actions = []
        if service_graph and top_service in service_graph.nodes:
            owner = service_graph.nodes[top_service].get('owner_pager') or service_graph.nodes[top_service].get('team')
            actions.append(f"page_oncall:{owner}") if owner else actions.append('page_oncall:platform-team')
        else:
            actions.append('page_oncall:platform-team')
        cluster_results.append({
            'cluster_id': cluster['cluster_id'],
            'services': cluster['services'],
            'root_cause': top_service,
            'confidence': confidence,
            'actions': actions,
            'similar_incidents': [item[0]['id'] for item in similar],
            'alert_count': cluster['alert_count'],
        })

    selected_cluster = max(cluster_results, key=lambda item: (item['alert_count'], item['confidence']))
    root_cause = {
        'service': selected_cluster['root_cause'],
        'confidence': selected_cluster['confidence'],
        'class': incident_history[0]['root_cause_class'] if incident_history else 'unknown',
    }
    return IncidentResponse(
        clusters=[ClusterResponse(cluster_id=item['cluster_id'], services=item['services'], root_cause=item['root_cause'], confidence=item['confidence']) for item in cluster_results],
        root_cause=root_cause,
        recommended_actions=selected_cluster['actions'],
        similar_incidents=selected_cluster['similar_incidents'],
        method='graph+tfidf',
    )
