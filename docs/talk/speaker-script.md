# Speaker script (rehearsal copy)

Bullets to say aloud, slide by slide. Not to be read: say it in your own words. **Bold** = the sentence to land. `→` = how to hand over to the next slide. Times add up to about 40 minutes without questions; cut Part F first if you run short.

Say honestly, early and again at the end: one owner, one system, twelve weeks, no control group.

---

## Opening

### 1. Title (1 min)
- Introduce yourself in one line: Luís Peixoto, work at FanDuel (Blip); this is a personal project, not a company one.
- I am going to tell you how I built a small platform with AI agents, what worked and what broke.
- One person, four repositories, one small Kubernetes cluster, twelve weeks.
- **This is one project with one owner: an observation, not a benchmark.**
- Every number on the slides has a source in the repository.

---

## Part A. The lab (about 6 min)

### 2. A homelab built from old hardware (2 min)
- Why: I had old hardware, no cloud budget, and I wanted to find where old hardware breaks.
- It started on a 10-year-old ThinkPad running Xubuntu, also my daily machine.
- Two experiments in one: run a real platform (Kubernetes, GitOps, Kafka, PostgreSQL, observability), and find out what AI can really do in building and running it.
- A constraint is a learning tool. Define "cluster" in one sentence first: several machines managed as one computer.
- Evidence I hit the limits: about 30 components, CPU requests at 93% of what Kubernetes could allocate, 5 GiB of swap in use. Those limits drove real decisions.
- → The limits are why I moved to dedicated hardware, but first, how I thought about nodes.

### 3. One node per machine, not virtual machines (2 min)
- Left: the laptop, 2 cores, about 19 GiB. Right: a mini PC, 16 threads, 58 GiB, 1 TB NVMe.
- Plan A was to simulate several nodes with VMs. I measured it: it did not fit.
- I could have run several VMs on the mini PC, but the AI recommended one node per physical machine, and I agree.
- **VMs hide what makes clusters hard**: unequal hardware, a real network between nodes, real failure modes.
- The old laptop comes back later as the second node. **Do not say it is running: it is a next step.**

### 4. My setup: a cluster I can reach from anywhere (2 min)
- Walk the diagram: my machines, Tailscale, the cluster.
- Tailscale gives a private network. I reach the cluster from any machine and nothing is open to the internet.
- One hosts-file entry maps 11 names to the cluster. No DNS server: a real domain costs money and a DNS server is one more thing to operate. The price is manual maintenance, fine for 11 names.
- kubectl, ArgoCD, Grafana, Prometheus and the service UIs are all behind it.
- A new machine needs: Tailscale login, the hosts lines, trust in the internal certificate authority, a kubeconfig.
- Anecdote (optional, 15 s): for a while the host IP was hardcoded and it broke the Cilium install.
- → Then the platform moved to the mini PC.

### 5. Moving to real hardware (1 min) **[draft: rewrite in your words]**
- The platform moved off the laptop to the mini PC.
- Rehearsed first with a restore drill that measured recovery times, then the cutover on 30-31 August.
- **The new host came up from Terraform and ArgoCD, because the configuration lives in git.** Same hostnames, new machine.
- Next: the laptop returns as a second node.

---

## Part B. The project (about 3 min)

### 6. Four repositories, one cluster (2 min)
- Walk the diagram left to right, one job per repository:
  - `adamastorx`: decisions, ADRs, backlog, reviews, agent roles.
  - `platform`: Terraform, Kubernetes manifests, ArgoCD apps, CI, alert rules, dashboards.
  - `services`: 11 applications in Java and Python.
  - `observability`: runbooks, rule tests, telemetry config.
- ArgoCD watches one repository. Code reaches the cluster through an image tag committed in `platform`.
- Today: 33 namespaces, 48 ArgoCD applications.
- Honest cost of the split: the tag is chosen in a different repo from the code. It left a deployment degraded. Automating that is planned after the talk.
- **The applications are a vehicle: they exist to generate traffic and real distributed-systems problems.**

### 7. Real workloads to produce real problems (1 min)
- ClinVar: an API looks up genetic variants and caches answers. A Python service ingests public ClinVar data and tells the cache what changed.
- Market data: live trades and news into Kafka, sentiment scored, joined with prices per ticker, shown in a viewer.
- Stack, in three groups only: infrastructure (k3s, Cilium, ArgoCD, Rollouts), data (Kafka, PostgreSQL, Redis), observability (Prometheus, Grafana, Loki, Tempo, Pyroscope, OpenTelemetry).
- **The product is irrelevant.** I want Kafka, caches and databases doing real work so I can observe what goes wrong. Product maturity is not a priority.
- → Now the main topic: how I work with AI.

---

## Part C. How I work with AI (about 12 min)

### 8. The loop (2 min)
- Walk top to bottom. Point at the three orange boxes: I set the direction, I review and merge, I answer the alert.
- Agents work in the middle.
- The loop closes: a review creates backlog, backlog creates work.
- → Who are the agents?

### 9. Roles: five agents with different powers (2 min)
- Architect, platform, backend, observability, documentation engineers.
- **The point is not many agents: it is separating contexts and giving each only the power it needs.**
- The architect cannot edit code or run a shell, so a design decision has to land as an ADR.
- The documentation agent has no shell.
- The main session routes each task by label. The independent reviewer is a fresh agent with a rubric, not one of the five.
- Be ready for "do they really use these roles?": at the start, no. I come back to it in Part E.

### 10. Planning (2 min)
- GitHub issues and the project board track work; `backlog.md` with 186 items is the written source of truth.
- Not Jira.
- Milestones M0 to M20, each item with acceptance criteria and dependencies.
- Definition of Ready, and Done means merged **and verified live**.
- 47 ADRs: every non-trivial decision is written, including reversed ones.

### 11. Reviews come in layers (2 min)
- Agent authors and opens a PR. CI gates run. An independent agent reviews platform-impacting changes, never the author.
- I review. For routine changes with green CI I sometimes let an agent review and merge, to save my time. **[confirm the proportion and wording]**
- Periodically a staff-level review of the whole system.
- Honest detail: the review happens in the terminal, not as GitHub review objects, and GitHub requires zero approvals. I come back to that in the gaps slide.
- The independent review was added after it was skipped on the first platform changes.

### 12. Staff-level review, then a new backlog (2 min)
- Go down the table, not every row: pick three.
  - 11 Aug: "never ship a component without its alert" was violated for a whole class.
  - 15 Aug: a 33-hour alert nobody answered. **Build rate had outrun operate rate.**
  - 9 Oct: a deployment left degraded by a merge-order gap; nothing would page if the cluster went dark.
- The latest review was led by a stronger model that delegated evidence gathering to cheaper ones.
- Each review ends in backlog items, and the loop restarts. Eight reviews so far.
- After the last one I added a milestone on top of its plan (SLO dashboards). The human decides priority.
- **Never say "month-long outage".** The 33 days off were me switching the machine off on purpose. The 33-hour alert is a different, real event.

### 13. Where I sit in the loop (1 min)
- Direction and priorities; design trade-offs; what merges; what touches the live system; keep or kill; noticing it is wrong.
- Pick the example that is the best story: the first SLO dashboard showed no SLOs. I saw it, the agent had not.
- **The human role is deciding, accepting accountability, and noticing when something plausible is wrong.**

### 14. An experiment: bounded agent loops (1 min)
- One iteration to green, $0.37, a diff identical to the human PR.
- Eight preconditions; one of them: no cluster credentials in the loop.
- Verdict: adopt, narrowed. A technique, not a working model.
- It converged in one step because the task was fully specified.
- **"The test went green" is never a merge criterion.** Two agents agreeing shows the patch is the obvious one, not that it is correct.

---

## Part D. Demo (about 7 min)

Tip: if the live system is reachable, flip to Grafana after slide 15 and back. Otherwise the screenshots are enough.

### 15. The infrastructure, on one screen (1.5 min)
- One mini PC: CPU 7%, memory 20%, disk 20%, 51 pods.
- The Wi-Fi link is on the dashboard: throughput and carrier drops. The cluster runs on a USB Wi-Fi dongle, so link drops are a first-class signal.
- GitOps state: apps synced and healthy; the amber tiles are real (one app degraded, one manual-sync app out of sync on purpose).

### 16. The services (1.5 min) **[re-capture before presenting]**
- What is running and how loaded.
- Memory against limits: Kafka is the biggest; Prometheus near its limit is the one to watch.
- Requests and p95 latency per service underneath.
- Traffic is deliberately low: the applications exist to generate load and failure modes.

### 17. The network: who talks to whom (1.5 min)
- Hubble shows one namespace at a time.
- Inside `api`: the API, its PostgreSQL, its Redis. Outside: Kafka, Pyroscope, the collector, Prometheus, Traefik.
- **A namespace is a home, not a service.** The map shows traffic, not ownership.
- Cilium and Hubble use eBPF; network policies decide what is allowed.

### 18. The product: a real ClinVar lookup (1.5 min)
- Real data, nothing mocked: a ClinVar release ingested by `clinvar-service`, served through `api`.
- Answer: rs80359550, BRCA2, pathogenic, reviewed by expert panel, with the release that produced it.
- Behind one click: browser, API, cache, ClinVar service, database.
- When a newer release is ingested, an event tells the API which cache keys to delete.

### 19. The market pipeline (1.5 min) **[re-capture on a weekday]**
- Two streams joined: trades and news sentiment, per ticker, in 15-minute windows.
- Honest empty state: one tick, +0.00%, because it was captured on a Saturday with the market closed.
- Sentiment is scored from news in the same window.
- → The demo looks smooth. Now what went wrong.

---

## Part E. What went wrong (about 8 min)

### 20. The agents did not follow the workflow (1 min)
- Walk the timeline; do not read it.
- Set up the next slide: there were three different causes.

### 21. Three different causes (1.5 min)
- **Configuration bug (18 Jul):** the agent files were prose with no frontmatter, so the tool could not invoke them. Our error, not the AI disobeying.
- **Convenience (19-24 Jul):** design calls made inline instead of by the architect; independent review skipped on the first platform changes. The natural shortcut.
- **Friction (15 Aug):** agents were never delegated to through the mechanism; of 146 board cards, 12 ever had a status. This is how any human team behaves.

### 22. The lesson: friction decides what survives (1.5 min)
- **A process survives in proportion to how much friction it takes to skip it, not how well-reasoned it was when written.**
- Review before merge survived because skipping it has consequences. The board did not, because skipping it cost nothing.
- The fix was never "tell the agents harder". It was: **make the right thing the easy thing.**

### 23. Green is not correct (2 min)
- Pick two stories, not four:
  - An alert that could never fire (comparing metrics with different labels). It passed review and CI; a live query found it.
  - A dashboard with no SLOs. An SLO is an indicator, an objective and a window. The first version showed only the indicator. I noticed, the agent had not.
- If time: heap sized from the host RAM instead of the container limit; liveness checks all green with the business path broken.
- **The AI writes and reviews plausibly and the gates pass; only measuring the real system finds the error.** Include the agent's mistakes: the weak spot is the process, not one model.

### 24. AI amplifies what is already there (1 min)
- For the better: ADRs, small single-concern PRs, tests first, docs in the same change, over 550 merged PRs in 12 weeks.
- For the worse: inline decisions, rules that exist only as prose, an alert nobody answers, a board nobody maintains.
- **Building got cheap. What stayed scarce: review, decisions, operation, accountability.**
- Repeat: one project, one owner, no baseline.

### 25. The bottleneck is the human (1 min) **[say it is opinion]**
- Detection worked: 189 notifications delivered, zero failures. The response was human, up to 33 hours later.
- What blocked progress was human: a merge decision, which updates to accept, whether to keep a component.
- **Faster agents move the queue to the human; they do not remove it.**
- Roles change, people stay: developers type less and specify, design gates, review; operations own the signal and the response; new role: whoever builds the guardrails.

---

## Part F. Gates and guardrails (about 3 min; cut first if short)

### 26. What we actually have (1.5 min)
- Do not read the list. Walk the layers (before code, session, PR, merge, deploy, runtime) and tell one story each at most:
  - CI: the security scan per image.
  - Session: a hook that stops a destructive `kubectl` without confirmation.
  - Deploy: canary with automated SLO analysis.

### 27. What the gates don't cover (1.5 min)
- GitHub requires zero approvals in all four repos: "the human reviews" is a rule, not an enforcement.
- `observability` has no required status check; admin enforcement is off.
- Network policies are not on every namespace yet.
- The uplink is a USB Wi-Fi dongle: the weak link of the whole system. I decided to keep it, so the work is making the control plane tolerate it.
- **A green gate can still mean a wrong system.** The answer is checks on the business path.
- Showing gaps makes the talk more credible than the list alone.

---

## Part G. Next steps (about 3 min)

### 28. More nodes, and a mesh (1.5 min)
- Second node: the old laptop returns as a worker. Unequal machines: stateless services on the small one, heavy components on the big one. It opens experiments one node cannot do: node loss, draining, replicated storage.
- Mesh (Istio): chaos experiments showed API threads hanging 30 to 60 seconds when Kafka or PostgreSQL went down. A mesh gives one place for timeouts and circuit breakers for Java and Python alike, plus encrypted authenticated calls.
- Cilium keeps owning network policy; running both is part of what I want to learn.
- **Do not give dates, and do not mention that the mesh is deferred.**

### 29. More SLOs, tuned, and a canary that reads them (1.5 min)
- More SLOs: turn the declared-but-unmeasurable ones into measured ones (variant lookup, ClinVar freshness, workers).
- Fine-tune objectives against a 28-day window, available from the end of October. **[depends on the talk date]**
- Today the canary checks error rate and latency before a new version takes all traffic, and it is proven in both directions. Next, gate it on the error budget.
- Be precise: its thresholds are alert trip-points, not the new objectives.
- **The point of an SLO is a decision: deploy, hold or roll back.**

---

## Close

### 30. Three things to take home (1 min)
- **Make the right thing the easy thing.** Prose rules decay; mechanical ones last.
- **Gates are not proof.** Verify against the real system, and say what you did not verify.
- **AI moves the bottleneck, it doesn't remove it.** Plan for the human who reviews, decides and answers the page.
- Close with the thesis: the work becomes designing the system in which humans and agents work together.
- Repeat the caveat: one owner, one system, twelve weeks, no control group.
- Questions.

### 31. Thank you
- Thank the audience; leave this slide up during questions.
- Name, email (lmpeixoto@gmail.com), FanDuel (Blip), blog (lmpeixoto.com).

---

## Likely questions (short answers)

- **Would this work for a team?** Unknown. One owner; the roles and gates are what I would try first, the evidence is not there yet.
- **How much did it cost?** I only have the number for the bounded-loop run ($0.37). I have no total; do not guess.
- **Was it faster than doing it alone?** No baseline, so I cannot say. Building was cheaper; review and operation were not.
- **Why not cloud?** No budget, and I wanted to find the hardware limits.
- **Why keep the Wi-Fi dongle?** A decision: it is the weak link and a useful constraint. The work is making the control plane tolerate it.
- **Why a mesh and Cilium?** Cilium for network policy and visibility; the mesh for timeouts, retries and mTLS. Overlap is something I want to learn about.
- **Do the agents really use the roles?** Now yes; at first no (slides 20-22).

## Before presenting

- Fix the talk date and adjust slides 28-29.
- Confirm slide 5 (migration) and slide 11 (review wording).
- Re-capture slides 16 and 19.
- Recompute the numbers (command in `slides-ai-development-loop.md`).
- Rehearse out loud once with a timer; target 40 minutes plus questions.
