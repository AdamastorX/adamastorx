# My AI reviewer wasn't wrong. My process was.

*A real, dated case study of what happened when an independent AI review
collided with a decision I'd already made — and what that near-miss
exposed about the rest of my engineering process.*

## The recommendation

Today, I asked an AI agent to run an independent, staff-level audit of
AdamastorX.

AdamastorX is the distributed system [I described building in my last
post](https://lmpeixoto.com/posts/building-adamastorx/) — one laptop,
with AI writing most of the code while I stay responsible for the
architecture, the decisions, and what happens when things break.

One of the questions I gave the reviewer was simple: is the technology
stack still earning its keep, or has it grown faster than the value it
produces?

It came back with a specific, well-evidenced answer.

Two components stood out: Beyla, an eBPF auto-instrumentation agent
running as an A/B experiment against my hand-built OpenTelemetry stack,
and Mimir, a long-term metrics store I'd deployed to see whether it was
worth the operational cost on a single-node cluster.

The numbers were real and checkable.

Beyla was using **823 MiB** of resident memory — the heaviest idle tenant
on the node after Prometheus and Kafka — while producing data that
nothing was actually consuming. No dashboard. No alert. No runbook.

Mimir was using **734 MiB**, had restarted **30 times**, and its own
architecture decision record already contained the verdict:

"Not yet worth it as a standing piece of this cluster's architecture at
its real current scale."

The recommendation was specific and two-part: extract the data that the
Beyla comparison was worth, then decommission it. For Mimir, stop
investing further and wind it down.

Nothing in that analysis was wrong.

That's what makes this interesting.

## The six-day-old decision it didn't know about

Six days before this review, a different independent review of the same
project had reached almost exactly the same conclusion.

Decommission Mimir and Beyla. Reclaim roughly **200m CPU** and **1.2
GiB** of memory on a node that was already under real, measured
pressure.

I'd read that review.

And I'd said no.

Not because the reviewer was wrong about the cost. The cost was real
then too.

I said no because I hadn't finished the experiment.

I had deliberately deployed these technologies to run them, break them,
and learn what operating them actually looked like. Removing them at
that point would have made the infrastructure lighter, but it would also
have ended part of the experiment before I had learned what I wanted to
learn.

I'd even written the decision down.

In the project backlog, dated and attached to the relevant item, my
answer was:

"Don't remove Mimir. Don't touch Beyla either. I want to keep testing
these technologies."

Six days later, another independent reviewer arrived at the same
recommendation. It had no memory of the first review or my response to
it. Nothing in the review process forced it to look for that particular
decision before making its recommendation.

And that was the near-miss.

The review's technical analysis was sound, though — both numbers were real, and so was Mimir's own "not yet worth it" verdict. Removing both would have been the correct answer to the question the review was actually asked. It just wasn't the only question I was answering, and the difference lived in my head and one line of backlog prose, not in the evidence the review actually read.

## So I audited the process itself

The Beyla/Mimir collision was resolved cleanly. But it left me with a
question: if a careful, independent review agent could walk past a
decision I'd explicitly written down, what else in this project was only
documented rather than actually happening?

So I changed the scope of the audit. This time, I wasn't asking it to
review the technology stack. I asked it to review my process.

Early in the project, I'd written a fairly deliberate engineering
workflow — five AI personas with scoped responsibilities, a shared
cross-repository project board with defined columns and rules, even an
explicit line saying a solo session driving the work didn't get an
exception from opening a PR and waiting for review.

It all looked very sensible on paper. I hadn't checked whether I was
actually following any of it for about a month.

The audit found something uncomfortable: two of the three main pieces
mostly weren't being used at all. And I was the person who was supposed
to notice.

## The personas never got staffed

`.claude/WORKFLOW.md` is explicit:

"Design decisions with rejected alternatives worth remembering (per
docs/adr/README.md) go through the architect agent — the session driving
the issue does not make those calls inline, even when it has an
opinion."

There are five real agent definitions under `.claude/agents/`:
`architect`, `platform-engineer`, `backend-engineer`,
`observability-engineer`, `documentation-engineer`. Each has scoped
responsibilities.

The architect is deliberately restricted from writing production code —
it can read the codebase and write an architecture decision record, but
it can't modify a Kubernetes manifest. That's intentional. The idea is to
separate the architectural decision from its implementation.

There are now **41 architecture decisions** in the project. As far as
the audit could find, **not one** had actually been delegated through
that mechanism. Every ADR had been written directly by the session that
was already doing the implementation work — exactly what the workflow
said not to do.

The other four roles had the same problem. They existed. They were well
defined. They had never really been used.

The process wasn't broken because the files were badly designed. It was
broken because there was an easier path: I could just make the decision
and keep moving. So I did.

## The project board quietly died

The shared project board was another example, and this one was easier to
measure.

There are **146 cards** across the four repositories. Only **12** have
ever had a status. Those 12 all belong to the initial bootstrap period:
creating the repositories, provisioning the cluster, setting up CI and
similar work.

The other **134 cards** — effectively the project's entire real life
after the initial setup — have no status at all. They aren't stuck in
"Inbox." They were simply never updated.

At some point, `docs/roadmap/backlog.md` had quietly become the real
source of truth. The board didn't get replaced. It just stopped being
used. Two systems ended up tracking roughly the same work — one was
maintained, one wasn't — and nobody consciously decided to retire the
board. I didn't even notice the transition happening.

I think that's what happens by default when the fastest path is "just do
the thing," and nothing in the moment forces the slower, more deliberate
path described in the documentation.

## The documentation kept saying things that weren't true

Not every drift in this project was about a component nobody delegated to. Some of it was more basic: tickets and architecture docs stating things that had already stopped being real, caught only when a staff-level review actually re-read them against the live system instead of trusting the prose.

`docs/architecture/overview.md` is the clearest case. A staff-level review in early August found it still claiming M13's five services "do not exist yet" — all five had been merged, deployed, and live for two days by then. That wasn't the first time either: the same file had drifted the same way twice before, both supposedly fixed. Three recurrences of the identical drift, on the same file, is not bad luck.

The same review found the backlog itself — this project's most carefully maintained document — carrying one item duplicated verbatim, both copies marked Done; a bad edit an hour earlier had re-emitted the whole block. Its own second pass, re-checking the first rather than trusting it, found something worse sitting right next to it: a different item's heading didn't exist at all, swallowed into the tail of its neighbor's text, invisible until someone went looking specifically.

A quieter version of the same failure recurs across nearly every staff review since. Work that was actually finished sat in the backlog marked as if it never happened — two items fixed weeks earlier, only marked Done when a later sweep found them; a whole CI job the same way; and, today, this project's entire windowed Kafka Streams pipeline — built, shipped, running in production with real dashboards — sitting unmarked until this same review found it by accident, checking something else entirely.

The freshest instance is today's own. An architecture decision had explicitly stated a correction that needed to reach the backlog. It never did — the backlog kept citing the old, now-wrong reasoning for a real blocker, a whole milestone's stated dependency, until this same day's staff review traced the citation back to its actual source instead of taking it on faith.

None of this was caught by the PR review that otherwise holds up. Every one of these needed something slower: a full, deliberate re-read of the project against its own live state, not a diff. That's expensive, which is exactly why it only happens when I schedule a staff-level review on purpose, not on any real cadence.

## And this isn't an AI problem

None of this is new. Large software projects have dealt with documentation drift for as long as I've been working in them — architecture diagrams going stale, runbooks describing systems that no longer exist, ADRs explaining decisions that were later reversed, tickets staying open long after the work was actually done. Teams end up maintaining two sources of truth and, eventually, only keep one of them honest.

AI didn't invent any of that.

What AI changes is the speed at which the gap becomes visible. When an agent can implement in an evening what used to take a week, the system moves faster than the documentation around it, unless something explicit keeps the two in sync.

There's a second effect, too. A human on a team can often compensate for stale documentation — someone remembers the diagram is six months out of date, or that the runbook stopped being accurate after the last migration. An agent doesn't have that memory unless it's actually written down somewhere it can read.

So the real finding isn't that AI is bad at following process. It's that AI exposes, faster than a human team usually notices, exactly which parts of a process are enforced and which were only ever documented.

## What actually survived

The process wasn't entirely imaginary. One part had survived contact
with reality: every PR gets an independent review before merge.

It's not routed through the correct persona according to the workflow —
it's still an informal generic reviewer rather than explicitly assigning
the architect or platform-engineer role. But it happens, every time, and
it has already caught several things that would otherwise have shipped.

- One PR quietly bundled three unrelated backlog edits into a single
  commit. They were leftover uncommitted changes from earlier work that
  came along when a new branch was created. Caught before merge.
- Another branch had been cut from the wrong base and silently included
  an unrelated document alongside the intended three-line change. Caught,
  rebased, re-pushed.
- A citation in a new backlog item named two of three real sources for a
  claim and silently dropped the third. Caught and fixed.
- A technical write-up quoted a Prometheus timestamp five seconds away
  from what the raw data actually showed. Caught and corrected to an
  honest range instead of false precision.

None of these were spectacular failures. That's partly the point. The
review worked because there was a real consequence for skipping it — an
unreviewed change could go straight into the live system. There was
friction. The other processes didn't have that.

## The decision check

There's another habit that emerged from the Beyla/Mimir incident. Before
acting on a recommendation, I now ask a deliberately boring question:
does this contradict anything we've already decided?

That was the question that prevented the reviewer's recommendation from
turning into an actual change without a second look — and it produced a
better outcome than either side of the argument on its own.

Beyla stayed exactly where it was. Mimir got something better than an
indefinite "keep testing" decision: instead of removing it immediately, I
gave it a concrete exit condition. It stays until it stops serving the
one remaining purpose it has and then it gets decommissioned through a
rollback path that's already documented.

The review brought the evidence. My previous decision brought the
context. The conflict between them produced a better decision than
either would have reached alone.

## The actual finding

The finding isn't "the AI doesn't follow process" — the AI review was the
thing that exposed the problem. The finding isn't "be more disciplined"
either; that's too vague to be useful.

The thing I actually trust is narrower: **a process survives in
proportion to how much friction it takes to skip it.** The independent
PR review survived because skipping it means shipping an unreviewed
change to a live system — real friction, every single time. The AI
personas didn't survive because there was an easier path right next to
them. The project board didn't survive for the same reason.

The documentation described a process. The actual system followed a
different one. And the actual system always wins.

## What I'm changing

I'm not going to pretend the answer is to suddenly delegate every
architecture decision to an AI persona that's been sitting idle for a
month, or backfill status on 134 stale cards so the board looks healthy
again. That would be another version of the same problem — following the
document instead of fixing the system.

The one I did fix, the same day: the board's status field no longer
depends on anyone remembering it.

It turns out GitHub Projects already ships six native automation rules
for exactly this — set a card's status when it's added, when a linked
pull request merges, when the issue itself closes — and this project had
exactly one of them turned on. Whatever I'd written down as the rule for
when a card should move, the actual mechanism enforcing it was zero.

I enabled four more, mapped to the board's own existing column
definitions, recorded as ADR 0042. One deliberate exception: a merged PR
moves the status to Done, but doesn't auto-close the issue, because this
project's own Definition of Done needs more than a merge, and a status
is cheap to correct where a closed issue is not.

I didn't do the equivalent for the personas, and I want to be honest
about why: there wasn't an equally clean mechanical fix sitting right
there.

## One final note

This is probably the first AdamastorX post where the project itself
isn't really the subject.

The subject is what happens when AI makes implementation cheap enough
that you start discovering which parts of your engineering discipline
were real, and which ones were just files in a repository.

And I think that's a much more interesting experiment than whether an AI
can write a Kubernetes manifest.

---

Everything is public: [github.com/AdamastorX](https://github.com/AdamastorX).

*Real evidence, for anyone who wants to check any of this rather than
take my word for it:*

- **The Beyla/Mimir override** — backlog item #120, dated and verbatim.
- **The stack-evaluation recommendation** —
  `docs/reviews/2026-08-15-operate-followthrough-and-m12-reality.md` §10.
- **Mimir's "not yet worth it" verdict and rollback path** — ADR 0038.
- **The resolved conditional-decommission decision** — backlog item #135.
- **Workflow and persona definitions** — `.claude/WORKFLOW.md` and
  `.claude/agents/*.md`.
- **The project board's rules** — `docs/roadmap/project-board.md`.
- **The 12-of-146 status count** — a live query against the real GitHub
  Project.
- **The four review catches** — real, ordinary pull requests from this
  same month.
- **The board-automation fix** — ADR 0042, including the six-workflow
  live inventory it found and the API limitation that meant enabling
  them still took a manual pass through the GitHub UI, not a script.

**A note on AI:** Yes, I used AI to write this article too. It helped
with structure, wording, and editing; the experiences, decisions, and
opinions are mine.
