# Validation

This tool is checked against a published link budget: a case computed independently,
by someone else, with its own constants and conventions. Agreeing with a textbook
formula proves only that the formula was typed in correctly; agreeing with a
complete worked budget end to end is a stronger claim, because every term has to be
interpreted the same way for the totals to land in the same place.

## Reference

R. Baktur, "CubeSat Link Budget: Elements, calculations, and examples,"
*IEEE Antennas and Propagation Magazine*, vol. 64, no. 6, pp. 16–28, Dec. 2022,
DOI [10.1109/MAP.2022.3201250](https://doi.org/10.1109/MAP.2022.3201250).

The case is the **downlink column of Table 3**, a budget developed by Dr. Charles
Swenson for the DICE (Dynamic Ionosphere CubeSat Experiment) mission: a 1 W, 465 MHz
downlink at 1.5 Mbit/s over a 1944 km path, received by a ground station with a
published figure of merit of 9.03 dB/K.

It was chosen because it is **complete and internally consistent**. Every input is
stated, and the reference's own intermediate values reproduce its totals exactly —
so a disagreement here is a disagreement about physics, not about a missing input
that had to be guessed.

The inputs are transcribed in [`scenarios/validation_dice_downlink.yaml`](../scenarios/validation_dice_downlink.yaml),
one line per reference quantity, with the citation as the scenario `name`. Reproduce
this table with:

```bash
python run.py scenarios/validation_dice_downlink.yaml
```

## Comparison

| Ledger line | Reference | This tool | Delta (dB) |
|---|---|---|---|
| TX power | 0.00 dBW | 0.00 dBW | 0.0000 |
| TX antenna gain | −3.50 dB | −3.50 dBi | 0.0000 |
| Total TX loss | 0.50 dB | 0.50 dB | 0.0000 |
| EIRP | −4.00 dBW | −4.00 dBW | 0.0000 |
| Path length | 1944 km | 1943.68 km | −0.0007 † |
| Path loss | 151.57 dB | 151.5693 dB | −0.0007 |
| Atmospheric + polarization loss | 1.50 dB | 1.50 dB | 0.0000 |
| RX figure of merit G/T | 9.03 dB | 9.03 dB/K | 0.0000 ‡ |
| C/N₀ | 80.56 dB-Hz | 80.5599 dB-Hz | −0.0001 |
| Data rate term 10·log₁₀(R_b) | 61.76 dB | 61.7609 dB | +0.0009 |
| **Eb/N₀** | **18.80 dB** | **18.7989 dB** | **−0.0011** |
| Required Eb/N₀ (threshold + impl. loss) | 11.60 dB | 11.60 dB | 0.0000 |
| **Link margin** | **7.20 dB** | **7.1989 dB** | **−0.0011** |

† The delta shown is the effect on path loss, not the 0.32 km difference in range — see below.
‡ Taken from the reference rather than computed; see "What this does not validate".

**No delta exceeds 0.3 dB.** The largest is 0.0011 dB, on Eb/N₀ and margin. Since the
brief asks for an explanation of any delta over 0.3 dB, there is nothing in that
category to explain — but the three non-zero deltas are worth accounting for, because
a delta of exactly zero on every line would suggest the comparison was not independent.

- **Path length, −0.32 km.** The reference states slant range directly; this tool
  derives it from altitude and elevation, so the scenario uses 450 km (DICE perigee)
  at 5° elevation, which gives 1943.68 km and costs 0.0015 dB of path loss.
- **Path loss, −0.0007 dB.** The residual after the range difference above: the
  reference uses the folded-constant form 20log₁₀(d_km) + 20log₁₀(f_MHz) + 32.45,
  where 32.45 is rounded; this tool computes 20log₁₀(4πd/λ) from the SI speed of light.
- **Eb/N₀ and margin, −0.0011 dB.** Rounding only. The reference quotes its data-rate
  term as 61.76 dB where 10·log₁₀(1.5 × 10⁶) = 61.7609 dB.

## The noise chain, checked separately

The scenario uses the reference's **published** G/T of 9.03 dB/K, so the tool's
dish-gain and noise-temperature functions do not run on the path above. They are
checked separately against the same table's stated values:

| Quantity | Reference | This tool | Delta |
|---|---|---|---|
| Receiver noise temperature from NF 3.08 dB | 300 K | 299.38 K | −0.62 K |
| System noise temperature (T_ant 200 K + T_rx) | 500 K | 499.38 K | −0.62 K (−0.0054 dB) |
| G/T from effective gain 36.02 dB | 9.03 dB | 9.0357 dB | +0.0057 dB |
| Noise density 10·log₁₀(k·T_sys) | −201.61 dBW/Hz | −201.6095 dBW/Hz | +0.0005 dB |

The 0.62 K difference is the reference rounding T_rx to 300 K; 290·(10^0.308 − 1)
= 299.38 K. Its effect on the budget is 0.0054 dB.

## What this does not validate

Stating the limits matters more than the agreement does.

- **G/T is taken, not computed.** The reference's ground antenna is a 37 dB array, not
  a parabolic dish, so `dish_gain_dbi` does not apply to it. The scenario therefore
  uses the published-G/T override, and the table's G/T row is an input echoed back,
  not a check. `dish_gain_dbi` is covered by its own unit tests against the spec, not
  by this document.
- **One case, one regime.** A single 465 MHz LEO downlink at 5° elevation. It exercises
  the chain end to end but says nothing about behaviour at other bands or geometries
  beyond what the unit tests already pin.
- **Rain and atmospheric loss are inputs, not models.** Both this tool and the reference
  take them as fixed numbers. Nothing here validates an atmospheric model, because
  neither has one.
- **The uplink column was not used.** Table 3 also carries an uplink budget; only the
  downlink was reproduced.

## Other references consulted

Two further documents were reviewed and did **not** yield a validation case:

- *Space Mission Engineering: The New SMAD*, Chapter 16 (web supplement), Table 16web-2.
  This is a return-link budget for a GEO mobile-satellite system with an Earth-coverage
  antenna and a GMR-1 3G waveform. It is a complete budget, but for a different regime
  — geostationary, with uplink and downlink combined into an end-to-end Eb/N₀ — and
  reproducing it would require modelling a bent-pipe transponder this tool does not
  have. A candidate for a future validation case, not this one.
- *CubeSat 101: Basic Concepts and Processes for First-Time CubeSat Developers*,
  NASA CSLI, 2017. A programme-level primer covering mission planning, integration and
  launch. It contains no numeric link budget; its references to "margin" are schedule
  margin. Useful background, not a reference budget.

## Reproducing this

```bash
python run.py scenarios/validation_dice_downlink.yaml
python -m pytest tests/test_validation.py -q
```

`tests/test_validation.py` pins the reference's C/N₀ and margin to within 0.3 dB, so
a future change that breaks agreement with the published budget fails the suite.
