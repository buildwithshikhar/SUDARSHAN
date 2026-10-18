"""Live training sessions: the server transport for a trainee playing a scenario (wave 5).

`catalog` finds the playable scenarios, `wire` builds and checks the protocol messages, and
`manager` runs the sessions. The protocol is `docs/LIVE_SESSION.md`; the typed messages are in
`app.contracts.live`.
"""
