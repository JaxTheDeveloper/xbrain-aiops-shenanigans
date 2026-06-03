def calculate_costs():
    tiers = {
        "small": {
            "services": 10,
            "logs_gb_day": 50,
            "metrics_sec": 100_000
        },
        "medium": {
            "services": 100,
            "logs_gb_day": 500,
            "metrics_sec": 1_000_000
        },
        "large": {
            "services": 1000,
            "logs_gb_day": 5000,
            "metrics_sec": 10_000_000
        }
    }

    # pricing constants for self-hosted (build)
    # 30-day log/metric retention on cloud block storage (ebs gp3 at $0.08 per gb-month)
    storage_per_gb_month = 0.08
    # data compression ratio estimate (timescaledb/zstd typically gets 4x to 10x compression)
    compression_ratio = 5.0
    
    # pricing constants for datadog (buy)
    datadog_host_price = 23.0 # enterprise tier per host-month
    datadog_log_ingest_per_gb = 0.10
    datadog_log_retain_per_million = 1.70 # 15 days standard retention
    avg_log_size_bytes = 500 # standard json log frame size

    print(f"{'tier':<10} | {'component':<15} | {'build (self-host)':<20} | {'buy (datadog)':<15}")
    print("-" * 68)

    for tier_name, config in tiers.items():
        services = config["services"]
        logs_day = config["logs_gb_day"]
        metrics_sec = config["metrics_sec"]

        # 1. self-hosted (build) cost model logic
        # storage calculation
        monthly_raw_logs_gb = logs_day * 30
        # metrics estimated at 8 bytes per sample, collected/aggregated hourly or retained raw
        # timescaledb averages ~1.5 bytes per metric point after internal compression
        monthly_raw_metrics_gb = (metrics_sec * 60 * 60 * 24 * 30 * 1.5) / 1e9
        compressed_storage_gb = (monthly_raw_logs_gb + monthly_raw_metrics_gb) / compression_ratio
        build_storage_cost = compressed_storage_gb * storage_per_gb_month

        # compute calculation (vm nodes based on compute requirements per tier)
        if tier_name == "small":
            build_compute_cost = 120.0 # 2x small-medium vms (e.g., t3.large)
            build_network_cost = 45.0  # basic nat gateway and cross-az traffic
        elif tier_name == "medium":
            build_compute_cost = 650.0 # cluster of memory-optimized vms (e.g., r6g.xlarge)
            build_network_cost = 250.0 # increased inter-node and ingestion data transfer
        else: # large
            build_compute_cost = 4500.0 # multi-node processing clusters + dedicated database nodes
            build_network_cost = 1800.0 # heavy network throughput fees

        build_total = build_storage_cost + build_compute_cost + build_network_cost

        # 2. datadog (buy) cost model logic
        buy_compute_cost = services * datadog_host_price # infrastructure base cost per host
        
        # log volume costs
        total_monthly_logs_bytes = logs_day * 1e9 * 30
        log_count_millions = (total_monthly_logs_bytes / avg_log_size_bytes) / 1e6
        buy_storage_cost = (logs_day * datadog_log_ingest_per_gb * 30) + (log_count_millions * datadog_log_retain_per_million)
        
        # custom metrics are heavily metered in datadog. 
        # standard allocation is 100 custom metrics per host. excess metrics charge approx $0.05 per metric-month.
        # converting throughput (events/sec) into active time-series combinations across hosts:
        if tier_name == "small":
            buy_network_cost = 800.0 # metered custom metrics surcharge
        elif tier_name == "medium":
            buy_network_cost = 7500.0
        else:
            buy_network_cost = 72000.0

        buy_total = buy_compute_cost + buy_storage_cost + buy_network_cost

        # display tabular results
        print(f"{tier_name:<10} | {'storage':<15} | ${build_storage_cost:<19,.2f} | ${buy_storage_cost:<14,.2f}")
        print(f"{'':<10} | {'compute':<15} | ${build_compute_cost:<19,.2f} | ${buy_compute_cost:<14,.2f}")
        print(f"{'':<10} | {'network/addons':<15} | ${build_network_cost:<19,.2f} | ${buy_network_cost:<14,.2f}")
        print(f"{'':<10} | {'total':<15} | ${build_total:<19,.2f} | ${buy_total:<14,.2f}")
        print("-" * 68)

if __name__ == "__main__":
    calculate_costs()