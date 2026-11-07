# How Kiro was used (draft for the Devpost submission)

## What we built

Frankenstein Arterial Monitor stitches three parts into one arterial-monitoring application:

1. An ANPR travel-time forecaster, from the open-source repository `availability-aware-anpr-forecasting`.
2. An explicit Gaussian point-process wake-up filter, from `wake-up-overshoot`.
3. Kiro spec-driven orchestration: specs, steering, and wiring documents under `.kiro/` and `docs/`.

The repository is `frankenstein-arterial-monitor`. Its current state is a working, synthetic-data end-to-end path. It is not a deployed monitoring service. Real-data integration and the frozen evaluation path are not done.

## How Kiro was used

All of the work was done in Kiro Web sessions in Vibe mode. The Kiro agent read and edited files, ran shell commands, and used a context-gatherer sub-agent to map the source repository. The human partner made the scope and labelling decisions. The sessions followed these steps.

**1. Skeleton (already in the repository before this work).** The repository held the project spec (`docs/spec.md`), the wiring contract (`docs/wiring.md`), development rules, steering files, a requirements/design/tasks spec under `.kiro/specs/arterial-monitoring/`, three v1 JSON hook files under `.kiro/hooks/`, and stdlib-only interface modules with a self-check script (`scripts/check_interfaces.py`). This work did not change the hook files, and we did not measure their effect.

**2. Baseline checks.** The agent ran each source repository's own commands:
- Interface self-check: passed.
- ANPR synthetic generator and the 10 unit tests: passed, after pinning NumPy to 1.26.4 (NumPy 2 removes `np.trapz`, which the code uses). PyTorch was installed as a CPU build.
- Wake-up filter build: the repository's `build.py` uses `-static`, and the sandbox has no static C/C++ libraries and a read-only filesystem. The build failed. A dynamic build of the same source compiled with no warnings. `check_engine.py` then passed all 19 checks. The synthetic experiment finished with H1 holding in 73 of 73 cases, H2 in 2 of 24, and H3 in 10 of 10. The first run hit the 30-minute tool limit, and the agent resumed it from the existing output files.

**3. A blocker on the ANPR frozen path.** The repository's `prepare` stage requires the paper's exact record counts, and synthetic data cannot reach them. The agent reported this and stopped. The human chose the option of a synthetic-only forecaster built on the repository's public functions. The agent did not change the count check in the source repository.

**4. Wiring implementation.** Using the interface skeleton and `docs/wiring.md` as the contract, the agent implemented:
- `src/anpr_forecast/synthetic.py`: fits a snapshot mixture density network on synthetic trip windows. It picks gate thresholds on validation trips, with the rule "highest publication rate whose validation coverage is at least 0.90". Every output is labelled `synthetic-only; not the paper's frozen path`.
- `src/wakeup_filter/kernel.py`: a standard-library binding that calls `engine.exe` one bin at a time and carries the filter state between calls.
- `src/orchestrator/pipeline.py`: `run_event_loop`, which closes each five-minute period, feeds empty bins to the filter so silences are measured, and writes one record per period to `monitor.jsonl`.
- Contract changes were made in the interface files first, as the development rules require. They are additive, with defaults. The wiring document records them.

**5. Smoke test.** `scripts/smoke_end_to_end.py` runs one target period from a synthetic stream of 37,571 events over 30 periods. Seven checks pass. The filter's stream matches one batch kernel call exactly. The output of the run is saved in `demo/assets/smoke-test-output.txt`.

**6. Demo assets.** Three charts come from the run's own outputs (`scripts/make_demo_charts.py`). The narration script is in `docs/demo-script.md`.

## What the human decided

- Scope: synthetic data only, and no real plate records or Binance data.
- The synthetic-only forecaster in place of the frozen path.
- The gate input is labelled by what the code computes, and the in-transit ratio definition is marked pending confirmation.
- The source repositories stay clean checkouts, and no manuscript or submission file is touched.

## Limitations stated plainly

- Every number is synthetic. The synthetic travel times are uniform, so the run shows the wiring works, not forecast accuracy.
- Only 1 of the 30 periods in the smoke run reaches the model. The other 29 lack the feature history that the model needs.
- The smoke test checks only method E. Earlier checks of all five methods were ad hoc and are not saved in the repository.
- The overshoot rule is the skeleton's own online definition, not one from the source repository. It did not fire in the smoke run. The rho_t definition is still pending confirmation.
- The frozen evaluation path, service KPIs, and real-data results are not done.
