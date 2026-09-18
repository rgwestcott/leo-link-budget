# CLAUDE.md — leo-link-budget

Claude Code reads this file at the start of every session. It is the spec. When code and this file disagree, this file wins; raise the conflict rather than silently changing either.

## What this project is

A parametric link-budget tool for a LEO (Low Earth Orbit) satellite downlink, written in Python. Given a scenario (orbit, frequency, transmitter, ground station, data rate, modulation/coding) it computes the full ledger — EIRP → slant range → free-space path loss → G/T → C/N₀ → Eb/N₀ → margin — and sweeps elevation and bit rate to show where a link opens and closes.

Purpose: a portfolio project demonstrating RF link analysis in Python for an aerospace RF-systems role. Audience: an RF engineer skimming the repo for about one minute. Readability outranks cleverness.

## Ground rules

- **Physics is pure.** `link_budget.py` has no printing, no file I/O, no plotting. Functions take numbers (or NumPy arrays) and return numbers (or arrays).
- **Every function documents itself.** Docstring contains: the formula it implements, the units of every argument, the units of the return value, and one reference value from the worked example below. Inline comments explain each non-obvious line. Code is read by humans first.
- **Units live in names.** `altitude_km`, `freq_mhz`, `cn0_dbhz`, `t_sys_k`. Never a bare `f`, `d`, `T` as a parameter.
- **NumPy-friendly.** Use `numpy` math (`np.log10`, `np.sqrt`, `np.radians`) so every function works on scalars and arrays without change. Sweeps depend on this.
- **Constants are computed, not typed.** `BOLTZMANN_DBW_PER_K_HZ` is `10*log10(k)`, not the literal −228.6. Same for anything derivable.
- **Formulas are the spec.** Never drop a term, "simplify," or substitute an approximation for a formula in this file. If a formula looks wrong, say so and stop.
- **Tests before commit.** `pytest -q` must pass. Every physics function has at least one test against the reference values in this file, with the stated tolerance.
- **One logical change per commit.** Message prefixes: `feat:`, `test:`, `docs:`, `chore:`, `fix:`. Before committing, show `git status` and the diff summary.
- **Ask before:** deleting files, changing a formula a test pins, adding a dependency beyond `requirements.txt`, or force-pushing.
- **No secrets.** Never hardcode credentials; never commit `.env`. None exist in this project — the rule is habit.
- **Update the Roadmap** checkboxes at the bottom of this file in the same commit that completes a step.

## Layout

```
leo-link-budget/
├── CLAUDE.md                # this file
├── README.md                # front page: what, example plot, how to run, method, assumptions, validation, roadmap, references
├── requirements.txt         # numpy, matplotlib, pyyaml, pytest
├── .gitignore               # __pycache__/, *.pyc, .venv/, venv/, .pytest_cache/, .env, plots/
├── link_budget.py           # physics: constants + one function per step + compute_ledger()
├── scenario.py              # Scenario dataclass + load_scenario(yaml_path)
├── sweeps.py                # parametric studies returning NumPy arrays (no plotting)
├── plots.py                 # matplotlib rendering of sweep results to PNG
├── run.py                   # CLI: print ledger, run sweeps, compare scenarios
├── scenarios/
│   ├── s_band_ttc.yaml      # the worked example (reference values below)
│   ├── x_band_payload.yaml  # high-rate comparison case
│   └── validation_*.yaml    # inputs from a published reference budget
├── docs/
│   ├── validation.md        # reference vs. tool, line by line, with deltas
│   └── img/                 # the one or two PNGs embedded in README
├── plots/                   # sweep output (gitignored)
└── tests/
    ├── __init__.py
    ├── test_helpers.py
    ├── test_geometry.py
    ├── test_antenna_noise.py
    ├── test_link_equations.py
    ├── test_scenario.py
    ├── test_worked_example.py
    └── test_sweeps.py
```

## Commands

```
# one-time setup
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# every session
pytest -q
python run.py scenarios/s_band_ttc.yaml
python run.py scenarios/s_band_ttc.yaml --sweep-elevation --sweep-rate --out plots/
python run.py scenarios/s_band_ttc.yaml --compare scenarios/x_band_payload.yaml
```

## Physics spec — source of truth

### Constants (`link_budget.py`)

| Name | Value | Units | Note |
|---|---|---|---|
| `EARTH_RADIUS_KM` | 6371.0 | km | mean Earth radius |
| `C_M_PER_S` | 299_792_458.0 | m/s | speed of light |
| `BOLTZMANN_J_PER_K` | 1.380649e-23 | J/K | Boltzmann's constant k |
| `BOLTZMANN_DBW_PER_K_HZ` | `10*log10(BOLTZMANN_J_PER_K)` | dBW/K/Hz | ≈ −228.599 — computed, not typed |
| `T0_K` | 290.0 | K | reference temperature for noise figure |

### Functions (`link_budget.py`), in dependency order

| Function | Formula | Reference value (tolerance) |
|---|---|---|
| `db(x)` | 10·log₁₀(x) | db(2) = 3.0103 (±0.001) |
| `lin(x_db)` | 10^(x_db/10) | lin(10) = 100 (±1e-9) |
| `dbw_from_w(p_w)` | 10·log₁₀(p_w / 1 W) | dbw_from_w(1) = 0; dbw_from_w(2) = 3.01 |
| `dbm_from_dbw(p_dbw)` | p_dbw + 30 | dbm_from_dbw(0) = 30 |
| `wavelength_m(freq_mhz)` | λ = c / (f·10⁶) | wavelength_m(2200) = 0.13627 (±1e-4) |
| `slant_range_km(altitude_km, elevation_deg)` | d = √[(R_E+h)² − (R_E·cos ε)²] − R_E·sin ε | (500, 90) = 500.0 (±1e-6); (500, 10) = 1694.6 (±1.0); (500, 5) = 2077.1 (±1.0) |
| `fspl_db(distance_km, freq_mhz)` | 20·log₁₀(4π·d/λ), d in metres. Docstring notes the shortcut 20log₁₀(d_km)+20log₁₀(f_MHz)+32.45 as a cross-check; the function implements the physical form, not the shortcut | (1694.6, 2200) = 163.88 (±0.05); equals shortcut form within 0.01 |
| `dish_gain_dbi(diameter_m, freq_mhz, efficiency=0.6)` | G = 10·log₁₀[η_a·(π·D/λ)²] | (3, 2200, 0.6) = 34.58 (±0.05) |
| `receiver_noise_temp_k(nf_db)` | T_rx = T₀·(10^(NF/10) − 1) | (1.0) = 75.09 (±0.05); (0.0) = 0.0 |
| `system_noise_temp_k(t_ant_k, t_rx_k)` | T_sys = T_ant + T_rx | (75, 75.09) = 150.09 |
| `g_over_t_db_per_k(g_rx_dbi, t_sys_k)` | G/T = G_rx − 10·log₁₀(T_sys) | (34.58, 150.09) = 12.82 (±0.05) |
| `eirp_dbw(p_tx_dbw, g_tx_dbi, l_tx_db)` | EIRP = P_tx + G_tx − L_tx | (0, 3, 1) = 2.0 |
| `cn0_dbhz(eirp_dbw, fspl_db, other_losses_db, g_over_t_db_per_k)` | C/N₀ = EIRP − FSPL − L_other + G/T − BOLTZMANN_DBW_PER_K_HZ | (2, 163.88, 2, 12.82) = 77.54 (±0.05) |
| `ebn0_db(cn0_dbhz, bit_rate_bps)` | Eb/N₀ = C/N₀ − 10·log₁₀(R_b) | (77.54, 2e6) = 14.53 (±0.05) |
| `esn0_from_ebn0_db(ebn0_db, bits_per_symbol, code_rate)` | Es/N₀ = Eb/N₀ + 10·log₁₀(bits_per_symbol · code_rate) | (1.0, 2, 0.5) = 1.0; (2.27, 2, 0.75) = 4.03 (±0.01) |
| `ebn0_from_esn0_db(esn0_db, bits_per_symbol, code_rate)` | inverse of the above | round-trips within 1e-9 |
| `margin_db(ebn0_db, required_ebn0_db, implementation_loss_db)` | Margin = Eb/N₀ − (Eb/N₀_req + L_impl) | (14.53, 1.5, 1.5) = 11.53 (±0.05) |
| `max_bit_rate_bps(cn0_dbhz, required_ebn0_db, implementation_loss_db, target_margin_db=3.0)` | R_max = 10^[(C/N₀ − Eb/N₀_req − L_impl − M_target)/10] | (77.54, 1.5, 1.5, 3.0) = 1.43e7 (±2 %) |
| `compute_ledger(scenario) -> dict` | runs the chain above in the Ledger order below | S-band scenario: C/N₀ 77.5, Eb/N₀ 14.5, margin 11.5 (each ±0.1) |

Argument conventions: `distance_km` is slant range; `freq_mhz` everywhere (never GHz inside the code); `bit_rate_bps` is information bits per second; angles in degrees at the API boundary, converted to radians inside.

### Ledger order (`compute_ledger` returns an ordered dict with these keys, in this order)

```
p_tx_dbw, g_tx_dbi, l_tx_db, eirp_dbw,
slant_range_km, fspl_db, other_losses_db,
g_rx_dbi, t_sys_k, g_over_t_db_per_k, minus_10log_k_dbw_per_k_hz,
cn0_dbhz,
bit_rate_bps, ten_log_bit_rate_db, ebn0_db,
ebn0_required_total_db,        # theory + implementation loss
margin_db,
max_bit_rate_bps_at_target_margin
```

Values in the dict are full precision; `run.py` rounds for display (2 decimals for dB, 1 for km and K, 3 significant figures for bit rates).

### Worked example — `scenarios/s_band_ttc.yaml`

```yaml
name: S-band TT&C downlink, 500 km, 10 deg elevation
# Geometry
altitude_km: 500.0
elevation_deg: 10.0
# Transmitter (satellite)
freq_mhz: 2200.0
p_tx_dbw: 0.0            # 1 W
g_tx_dbi: 3.0            # low-gain TT&C patch
l_tx_db: 1.0             # cable, connectors, filter, pointing
# Path
other_losses_db: 2.0     # atmosphere 0.5 + polarization 0.5 + pointing 0.5 + misc 0.5
# Receiver (ground station)
rx_dish_diameter_m: 3.0
rx_efficiency: 0.6
t_ant_k: 75.0
lna_nf_db: 1.0
g_over_t_db_per_k: null  # if set, overrides the dish/noise calculation (use when the operator publishes G/T)
# Data and modem
bit_rate_bps: 2.0e6
bits_per_symbol: 2       # QPSK
code_rate: 0.5
required_ebn0_db: 1.5    # rate-1/2 LDPC, BER 1e-5, per information bit
implementation_loss_db: 1.5
target_margin_db: 3.0
```

Expected ledger: EIRP 2.0 dBW · slant range 1694.6 km · FSPL 163.88 dB · G_rx 34.58 dBi · T_sys 150.1 K · G/T 12.82 dB/K · C/N₀ 77.54 dB-Hz · Eb/N₀ 14.53 dB · required 3.0 dB · margin 11.53 dB · max rate ≈ 14.3 Mbit/s at 3 dB margin.

### Comparison case — `scenarios/x_band_payload.yaml`

```yaml
name: X-band payload downlink, 500 km, 10 deg elevation
altitude_km: 500.0
elevation_deg: 10.0
freq_mhz: 8200.0
p_tx_dbw: 7.0            # 5 W
g_tx_dbi: 6.0            # medium-gain payload antenna
l_tx_db: 1.5
other_losses_db: 3.0     # rain 1.0 + atmosphere 0.5 + polarization 0.5 + pointing 1.0
rx_dish_diameter_m: 3.0
rx_efficiency: 0.6
t_ant_k: 60.0
lna_nf_db: 1.5
g_over_t_db_per_k: null
bit_rate_bps: 50.0e6
bits_per_symbol: 2
code_rate: 0.75
required_ebn0_db: 2.3    # DVB-S2 QPSK 3/4: Es/N0 4.03 dB → Eb/N0 ≈ 2.27 dB
implementation_loss_db: 1.5
target_margin_db: 3.0
```

Expected: FSPL exceeds the S-band case by 11.43 dB (±0.05) at equal range; margin lands around 4.5 dB — deliberately tight.

### Scenario schema (`scenario.py`)

`@dataclass(frozen=True) class Scenario` with exactly the keys above, in that order, typed `float` except `name: str`, `bits_per_symbol: int`, and `g_over_t_db_per_k: float | None`. `load_scenario(path) -> Scenario` parses YAML and raises `ValueError` naming any unknown or missing key.

## Style exemplar

Match this shape for every physics function:

```python
# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def slant_range_km(altitude_km, elevation_deg):
    """Straight-line distance from ground station to satellite.

    Law of cosines on the Earth-center / ground-station / satellite triangle;
    the angle at the ground station is 90° + elevation:

        d = sqrt((R_E + h)^2 - (R_E * cos(eps))^2) - R_E * sin(eps)

    Args:
        altitude_km:   orbit altitude above mean Earth surface [km]
        elevation_deg: satellite elevation above local horizon [deg]
                       (0 = horizon, 90 = directly overhead)
    Returns:
        slant range [km]. Equals altitude_km at 90° elevation.
    Reference:
        slant_range_km(500, 10) ≈ 1694.6 km
    """
    eps = np.radians(elevation_deg)                       # trig wants radians
    r_sat = EARTH_RADIUS_KM + altitude_km                 # orbit radius from Earth center
    return (np.sqrt(r_sat**2 - (EARTH_RADIUS_KM * np.cos(eps))**2)
            - EARTH_RADIUS_KM * np.sin(eps))
```

## Roadmap (tick in the same commit that completes the step)

- [ ] 0 · scaffold: layout, .gitignore, requirements, README skeleton, venv, git init, GitHub repo
- [ ] 1 · constants + dB helpers + tests
- [ ] 2 · slant range, wavelength, FSPL + tests
- [ ] 3 · dish gain, noise temperatures, G/T + tests
- [ ] 4 · EIRP, C/N₀, Eb/N₀, Es/N₀ conversions, margin, max-rate solver + tests
- [ ] 5 · Scenario dataclass, YAML loader, s_band_ttc.yaml + tests
- [ ] 6 · compute_ledger + run.py table + end-to-end test
- [ ] 7 · sweeps (elevation, bit rate, max-rate-vs-elevation) + plots + CLI flags + example PNG in README
- [ ] 8 · x_band_payload.yaml + --compare
- [ ] 9 · validation against a published reference + docs/validation.md + pinning test
- [ ] 10 · README complete
- [ ] later · elevation-dependent atmospheric loss · ITU-R P.618 rain · antenna pattern vs off-boresight · feed loss ahead of LNA · Doppler · bandwidth limits · interference
