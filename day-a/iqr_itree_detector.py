import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score
import joblib

# load data
df = pd.read_csv('rogue_agent_key_hold (1).csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

# ground truth window generation
threshold = df['value'].quantile(0.995) 
true_anomaly_timestamps = df[df['value'] > threshold].index

df['ground_truth'] = 0
for target in true_anomaly_timestamps:
    mask = (df.index >= target - pd.Timedelta(hours=2)) & (df.index <= target + pd.Timedelta(hours=2))
    df.loc[mask, 'ground_truth'] = 1

# detector 1: iqr method
q1 = df['value'].quantile(0.25)
q3 = df['value'].quantile(0.75)
iqr_val = q3 - q1
upper_bound = q3 + 1.5 * iqr_val
lower_bound = q1 - 1.5 * iqr_val

df['pred_iqr'] = 0
df.loc[(df['value'] > upper_bound) | (df['value'] < lower_bound), 'pred_iqr'] = 1

# feature engineering for trend awareness
df['hour'] = df.index.hour
df['dayofweek'] = df.index.dayofweek

# lag features
df['lag_1'] = df['value'].shift(1).fillna(0)
df['lag_2'] = df['value'].shift(2).fillna(0)

# difference features for velocity and acceleration
df['diff_1'] = df['value'].diff(1).fillna(0)
df['diff_2'] = df['value'].diff(2).fillna(0)

# rolling windows
df['rolling_mean_6'] = df['value'].rolling(window=6, min_periods=1).mean()
df['rolling_std_6'] = df['value'].rolling(window=6, min_periods=1).std().fillna(0)
df['rolling_mean_24'] = df['value'].rolling(window=24, min_periods=1).mean()
df['rolling_std_24'] = df['value'].rolling(window=24, min_periods=1).std().fillna(0)
df['rolling_max_24'] = df['value'].rolling(window=24, min_periods=1).max().fillna(0)
df['rolling_min_24'] = df['value'].rolling(window=24, min_periods=1).min().fillna(0)

# ewma feature
df['ewm_mean'] = df['value'].ewm(span=12, adjust=False).mean()

features = [
    'value', 'hour', 'dayofweek', 'lag_1', 'lag_2', 'diff_1', 'diff_2',
    'rolling_mean_6', 'rolling_std_6', 'rolling_mean_24', 'rolling_std_24', 
    'rolling_max_24', 'rolling_min_24', 'ewm_mean'
]
x = df[features]

# tune contamination
contaminations = [0.01, 0.02, 0.05]
best_f1 = 0
best_c = 0.01

print("isolation forest tuning:")
for c in contaminations:
    iso = IsolationForest(contamination=c, random_state=42)
    df['pred_iso_temp'] = iso.fit_predict(x)
    df['pred_iso_temp'] = df['pred_iso_temp'].map({1: 0, -1: 1})
    
    p = precision_score(df['ground_truth'], df['pred_iso_temp'], zero_division=0)
    r = recall_score(df['ground_truth'], df['pred_iso_temp'], zero_division=0)
    f = f1_score(df['ground_truth'], df['pred_iso_temp'], zero_division=0)
    print(f"c={c} -> precision: {p:.4f}, recall: {r:.4f}, f1: {f:.4f}")
    
    if f > best_f1:
        best_f1 = f
        best_c = c

# train final model
final_iso = IsolationForest(contamination=best_c, random_state=42)
df['pred_iso'] = final_iso.fit_predict(x)
df['pred_iso'] = df['pred_iso'].map({1: 0, -1: 1})

joblib.dump(final_iso, 'isolation_forest.joblib')

# final evaluation
p_iqr = precision_score(df['ground_truth'], df['pred_iqr'], zero_division=0)
r_iqr = recall_score(df['ground_truth'], df['pred_iqr'], zero_division=0)
f_iqr = f1_score(df['ground_truth'], df['pred_iqr'], zero_division=0)
fp_iqr = ((df['pred_iqr'] == 1) & (df['ground_truth'] == 0)).sum()

p_iso = precision_score(df['ground_truth'], df['pred_iso'], zero_division=0)
r_iso = recall_score(df['ground_truth'], df['pred_iso'], zero_division=0)
f_iso = f1_score(df['ground_truth'], df['pred_iso'], zero_division=0)
fp_iso = ((df['pred_iso'] == 1) & (df['ground_truth'] == 0)).sum()

print("\nfinal results:")
print(f"detector 1 (iqr) - precision: {p_iqr:.4f}, recall: {r_iqr:.4f}, f1: {f_iqr:.4f}, false alarms: {fp_iqr}")
print(f"detector 2 (if)  - precision: {p_iso:.4f}, recall: {r_iso:.4f}, f1: {f_iso:.4f}, false alarms: {fp_iso}")

# plot and save
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)

ax1.plot(df.index, df['value'], color='blue', alpha=0.6, label='value')
anomalies_iqr = df[df['pred_iqr'] == 1]
ax1.scatter(anomalies_iqr.index, anomalies_iqr['value'], color='red', label='iqr anomaly')
ax1.set_title('detector 1: iqr anomalies')
ax1.legend()

ax2.plot(df.index, df['value'], color='blue', alpha=0.6, label='value')
anomalies_iso = df[df['pred_iso'] == 1]
ax2.scatter(anomalies_iso.index, anomalies_iso['value'], color='orange', label='iso forest anomaly')
ax2.set_title(f'detector 2: isolation forest anomalies (c={best_c})')
ax2.legend()

plt.tight_layout()
plt.savefig('anomalies_comparison.png')
plt.close()