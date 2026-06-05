"""scan birthdays to find ones where fault starts early (real-time seconds)"""
# the code claims to speed up firing, that isnt the case, from my observations, you have to wait actual 100+ minutes 
# to receive it
import hashlib, random

FAULT_TYPES = ["memory_leak", "traffic_spike", "dependency_timeout"]

def compute_fault_params(birthday: str) -> dict:
    s = int(hashlib.sha256(birthday.encode()).hexdigest(), 16)
    rng = random.Random(s)
    fault_type = FAULT_TYPES[s % 3]
    fault_start_real_seconds = rng.uniform(30 * 60, 150 * 60)
    return {"fault_type": fault_type, "fault_start_real_seconds": fault_start_real_seconds}

results = []
for year in range(1990, 2010):
    for month in range(1, 13):
        for day in range(1, 29):  # 28 safe for all months
            bd = f"{year:04d}-{month:02d}-{day:02d}"
            p = compute_fault_params(bd)
            results.append((p["fault_start_real_seconds"], bd, p["fault_type"]))

results.sort()
print(f"{'Birthday':<14} {'Fault type':<22} {'Real-time start':>16}  {'@ speed=120'}")
print("-" * 70)
for secs, bd, ft in results[:20]:
    at_120 = secs / 120
    print(f"{bd:<14} {ft:<22} {secs/60:>12.1f} min  ({at_120:.0f}s real @ 120x)")
