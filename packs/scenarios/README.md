# scenarios

Scenario packs: scripted and generated scenario specifications.

Everything in this directory is fictional / uses open-source parameters. Nothing here represents a real site, system or operational figure.

## Files

`*.v1.json` and `*.v1.yaml` are `scenario.v1` documents (the YAML form is what the scenario editor reads and writes; see [docs/SCENARIO_ENGINE.md](../../docs/SCENARIO_ENGINE.md)). The session catalogue plays every file here that loads.

## Curriculum

Twelve scripted scenarios, in the order `meta.curriculum_order` gives, each adding one idea to the one before. Each is "verified solvable by test run": a test runs the oracle defender (a perfect-policy test agent on the same sim core) on every one and requires it to clear every hostile contact at 80% or better. That is a practical check of what the oracle exercises, not a proof, and says nothing about how hard a scenario is for a person. Sites and names are fictional; the Hindi text is unreviewed.

| Order | File | Terrain | Adds |
|---|---|---|---|
| 1 | `curriculum-01-first-contact` | Heron Ridge (rural) | day, clear, one drone |
| 2 | `curriculum-02-town-traffic` | Osprey Town (urban) | a filed civil flight and birds among the traffic |
| 3 | `curriculum-03-dusk-watch` | Heron Ridge | falling light, a thermal imager |
| 4 | `curriculum-04-night-watch` | Heron Ridge | night: night-vision and thermal sensors |
| 5 | `curriculum-05-silent-approach` | Osprey Town | a radio-silent drone |
| 6 | `curriculum-06-sensor-outage` | Heron Ridge | a radar outage and haze |
| 7 | `curriculum-07-blind-sector` | Osprey Town | a radar blind sector and radio interference |
| 8 | `curriculum-08-small-swarm` | Heron Ridge | a seven-drone leader-follower swarm |
| 9 | `curriculum-09-decoy-swarm` | Osprey Town | a night swarm with decoys among its members |
| 10 | `curriculum-10-fast-mover` | Heron Ridge | a fast first-person-view class drone and a bird flock, at dawn |
| 11 | `curriculum-11-fixed-wing-clutter` | Osprey Town | a medium fixed-wing drone, a kite and a balloon |
| 12 | `curriculum-12-night-swarm-capstone` | Heron Ridge | a night swarm with a decoy and a radio-silent member, a thermal outage and a civil flight |

No route comes closer than a stand-off to the defended place, and threat behaviour is kinematics only (locked rule 2).
