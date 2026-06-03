import pandas as pd
import numpy as np
# doubly ended queue, easier to manage rolling windows
from collections import deque

def run_consumer(q, output_file):
    window_size = 12 # 1 hour window for 5-minute intervals
    window = deque(maxlen=window_size)
    results = []
    prev_value = None

    while True:
        item = q.get()
        if item is None:
            q.task_done()
            break
        
        val = float(item['value'])
        timestamp = item['timestamp']
        
        window.append(val)
        
        # calculate streaming features
        rolling_mean = np.mean(window) if len(window) > 0 else val
        rolling_std = np.std(window) if len(window) > 1 else 0.0
        roc = val - prev_value if prev_value is not None else 0.0
        
        results.append({
            'timestamp': timestamp,
            'value': val,
            'rolling_mean': rolling_mean,
            'rolling_std': rolling_std,
            'rate_of_change': roc
        })
        
        prev_value = val
        q.task_done()
        
    # save structured features to parquet
    df = pd.DataFrame(results)
    df.to_parquet(output_file, index=False)