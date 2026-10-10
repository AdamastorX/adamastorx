# Talk outline: building a platform with AI agents

Slides are in `slides.html` (English; arrow keys, `N` for speaker notes, `F` fullscreen). Open it from this folder so the images load. The speaker notes carry the sources. Audience: engineering students, some senior developers and professors.

## Structure (31 slides)

| Part | Slides |
|---|---|
| Opening | cover: project name, title, author (`img/cover.jpg`) |
| A. The lab | a homelab from old hardware; one node per machine, not VMs; the setup (Tailscale, hosts file, ingress); moving to real hardware (**draft: check with the owner**) |
| B. The project | four repositories, one cluster; real workloads to produce real problems |
| C. How I work with AI | the loop; five agents with different powers; planning (issues, backlog, milestones, ADRs); reviews in layers; staff-level review then a new backlog; where I sit; bounded agent loops |
| D. Demo | infrastructure overview; services overview (**re-capture: the table is now per workload**); Hubble, namespace `api`; ClinVar viewer; market sentiment viewer (**re-capture on a weekday**) |
| E. What went wrong | the agents did not follow the workflow; three causes; friction decides what survives; green is not correct; AI amplifies what is there; the bottleneck is the human |
| F. Gates and guardrails | what we have; what they don't cover |
| G. Next steps | a second node and a service mesh; more SLOs, tuned, and an SLO-driven canary |
| Takeaways | three things to take home |
| Close | thank you, contact details |

Diagrams in this folder: `access-setup`, `repos-and-cluster`, `ai-development-loop`, `problems-timeline`, `gates-and-guardrails`. Screenshots in `img/`.

## Numbers to recompute right before the talk

```bash
for r in adamastorx platform services observability; do
  gh pr list --repo AdamastorX/$r --state merged --limit 2000 --json number -q 'length'; done   # merged PRs, summed
ls docs/adr/[0-9]*.md | wc -l            # ADRs
grep -c -E '^\*\*[0-9]+\. ' docs/roadmap/backlog.md   # backlog items
ls docs/reviews | wc -l                  # staff-level reviews
```

On 2026-10-10: about 554 merged pull requests (219 + 225 + 74 + 36), 47 ADRs, 186 backlog items, 8 reviews, milestones M0 to M20, 33 namespaces, 48 ArgoCD applications, in about 12 weeks (first commit 2026-07-18).

## Open points before presenting

- **The talk date** decides what is "next" and what is "done" (the second node, the 28-day SLO window from about 2026-10-31).
- **Review wording** (slide "Reviews come in layers"): GitHub shows no formal review on any merged PR and requires zero approvals; the slide says reviews happen in the terminal and routine changes are sometimes auto-merged on green CI. Confirm this is accurate.
- **The staging of the migration slide** is built from the repository, not from the owner's own account.
- **Image promotion** (code in one repo, image tag in another) is a known cost of the repository split; an ADR is planned after the talk.
- The 33 days the mini PC spent switched off after the cutover were deliberate: never present them as an outage. The 33-hour alert (2026-08-11) is a different, real event.

## Honest limits to say out loud

- One owner, one system, twelve weeks. There is no control group and no productivity measurement.
- The loop experiment is one run; the review of it is scheduled for five runs or 2026-12-01.
- Several problems were found by independent reviews and live measurement, which is the same human-plus-agent loop being described, not something the agents did unprompted.
