/**
 * Sample scenario texts for the mock backend and the mock specs. Strings only, so a Playwright
 * spec can import them without pulling in the app (no import.meta.env here).
 */

export const SAMPLE_ID = 'marlin-hill-evening-picket'

export const SAMPLE_YAML = `contract: scenario.v1
id: ${SAMPLE_ID}
version: 1.0.0
title:
  en: "Marlin Hill: evening picket"
  hi: "मार्लिन हिल: शाम की चौकी"
summary:
  en: Two small rotary contacts close on the depot from the west while a bird flock works the north fields and a civil survey flight is filed to the south.
  hi: दो छोटे रोटरी संपर्क पश्चिम से डिपो की ओर आते हैं, जबकि उत्तर के खेतों में पक्षियों का झुंड है और दक्षिण में एक नागरिक सर्वे उड़ान दर्ज है।
fictional: true
default_seed: 260311
duration_s: 360
world:
  terrain: {kind: pack, id: heron-ridge, version: 1.0.0}
  half_extent_m: 2000
  start_time_of_day_h: 17.5
  weather: {condition: haze, visibility_m: 6200, wind_speed_mps: 4.1, wind_from_deg: 270, gust_sigma_mps: 0.8, temperature_c: 27, cloud_cover_pct: 40}
rule_pack: {id: training-baseline, version: 1.0.0}
zones:
  - {id: inner, role: inner, label: {en: Inner zone, hi: आंतरिक क्षेत्र}, center: {x: 0, y: 0, z: 34.5}, radius_m: 500}
  - {id: outer, role: outer, label: {en: Outer zone, hi: बाहरी क्षेत्र}, center: {x: 0, y: 0, z: 34.5}, radius_m: 1500}
assets:
  - {id: marlin-hill-depot, label: {en: Marlin Hill depot, hi: मार्लिन हिल डिपो}, position: {x: 0, y: 0, z: 34.5}}
sensors:
  - {id: radar-1, profile: {id: radar-generic-s, version: 0.2.0}, position: {x: -60, y: 40, z: 40.1}, boresight_deg: 0}
  - {id: eo-1, profile: {id: eo-generic-day, version: 0.1.0}, position: {x: -55, y: 45, z: 42.1}, boresight_deg: 270}
  - {id: rf-1, profile: {id: rf-generic-passive, version: 1.0.0}, position: {x: 70, y: -30, z: 37.4}, boresight_deg: 0}
groups:
  - id: grp-pair
    members: [th-quad-a, th-quad-b]
    kind: swarm
    topology: leader-follower
    leader: th-quad-a
    link_range_m: 140
    spacing_m: 40
    route:
      - {position: {x: -1500, y: 140, z: 90}, speed_mps: 13}
      - {position: {x: -420, y: 40, z: 70}, speed_mps: 11}
threats:
  - id: th-quad-a
    label: {en: Contact quad A, hi: संपर्क क्वाड A}
    class_id: autonomous-small
    disposition: hostile
    spawn_s: 46
    start: {x: -1500, y: 140, z: 90}
    start_heading_deg: 90
    start_speed_mps: 12
    on_route_end: loiter
    limits: {max_speed_mps: 18, max_accel_mps2: 4, max_turn_rate_dps: 90, max_climb_mps: 5, max_descent_mps: 5, min_altitude_m: 10, max_altitude_m: 120}
    route:
      - {position: {x: -1500, y: 140, z: 90}, speed_mps: 13}
      - {position: {x: -420, y: 40, z: 70}, speed_mps: 11}
  - id: th-quad-b
    label: {en: Contact quad B, hi: संपर्क क्वाड B}
    class_id: autonomous-small
    disposition: hostile
    spawn_s: 52
    start: {x: -1540, y: 100, z: 88}
    start_heading_deg: 90
    start_speed_mps: 12
    on_route_end: loiter
    limits: {max_speed_mps: 18, max_accel_mps2: 4, max_turn_rate_dps: 90, max_climb_mps: 5, max_descent_mps: 5, min_altitude_m: 10, max_altitude_m: 120}
    route:
      - {position: {x: -1540, y: 100, z: 88}, speed_mps: 13}
      - {position: {x: -460, y: 0, z: 70}, speed_mps: 11}
  - id: th-flock
    label: {en: Contact flock, hi: संपर्क झुंड}
    class_id: bird
    disposition: clutter
    spawn_s: 0
    start: {x: 300, y: 1100, z: 60}
    start_heading_deg: 200
    start_speed_mps: 9
    on_route_end: loop
    limits: {max_speed_mps: 14, max_accel_mps2: 6, max_turn_rate_dps: 120, max_climb_mps: 4, max_descent_mps: 6, min_altitude_m: 15, max_altitude_m: 150}
    route:
      - {position: {x: 300, y: 1100, z: 60}, speed_mps: 9}
      - {position: {x: 700, y: 900, z: 70}, speed_mps: 9}
  - id: th-survey
    label: {en: Contact survey, hi: संपर्क सर्वे}
    class_id: civil-drone
    disposition: civil-permitted
    spawn_s: 24
    start: {x: 100, y: -1300, z: 80}
    start_heading_deg: 0
    start_speed_mps: 8
    on_route_end: despawn
    limits: {max_speed_mps: 15, max_accel_mps2: 3, max_turn_rate_dps: 60, max_climb_mps: 4, max_descent_mps: 4, min_altitude_m: 20, max_altitude_m: 110}
    route:
      - {position: {x: 100, y: -1300, z: 80}, speed_mps: 8}
      - {position: {x: -200, y: -900, z: 80}, speed_mps: 8}
`

/** The sample with two errors the contract reports, each on its own line. */
export const SAMPLE_YAML_ERRORS = SAMPLE_YAML.replace(
  'duration_s: 360',
  'duration_s: soon',
).replace('  - id: th-quad-b\n', '\t- id: th-quad-b\n')

/** The sample with a threat timed before the reaction window and a group link too short. */
export const SAMPLE_YAML_LINT = SAMPLE_YAML.replace('spawn_s: 46', 'spawn_s: 12').replace(
  'link_range_m: 140',
  'link_range_m: 30',
)
