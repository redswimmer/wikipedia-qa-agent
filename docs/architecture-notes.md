# Architecture notes: abstractions and the test pyramid

Original notes summarizing the guidance behind the "Design principles" section
of [`CLAUDE.md`](../CLAUDE.md), so it can be referenced without needing to
re-fetch the source. These are paraphrased in our own words, not excerpts —
for the original text, see:

- Chapter 3, "A Brief Interlude: On Coupling and Abstractions":
  https://www.cosmicpython.com/book/chapter_03_abstractions.html
- Chapter 5, "TDD in High Gear and Low Gear":
  https://www.cosmicpython.com/book/chapter_05_high_gear_low_gear.html

Both are from *Architecture Patterns with Python* by Harry Percival and Bob
Gregory (O'Reilly).

## Chapter 3: abstractions and coupling

The chapter's core argument is that tightly coupling business logic directly
to I/O (filesystems, networks, databases) makes code expensive to test and
change, because every test of the logic has to go through the slow, messy
real thing. The fix isn't "add more mocks" — it's finding the right
abstraction to put between the logic and the I/O.

Their running example is a file-sync tool. Instead of writing code that
walks the filesystem and issues copy/move/delete calls inline with the
comparison logic, they factor it into three separate concerns:

1. Read the real state of the world into a simple data structure (e.g. a
   dict mapping content hashes to file paths).
2. Run pure comparison logic against that data structure to decide what
   *should* happen, expressed as plain data (e.g. tuples like
   `("COPY", src, dest)`) rather than as direct filesystem calls.
3. Interpret that plain data and apply the actual I/O.

The key move is representing both "the state of the world" and "the actions
to take" as ordinary data structures instead of objects that do things. That
turns the interesting logic into something you can unit test with plain
Python values and no I/O at all.

Rules of thumb they offer for finding this kind of seam:
- Can messy, real-world state be represented with a familiar data structure
  (dict, list, tuple, dataclass)?
- Separate *what* should happen from *how* it gets executed.
- Look for a natural boundary where a simplifying abstraction could sit.
- What responsibilities are currently tangled together that could be split
  into distinct, named components?

On testing: they explicitly argue against reaching for `mock.patch` as the
default way to isolate code from I/O. Patching lets you test code without
first designing a clean seam, which means the coupling problem never
actually gets fixed — it just gets hidden by the mock. Their preferred
alternative is dependency injection with a hand-written fake (e.g. an
in-memory fake filesystem) that implements the same interface as the real
thing. Because the fake is a real object with real (if simplified) behavior,
tests using it exercise the actual entrypoint logic edge-to-edge, not just
the parts convenient to patch.

## Chapter 5: the test pyramid, high gear and low gear

The chapter uses a bicycle-gears metaphor for two different testing modes,
and argues most projects should use both, at different times:

- **Low gear — domain-layer tests.** Tests written directly against core
  business-logic objects. High effort per unit of coverage, tightly coupled
  to implementation details (so they break when internals change even if
  behavior doesn't), but they give strong design feedback and read as
  precise documentation of the domain rules. Best suited to the early,
  exploratory phase of building something new or genuinely complex, where
  you're still discovering what the right domain model even is.
- **High gear — service-layer tests.** Tests written against a layer that
  sits above the domain model — the entry points application code actually
  calls. Looser coupling to internals (so refactors don't break them), wider
  coverage per test, and they still avoid real I/O by using fakes for
  anything external. Best suited to routine, ongoing feature work and bug
  fixes once the domain model has stabilized.

They recommend most of a project's test suite live at the service layer once
past the initial exploratory phase: a small number of domain-layer tests kept
for the trickiest business rules (or deleted once service-layer tests cover
the same ground), a larger set of service-layer tests doing the bulk of edge
case coverage, and a small number of true end-to-end tests — roughly one per
user-facing feature — that exercise the real entry point (e.g. an HTTP API)
to confirm the pieces are wired together correctly. Their reasoning: as the
proportion of slow, brittle tests grows, the whole suite gets slower and
harder to maintain, so the fast, loosely-coupled layer should carry most of
the weight.

A related piece of guidance: service-layer functions should take primitive
arguments (strings, ints, plain dicts) rather than requiring the caller to
construct domain objects by hand. If writing a service-layer test keeps
needing you to reach into domain internals to set up state, that's a signal
the service layer is missing an operation — add it, rather than working
around the gap in the test.
