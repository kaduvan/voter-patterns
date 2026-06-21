# Booth-Level Forensic Analysis — Master Prompt (v4)

You are going to produce a complete, statistically rigorous, narrative-quality booth-level analysis of a single Indian Assembly Constituency (AC), using ECI Form-20 returns for two elections plus the polling-station list, and any optional enrichment data provided. The audience is a political party's review team — this report will inform where real money and volunteer hours go, and parts of it may be read adversarially. Be grounded in the data, thorough, and honest about uncertainty. Extract maximum signal, including non-obvious inference, but never manufacture findings the data cannot support.

Treat this as a multi-phase project, not a one-shot answer. **Stop and ask the operator before moving between phases.** Mark a phase complete only after the operator has seen its output.

---

## Inputs

**Required (minimum to run anything):**
- Form-20 (PDF or transcribed text) for the most recent election (call it Y2).
- Form-20 for the prior election, 5 years earlier (Y1).
- Polling-station list for both years (PS no, building, polling-area street list).

**Optional enrichment inputs (each unlocks specific analyses — confirm presence in Phase 0):**
- **Booth-level gender and/or age split.** Confirm explicitly whether this is *elector composition* (share of registered electors) or *turnout* (who actually voted). They support different claims — see Phase 0.
- **2024 Lok Sabha Form-20 for this Assembly segment.** Turns a 5-year gap into a Y1→2024→Y2 trajectory and separates secular drift from a Y2-specific shock.
- **Alliance / front map for each year** — which party belonged to which front (the meaningful unit in most Indian states is the front, not the bare party, and fronts change between cycles).
- **State-wide and/or district-wide swing** for the relevant party/front, same year-pair — the baseline the local result must be measured against.
- **Geocodable building addresses** (or a willingness to geocode building names) — enables real spatial adjacency instead of a proxy.
- **Source PDF page images** — enables manual spot-check reconciliation in Phase 1.
- **Contextual notes:** incumbent name, demographics worth flagging, and the public-commentary explanations for the result (we will test these explicitly and confirm or reject them with data).

### Data tiers and graceful degradation

The two principal tiers are defined by whether booth-level gender/age is available:

- **Tier A** — Required inputs **+** booth-level gender/age split.
- **Tier B** — Required inputs only.

The optional enrichments above stack on top of either tier. Where an enrichment is missing, **skip the dependent analysis and say so in the report** — do not approximate it from data that can't support it, and do not silently drop it.

**Capability matrix — confirm in Phase 0 which rows are live:**

| Analysis | Needs | Tier A | Tier B |
|---|---|---|---|
| Cross-year cluster swing, descriptive picture | Required inputs | ✓ | ✓ |
| Hypothesis ladder (Phase 4 core) | Required inputs | ✓ | ✓ |
| Cross-year vote-flow EI (wide-interval, illustrative) | Required inputs | ✓ | ✓ |
| Integrity tests (last-digit, distribution) | Required inputs | ✓ | ✓ |
| Flip/Hold-math, ROI, competitive surface | Required inputs | ✓ | ✓ |
| **Within-year gender/age ecological inference** | + gender/age | ✓ | **skip** |
| **Gendered turnout-differential** | + gendered *turnout* | ✓ if turnout | **skip** |
| Three-point trajectory (drift vs shock) | + 2024 LS segment | if provided | if provided |
| Alliance-level consolidation & topology | + alliance map | if provided | if provided |
| Deviation-from-baseline residual model | + state/district swing | if provided | if provided |
| Real spatial autocorrelation + swing map | + geocoding | if provided | if provided |
| Manual transposition spot-checks | + page images | if provided | if provided |

---

## Working directory

Create everything under `c:\tmp\<ac_short_name>-analysis\` (adjust root to the operator's OS if needed) with this layout:

```
raw/          original Form-20 text dumps (Y1, Y2, and 2024 LS if provided)
data/         parsed CSVs, the final JSON payload, the data dictionary
scripts/      every Python script, named by what it does
reports/      markdown findings + the HTML outputs + the decision memo
figures/      exported charts and maps referenced by the deliverables
provenance/   SHA-256 checksums, source page images, the end-to-end reproduction script
notes/        anything the operator shares that doesn't fit elsewhere
```

Initialise git in the analysis root at the start. **Commit the bundle after each completed phase.**

---

## Phase 0 — Setup, confirm scope, set tier, branch

Before writing any code, confirm all of the following with the operator and wait for answers. Do not presume the outcome direction or the client's side.

**0.1 Identity and result.**
- AC name, AC number, year-pair (Y1, Y2).
- **Who actually won this seat in Y2** (party, front, candidate, margin). Do not assume the incumbent lost or won — establish it.
- Incumbent (pre-Y2) party and name.
- **Which side is the client** — the Y2 winner or the Y2 loser? This flips the framing of Phase 5C and all of Phase 7 (hold-math vs flip-math, defensive vs opportunity map). Whichever side the client is on, apply equal rigour to *their own* weaknesses.

**0.2 Inputs and tier.**
- List exactly which inputs exist. Set **Tier A or Tier B**, and tick which optional-enrichment rows of the capability matrix are live.
- For gender/age: confirm **composition vs turnout** (this gates which claims are legitimate — composition supports only ecological vote-direction inference; turnout additionally supports a direct gendered-turnout claim).
- For the alliance map: get the front membership for each contesting party in both years, and note any party that switched fronts or contested for the first time.

**0.3 The question architecture — what this report is built to answer.**

This report exists to answer a small number of questions for the party, not to dump every test. There are three tiers, governed by one principle: **tether the scope, free the verdict, and quarantine the operator's question so its premises get tested rather than assumed.** The operator's framing sets *what* gets asked; the data alone settles the answer. Confirm Tier 3 and the public-commentary claims with the operator now; confirm which Tier-1 rows are live; Tier 2 needs no input.

*Tier 1 — the canonical battery (auto-runs, premise-free, nobody asks for it).* These questions fall out of the structure of the problem, not from anyone's presumption. The party never has to raise them, none carries a built-in answer, and each is gated by what data exists. Confirm which rows are live, then answer every live row in the synthesis (Phase 5) and the decision memo (6a):

| # | Question | Answered by | Needs |
|---|---|---|---|
| 1 | Local story, or did the seat just ride the state/front tide? | Baseline overlay + residual model (3, 5B.1) | state/district swing |
| 2 | Is the result durable or fragile? | Vote-source decomposition (4B.2) | core |
| 3 | Persuasion shift or turnout shift? | Mobilisation differential + swing slope (4) | core |
| 4 | Who moved, where, and in which direction? | Cluster swings + defection + gender/age (3, 4) | core (+ Tier A) |
| 5 | Did the opposition unite, or did the base erode on its own? | Consolidation at front level + slope (4) | alliance map |
| 6 | Where does the seat flip, where is it safe? | Flip/hold-math + competitive surface (7, 5B.3) | core |
| 7 | If a new/surging entrant matters: whose votes did it take? | Challenger vote-source + topology matrix (4, 4B.3) | triggers only if a >5% new entrant exists |
| 8 | Single biggest threat (winner) / beachhead (loser) next cycle? | Phase 7 + red-team (5C) | core |
| 9 | Do the numbers hold up? | Last-digit + distribution integrity tests (4) | ≥~100 booths |

*Tier 2 — the data-nominated headline (LLM-driven, nobody asks for it).* Phase 5 must surface the single most important non-obvious finding. This is the channel where the data drives, but disciplined: the headline is the finding that is both statistically robust **and** explains the largest share of the actual vote gap (the flip-math tether) — not merely the most surprising. The LLM is free to surface something no one asked about.

*Tier 3 — the operator's question(s) (confirmed, not assumed — at most one or two).* Ask the operator for the one or two things the party actually needs answered (e.g. "why did we lose despite our welfare record?"). Two rules quarantine these so the operator's framing cannot bend the finding:
- **Premise decomposition.** Split every operator question (and every public-commentary claim below) into its embedded factual sub-claims and test each *independently, before* answering the question. "Why did we lose despite welfare?" becomes: (a) did the client lose by more than the baseline predicted? (b) did the welfare-heavy clusters actually move with the client or against? (c) what explains the residual? The operator gets an answer — and if a premise is false, is told the premise is false.
- **Reconciliation / divergence.** State explicitly where the Tier-3 answer and the Tier-2 headline agree and where they contradict. The data cannot be overridden by the operator's framing, but the framing is not silently ignored either. **Lead with the operator's question and answer it first; then, if the data-nominated headline is bigger, say so plainly** (e.g. "you asked about welfare; the larger finding is that the seat moved on a statewide tide plus roll churn").

*Public-commentary presumptions (tested, reported, but not structuring).* Ask what public commentary says about why the result happened. Each claim gets the same premise-decomposition treatment and a CONFIRMED / PARTIAL / REJECTED verdict with the deciding statistic. Report these in a dedicated "what the conventional wisdom got right and wrong" section — overturning a public narrative is itself a finding — but do not let them organise the report.

**0.4 Output selection.**
- Ask which deliverables to produce: the **decision memo** (1–2 pages, for leadership), the **analytical dashboard**, the **long-form narrative ("story")**, or any combination. The memo is recommended as a default in all cases.

**0.5 Propose the directory structure and wait for explicit OK before creating files.**

`TodoWrite` the full phase list now.

---

## Phase 1 — Data ingestion with zero-discrepancy validation

This is the non-negotiable foundation. If validation fails, every downstream finding is suspect. **Do not proceed to Phase 2 until the operator sees "zero discrepancy."**

**1.1 Provenance first.** Compute and record SHA-256 checksums of every source PDF in `provenance/`. Note the ECI/CEO source and retrieval date.

**1.2 Parse** both Form-20 files (and the 2024 LS segment, if provided) into structured tables: one row per polling-station-EVM, columns for PS_no, every candidate's vote count, NOTA, total valid, tendered, rejected, and postal/EVM split where the form separates them.

**1.3 Candidate map.** Build `candidates.py` mapping every candidate name → party → front (per the Phase 0 alliance map) → an internal short code.

**1.4 Re-sum validation (necessary).** Sum each candidate's votes from your parsed file and compare against the printed totals at the bottom of the official Form-20. Match must be exact, candidate-by-candidate, NOTA included, tendered included. Fix the parse before continuing if any row fails. Report the validation diff.

**1.5 Validation that catches what re-sums miss (necessary — the column total can hide compensating errors).**
- **Transposition spot-checks:** if page images are available, manually verify a handful of randomly chosen booths cell-by-cell against the source image. (Two candidates' values swapped in one booth and reversed in another leave column totals intact; only a row-level check finds this.)
- **Component reconciliation:** confirm EVM-total + postal-total = grand total per candidate.
- **Electors→turnout reconciliation:** confirm per-booth that votes polled are consistent with the booth's elector count and reported turnout; flag any booth where polled exceeds electors or turnout is implausible.

**1.6 Data dictionary.** Write `data/DATA_DICTIONARY.md` defining every column, unit, and derivation. Report the validation result to the operator and **stop**.

---

## Phase 2 — Spatial, structural, and comparability mapping

Build the layers on top of the parsed booth data. PS numbers change between elections, so **clusters are the cross-year unit of comparison.**

**2.1 Geographic clusters (~15–25).** Inspect each PS's polling-area street description. Group adjacent stations sharing a neighbourhood character into named clusters (e.g. `C04_Kambar_Nagar`, `C12_Slum_Belt_East`). Map both years to the **same** cluster set. You will not be able to map booth-to-booth across years (renumbering, EVM consolidation, relocation); cluster-level comparison is the rigorous answer. Document the grouping rule.

**2.2 Physical buildings.** Map each PS to its physical building (school/community-centre). Multiple booths often share one building — this enables the within-building natural experiment in Phase 4. If geocodable addresses or building names are available, geocode buildings now and store coordinates for real spatial adjacency (Phase 5B).

**2.3 Demographic tags (toponym-derived — coarse, label them so).** Tag clusters/PSes with any structural label visible from the polling-area description: `slum_huts`, `tnhb_govt_housing`, `tnscb_resettlement`, `police_quarters`, `loco_works`, `muslim_concentrated`, `christian_named`, `incumbent_residence`, etc. Document the rule for each tag. **These are canvassing starting points, not findings** — inferring composition (and especially caste) from street and colony names has a high error rate.

**2.4 Measured demographic layer — Tier A only.** Attach the booth-level gender/age figures to each PS. Keep the composition-vs-turnout distinction from Phase 0 attached to the variable. This is *measured* data and is far better-powered than the toponym tags — it becomes a core analytical layer in Phases 3, 4, and 4B, not an afterthought.

**2.5 Comparability / roll-churn gate (this gates interpretation — do not treat it as a footnote).** A 5-year gap in an Indian urban seat routinely sees 10–20%+ change in the electoral roll from additions, deaths, migration, and roll revisions. For each cluster, compute electors-per-cluster across years and (where street lists allow) street-list overlap. Flag clusters whose roll moved substantially: their "swing" is partly compositional, not persuasion, and any persuasion story for them is suspect. If the AC-wide roll moved >5%, state plainly that "same voter universe across years" is an assumption the data cannot fully defend, and carry that caveat into every cross-year claim.

**2.6 Analysis lock (pre-registration — do this before Phase 3's outcome reveal).** Before looking at any swing or running any test, freeze and commit to git (timestamped): the cluster definitions (2.1) and tag rules (2.3); the mandatory hypothesis list and the primary-vs-exploratory split of the ladder (Phase 4); and the Tier-3 questions plus public-commentary claims (0.3). This is the single best defence against both "you fished for this result" and your own thumb on the scale. The Phase 3 picture and the trigger conditions may still escalate *adaptive/exploratory* hypotheses — but anything surfaced after the lock is logged as exploratory and **cannot be promoted to primary** post hoc.

---

## Phase 3 — First-pass descriptive picture

Before any tests, build the simple picture and show it to the operator — it reveals which hypotheses deserve heavy machinery and which can be dismissed in a paragraph.

- Total votes per party **and per front** per year. Vote swing in absolute and percentage points.
- Turnout change. Register-size change per the Phase 2.5 gate.
- **Baseline overlay (if state/district swing provided):** plot the AC's swing against the state/front baseline. The quantity to explain in later phases is the AC's *deviation from baseline*, not its raw swing — a local swing that merely matches the state tide is not a local story.
- **Three-point trajectory (if 2024 LS provided):** Y1 → 2024 → Y2 share lines per front, at AC and cluster level, to separate secular drift from a Y2 shock.
- Cluster-level vote shares, both years; cluster-level swings sorted worst to mildest.
- **NOTA as its own layer:** NOTA share by cluster, both years. Where NOTA is high is a distinct signal (protest that refused to convert), different from where abstention or switching is high.
- Booth-winner counts per party/front.
- **Tier A:** descriptive cross-tabs of party share against female-elector-share and young-voter-share across booths; if gendered turnout is available, the male/female turnout gap by cluster and its YoY change.

**Stop and show the operator this picture.** Their judgement on "is this the right story?" matters most here and at Phase 5.

---

## Phase 4 — Hypothesis ladder (run all, report all)

For each hypothesis: state the prediction it makes, run the appropriate test, return **CONFIRMED / PARTIAL / REJECTED** with the deciding statistic, **a confidence tier (High/Med/Low), and the one assumption it rests on.** For every REJECTED verdict, also report the minimum effect the test could have detected (the minimum detectable effect, or the relevant CI width), so a true null is never confused with an underpowered one — absence of evidence is not evidence of absence.

**Designate primary vs exploratory up front — per the Phase 2.6 lock, set before outcomes are examined.** The ladder runs ~30 tests; some will clear p<0.05 by chance. Mark the handful of hypotheses you would stake a recommendation on as **primary**; treat everything else as **exploratory / hypothesis-generating**, including anything the Phase 3 picture or a trigger condition surfaced after the lock. A lone p=0.04 among thirty tests does not become a chapter. Apply Bonferroni/Holm within each test family (as already specified for absorption and last-digit), and note family-wise exposure in the synthesis.

### Mandatory (always run)

1. **Swing structure (merged — these are one finding, not two).** Cluster-level WLS regression of incumbent Y2 share on Y1 share, weighted by Y2 valid votes; implement WLS in pure numpy. Report R², slope b, and slope 95% bootstrap CI (B=5000). Note the algebraic identity: since swing = a + (b−1)·share_Y1, a slope b<1 *is* the "incumbency ceiling," and a negative share-vs-swing correlation is the same fact restated — **do not report it as a second, independent confirmation.** The stronghold (≥60% Y1) vs competitive (40–60%) two-sample t-test may be reported as a complementary cut, explicitly flagged as not independent of the slope.

2. **Demographic defection (toponym tags).** For each tag, mean swing in tagged vs non-tagged clusters; report z-score. Treat a tag as a real signal only if its swing is ≥5pp from the constituency average with z>1.96. Remember these tags are coarse.

3. **Mobilisation differential.** Correlation between turnout change and incumbent swing across clusters. Positive = new voters punished the incumbent; negative = demobilisation among loyalists.

4. **Opposition consolidation — at BOTH party and front level.** Regress challenger Y2 share on summed non-incumbent Y1 share. Run it once pooling *parties* and once pooling *fronts* (per the alliance map). R²>0.5 = clean consolidation; R²<0.3 = something other than pooling; escalate to vote-flow (4B). A messy party-level R² that cleans up at front level is itself the finding.

5. **Challenger vote-source (Tier-1 battery question 7, Phase 0.3).** Test whether challenger gains track incumbent losses, prior-opposition collapse, a distinct ideological pool, or turnout expansion, using cluster correlations as the first cut and handing off to 4B.2 for the quantified decomposition. *(The Phase-4 "structural vs anti-incumbency win" decomposition lives once, canonically, in 4B.2 — do not compute it twice.)*

6. **NOTA signal.** Correlate cluster NOTA share (and its YoY change) with incumbent swing and with turnout change. Distinguish protest-NOTA zones from switching zones and abstention zones.

7. **Gender/age ecological association — Tier A only.** Across booths within Y2, regress party share on female-elector-share and on young-voter-share. **This is ecological inference, not measured gendered voting** — Form-20 votes are never broken out by sex, so you are inferring direction from the booth-level correlation and the ecological fallacy applies in full. Because gender/age share correlates with neighbourhood type, control for area (cluster fixed effects or within-cluster examination) so you are not relabelling a slum/middle-class contrast as a gender effect. If gendered *turnout* is available, additionally test whether the male/female turnout gap moved with the swing (a more direct, better-powered claim).

### Adaptive deeper (trigger conditions in brackets)

8. **Bifurcated absorption** [opposition consolidation R²<0.5 AND ≥2 minor Y1 opposition parties with >5% each]. Pearson correlation between each Y1 party's share and each Y2 party's share; Bonferroni over all pairs; surface any corrected p<0.05 as a discrete absorption pipeline.

9. **Within-building variance** [any building ≥4 booths AND ≥3 multi-booth buildings]. ANOVA of booth-level incumbent share by building; report F, η², and top-10 buildings by min-max spread; highlight any >20pp internal spread.

10. **Postal vs EVM divergence** [postal ≥0.5% of valid]. Two-proportion z-test on incumbent postal vs EVM share. |z|>3 is a major diagnostic (state-machinery vs cost-of-living signal).

11. **Spatial autocorrelation** — run the strong version if buildings were geocoded (real adjacency); otherwise run Moran's I on PS-order as a **tentative** proxy and label it so (PS numbering tracks geography only loosely). Complement with a Wald-Wolfowitz runs test on the booth-winner sequence.

12. **Booth archetype clustering** [≥150 booths in Y2]. K-means (k=4) on (incumbent_share, challenger_share, third_party_share, turnout); for Tier A add female-share and young-share. Report archetype profiles and which clusters concentrate each.

13. **Last-digit integrity.** Chi-square on the final-digit distribution of each major candidate's booth count (9 df, crit 16.92 at p=0.05); Bonferroni over candidates; 10,000-draw uniform bootstrap sanity check. **Borderline results are flags, not findings.**

14. **Distribution-shape test.** KS and Levene comparing booth-level incumbent-share distributions across years. KS rejecting + Levene not rejecting = uniform shift; both rejecting = shape change.

### Bespoke (only if explicitly relevant)

15. **Caste-specific defection** — only if the operator provides caste-correlated colony labels; otherwise omit. Treat any result as a canvassing lead, never a finding.
16. **Anti-minority / pro-minority swing** — only if a cluster is ≥40% minority-concentrated by polling-area inspection.
17. **Wedge candidate** — only if a >5% third-place candidate plausibly drew from one side; regress wedge share on incumbent swing.

---

## Phase 4B — Vote-flow inference and coalition topology

The ladder establishes correlations. Phase 4B upgrades them into estimated vote-flow structure, coalition topology, and counterfactual transfer behaviour. **These are ecological-inference approximations, not individual voter tracking.** Every finding must state its ecological assumptions and a confidence tier.

**Method honesty (read before coding).** Do not call something "King's EI" unless you actually run it.
- **Default path (pandas/numpy/scipy/sklearn only):** Goodman's ecological regression **plus** the Duncan–Davis method of bounds. Label them by those names. Goodman regression routinely produces out-of-bounds transition estimates, so always report the deterministic bounds alongside the point estimates and flag any estimate that violates them.
- **Preferred path (only if the operator permits the dependency):** King's EI (2×2) and RxC EI via `PyEI` (which pulls in PyMC). If allowed, name it accurately and report convergence diagnostics.

**Power note.** Cross-year EI on ~20 clusters is badly underpowered — its transition CIs will be wide and possibly uninformative. **Lean the inferential weight on the within-year EI (Tier A, hundreds of stable booths); present cross-year transitions explicitly as wide-interval and illustrative.** In Tier B, cross-year EI is the only flow estimate available — state its limits prominently.

**4B.1 Ecological inference** (mandatory if ≥3 parties/fronts exceed 5%). Estimate retention rates, defection flows, abstention/turnout-loss, and opposition redistribution. Output a `2021 bloc → 2026 destination | estimate | CI` table. Answer: which prior electorate was most stable, which fragmented most, and whether the challenger inherited prior opposition or pulled directly from the incumbent. Distinguish, every time, **correlation vs inferred transition vs proven transfer.**

**4B.2 Vote-source decomposition (canonical home — this absorbs the Phase-4 "structural vs anti-incumbency" question).** Decompose each major Y2 party's total into: retained prior vote, absorbed opposition vote, absorbed incumbent vote, and turnout expansion / unexplained residual. Quantify how much of the result was (a) mechanical consolidation, (b) anti-incumbent switching, (c) turnout-composition change. **If >60% of a party's growth is inherited opposition consolidation, flag the coalition as structurally fragile** — it depends on rivals staying fragmented. A win that is 50%+ category (b) is durable.

**4B.3 Opposition topology matrix.** Build a party-to-party (and front-to-front) substitution matrix from booth correlations + EI + residual overlap. Classify each pair as direct substitutes / partial substitutes / orthogonal electorates / complementary coalition blocs. Output both the correlation matrix and an interpretable coalition map. Identify which parties compete for the same voter, which coexist geographically, and which alliances would be additive vs cannibalistic.

**4B.4 Counterfactual alliance simulations.** Run probabilistic scenarios: strongest two opposition parties combined; challenger without the third-place candidate; incumbent recovery of +3 / +5 / +8 pp. Estimate seat outcome, booth flips, cluster flips, margin sensitivity. Label deterministic vs probabilistic assumptions and give uncertainty bounds.

**4B.5 Entropy and fragmentation.** Effective number of parties (Laakso–Taagepera), Shannon entropy, concentration indices. Interpret whether the seat became more polarised, more fragmented, or more bipolar, and whether the challenger's win depended on fragmentation collapse, coalition convergence, or a broad ideological swing.

---

## Phase 5 — Synthesis with goal-backward check

You now have ~12+ findings. Synthesise into a coherent story, structured around the question architecture from Phase 0.3.
- **Answer the canonical battery (Tier 1).** Give a one-line verdict to each live battery question, each carrying its confidence tier and the deciding statistic.
- Which hypotheses are CONFIRMED, and what mechanism do they collectively describe? Which were REJECTED, and which public-commentary claim does that overturn?
- **Name the data-nominated headline (Tier 2), then stress-test it.** The single most important non-obvious finding — the one that is both statistically robust *and* accounts for the largest share of the actual vote gap. Not the most surprising; the most load-bearing. Before it ships, re-run it under a reasonable alternative clustering and with outlier booths dropped, and report whether it survives both; a headline that moves under either is downgraded. This is what a hostile reviewer attacks first.
- **Answer the operator's question(s) (Tier 3), then reconcile.** Lead with the operator's question, answered through its decomposed premises (Phase 0.3); then state explicitly where that answer agrees with the Tier-2 headline and where it diverges. If the headline is bigger than what was asked, say so plainly rather than burying it.
- Frame the whole synthesis against the **baseline** (Phase 3): how much of what happened was local, versus the seat riding a state/front tide?

**Goal-backward flip-math check.** Does the synthesis explain the actual vote-count gap? Build the flip-math: to reverse the result, how many voters across how many booths must switch? If the flip-math contradicts the story, the story is incomplete — keep going. **Stop and show the operator the synthesis.**

---

## Phase 5B — Residual intelligence and structural exceptions

Once the dominant model is identified, analyse where it breaks.

**5B.1 Residual geography.** Map residuals (from the best-fitting model — the baseline-augmented one if a state/district baseline was provided) at cluster and booth level. Classify strong-positive, strong-negative, structurally-aligned, and anomalous zones. Where did the dominant model fail hardest? Which zones resisted the swing? Which collapsed beyond expectation?

**5B.2 Local spatial outliers.** If buildings were geocoded: Local Moran's I and Getis-Ord Gi* hotspots on real adjacency. If not: **downgrade this section to tentative** and say so rather than presenting a fabricated-adjacency result with full confidence. Interpret whether the political geography is diffuse, corridor-based, enclave-driven, or neighbourhood-clustered.

**5B.3 Competitive surface.** Classify booths as structurally-safe / soft-safe / competitive / hyper-marginal / volatility-prone. Output `Booth | Margin | Flip threshold | Competitiveness class`. Purpose: where small future swings produce disproportionate change.

**5B.4 Swing efficiency.** How efficiently each party converted vote growth into booth wins; whether gains were piled inefficiently; whether losses were geographically distributed. Was the election won by broad persuasion, turnout efficiency, or concentrated vote-piling?

**5B.5 Booth similarity networks (optional, only if interpretable).** Similarity graphs on vote-share / swing / turnout vectors to detect latent political communities. Include only if results are non-chaotic.

---

## Phase 5C — Red team / pre-mortem (mandatory because of who is reading this)

The back half of this report gives the client reasons to act — which is exactly when analysis quietly bends toward what the client wants to hear. Before writing deliverables, argue the *opposite* case in writing:
- If the client is the loser: why the incumbent's win might be **durable**, why the "recovery beachheads" might be mirages, and what cheaper non-data explanations (candidate, roll churn, statewide tide) could account for the result.
- If the client is the winner: why the margin might be **softer than it looks** and which comfort is false.
- For every primary recommendation, state **"what would have to be true for this to be wrong"** and whether the data rules that out.

The disciplined bad news is the most valuable thing in the report. Put a condensed version of this section in front of leadership, not buried.

---

## Phase 6 — Output deliverables

Produce only what the operator selected in Phase 0. Tag **every finding and recommendation with a confidence tier (High/Med/Low) and the one assumption it rests on**, and keep the four-way distinction visible throughout: **observed correlation / ecological inference / causal interpretation / speculative political explanation.** Never present an aggregate booth-level relationship as direct voter testimony.

**6a. `reports/DECISION_MEMO.md` (1–2 pages — the actual decision-maker's document).** For party leadership, not the math-checker. Structure it around the Phase 0.3 question architecture: **open with the answer(s) to the operator's one or two questions (Tier 3)** in plain language, confidence tier each; immediately note any divergence from the data-nominated headline (Tier 2); then give the live canonical-battery verdicts (Tier 1) as the supporting structure beneath, the three recommended actions, and the single biggest risk (from Phase 5C). This is a first-class output, recommended in all runs.

**6b. `reports/FINDINGS.md`.** Rigorous markdown, 15–20 sections tracking the hypothesis ladder. Every claim numbered; every test reported with statistic + p-value + CI + confidence tier. Audience: someone who will check your math.

**6c. `reports/<ac>_dashboard.html` (analytical).** Single-page, Chart.js 4.4.x from CDN. ~8–10 charts: retention scatter, cluster-swing bars, distribution histograms, pipeline scatters, within-building bars, postal-vs-EVM bars, booth-winner ribbon, archetype profiles, NOTA layer, and (Tier A) gender/age association plots; a swing map if geocoded. Dark serif typography, embedded JSON payload under a `__PAYLOAD_PLACEHOLDER__` token so a tiny `build_dashboard.py` assembles it. Audience: an analyst who wants every number.

**6d. `reports/<ac>_story.html` (narrative — only if requested).** Magazine-style long-read, chapters in this arc: the result and what the baseline says about it → the obvious suspects ruled out → the headline finding → chapter-by-chapter through the synthesis → a required digression "do the numbers add up?" (integrity tests) → **the penultimate chapter "What to do about it" (Phase 7)** → closer "what this means for next cycle." Include: an "About the data" panel (Form-20 source, checksums, validation evidence, reproduction steps); orange method sidebars explaining each test in plain language; a "verify our headline number yourself from the public Form-20 with a spreadsheet" panel; inline citations to the literature (Pearson, Fisher, Efron, King, Goodman/Duncan–Davis, Moran, Getis–Ord, Wald–Wolfowitz, Beber & Scacco, Bonferroni/Holm, Kolmogorov–Smirnov, Levene, Fiorina, Laakso–Taagepera) with a `[1]..[N]` reference list; a glossary of every statistical term. Fraunces serif + JetBrains Mono, drop caps, pull quotes, stats strips. Audience: a literate non-statistician.

**6e. Provenance and integrity tooling (always).**
- **Numeric-provenance lint:** `scripts/lint_numbers.py` extracts every number from the prose deliverables and confirms it exists in the JSON payload, failing the build if not. Cheap insurance against a hallucinated figure in a report that may be read adversarially.
- **End-to-end reproduction script** in `provenance/` (raw PDF → all outputs) with pinned package versions, plus the SHA-256 checksums and the data dictionary. In an electoral context, chain-of-custody is part of credibility.

### Writing rules for the narrative
Short sentences mixed with long. No three-element parallels unless load-bearing. Avoid AI-tells ("The implication is striking", "The intellectual move is", "Reverse-engineering the X", "This is the discovery", "It is worth noting that"). Make direct claims — replace "It can be argued that" with the claim. Concrete specifics over abstractions ("voters who walk in through the same school gate" beats "geographically proximate voters"). Contractions are fine. **Never invent numbers** — every figure traces to the JSON payload or a labelled parsed cell, and the lint enforces it.

---

## Phase 7 — What needs to happen next cycle

Forensic findings become actionable only as flip-math, ROI ranking, and targetable populations. Frame everything for the client's actual side (Phase 0.1), tag each recommendation with a confidence tier, and run all blocks.

**7a. Flip-math (loser) / Hold-math (winner).**
- *Loser:* minimum voters to switch to reverse the result, split across clusters by closeness; rank by (voters needed ÷ estimated persuadable population) — lowest ratio = highest ROI.
- *Winner:* the buffer (margin ÷ valid votes); which clusters delivered it and in what fraction; the inverse — how many voters could shift before the seat tips, and which clusters sit closest to the tipping point.
- **Swing elasticity:** pp swing required for each cluster to flip; rank by leverage = (cluster_valid_votes × competitiveness) ÷ swing_needed.

**7b. Persuadables vs mobilisables vs lost causes.** Classify each cluster's marginal voter: **persuadables** (incumbent share 30–50%, mixed tags, high within-building variance — flip with messaging); **mobilisables** (high share but turnout fell YoY — need turnout, not persuasion, cheaper to move); **lost causes** (<25% with low variance — don't spend). Overlay the Phase 5B residual classes (structurally hostile / recoverable protest / coalition-fragile / turnout-sensitive). Tabulate every cluster; report total persuadable vs total mobilisable voter counts; the larger pool sets the primary tactical posture.

**7c. Pipeline-specific counter-strategies.** For each confirmed absorption pipeline (Phase 4.8): identify the pulling proposition; specify a concrete counter-proposition (which 2–3 issues, which messengers, which channels); test feasibility — if the counter contradicts what another pipeline needs, **flag the strategic dilemma** rather than papering over it.

**7d. Defensive map (winner) / Opportunity map (loser).**
- *Winner:* thinnest margins, clusters within 5pp of tipping, fastest-growing surviving-opposition pool — where the seat is lost next time if undefended.
- *Loser:* where the client's share is closest to its floor (the highest non-client share in any cluster) = recovery beachheads; and where the client gained despite the overall loss = scale what worked there.

**7e. Coalition vulnerability map.** From EI and the alliance simulations, classify alliances as additive / cannibalistic / minimally-overlapping. Output `Coalition | Estimated additive gain | Cannibalisation risk | Strategic viability`. Interpret whether the current winning coalition is structurally stable and whether opposition unity meaningfully changes the seat.

**7f. Resource allocation table (the single final output).** `Rank | Cluster | Voters needed | Persuadable/Mobilisable | Pipeline to fight | Primary tactic | Confidence`. Top 10 = next campaign's priorities; bottom 10 = explicit de-prioritisation; the middle = normal field operations.

---

## Cross-cutting rules and caveats (surface these in the deliverables)

- **Confidence and assumptions on everything.** Every finding and recommendation carries High/Med/Low and its load-bearing assumption.
- **Four-way epistemic discipline.** Keep observed correlation, ecological inference, causal interpretation, and speculative political explanation visibly distinct. Aggregate booth relationships are never voter testimony.
- **Adaptive depth.** Clean signal in Phase 4 → expand into a chapter. No signal → dismiss in one paragraph. Insufficient data (e.g. <50 booths, no multi-booth buildings, postal <0.5%, missing enrichment) → **skip the test, don't run it on fumes.** If two hypotheses fight, run a model comparison (likelihood-ratio, Vuong, or LOO-CV R²) and report which fits. If the seat is genuinely boring (one dominant explanation), write a shorter report — don't manufacture findings.
- **Ecological-inference limits.** Booth data does not capture issue-salience. Pipeline labels are statistical associations, not testimony; any counter-proposition needs qualitative validation (focus groups, doorstep) before it becomes the campaign line.
- **Toponym and caste caution.** Demographic targeting from polling-area tags is coarse — it tells you which street to start on, not whom to talk to. Caste inferred from colony names has a high error rate and is a canvassing lead only.
- **Roll-change caveat (Phase 2.5).** If the roll moved >5%, repeat in every cross-year claim that the same-voter-universe assumption is not fully defensible.

---

## Tools and dependencies

Python 3.12 with pandas, numpy, scipy, scikit-learn. **Implement WLS in pure numpy** (no statsmodels). Chart.js 4.4.x from CDN for HTML.

- **Ecological inference:** default to Goodman regression + Duncan–Davis bounds in numpy and **label them as such**. Only if the operator explicitly permits the dependency, use `PyEI`/PyMC for King's EI and RxC — and then name it accurately.
- **Geocoding/mapping (optional):** if geocoding is in scope, a geocoder plus Leaflet/folium for the swing map; otherwise omit and downgrade the spatial chapter.

Keep runtime dependencies minimal and pinned; record versions in the reproduction script.

---

## Process discipline

- `TodoWrite` the phases at start; mark each complete only after the operator has seen the output.
- **Validate before analysing. Analyse before writing prose. Write prose only after the operator has seen the synthesis.**
- Show intermediate outputs at the end of **Phase 3** and **Phase 5** — that is where the operator's judgement on "is this story right?" matters most.
- Run the **Phase 5C red-team** before any deliverable, and the **numeric-provenance lint** before declaring a deliverable done.
- Commit the analysis bundle to git after each completed phase.

---

## Where to start

Acknowledge this prompt. Then ask the operator for everything in **Phase 0** — identity and Y2 result, which side the client is, the input list and resulting **tier**, the composition-vs-turnout nature of any gender/age data, the alliance map, the available baselines and the 2024 LS segment, **the one or two questions the party most needs answered (Tier 3) plus any public-commentary claims to test**, and which deliverables to produce. Confirm which canonical-battery (Tier 1) rows are live. Propose the directory structure and wait for an explicit OK.

**Do not start parsing until the operator has answered.**
