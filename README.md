# leo-link-budget

> The full downlink ledger — EIRP to link margin — from a YAML scenario, with
> elevation and bit-rate sweeps that show where the link closes.

## What it is

A parametric link-budget analysis for a LEO satellite downlink, in Python with NumPy.
Given a scenario — orbit, frequency, transmitter, ground station, data rate,
modulation and coding — it computes the full downlink ledger: EIRP → slant range →
free-space path loss → G/T → C/N₀ → Eb/N₀ → margin, with every physics function
documented against a reference value and pinned by one of 232 tests, and the whole
chain validated end to end against a published budget. The sweeps vary elevation
angle and bit rate to show where a link opens and closes: how much margin a pass
holds at each elevation, and how fast the link can run before margin reaches zero.

## How to run

```
# one-time setup
python -m venv .venv
.venv\Scripts\activate             # Windows
source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt

# every session
pytest -q
python run.py scenarios/s_band_ttc.yaml
python run.py scenarios/s_band_ttc.yaml --sweep-elevation --sweep-rate --out plots/
python run.py scenarios/s_band_ttc.yaml --compare scenarios/x_band_payload.yaml
```

## Example result

![Link margin versus elevation angle for the S-band TT&C downlink](docs/img/margin_vs_elevation.png)

Link margin for a 1 W, 2 Mbit/s S-band TT&C downlink from a 500 km orbit to a 3 m
ground station, swept from the horizon to zenith: margin rises steeply through the
first few degrees of elevation, where a degree buys a large reduction in slant range,
and flattens toward zenith, where it buys almost none.

`python run.py scenarios/s_band_ttc.yaml` prints the ledger — abridged here to the
six lines that carry the argument, of eighteen:

```
S-band TT&C downlink, 500 km, 10 deg elevation
==============================================
  EIRP                               2.00  dBW
  Free-space path loss             163.88  dB
  G/T                               12.82  dB/K
  C/N0                              77.54  dB-Hz
  Eb/N0                             14.53  dB
  Margin                            11.53  dB
```

`--compare scenarios/x_band_payload.yaml` puts two cases side by side with a delta
column, and the interesting result is what cancels. X-band pays **11.43 dB** more
path loss than S-band at the same slant range — and the same 3 m dish gains back
**exactly 11.43 dB**, because gain and free-space loss both go as f². The band change
is free; what makes the X-band case tight (4.5 dB of margin against S-band's 11.5) is
its 25× bit rate, worth 13.98 dB.

## Method

**EIRP** — `eirp_dbw`. Transmit power plus antenna gain minus the losses between
them. It is the power an isotropic radiator would need to put the same flux on
boresight, which collapses the whole transmit chain into one number.

**Slant range** — `slant_range_km`. Law of cosines on the Earth-centre / ground-station
/ satellite triangle. Range grows sharply toward the horizon: a 500 km orbit is 500 km
away overhead and 2077 km away at 5°, which is what drives the elevation sweep.

**Free-space path loss** — `fspl_db`. Spreading over a sphere costs 1/(4πd²), which has
no frequency in it. Frequency appears because the loss is quoted against an *isotropic*
receiver, whose effective aperture is λ²/4π — so a fixed-gain antenna captures less
power as wavelength shrinks. That is why the term goes as 20log₁₀(f), and why a bigger
dish, whose aperture is fixed in metres rather than wavelengths, gives it all straight
back.

**Other losses** — a scenario input. Atmosphere, rain, polarization mismatch and
pointing error, entered as one budgeted figure rather than modelled.

**G/T** — `dish_gain_dbi`, `receiver_noise_temp_k`, `system_noise_temp_k`,
`g_over_t_db_per_k`. Noise is bookkept as a temperature because a resistor at T
delivers exactly k·T W/Hz, so the sky, the ground and the amplifier all add in the same
unit. G/T is a ratio because gain and noise never appear apart in the ledger: +1 dB of
gain and halving T_sys are the same trade, so one number characterises the station. A
published G/T can be used directly instead.

**C/N₀** — `cn0_dbhz`. Carrier power over noise *density*, not noise power, because
dividing by density removes bandwidth from the expression — and bandwidth is not known
until a modem, symbol rate and filter roll-off are chosen, long after the RF chain is
fixed. C/N₀ is therefore the last quantity belonging purely to the link.

**Eb/N₀** — `ebn0_db`. C/N₀ less 10log₁₀(R_b): spreading the carrier across more bits
per second leaves less energy in each, so every doubling of rate costs 3.01 dB. The
rate is *information* bits per second.

**Required Eb/N₀** — a scenario input, plus `esn0_from_ebn0_db` / `ebn0_from_esn0_db`
to convert the Es/N₀ that standards tables quote. It must be stated per information
bit to match; a per-channel-bit figure differs by 10log₁₀(code rate), 3 dB at rate ½.

**Margin** — `margin_db`, and `max_bit_rate_bps` for the inverse question. Achieved
Eb/N₀ less the requirement and the modem's implementation loss. Positive closes.

## Assumptions

Defaults in [`scenarios/s_band_ttc.yaml`](scenarios/s_band_ttc.yaml):

| Input | Value | Why |
|---|---|---|
| `altitude_km` | 500 | Typical LEO rideshare altitude |
| `elevation_deg` | 10 | Common minimum mask; near worst case for a usable pass |
| `freq_mhz` | 2200 | S-band space-research downlink allocation |
| `p_tx_dbw` | 0 (1 W) | Representative CubeSat TT&C transmitter |
| `g_tx_dbi` | 3 | Low-gain patch; near-omni so the link survives tumbling |
| `l_tx_db` | 1.0 | Cable, connectors, filter and transmit pointing |
| `other_losses_db` | 2.0 | Atmosphere 0.5 + polarization 0.5 + pointing 0.5 + misc 0.5 |
| `rx_dish_diameter_m` | 3.0 | Modest university-class ground station |
| `rx_efficiency` | 0.6 | Typical for a well-fed prime-focus dish |
| `t_ant_k` | 75 | Sky plus ground spillover at moderate elevation |
| `lna_nf_db` | 1.0 | Good uncooled LNA at the feed |
| `g_over_t_db_per_k` | null | Computed from the dish and noise terms; set it to override |
| `bit_rate_bps` | 2e6 | Representative TT&C downlink rate |
| `bits_per_symbol` / `code_rate` | 2 / 0.5 | QPSK, rate-½ coding |
| `required_ebn0_db` | 1.5 | Rate-½ LDPC at BER 1e-5, per information bit |
| `implementation_loss_db` | 1.5 | Real modem shortfall against theory |
| `target_margin_db` | 3.0 | Reserve held by the max-rate solver |

Constants are computed rather than typed — `BOLTZMANN_DBW_PER_K_HZ` is `10log₁₀(k)`,
not −228.6. A spherical Earth is assumed, atmospheric loss is a fixed input rather
than elevation-dependent, and the antenna is treated as on boresight.

## Validation

Checked end to end against a published budget — the DICE mission downlink from
Baktur, *IEEE Antennas & Propagation Magazine*, Dec 2022, Table 3. **The largest delta
is 0.0011 dB**, on Eb/N₀ and margin, and every delta reduces to rounding in the
published table or to the one place the schema differs. Line-by-line comparison, and a
statement of what the check does *not* cover, in [`docs/validation.md`](docs/validation.md).

## Roadmap

Elevation-dependent atmospheric loss · ITU-R P.618 rain attenuation · antenna pattern
versus off-boresight angle · feed loss ahead of the LNA · Doppler · bandwidth limits ·
interference.

## References

- CCSDS 130.1-G — *TM Synchronization and Channel Coding — Summary of Concept and Rationale*
- ETSI EN 302 307 (DVB-S2), Table 13 — required Es/N₀ by modulation and code rate
- ITU-R P.618 — propagation data and prediction methods for Earth-space paths
- ITU-R P.676 — attenuation by atmospheric gases
- Wertz, Everett & Puschell, *Space Mission Engineering: The New SMAD*, Microcosm, 2011
- R. Baktur, "CubeSat Link Budget: Elements, calculations, and examples," *IEEE Antennas
  and Propagation Magazine*, 64(6), Dec. 2022, [DOI 10.1109/MAP.2022.3201250](https://doi.org/10.1109/MAP.2022.3201250)
