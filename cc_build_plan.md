# Build plan — prompting Claude Code through leo-link-budget

One step = one prompt = one commit. Paste each prompt as written; adjust only where marked. CLAUDE.md is the spec; the prompts point at it rather than restating formulas, so keep it accurate.

## Before the first session (once)

1. `gh auth login` done (you, in your own terminal — never hand a token to an agent).
2. Claude Code installed and logged in.
3. `mkdir leo-link-budget && cd leo-link-budget`, copy `CLAUDE.md` into it, then `claude`.
4. Leave "accept all" **off** for this project. Reading each diff against the walkthrough is the point.

## The loop, every step

1. Paste the prompt.
2. Claude Code proposes files and diffs. Before approving, check three things: the docstring formula matches CLAUDE.md, units are in the argument names, comments are present.
3. Approve. Then: `run pytest -q`. Fix until green.
4. `commit with the message "<from the step>"`, then `push`.

If it goes off-spec, say so in one line: "That drops the sin term — re-read slant_range in CLAUDE.md." "Add the docstring formula and units before I approve." "No new dependency; use numpy."

Starting a later session: `cd leo-link-budget && claude`, then:

> Read CLAUDE.md and `git log --oneline`. Tell me which Roadmap step is next and what it requires. Don't write anything yet.

---

## Step 0 — Scaffold

> Read CLAUDE.md. Scaffold the project exactly as its Layout section describes: `.gitignore` (Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.pytest_cache/`, `.env`, `plots/`), `requirements.txt` (numpy, matplotlib, pyyaml, pytest), `tests/__init__.py`, placeholder modules `link_budget.py`, `scenario.py`, `sweeps.py`, `plots.py`, `run.py` each containing only a one-paragraph module docstring saying what it will hold, empty `scenarios/`, `docs/img/`, and `plots/` (with a `.gitkeep` in `docs/img/`), and a `README.md` skeleton with these section headers: What it is · Example result · How to run · Method · Assumptions · Validation · Roadmap · References. Create the virtual environment, install requirements, and confirm `pytest -q` runs with zero tests. Then `git init`, stage everything, and show me `git status` — don't commit yet.

Check: `.gitignore` contains `plots/` and `.env`; nothing under `.venv/` is staged.

> Commit with the message "chore: scaffold project structure". Then create a public GitHub repository named leo-link-budget from this folder using `gh repo create leo-link-budget --public --source=. --push`, and confirm the remote URL and that the push succeeded. Tick Roadmap step 0 in CLAUDE.md and commit that as "docs: roadmap step 0".

Check on github.com: the repo exists, `CLAUDE.md` and `README.md` are visible.

---

## Step 1 — Constants and dB helpers

> Implement the Constants table and the first four functions of the Physics spec in `link_budget.py`: `EARTH_RADIUS_KM`, `C_M_PER_S`, `BOLTZMANN_J_PER_K`, `BOLTZMANN_DBW_PER_K_HZ` (computed from k, not typed), `T0_K`, and `db()`, `lin()`, `dbw_from_w()`, `dbm_from_dbw()`. Follow the Style exemplar: section banner comment, docstring with formula, units, and reference value, inline comments. Use numpy so scalars and arrays both work. Then write `tests/test_helpers.py` covering every reference value in the spec table for these functions, plus `BOLTZMANN_DBW_PER_K_HZ ≈ −228.6` within 0.01. Run `pytest -q` and show me the result.

Check: `BOLTZMANN_DBW_PER_K_HZ` is an expression, not a literal.

Commit: `feat: constants and dB helpers with tests` — then tick step 1, push.

---

## Step 2 — Geometry and path loss

> Add `wavelength_m`, `slant_range_km`, and `fspl_db` to `link_budget.py` per the spec. `fspl_db` must implement `20·log10(4π·d/λ)` with d converted to metres and λ from `wavelength_m` — the 32.45 shortcut goes in the docstring as a cross-check only. `tests/test_geometry.py`: every reference value in the spec for these three functions, plus a test that `fspl_db` agrees with `20*log10(d_km) + 20*log10(f_mhz) + 32.45` within 0.01 dB, plus a test that `slant_range_km` on a numpy array of elevations returns an array of the same shape. Run pytest.

Check: `slant_range_km(500, 90)` test asserts exactly 500 (tolerance 1e-6) — that's the geometric sanity check.

Commit: `feat: slant range and free-space path loss` — tick step 2, push.

---

## Step 3 — Antenna and noise

> Add `dish_gain_dbi`, `receiver_noise_temp_k`, `system_noise_temp_k`, and `g_over_t_db_per_k` per the spec. In the `receiver_noise_temp_k` docstring, explain in two sentences why noise is expressed as a temperature (a resistor at T produces k·T W/Hz) and why the LNA sits at the antenna (Friis cascade — later stages' noise is divided by the gain ahead of them). `tests/test_antenna_noise.py` with every reference value from the spec. Run pytest.

Check: `dish_gain_dbi` uses `wavelength_m`, not its own c/f.

Commit: `feat: dish gain, noise temperature, G/T` — tick step 3, push.

---

## Step 4 — Link equations

> Add `eirp_dbw`, `cn0_dbhz`, `ebn0_db`, `esn0_from_ebn0_db`, `ebn0_from_esn0_db`, `margin_db`, and `max_bit_rate_bps` per the spec. `cn0_dbhz` must subtract `BOLTZMANN_DBW_PER_K_HZ` (i.e. add 228.6), never a typed constant. In the `cn0_dbhz` docstring, state why C/N₀ is preferred over C/N (it removes the bandwidth, which isn't chosen until the modem is). In the `ebn0_db` docstring, state that `bit_rate_bps` is information bits per second and the required Eb/N₀ values must be quoted per information bit to match. `tests/test_link_equations.py` with every reference value from the spec, and an Es/N₀ ↔ Eb/N₀ round-trip test. Run pytest.

Check: `max_bit_rate_bps` returns ≈ 1.43e7 for the worked example.

Commit: `feat: EIRP, C/N0, Eb/N0, margin, max-rate solver` — tick step 4, push.

---

## Step 5 — Scenario inputs

> Create `scenario.py` with the frozen `Scenario` dataclass from the spec's Scenario schema (exact field names and order, correct types, `g_over_t_db_per_k` optional) and `load_scenario(path)` that reads YAML and raises `ValueError` naming any unknown or missing key. Write `scenarios/s_band_ttc.yaml` exactly as given in CLAUDE.md, comments included. `tests/test_scenario.py`: loading the YAML yields the expected field values; a copy with a misspelled key raises; a copy with a missing key raises. Run pytest.

Check: the YAML comments survived — they're documentation for the reader.

Commit: `feat: scenario dataclass and YAML loader` — tick step 5, push.

---

## Step 6 — Ledger and CLI

> Add `compute_ledger(scenario)` to `link_budget.py` returning a dict with exactly the keys and order in the spec's Ledger order. When `g_over_t_db_per_k` is set in the scenario, use it and set `g_rx_dbi` and `t_sys_k` to `None` in the ledger; otherwise compute them from the dish and noise fields. Then implement `run.py`: `python run.py scenarios/s_band_ttc.yaml` prints the scenario name, then the ledger as an aligned two-column table with units, rounding per the spec, and a final line with the max bit rate at the target margin. `tests/test_worked_example.py`: the S-band scenario yields C/N₀ 77.5, Eb/N₀ 14.5, margin 11.5, each within 0.1 dB. Run pytest and show me the CLI output.

Check: the printed table reads like the ledger in the walkthrough — someone could follow it line by line.

Commit: `feat: end-to-end ledger and CLI` — tick step 6, push.

---

## Step 7 — Sweeps and plots

> Implement `sweeps.py`: `sweep_elevation(scenario, elevation_deg)` returning a dict of arrays (`elevation_deg`, `slant_range_km`, `fspl_db`, `cn0_dbhz`, `ebn0_db`, `margin_db`) computed vectorially with numpy — no Python loops; `sweep_bit_rate(scenario, bit_rate_bps)` returning `ebn0_db` and `margin_db` arrays; and `max_rate_vs_elevation(scenario, elevation_deg)`. Implement `plots.py`: `plot_margin_vs_elevation`, `plot_margin_vs_bit_rate` (log x-axis), `plot_max_rate_vs_elevation`, each saving a PNG to a given path with axis labels carrying units, a dashed reference line at the target margin, and the scenario name in the title. Add `--sweep-elevation`, `--sweep-rate`, and `--out DIR` flags to `run.py` (default sweep ranges: 5–90° in 1° steps; 100 kbit/s–100 Mbit/s log-spaced, 50 points). `tests/test_sweeps.py`: `sweep_elevation` at the single value [10.0] reproduces `compute_ledger`; margin increases monotonically with elevation; the rate sweep crosses the target margin exactly where `max_bit_rate_bps` says it should (within 2 %). Run pytest, then run the sweeps for the S-band scenario.

Check: open `plots/margin_vs_elevation.png` — the curve should be steep at low elevation and flatten toward zenith.

Commit: `feat: elevation and bit-rate sweeps with plots` — then:

> Copy `plots/margin_vs_elevation.png` to `docs/img/` and embed it in README under "Example result" with a one-sentence caption stating the scenario. Commit as "docs: add example plot". Tick step 7, push.

---

## Step 8 — X-band comparison

> Write `scenarios/x_band_payload.yaml` exactly as given in CLAUDE.md. Add `--compare OTHER.yaml` to `run.py` that prints both ledgers side by side with a delta column (other minus base). `tests/test_sweeps.py` or a new test: at equal slant range, X-band FSPL exceeds S-band by 11.43 dB within 0.05. Run pytest and show me the comparison output.

Check: the X-band margin lands near 4.5 dB — tight on purpose; that's the case the tool is for.

Commit: `feat: scenario comparison` — tick step 8, push.

---

## Step 9 — Validation against a published budget

You supply the reference. Find one full link table you can cite — SMAD's communications chapter example, or any university CubeSat paper with a complete downlink budget — and type its inputs into the prompt. Where the reference gives G/T directly, set `g_over_t_db_per_k` instead of dish and noise fields.

> Create `scenarios/validation_<short-name>.yaml` with these inputs: [paste them, one per line, with the source citation as the `name`]. Run it. Write `docs/validation.md` as a table: ledger line · reference value · this tool · delta (dB). Explain any delta over 0.3 dB in one sentence under the table (usually a different constant, rounding, or a loss the reference lumped differently). Add `tests/test_validation.py` pinning the reference's C/N₀ and margin within 0.3 dB. Run pytest.

Check: you can explain every delta. That sentence is the interview answer.

Commit: `test: validate against <short-name>` — tick step 9, push.

---

## Step 10 — README

> Complete README.md. "What it is": three sentences — what the tool computes, that it's a parametric LEO downlink link-budget analysis in Python, and what the sweeps show. "Example result": the plot already embedded plus the S-band ledger table copied from the CLI output. "How to run": the Commands block from CLAUDE.md. "Method": one short paragraph per step of the chain — EIRP, slant range, FSPL, other losses, G/T, C/N₀, Eb/N₀, required Eb/N₀, margin — each naming the function that implements it and stating the mechanism in plain language (why frequency appears in FSPL; why G/T is a ratio; why C/N₀ before choosing a bandwidth). "Assumptions": every default in the S-band scenario and one line on why. "Validation": link `docs/validation.md` and state the largest delta. "Roadmap": the "later" items from CLAUDE.md. "References": CCSDS 130.1-G, ETSI EN 302 307 (DVB-S2, Table 13), ITU-R P.618, ITU-R P.676, SMAD. Keep the whole file under two screens.

Check: read it as the hiring manager — can they get what the tool does, see a result, and run it, in one minute?

Commit: `docs: complete README` — tick step 10, push.

---

## Step 11 — Publish

On github.com: pin the repo on your profile. Copy the URL into the résumé Projects entry and the header. Done — later commits (the "later" roadmap items) keep it visibly alive while applications are out.
