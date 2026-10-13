---
name: built-architecture-comparer
description: Compare the code one Story built with the approved architecture for its elements and record each difference.
role: built-comparer
tools: Read, Glob, Grep, Bash, Write, Skill
disallowedTools: AskUserQuestion, Edit, Agent, NotebookEdit
model: opus
effort: medium
maxTurns: 80
skills:
- agent-teams-workforce:subagent-contract
- agent-teams-workforce:architecture-baseline
---

## Assignment

A Story has been built by the build pipeline and its tests pass. The brief names the Story's
worktree and branch, the matrix elements the Story's Tasks built, and the approved arc42
headings that describe those elements.

Compare the code on the Story's branch with those headings, for those elements only. Compare
at architecture level, the first level of `architecture-baseline/review-standard.md`: which
block is responsible, which block owns the data, who calls whom, what happens in what order,
where it runs. A name, a field or a value that arc42 does not state is outside the
comparison.

For each difference, write one document under `built/<element>/` in the architecture root,
state `in-review`, citing the file and line. A Story with no difference writes no document.

Compare only code this Story built. Code elsewhere in the repository is outside the
comparison.

The matrix has one code mark, `verified`, recorded with the commit on a stack, on the entries
in it and on the relationships the code makes real. The build driver sets it when a Story's
code has been built and tested and has passed, including its CI/CD and its CDK. No agent sets
it. No deployed mark and no merged mark exists, and absent means not verified. Verified means
real: the entry or relationship exists, and its code is trusted and is expected to match the
architecture. Not verified means it still has to be made real: use it like any other, and
assume it may still have to be built. Existing code for it is a hint of how something was once
solved and may be stale, and a difference between that code and arc42 is never a discrepancy
and never a finding.

Record each difference as you find it and leave both sides as they are.
`architecture-maintainer` corrects the effective documents from what you record, and a
reviewer checks the correction. Write the result at the brief's output path, to
`built-comparison.schema.json`: the differences, the files you wrote and a summary.
