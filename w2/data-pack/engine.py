"""Optional starting skeleton — feel free to ignore and write from scratch.

changes from thanh: stipped extract_features, similarity, retrieve and vote, and select action.
those are implemented on constituent files, so as to not make things worse on my eyes.
those are defined, as follows
"""
import argparse
import json
import yaml
from pathlib import Path
from features import extract_features
from retrieval import retrieve_and_vote
from decision import select_action

def decide(incident_path: Path, history_path: Path, actions_path: Path) -> dict:
    incident = json.loads(incident_path.read_text())
    history = json.loads(history_path.read_text())
    actions_catalog = yaml.safe_load(actions_path.read_text())
    
    # extract clean evaluation incident identifier to match expected json keys
    stem = incident_path.stem
    if stem.startswith("E") and len(stem) <= 4:
        incident_id = stem
    else:
        internal_id = incident.get("incident_id") or incident.get("id") or stem
        incident_id = internal_id.split("-")[0] if "-" in str(internal_id) else internal_id
        
    # execute pipeline sequential layer transitions
    vec = extract_features(incident, incident_id=incident_id)
    candidates = retrieve_and_vote(vec, history)
    decision = select_action(candidates, actions_catalog)
    return decision

def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("decide")
    d.add_argument("--incident", required=True)
    d.add_argument("--history", default="incidents_history.json")
    d.add_argument("--actions", default="actions.yaml")
    args = p.parse_args()
    
    if args.cmd == "decide":
        out = decide(Path(args.incident), Path(args.history), Path(args.actions))
        print(json.dumps(out, indent=2))
        
        # append the engine evaluation results to the target audit logs
        with open("audit.jsonl", "a") as f:
            f.write(json.dumps(out) + "\n")
        return 0
        
    p.print_help()
    return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())