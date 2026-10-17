# 03 · Research brief

Public sources only, accessed 2026-10-17. **UNVERIFIED** marks a claim not confirmed on a primary page. Figures are published orders of magnitude, used for scenario realism; they are not engineering specifications. Defensive scope only: recognise, classify, respond. The data register is in [03-data-register.md](03-data-register.md).

## 1. How drone and counter-drone training is done today

| Who | What they do | Source |
|---|---|---|
| US Joint C-sUAS University, Fort Sill (opened Oct 2023) | Operator, Planner and Installation-Protection courses of 1–3 weeks, ~36 students per class. Students rotate through camera, radar and C2 roles in trailer-based command-post simulations, then a joint exercise against simulated threats. Target drones cost ≥ US$1k each. Curriculum revised about every 6 months. | [WUNC 2023](https://www.wunc.org/military/2023-10-02/school-trains-us-troops-military-fights-small-weaponized-drones), [Soldier Systems 2025](https://soldiersystems.net/2025/09/23/drones-101-welcome-to-dows-joint-counter-small-uas-university/) |
| US Army NTC (CALL, Sep 2025) | Live replication with swarm platforms, FPV and replica jammers. Documented gaps: drone engagements are not integrated with MILES, so scoring is manual, slow and often missed; GPS jamming is banned in training, so trainees distrust soft-kill; soldiers hesitate or wait for guidance. | [army.mil](https://www.army.mil/article/288207/counter_unmanned_aerial_systems_c_uas_training_and_implementation_at_the_national_training_center) |
| NATO C-UAS TIE24 (NL, Sep 2024); BATT25 (Latvia, Aug 2025) | Live interoperability testing of 60+ systems from 19 Allies. BATT25 trained the find-fix-track-target-engage-assess chain under degraded conditions. | [NCIA TIE24](https://www.ncia.nato.int/about-us/newsroom/nato-tests-counter-drone-technology-during-interoperability-exercise), [NCIA BATT25](https://www.ncia.nato.int/newsroom/news/ncia-and-latvia-host-joint-exercise-to-enhance-defence-readiness-against-threats-on-latvian-border) |
| RUSI (UK) | Classification is harder than detection, so fuse emissions, flight profile, silhouette and sound. Use synthetic environments where live use of effectors is impossible. Skills fade fast without practice; airspace rules cap most UK units at ~2 km BVLOS. | [Watling & Bronk 2024](https://static.rusi.org/protecting-the-force-from-uncrewed-uas.pdf), [Brazier 2025](https://www.rusi.org/explore-our-research/publications/commentary/unshackling-training-drones-army) |
| Commercial | ST Engineering AGIL C-UAS sim: instructor/planning, C2, interceptor-pilot and VR jammer-operator stations, plus analytics. VBS4 can model armed UAVs. MASS argues live trials are costly and weather- and range-limited (vendor claim). DroneShield VR trainer: feature details UNVERIFIED. | [ST Engineering](https://www.stengg.com/getmedia/1fb83905-33a1-48ce-98ae-ccc9703235de/AGIL-Counter-Unmanned-Aerial-Systems-Simulation-System.pdf), [Janes](https://www.janes.com/defence-news/news-detail/itec-2024-latest-version-of-bisims-vbs4-to-feature-munition-equipped-uavs), [MASS](https://www.mass.co.uk/bridging-the-gap-why-synthetic-environments-matter-for-c-uas/) |
| India | AADC Gopalpur ran a tri-service Anti-RPAS course (May 2026); no simulator named publicly. Zen Technologies supplied an operational anti-drone system to AADC (2024). Army plan (Sep 2025): 19 drone training centres, ~1,000 training drones, 600 simulators, counter-drone tactics in the curriculum (secondary source). BSF Drone Warfare School, Tekanpur (Sep 2025). | [SSBCrack AADC](https://ssbcrackexams.com/tri-services-anti-rpas-course-concludes-at-army-air-defence-college/), [Mysuru Infra Hub](https://mysuruinfrahub.com/zen-technologies-delivers-advanced-anti-drone-system-to-indian-army-air-defence-college/), [SSBCrack centres](https://ssbcrackexams.com/indian-army-to-establish-19-drone-training-centres-to-enhance-military-capabilities/), [Tribune](https://www.tribuneindia.com/news/india/bsf-steps-up-counter-drone-tactics-along-pakistan-border/) |
| Ukraine lessons (CSIS) | Shahed-type launches rose from ~130 to ~1,100 a week. Decoys mixed into salvos cannot be told apart in public data, which makes this a real classification problem. Recommended defences are layered and low-cost, built on acoustic networks and a common operating picture. | [CSIS Drone Saturation 2025](https://www.csis.org/analysis/drone-saturation-russias-shahed-campaign), [CSIS cost-effectiveness 2025](https://www.csis.org/analysis/calculating-cost-effectiveness-russias-drone-strikes) |

**Implications for us.**
- Train each sensor role on its own, then fused (as JCU does).
- Score automatically, because manual scoring is the documented NTC gap.
- Make soft-kill and jamming effects trainable, which live ranges cannot do.
- Make decoy and clutter discrimination a scored skill.
- Treat rapid content refresh (scenario and threat packs) as a requirement, given the ~6-month curriculum churn.
- India is scaling simulator-based drone training, so a unit-level, zero-licence trainer has a clear user.

## 2. Threat taxonomy and sensor appearance

**Classes.** These use the US DoD UAS groups as a neutral public reference ([Wikipedia summary of JP 3-30](https://en.wikipedia.org/wiki/UAS_groups_of_the_United_States_military), [CRS IF12797](https://www.everycrsreport.com/reports/IF12797.html)):

- Group 1: ≤ 20 lb, < 1,200 ft AGL, < 100 kt.
- Group 2: 21–55 lb, < 3,500 ft, < 250 kt.
- Group 3: < 1,320 lb, < FL180. Group 3–5 speed and altitude cells are UNVERIFIED.

Simulator classes are generic: COTS quadcopter, FPV, fixed-wing one-way/loitering type, swarm/salvo, plus civil clutter (birds, kites, balloons, permitted civil drones). Kinematic envelopes come from the CC0 [UAV Database](https://doi.org/10.18710/L41IGQ) (X01) and survey ranges (small UAS typically ≤ 15 m/s; [Seidaliyeva et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10780901)).

| Sensor | How small drones appear | Key confuser and discriminator | Sources |
|---|---|---|---|
| **Radar** | Small multirotor RCS ≈ −20 to −8 dBsm. Measured ≈ −15 dBsm at 15 GHz and −12 to −10 dBsm at 25 GHz for common COTS types. Low-slow-small targets suffer clutter and false tracks. | Birds ≈ −30 to −19 dBsm overlap, so RCS alone fails. **Micro-Doppler** separates them: rotors give steady, symmetric sidebands; birds give slow, asymmetric wing-beat modulation. | [Ezuma et al. 2019](https://ar5iv.arxiv.org/html/1911.05926), [Seidaliyeva 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10780901), [everythingRF (secondary)](https://www.everythingrf.com/community/how-do-radar-systems-differentiate-drones-from-birds-in-real-world-conditions) |
| **EO/IR** | Johnson-criteria pixel thresholds. With a 320×256, 24° thermal camera a drone reaches detection size (5 px) at ~60 m and recognition size (15 px) at ~20 m. Model apparent size as target size ÷ (range × IFOV). Thermal works at night but needs line of sight. Motor and battery heat contrast figures: UNVERIFIED. | Birds reach the same pixel sizes at ~120 m and ~40 m, so classification at range is genuinely hard. Helicopters and aircraft are the other confusers. | [Svanström et al. 2021](https://arxiv.org/pdf/2111.01888), [Kaleem & Rehmani](https://arxiv.org/pdf/1710.02382) |
| **RF** | Most COTS drones control on 2.4 GHz with video on 5.8 GHz; other bands are 900/433 MHz and 1.2/1.3 GHz; frequency hopping is common (secondary source). | **Autonomous, pre-programmed and fibre-optic drones emit nothing**, so RF-silent threats are mandatory. Wi-Fi and Bluetooth are confusers. | [Seidaliyeva 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10780901), [drone-warfare.com (secondary)](https://drone-warfare.com/counter-uas/rf-detection/) |
| **Acoustic** | Blade-pass frequency = blades × rev/s, plus harmonics; energy 100 Hz–10 kHz. Detection ranges ~50–300 m; a 2026 MEMS array detected to ~60 m. Cheap and needs no line of sight. | Wind and background noise degrade it. Bird wing-beat 5–20 Hz vs drone fundamental 50–400 Hz is UNVERIFIED (secondary only). | [Ghouli 2026, Acta Acustica](https://acta-acustica.edpsciences.org/articles/aacus/full_html/2026/01/aacus250134/aacus250134.html), [Kaleem & Rehmani](https://arxiv.org/pdf/1710.02382) |

Survey anchors: [Taha & Shoufan 2019, IEEE Access](https://api.openalex.org/works/doi:10.1109/ACCESS.2019.2942944) (abstract read only), [Park et al. 2021, IEEE Access](https://doaj.org/article/fca46b3961804b4e97dd7cd0525e925e), and Seidaliyeva 2023 (above). Guvenc et al. 2018 is UNVERIFIED.

**Implications for us.**
- Each sensor model is a probability-of-detection and measurement-noise function of range, aspect, weather and time of day, with a class-confusion matrix per sensor.
- The trainee's job is to fuse imperfect cues. No single sensor should ever be decisive.
- Every number lives in a sensor profile YAML that carries its register ID.

## 3. Swarm behaviour models

| Model | What it gives the simulator | Training lever | Source |
|---|---|---|---|
| Reynolds boids | Separation, alignment, cohesion, plus goal-seeking and obstacle terms | Weights shape tight or loose formations | [Boids](https://en.wikipedia.org/wiki/Boids) |
| Vicsek | Heading alignment with noise η; order-to-disorder transition | One "discipline" knob for difficulty | [Vicsek review](https://arxiv.org/abs/cond-mat/0611743) |
| Olfati-Saber flocking | Leaderless lattice, obstacle avoidance, split and rejoin; tested at 40–150 agents | Realistic splitting around terrain | [Caltech TR](https://authors.library.caltech.edu/records/srjr9-h3r57) |
| Consensus with link loss | Convergence depends on graph connectivity and delays | Models the effect of RF degradation on swarm cohesion (behaviour-level, fictional) | [Olfati-Saber, Fax & Murray 2007](https://murray.cds.caltech.edu/Consensus_and_Cooperation_in_Networked_Multi-Agent_Systems) |
| Leader-follower | Followers hold range and bearing to a leader | A teachable weakness: what changes if the leader is removed | [Desai et al. 2001](https://repository.upenn.edu/meam_papers/243) |
| Stigmergy | Decaying markers drive area search | Probing and reconnaissance behaviour | [Brambilla et al. 2013](https://research.birmingham.ac.uk/en/publications/swarm-robotics-a-review-from-the-swarm-engineering-perspective/) |
| Precedent | Unity counter-swarm serious game; outcome depended on attacker distribution and defender response time | Validates the training concept | [Karadeniz et al. 2023](https://research.itu.edu.tr/en/publications/simulation-of-counter-uav-tactics-against-drone-swarms-a-serious-/) |

**Implications for us.** Use boids as the base, with Vicsek noise for discipline and a choice of leader-follower or leaderless topology. Intent (loiter / probe / saturation), decoy fraction, RF-silent fraction, arrival profile and clutter density become scenario parameters. All of it is behaviour-level kinematics, with no guidance or terminal-attack logic (locked rule 2).

## 4. Decision-tree scoring and ROE-based assessment

- **Doctrine anchors.** Army ATP 3-01.81 (Aug 2023) gives active C-UAS steps as Detect, Identify, Decide, Defeat/Engage, Exploit. Positive ID is "preferred", the aim is to avoid fratricide, and units operate under established ROE ([ATP 3-01.81 via FAS](https://irp.fas.org/doddir/army/atp3-01-81.pdf)). DoD wording is "detect, track, identify, and defeat" ([DOT&E FY2020](https://www.dote.osd.mil/Portals/97/pub/reports/FY2020/army/2020csuas.pdf)). Do not call this a "kill chain"; no source defines it that way.
- **Our tree: Detect → Classify → Assess → Respond.** It maps onto ATP 3-01.81 as Detect, Identify, Decide and Defeat/Engage. The **ROE gate is a hard fail**: engaging without positive ID, or engaging a neutral or friend, fails the threat whatever the other points.
- **Classification metrics.** Use signal-detection theory per session: hit rate, false-alarm rate, d′ = z(H) − z(FA), with a 0.25–0.5 count correction for 0 or 1 rates ([McMaster SDT](https://brain.mcmaster.ca/SDT/dprime.html), [Brown & White 2005](https://link.springer.com/article/10.3758/BF03192712)). The criterion c is a standard SDT result; its exact form is UNVERIFIED here.
- **Timing.** Score in capped bands against a per-scenario standard, so rushing into an ROE breach never pays. No doctrinal timing standard exists publicly (UNVERIFIED); ours are fictional and editable.
- **AAR structure.** Use the four AAR questions: what was supposed to happen, what happened, why, and what to sustain or improve ([ADI guide derived from TC 25-20](https://www.adi.org/downloads/After-Action-Review-Guide.pdf); TC 25-20 itself not fetched, UNVERIFIED). The Army treats the AAR as the primary feedback method for collective training ([DTIC](https://apps.dtic.mil/sti/html/tr/ADA368651/index.html)).
- **Claims discipline.** Claim only Kirkpatrick levels 1–2 (reaction, learning), never behaviour or results ([Training Industry](https://trainingindustry.com/wiki/measurement-and-analytics/the-kirkpatrick-model/)). Frame the design with evidence-centred design: competency → logged evidence → task features ([Mislevy et al. 2003, ETS](https://www.ets.org/research/policy_research_reports/publications/report/2003/hsgs.html); model names UNVERIFIED).

## 5. Adaptive learning for a small-data setting (12–50 learners)

| Method | Data need | Verdict | Source |
|---|---|---|---|
| **Elo per skill** with decaying K = a/(1+bn) | ~10 answers per learner gives skill correlation ~0.8 in simulation; item difficulty needs ≥ 100 learners | **Use** for learner skill. Set scenario difficulty a priori from generator features. | [Pelánek 2016](https://www.fi.muni.cz/~xpelanek/publications/CAE-elo.pdf) |
| **BKT**, 4 parameters, hand-set | Low | **Use** for the "mastered" display only. Parameters and the 0.95 threshold are our heuristics. | [Corbett & Anderson 1994](https://link.springer.com/doi/10.1007/BF01099821) |
| IRT 1PL/2PL | Needs calibration data | Later, if pilot data grows | [Stan guide](https://mc-stan.org/docs/2_29/stan-users-guide/item-response-models.html) |
| PFA | Moderate | Alternative to Elo; not needed | [Pavlik et al. 2009](https://digitalcommons.memphis.edu/facpubs/8350) |
| DKT | ~250k parameters vs ~200 for BKT; extended BKT roughly matches it | **Reject** | [Khajah et al. 2016](https://arxiv.org/pdf/1604.02416) |
| Leitner / SM-2 | None | **Use** for signature flashcard drills | [Leitner](https://en.wikipedia.org/wiki/Leitner_system), [SM-2](https://www-v1.supermemo.com/archives1990-2015/english/ol/sm2) |
| FSRS / half-life regression | Needs review history | Scale-up path only | [Anki FSRS](https://docs.ankiweb.net/faqs/what-spaced-repetition-algorithm), [Settles & Meeder 2016](https://aclanthology.org/P16-1174.pdf) |
| Difficulty target | — | Aim at ~85% predicted success. This is a **heuristic**: Wilson et al. derived it for machine learners, not humans. No source supports a "70–85%" band. | [Wilson et al. 2019](https://ideas.repec.org/a/nat/natcom/v10y2019i1d10.1038_s41467-019-12552-4.html), [Hunicke, Hamlet](https://users.cs.northwestern.edu/~hunicke/pubs/Hamlet.pdf) |

## 6. Procedural scenario generation with solvability and diversity

- **Pipeline:** seeded sample → hard constraints by rejection sampling (Scenic-style `require`) → headless run with an **oracle defender** that follows the ROE tree → accept only if the oracle wins within the time budget → archive. ([Fremont et al., Scenic, PLDI 2019](https://ar5iv.labs.arxiv.org/html/1809.09310); simulation-based evaluation per [Togelius et al. 2011](https://gpbib.cs.ucl.ac.uk/gp-html/Togelius_2011_TCIAIG.html).)
- **Honest wording:** this is a *practical* solvability guarantee, since it covers what the oracle checks. A formal guarantee would need ASP/constraint encoding ([Smith & Mateas 2011](https://course.ccs.neu.edu/cs5150f14/readings/smith_asp4pcg.pdf)). We say "verified solvable by an oracle run", never "provably solvable".
- **Diversity:** a MAP-Elites grid over 2–3 features (for example threat count × ID ambiguity × approach-speed band). Report coverage, QD-score and mean pairwise distance ([Mouret & Clune 2015](https://arxiv.org/abs/1504.04909), [Pugh et al. 2016](https://www.frontiersin.org/articles/10.3389/frobt.2016.00040/pdf)). Show an expressive-range heat map as the demo visual ([Smith & Whitehead 2010](https://www.pcgworkshop.com/archive/smith2010analyzing.pdf)).
- **Anti-rote filter:** reject candidates whose k-nearest-neighbour feature distance to the trainee's own history falls below a threshold ([Lehman & Stanley 2011](https://www.cs.swarthmore.edu/~meeden/cs81/f17/papers/lehman_ecj11.pdf)).
- **Reproducibility:** the seed and generator version are stored in the scenario ID, and the same seed always gives an identical spec (a CI test).

## 7. Open datasets

The full table of 26 entries with licence, size, URL and use is in [03-data-register.md](03-data-register.md). Headlines:

- **Cleanly licensed and usable as raw data:**
  - KTH/SAAB 77 GHz radar of drones, birds and humans ([CC BY 4.0](https://zenodo.org/records/5511912)).
  - UAV spec database ([CC0](https://doi.org/10.18710/L41IGQ)).
  - SRTM ([unrestricted](https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003)).
  - OSM ([ODbL](https://www.openstreetmap.org/copyright), with attribution and share-alike).
  - ERA5 ([CC-BY](https://cds.climate.copernicus.eu/doi/10.24381/cds.adbb2d47)).
  - NOAA GFS/ISD ([open, attribution requested](https://registry.opendata.aws/noaa-isd)).
  - Svanström multi-sensor IR/visible/audio set ([Zenodo, "Other (Open)"](https://zenodo.org/records/5500576); exact wording UNVERIFIED).
- **Research or non-commercial only (calibration only, no redistribution):** Drone-vs-Bird (data usage agreement), FBD-SV-2024, DIAT-µSAT (Indian X-band micro-Doppler, DIAT Pune), DREGON, Anti-UAV, ISRO Bhuvan/NRSC (non-commercial, attribution "Source: NRSC, ISRO/DOS").
- **No data licence stated** (treat as all rights reserved, calibration only): DUT Anti-UAV, MAV-VID, Det-Fly, DroneRF (paper CC BY, data field blank), CardRF, DroneAudioDataset, NYU 60 GHz, MAFAT. Repo code licences (MIT/Apache) do not cover the data.
- **Could not locate:** "Real Doppler RAD-DAR". Dropped unless you have a link.
- **Consequence for the pitch:** say "parameters calibrated from published open research datasets (see data register)". Never say "trained on" a dataset we only read numbers from.

## Not verified (consolidated)

- Guvenc et al. 2018; Taha & Shoufan beyond the abstract; DoD Group 3–5 cells.
- Motor/battery thermal contrast figures; bird wing-beat band; RF detection-range table; long-range acoustic network ranges.
- TC 25-20 primary text; ECD model names; SDT criterion form.
- Hunicke Hamlet venue; FSRS data needs; any "70–85%" band.
- Which simulators AADC Gopalpur uses; Dedrone, MyDefence, Rheinmetall and Saab trainer details.
- Data licences of Anti-UAV, MAV-VID, DroneRF, CardRF, DroneAudioDataset, NYU 60 GHz and MAFAT; the full Bhuvan and GODL-India terms; the current Drone-vs-Bird size.
