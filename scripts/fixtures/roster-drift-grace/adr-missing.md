# Fixture: no component name, no reason

Deliberately does not name the synthetic fixture component under test,
and states no exemption for it either. Proves check-roster-drift.sh
fails a past-grace-period component with no SLO-table row and no
exemption (backlog #109).
