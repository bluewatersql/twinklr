# Review a Change

Use for independent review of implemented work. The reviewer is a different agent or
session from the author; never approve work in the context that authored it.

1. Read the original acceptance criteria and the active plan.
2. Inspect the actual diff, not the author's narrative.
3. Read the relevant source, tests, config, and docs around the diff.
4. Check the validation evidence: were the claimed commands run, and do the results
   support the claims? Rerun what is cheap to rerun.
5. Check that no empirical outcome (live run, xLights acceptance, human judgment) is
   claimed without its dated evidence record.
6. Assess impact on the LLM/renderer boundary, public schemas, CLI behavior, and output
   formats.
7. Check the context, memory, and handoff updates that the change should have made.
8. Record findings with file and line in the change folder (start from
   [changes/_templates/review.md](../../changes/_templates/review.md)) or the PR, with a
   verdict: approved, changes requested, or blocked.
