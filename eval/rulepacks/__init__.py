"""Rule packs: one versioned, hashed bundle of reading rules and guards per evidence type.

A pack is drafted (by a person or an AI session), then tested by the trap harness, then
signed. A pack never decides a verdict: core/audit/rules.py does, on the check results the
pack's checks and guards produce. See README.md and baker/plans/rule-drafting.md.
"""
