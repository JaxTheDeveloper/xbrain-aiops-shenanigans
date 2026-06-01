import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import skew
from statsmodels.graphics.tsaplots import plot_acf

# load data
df = pd.read_csv('rogue_agent_key_hold (1).csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

# 1. plot and save raw time series
plt.figure(figsize=(12, 4))
plt.plot(df.index, df['value'], color='blue', linewidth=1)
plt.title('raw time series')
plt.xlabel('time')
plt.ylabel('value')
plt.tight_layout()
plt.savefig('raw_time_series.png')
plt.close()

# 2. calculate basic stats
mean_val = df['value'].mean()
std_val = df['value'].std()
min_val = df['value'].min()
max_val = df['value'].max()
skew_val = skew(df['value'].dropna())

print("basic statistics:")
print(f"mean: {mean_val:.4f}")
print(f"std: {std_val:.4f}")
print(f"min: {min_val:.4f}")
print(f"max: {max_val:.4f}")
print(f"skewness: {skew_val:.4f}")

# 3. plot and save histogram + density
plt.figure(figsize=(8, 4))
sns.histplot(df['value'], kde=True, bins=50, color='purple')
plt.title('histogram and density plot')
plt.xlabel('value')
plt.tight_layout()
plt.savefig('hist_density.png')
plt.close()

# 4. plot and save acf
plt.figure(figsize=(10, 4))
plot_acf(df['value'].dropna(), lags=50, ax=plt.gca())
plt.title('autocorrelation function')
plt.tight_layout()
plt.savefig('acf_plot.png')
plt.close()