# Demo script: Frankenstein Arterial Monitor

Target length: about 140 seconds of narration. Every number below comes from the smoke-test run saved in `demo/assets/smoke-test-output.txt` and `outputs/smoke/last_run.json`. All data is synthetic.

Charts: `demo/assets/chart-a-intervals.png`, `chart-b-gate.png`, `chart-c-filter.png`.

---

**[0:00 to 0:20] Problem** (chart: none, title card)

"A monitor for an urban arterial needs two answers. How long will a trip take, with an honest range? And is the event feed behaving? A forecast that never admits uncertainty is hard to trust. Frankenstein Arterial Monitor combines three parts into one application."

**[0:20 to 0:50] The three parts**

"The first part is an ANPR travel-time forecaster. For each five-minute period it predicts a distribution of travel times and gates the result. When the information is thin, it falls back to a training prior.

The second part is a wake-up filter. It is an explicit Gaussian point-process filter, and it works on the event stream one bin at a time. It flags overshoot when the prediction after a long silence runs above the resumed rate.

The third part is orchestration. Kiro holds the spec, the wiring contract, and the implementation tasks. The orchestrator routes events, closes each period, and writes one monitoring record per period."

**[0:50 to 1:25] What the smoke test shows** (charts a, b, c)

"This is the end-to-end smoke test. It runs one full period over a synthetic stream of 37,571 events across 30 periods.

Only the last period has the full 29 rows of feature history the model needs. The other 29 fall back for insufficient history. That is chart B: one published period, 29 fallbacks.

For the published period, the model's 90 percent interval is 47.7 to 145.0 seconds. All 15 synthetic trips in that period land inside it. That is chart A.

The filter runs the same stream as one batch kernel call, and the results match exactly. The period has a 60-second silence, and the filter raises no overshoot flag there. That is chart C. Seven checks pass."

**[1:25 to 1:50] The caveat**

"Every number in this demo comes from synthetic data. The travel times are generated uniformly between 45 and 150 seconds, so this run shows that the wiring works. It does not show that the forecasts are accurate. On validation, the model interval covered 92 percent of trips against a 90 percent target, and the prior covered 95 percent.

The paper's real results need authorized records, and this demo does not use any. The frozen evaluation path has not been run."

**[1:50 to 2:20] Close**

"Two items remain open for review: the definition of the gate input, and the online overshoot rule. Both are documented in the wiring file. Thank you for watching."

---

Production notes:
- Show the terminal output from `demo/assets/smoke-test-output.txt` while narrating section 0:50 to 1:25.
- Chart B's title states that 29 of 30 periods have only one feature row in the stream. Keep the title on screen during that line.
