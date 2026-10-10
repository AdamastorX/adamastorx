# Slides: the AI development loop, what went wrong, and the gates

Slide text is in English (it matches the diagrams); the speaker notes are in Portuguese. Every claim carries its source
so it can be checked before it is said on stage. Where something is an opinion rather than a measurement, the slide
says so.

**Diagrams used** (in this folder, each with `.mmd`, `.svg`, `.png`): `ai-development-loop`, `problems-timeline`,
`gates-and-guardrails`. The system, event and infrastructure diagrams are in `../architecture/diagrams/`.

**Numbers to recompute right before the talk** (they grow every day):

```bash
for r in adamastorx platform services observability; do
  gh pr list --repo AdamastorX/$r --state merged --limit 2000 --json number -q 'length'; done   # merged PRs, summed
ls docs/adr/[0-9]*.md | wc -l            # ADRs
grep -c -E '^\*\*[0-9]+\. ' docs/roadmap/backlog.md   # backlog items
ls docs/reviews | wc -l                  # staff-level reviews
```

On 2026-10-09 these gave: **536 merged PRs** across the four repos (212 + 219 + 74 + 31), **46 ADRs**, **162 backlog
items**, **7 reviews**, milestones **M0 to M17**, in about **12 weeks** (first commit 2026-07-18).

---

# Part A: how the work flows

## Slide 1 · The loop

**Diagram:** `ai-development-loop`

- The owner sets goals; agents propose; gates and humans decide.
- Three human decisions are in the loop on purpose: **set the direction, review and merge, answer the alert**.
- Nothing merges itself, whoever wrote it.

**Notas:** Mostrar o diagrama de cima para baixo e apontar as três caixas laranja. A ideia a transmitir é que a IA
trabalha no meio, mas o princípio e o fim do ciclo são humanos. *Source:* `.claude/WORKFLOW.md` (Branching & PRs:
"Nothing gets merged by the agent that opened it").

## Slide 2 · Roles: five personas, least privilege

| Persona | Owns | Tools it was given |
|---|---|---|
| `architect` | design calls, ADRs | Read, Grep, Glob, Write (no Edit, no Bash) |
| `platform-engineer` | Terraform, Helm, ArgoCD, CI | Read, Edit, Write, Grep, Glob, Bash |
| `backend-engineer` | Spring Boot, Kafka, Redis, Postgres | same |
| `observability-engineer` | telemetry, dashboards, alerts, SLOs | same |
| `documentation-engineer` | READMEs, ADRs after a merge | no Bash |

- The **main session** reads the issue and routes it **by label** to the persona that owns it.
- A persona is a role *and* a limit: the architect cannot run a command, the documenter cannot either.

**Notas:** O ponto não é "ter vários agentes", é separar contextos e dar a cada um só o poder de que precisa. O
architect não pode mudar código, por isso uma decisão de design tem de passar por um ADR. *Source:*
`.claude/agents/*.md` (frontmatter `tools:`), `.claude/WORKFLOW.md` (Agent delegation).

## Slide 3 · Project management is just GitHub, plus one honest source of truth

- **Issue = backlog item**: Purpose, Acceptance Criteria, Dependencies, Priority, labels.
- **Definition of Ready** (criteria written, dependencies known, one epic) and **Definition of Done** (criteria met,
  docs updated, PR reviewed and merged by the human).
- **Milestones M0 to M17**, "ordered by goal, not a hard gate": an item starts when *its own* dependencies are met.
- **Org-level project board**, five columns: Inbox, Ready, In Progress, Review, Done.
- The real source of truth is `docs/roadmap/backlog.md` (162 items); the board mirrors it.

**Notas:** Dizer que o backlog em Markdown é o que manda, e o quadro do GitHub é um espelho. Isto não foi desenho,
foi o que aprendemos (slide 11). *Source:* `.claude/PROJECT.md` (Definition of Ready/Done), `docs/roadmap/milestones.md`,
`docs/roadmap/project-board.md`, `docs/adr/0042`.

## Slide 4 · Reviews come in layers

1. The **author** is a persona agent; it opens a PR.
2. **Required CI** (slide 12).
3. An **independent review** by a *fresh* agent, never the author, for platform-impacting changes: "a second,
   unbiased read, not a rubber stamp from the same context that already talked itself into the approach".
4. **The owner reviews and merges.**
5. Periodically, a **staff-level review** of the whole system (below).

**Notas:** A citação do passo 3 está literal no `WORKFLOW.md`, e nasceu de uma falha (slide 9): isto não aconteceu nas
alterações de plataforma dos primeiros serviços. *Source:* `.claude/WORKFLOW.md` (Agent delegation).

## Slide 5 · The staff-level review: an independent audit, on a schedule

Seven reviews so far, each a fresh context with a rubric (the owner's four objectives) and a rule: **verify live, do not
assume**.

| Date | What it found |
|---|---|
| 2026-08-06, 08-09 | A strong project; drift between docs and reality; live access added in the second |
| 2026-08-11 | "Never ship a component without its alert" violated for a whole class; the rebuild had no whole-system acceptance criteria |
| 2026-08-15 | The system alerted correctly on a 33-hour incident **nobody answered**: build rate had outrun operate rate |
| 2026-08-21 | Full audit across ten questions: untracked debt, rules that were only prose, Claude Code features unused |
| 2026-10-01 | Audits *how the system is built*: adopt agent loops narrowed, human outer loop "unchanged, and load-bearing" |

- The reviews review themselves: each has a closing section "Review of this review (before merge)".

**Notas:** É aqui que a análise "de staff" se vê: não são sugestões genéricas, são factos medidos no cluster vivo que
viraram itens de backlog e ADRs. *Source:* `docs/reviews/*.md`, `docs/operations/2026-08-11-cycle-1-the-33-hour-incident.md`.

## Slide 6 · Where the human sits

| The human decides | Example from this project |
|---|---|
| Direction and priorities | the four objectives every review is graded against |
| Design trade-offs | the architect writes the ADR, the owner accepts or rejects it |
| What merges | every PR, however small |
| What touches the live system | a mutating `kubectl` needs explicit confirmation |
| Keep or kill | "keep Mimir" (backlog #135), recorded as a decision, not a default |
| The physical world | a network cable and a router reservation (backlog #162) |
| **Answering the alert** | the 33-hour incident |

**Notas:** Isto responde à pergunta "qual é o papel humano": decidir, aceitar responsabilidade e atuar no mundo físico.
*Source:* `.claude/WORKFLOW.md`, `docs/roadmap/backlog.md` (#135, #162).

## Slide 7 · An experiment: bounded agent loops

- A loop ran until a single failing test went green: **one iteration, $0.37**, a diff identical to the human PR.
- Verdict: **adopt, narrowed**, as a technique for Implement/Test, **not** as a working model. Eight preconditions, one
  of them: **no `KUBECONFIG` in the loop's environment**.
- Why narrowed: it converged in one iteration *because the task was already fully specified*. $0.37 is a floor, not an
  estimate.
- And the rule it forced into words: **"The test went green" is never a merge criterion.**

**Notas:** Contar o resultado com honestidade, incluindo a crítica do próprio review: dois agentes a concordar mostra
que o patch é o óbvio, não que é o correto. *Source:* `docs/reviews/2026-10-01-agentic-working-model-assessment.md`
(§1, §2), `docs/runbooks/verified-agentic-loop.md`, `docs/adr/0046`.

---

# Part B: what went wrong, and what it says

## Slide 8 · Even this talk was named as a pressure

- ADR 0046 names the talk itself as a pressure and refuses two shortcuts: merging parked, unreviewed hook PRs to
  complete the story, and enabling the plugins in all four repos so the adoption looks uniform.
- Its own warning: the model is "unusually demo-friendly, which is a reason to be *more* suspicious of it, not less".
- Status is **Proposed**, with a review at five recorded runs or 2026-12-01, whichever comes first.

> *Optional, your call:* what you decided afterwards. The repo records the ADR's refusal; the decision to merge anyway
> is yours to tell or not. It is the clearest example in the project of the human being both the safeguard and the
> pressure.

**Notas:** Slide opcional mas forte para a tese: mesmo com um agente a recusar o atalho, a decisão final e a pressão
são humanas. *Source:* `docs/adr/0046-bounded-verification-loops-and-the-operator-toolchain-rule.md` (the talk as a
named pressure).

## Slide 9 · The agents did not follow the workflow

**Diagram:** `problems-timeline`

Three different causes, and only the last one is about "willpower":

1. **A configuration bug.** 2026-07-18: the persona files were *prose only* and "never ran"; they had no frontmatter, so
   the Agent tool could not invoke them. (Commit `0975d44`.)
2. **Convenience.** 2026-07-19 and 07-24: design calls with rejected alternatives were made *inline* by the driving
   session instead of the architect, and the independent review "didn't happen" for the first platform changes.
3. **Friction.** 2026-08-15 audit: the five personas "were never delegated to through the mechanism"; of 146 board
   cards only **12** had ever had a status set.

**Notas:** Distinguir as causas é a parte interessante: o primeiro era um erro nosso de configuração, não "a IA
desobedeceu". O segundo é o atalho natural. O terceiro é como qualquer equipa humana. *Source:* commits `0975d44`,
`30f50c7`, `b135581`; `docs/adr/0042`.

## Slide 10 · The lesson: friction decides what survives

> "A process survives in proportion to how much friction it takes to skip it, not how well-reasoned it was when
> written down." (ADR 0042)

- `review-before-merge` survived because skipping it has consequences. The board did not, because skipping it costs
  nothing.
- The fix was never "tell the agents harder". It was to **make the right thing the easy thing**: native board
  automation, a hook that enforces the safety rule, CI checks that fail.

**Notas:** Esta é a frase central da parte dos problemas, e é do próprio ADR. *Source:* `docs/adr/0042`.

## Slide 11 · Green is not correct

- 2026-08-10, the cluster rebuild: **every** liveness check passed (35/35 scrape targets up, `cilium status OK`) *and*
  the system was broken in three places. The checks tested components, not the business path.
- This week: an alert that **could never fire** (a `>` between metrics with different labels); it passed review and
  CI and was found only by querying the live Prometheus.
- This week: a Kafka heap that every comment said was "75% of the limit" was 50% of the **host's** RAM; the broker kept
  getting OOM-killed until a `jcmd` showed the real heap.
- "Done" that was not live: a merged change on a manual-sync Application changes nothing until someone syncs it.

**Notas:** Estes exemplos servem a tese: a IA escreve e revê plausivelmente, e os gates passam, mas só medir o
sistema real encontra o erro. Incluir os erros da própria IA (um PR meu que duplicava regras de rede já existentes (#223 vs #201)) mostra que o problema é do processo, não do modelo. *Source:* `docs/reviews/2026-08-11-*` (4b.3),
`docs/SESSION_STATE.md` (2026-10-04 and 10-06 sections), backlog #123, #142, #161.

## Slide 12 · AI amplifies what is already there

| Amplified for the better | Amplified for the worse |
|---|---|
| ADRs, small single-concern PRs | decisions made inline, unreviewed |
| tests written to fail first | a rule that exists only as prose |
| 536 merged PRs in 12 weeks | an alert nobody answers (33 h) |
| docs updated in the same PR | a board nobody maintains, docs that drift |

- Building became cheap. What stayed scarce: **review, decisions, operation, accountability**.
- This is an observation about *this* project (one owner, one system), not a benchmark. There is no human-only
  baseline to compare against.

**Notas:** Marcar claramente que é uma observação de um caso, não uma medição de produtividade. *Source:* the
slides above; `docs/reviews/2026-08-15-*` ("build rate has outrun operate rate").

## Slide 13 · The bottleneck is the human (my view)

- Detection worked; **the response was human**: 189 notifications delivered, zero failures, up to 33 hours to be
  acknowledged.
- The things that blocked progress this week were all human or physical: a merge decision, a router reservation, which
  dependency updates to accept, whether to keep a component.
- Faster agents move the queue to the human; they do not remove it.

**Roles change, people stay (opinion):**
- *Dev:* less typing, more **specifying** (acceptance criteria), **designing gates**, and **reviewing**.
- *Ops:* less running things, more **owning the signal and the response**.
- *New:* someone has to build and maintain the guardrails themselves.
- People remain for accountability, judgment under ambiguity (keep or kill), and the physical and organisational world.

**Notas:** Esta é a tua opinião; apresentá-la como tal. A prova que a sustenta está nos slides 5, 6 e 9. *Source:*
`docs/operations/2026-08-11-cycle-1-the-33-hour-incident.md`.

---

# Part C: quality gates and guardrails

## Slide 14 · What is implemented

**Diagram:** `gates-and-guardrails`

**Before code:** Definition of Ready, ADRs for design calls, least-privilege personas.
**In the session:** a `PreToolUse` hook that blocks mutating `kubectl`/`terraform` without a token; permission rules and
the auto-mode classifier; bounded loops with eight preconditions and no cluster credentials.
**In the PR (required CI):**

| Repo | Checks |
|---|---|
| platform | `terraform` fmt/validate, `kubeconform -strict`, `helm template`, `shellcheck`, resource-limit assertion |
| services | per-service tests, **Trivy CVE scan per image (HIGH/CRITICAL fails)**, JSON-schema event contracts |
| adamastorx | backlog structure and status-marker consistency, docs-vs-live-components drift |
| observability | one alert = one runbook, `promtool` unit tests, `sre-agent` tests |

**At merge:** branch protection (`ci` required, branch up to date), independent agent review for platform changes,
a human merges.
**At deploy:** GitOps only (ArgoCD `selfHeal`), manual sync for risky Applications, image tag = commit SHA,
canary with automated SLO analysis, `ResourceQuota` and `LimitRange` per namespace.
**At runtime:** Cilium NetworkPolicies, hardened pods (non-root, read-only root, no capabilities), alerts with runbooks
and SLOs, Alertmanager to a phone.

**Notas:** Não ler a lista toda; escolher uma por camada e contar uma história (o gate de CVEs do Trivy, o hook que impede um
`kubectl delete` sem confirmação). *Source:* each repo's `.github/workflows/ci.yml`, `.claude/WORKFLOW.md`,
`docs/runbooks/verified-agentic-loop.md`.

## Slide 15 · The gaps (checked on 2026-10-09)

- GitHub requires **0 approvals**: "the human reviews" is a rule, not an enforcement.
- `observability` has **no required status check**, even though its CI exists.
- `enforce_admins` is off in all four repos.
- NetworkPolicies are not on every namespace yet (backlog #126).
- A hook can be defeated by a model that writes the confirmation token itself; it is a speed bump for one operator, not
  a security boundary, and the docs say so.
- A green gate can still mean a wrong system: the answer is business-path checks, not more unit tests (backlog #123).

**Notas:** Mostrar as lacunas faz a talk mais credível do que a lista de gates sozinha. *Source:*
`gh api repos/AdamastorX/<repo>/branches/main/protection`, backlog #126 and #123, `.claude/WORKFLOW.md` (Safety).

## Slide 16 · Takeaways

1. **Make the right thing the easy thing.** Prose rules decay; mechanical ones last.
2. **Gates are not proof.** Verify against the real system, and say what you did not verify.
3. **AI moves the bottleneck, it does not remove it.** Plan for the human who reviews, decides and answers the page.

**Notas:** Fechar com a tese: o trabalho passa a ser desenhar o sistema em que humanos e agentes trabalham.

---

## Honest limits to say out loud

- One owner, one system, twelve weeks. There is no control group and no productivity measurement.
- The loop experiment is one run; the review of it is scheduled for five runs or 2026-12-01.
- Several of the problems above were found by *independent reviews and live measurement*, which is the same human-plus-
  agent loop being described, not something the agents did unprompted.

---

# Part D: demo (screenshots, added 2026-10-10)

Three slides in `slides.html` (before the takeaways), images in `img/`:

- **The infrastructure, on one screen**: Grafana "Infrastructure overview" (CPU/memory/disk gauges, the Wi-Fi link panels, ArgoCD counts).
- **The services: what is running and how loaded**: Grafana "Services overview". This capture groups by namespace; the table has since become one row per workload, so re-capture before presenting.
- **The network: who talks to whom**: Hubble, namespace `api` (API, PostgreSQL, Redis inside; Kafka, Pyroscope, OpenTelemetry collector, Prometheus, Traefik outside).
- **The product: a real ClinVar lookup**: the Clinical Variant Explorer (rs80359550, BRCA2). An unrelated browser tooltip was painted out of the capture.
- **The market pipeline: prices and sentiment**: the market sentiment viewer, captured on a Saturday (flat prices, one tick per window).

