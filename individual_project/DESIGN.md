# detection approach

## note on generator fixes

a significant portion of lab time was spent diagnosing and fixing bugs in the provided `stream_generator.py` before any detection work could be validated:

- the `--speed` flag controlled POST interval but not `fault_start_real_seconds`, which was always in wall-clock seconds. a fault configured to start at 30 min would wait 30 real minutes regardless of speed. fixed by dividing `fault_start_real_seconds / args.speed`.
- a minimum floor of 10 real seconds was added to guarantee the pipeline collects clean baseline data before fault injection, since at high speed the fault could fire before the window was warm.
- the frozen baseline was being contaminated when the fault started before 15 ticks had elapsed (baseline would snapshot fault-level data and all subsequent z-scores were near zero). fixed with a sanity check on mean rps and queue before freezing.
- f-string conditional format specifiers (e.g. `f"{x:.2f if x else 'N/A'}"`) are not valid python syntax — these caused 500 errors on every request until fixed.

---

## pipelines

- `pipeline.py` — frozen-baseline z-score + absolute threshold guards, port 8000
- `pipeline_stl.py` — STL residual z-score (default) or plain z-score fallback, port 8001

---

## diurnal structure

from reverse-engineering `stream_generator.py`, the baseline follows:

$$d(t) = 1.0 + 0.4 \cdot \sin\!\left(\frac{2\pi(t - 6)}{24}\right)$$

where $t$ is simulated production hours. this gives:

- period $T = 24\text{h}$
- amplitude $A = 0.4$, mean $\mu_d = 1.0$
- range: $d(t) \in [0.6,\ 1.4]$ for all $t$, since $|0.4\sin(\cdot)| \leq 0.4 < 1.0$
- no zero-crossings — $d(t) > 0$ always
- peak at $t = 6 + T/4 = 12\text{h}$, trough at $t = 6 + 3T/4 = 0\text{h}$

metrics that inherit this seasonality:

$$\text{rps}(t) = 120 \cdot d(t) + \varepsilon, \quad \varepsilon \sim \mathcal{N}(0,\ 10^2)$$

$$\text{cpu}(t) = 25 + 15 \cdot d(t) + \varepsilon, \quad \varepsilon \sim \mathcal{N}(0,\ 3^2)$$

$$\text{p99}(t) = 45 + 10 \cdot d(t) + \varepsilon, \quad \varepsilon \sim \mathcal{N}(0,\ 5^2)$$

memory, gc, queue, 5xx, and upstream_timeout do not inherit $d(t)$ — their baselines are stationary.

---

## pipeline.py — frozen baseline z-score

collect 15 ticks. if $\bar{x}_{\text{rps}} < 300$ and $\bar{x}_{\text{queue}} < 50$, snapshot:

$$\mu_k = \frac{1}{15}\sum_{i=1}^{15} x_{i,k}, \qquad \sigma_k = \max\!\left(\text{stdev}(x_{1..15,k}),\ 1.0\right)$$

thereafter, for any new observation $x$:

$$z_k(x) = \frac{x - \mu_k}{\sigma_k}$$

the baseline is never updated — this prevents fault data from drifting the reference distribution.

alert conditions:
- traffic_spike: $z > 3$ on $\geq 2$ of $\{\text{rps, queue, p99}\}$, or absolute guard rps > 400 and queue > 30
- memory_leak: $z > 3$ on memory_bytes, or mem_util > 80%, confirmed by gc z-score or log keywords
- dependency_timeout: $z > 3$ on upstream_timeout, and upstream_timeout > 5% absolute

---

## pipeline_stl.py — STL residual z-score

### why STL suits this data

STL is designed for data with repeating rises and drops — periodic signals where the shape of each cycle is consistent. it is especially well-suited here because the seasonal structure is not just approximately sinusoidal, it is exactly sinusoidal and fully known from the generator source. this means we are not estimating the seasonal component from data alone — we are exploiting a known pattern. phase-averaging converges exactly to the true seasonal curve under Gaussian noise, rather than approximating it via LOESS as in the general case.

the practical consequence: the residual $R_n = x_n - S_n - T_n$ carries none of the diurnal variation. a z-score on $R_n$ is therefore sensitive only to structural breaks (faults), not to the expected daily rhythm. a plain z-score on raw $x_n$ would approach the alert threshold every time traffic peaks at $t = 12\text{h}$, regardless of whether a fault is occurring.

### decomposition

for a time series $x_1, x_2, \ldots, x_n$:

$$x_n = T_n + S_n + R_n$$

**seasonal component** via phase-averaging:

$$p = n \bmod P, \qquad I_p = \{i : i \bmod P = p,\ i < n\}$$

$$S_n = \frac{1}{|I_p|} \sum_{i \in I_p} x_i$$

$P$ = season period in ticks (default 48, corresponding to $48 \times 30\text{s} = 24\text{h}$ simulated).

**trend component** via trailing moving average:

$$T_n = \frac{1}{W} \sum_{i=n-W+1}^{n} x_i, \qquad W = 12 \text{ ticks}$$

**residual:**

$$R_n = x_n - S_n - T_n$$

under the null (no fault): $R_n \approx \varepsilon_n \sim \mathcal{N}(0,\ \sigma_\varepsilon^2)$.

### residual scoring

$$z_n = \frac{R_n - \mu_R}{\sigma_R}, \qquad \mu_R = \frac{1}{W}\sum_{i=n-W}^{n} R_i, \quad \sigma_R = \text{stdev}(R_{n-W..n})$$

alert fires when $z_n > \theta$ (default $\theta = 3.0$). under $\mathcal{N}(0,1)$, $P(z > 3) \approx 0.0013$, giving approximately 0.1% false positive rate per metric per tick.

### formal argument

if $x_n = T_n + S_n + f_n + \varepsilon_n$ where $f_n$ is the fault signal, then:

$$R_n = x_n - S_n - T_n \approx f_n + \varepsilon_n$$

$$z_n \approx \frac{f_n}{\sigma_\varepsilon}$$

$z_n$ grows proportionally to fault magnitude, independent of diurnal phase. a plain z-score on raw $x_n$ gives instead:

$$z_n^{\text{raw}} \approx \frac{f_n + (S_n - \bar{S})}{\sigma_x}$$

where $(S_n - \bar{S})$ is the seasonal deviation from the overall mean — up to $0.4 \times \text{metric amplitude}$, which is comparable to an early-stage fault signal.

---

## parameters

| parameter | default | notes |
|---|---|---|
| `--season-period` | 48 | ticks per cycle. $48 \times 30\text{s} = 1440\text{s} = 24\text{h}$ simulated |
| `--z-threshold` | 3.0 | $P(z > 3) \approx 0.0013$ under $\mathcal{N}(0,1)$ |
| `--residual-window` | 20 | window for $\mu_R$, $\sigma_R$ estimation |
| `--detector` | stl | `stl` or `zscore` |
| cooldown | 60s | minimum gap between alerts of the same type |

---

## warm-up

- `pipeline.py`: 15 ticks (~7.5s at speed=120)
- `pipeline_stl.py`: $P = 48$ ticks for seasonal estimate (~24s at speed=120); absolute threshold guard covers the pre-warm-up window

---

## results

fault injected: `traffic_spike`, seed birthday `2009-04-13`, speed=120x.

first alert fired at `2026-06-05T00:59:36`, triggered by absolute threshold (rps=547, queue=187) before z-score was reliable ($z = \text{N/A}$ — baseline had not yet frozen cleanly due to early fault injection). subsequent alerts confirmed by both absolute and z-score signals. all 22 alerts in `alerts.jsonl` occurred while fault was active — no false positives before fault injection.

sample alerts:

```json
{"timestamp": "2026-06-05T00:59:36.846+00:00", "type": "traffic_spike", "severity": "critical", "message": "RPS=547 z=N/A, queue=187, p99=1248.0ms"}
{"timestamp": "2026-06-05T01:03:41.654+00:00", "type": "traffic_spike", "severity": "critical", "message": "RPS=1302 z=1.80, queue=247, p99=1191.2ms"}
{"timestamp": "2026-06-05T01:21:02.802+00:00", "type": "traffic_spike", "severity": "critical", "message": "RPS=758 z=-1.43, queue=207, p99=1201.9ms"}
```

the negative z-scores in later alerts are expected: once the fault is sustained, the residual window fills entirely with fault-level values, so $\mu_R$ drifts toward the fault mean and $z_n \to 0$. detection continued via the absolute threshold guard, which does not depend on distributional assumptions.

---

## future improvements

**AR(p) residual modelling**

instead of subtracting a seasonal mean, fit an autoregressive model on the residuals:

$$R_n = \varphi_1 R_{n-1} + \varphi_2 R_{n-2} + \cdots + \varphi_p R_{n-p} + \varepsilon_n$$

i would also want to implement AR(1) or AR(2) is preferable over first-order differencing ($\Delta x_n = x_n - x_{n-1}$) because differencing removes trend but amplifies high-frequency noise — it doubles the variance of white noise since $\text{Var}(\Delta \varepsilon_n) = 2\sigma_\varepsilon^2$. AR(p) exploits the autocorrelation structure of the residuals directly. if the generator noise has AR structure, the model absorbs it and leaves a cleaner $\varepsilon_n$. like STL, AR(p) benefits from knowing the data-generating process: since the generator noise is i.i.d. Gaussian by construction, the coefficients $\varphi_i$ should be near zero at baseline, making fault detection equivalent to a structural break test on $\varphi$.

also, we also know that AR is part of the ARIMA algorithm. the first hyperparameter is AR, and the second hyperparam represents d-th order difference.

the major drawback: AR(p) assumes the coefficients $(\varphi_1, \ldots, \varphi_p, \sigma_\varepsilon)$ are stationary over time. in a real production system with drifting load patterns, this breaks and the model needs periodic re-estimation. for this lab the assumption holds since the generator noise process is fixed.

**other improvements**





- EWMA trend instead of trailing MA... which is an exponential weighting is more sensitive to recent drift, which helps with memory_leak slope detection. not thought of since i'm a bit too included in my discovery of exploitatation.
- persist history and baseline across restarts
- ensemble both pipelines: require agreement before firing to reduce false positives at the cost of higher TTD
