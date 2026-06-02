import sys
import pandas as pd
from collections import Counter
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

def run_analyzer(file_path):
    # check format and extract raw line content safely
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            if "Content" in df.columns:
                lines = df["Content"].astype(str).tolist()
                timestamps = pd.to_datetime(df["Timestamp"], unit="s").tolist() if "Timestamp" in df.columns else None
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file_io:
                    lines = [line.strip() for line in file_io.readlines()]
                timestamps = None
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file_io:
                lines = [line.strip() for line in file_io.readlines()]
            timestamps = None
    except Exception:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file_io:
            lines = [line.strip() for line in file_io.readlines()]
        timestamps = None

    total_lines = len(lines)
    if total_lines == 0:
        print("error: targeted file contains zero readable lines")
        return

    # initialize drain3 using optimal configuration
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.5
    miner = TemplateMiner(config=config)

    template_ids = []
    id_to_template = {}

    for line in lines:
        res = miner.add_log_message(line)
        cluster_id = res["cluster_id"]
        template_ids.append(cluster_id)
        id_to_template[cluster_id] = res["template_mined"]

    unique_count = len(id_to_template)
    compression_ratio = ((total_lines - unique_count) / total_lines) * 100

    print(f"analysis target file: {file_path}")
    print(f"total processed records: {total_lines}")
    print(f"unique template clusters extracted: {unique_count}")
    print(f"calculated data compression ratio: {compression_ratio:.2f}%")

    # isolate top heavy hit operational log patterns
    counts = Counter(template_ids).most_common(5)
    print("top 5 dominant log signatures:")
    for tid, cnt in counts:
        share = (cnt / total_lines) * 100
        print(f"  id {tid} | count: {cnt} ({share:.2f}%) | template: {id_to_template[tid]}")

    # parse sliding window temporal behavior if accurate tracking timestamps exist
    if timestamps and len(timestamps) == total_lines:
        df_time = pd.DataFrame({"timestamp": timestamps, "template_id": template_ids})
        max_time = df_time["timestamp"].max()
        cutoff_hour = max_time - pd.Timedelta(hours=1)

        recent_window = df_time[df_time["timestamp"] >= cutoff_hour]
        past_window = df_time[df_time["timestamp"] < cutoff_hour]

        if not past_window.empty and not recent_window.empty:
            past_uniques = set(past_window["template_id"].unique())
            recent_uniques = set(recent_window["template_id"].unique())
            novel_discoveries = recent_uniques - past_uniques

            print(f"temporal validation window: final tracked hour context")
            print(f"  new unique signatures introduced: {len(novel_discoveries)}")
            for nid in list(novel_discoveries)[:3]:
                print(f"    - id {nid}: {id_to_template[nid]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python log_analyzer.py <path_to_logfile>")
    else:
        run_analyzer(sys.argv[1])
