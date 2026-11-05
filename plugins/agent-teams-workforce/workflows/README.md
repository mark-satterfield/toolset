# Optional judgment workflows

Elaboration, build and deployment use the Python orchestrator and the control repository's
Python driver. Their source is `orchestrator/`; the blueprint documents their behavior.
The owner starts the pipelines through keeper.

This folder contains the independent `adversarial` and `gate-enforce` judgment workflows.
The Python pipelines do not dispatch either script. Their canonical shared blocks remain in
`scripts/shared-blocks/`, with registered consumers in `scripts/shared-blocks.mjs`.

Manual dependency assessment and WSJF scoring are owner commands implemented by
`bin/atw-portfolio` and `orchestrator/portfolio.py`. They preserve genuine specialist judgments
while executing planning, validation and writes directly, without a command-runner agent.
