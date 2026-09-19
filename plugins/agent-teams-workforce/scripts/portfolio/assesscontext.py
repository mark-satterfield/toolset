#!/usr/bin/env python3
"""The material one Epic's dependency assessment reads.

The assessing session reads the Epic's own PRD in full, and finds the other PRDs it needs
by searching a corpus: every open Epic's PRD as its own file, and an index naming each
one's title, elaboration state and section headings. It also needs every edge already
standing between the Epic and another open Epic, whichever way it points, with the reason
recorded for it, because it must keep or withdraw each owned one with a reason that
answers the recorded one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import beadgraph
from edgeset import SequencingError, standing_edges
from prds import ELAB_KEY, write_index, write_prds

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Graph


def assess_context(graph: Graph, epic: str, out_dir: Path) -> dict:
    """Write the PRD corpus and index, and return the Epic and its standing edges.

    Args:
        graph: The tracker graph, read with descriptions.
        epic: The Epic to be assessed.
        out_dir: The directory to write into: `prd/<id>.md` per open Epic, and
            `index.md`.

    Returns:
        `epic` (`{id, title, fingerprint, elaborationState, prdPath}`), `standing` (every
        edge between the Epic and another open Epic, from `edgeset.standing_edges`),
        `corpusDir`, `indexPath`, and a `summary` of counts.

    Raises:
        SequencingError: `epic` is not an open Epic.
    """
    epics = [b for b in graph.of_kind("epic") if not b.closed]
    bead = next((b for b in epics if b.id == epic), None)
    if bead is None:
        msg = f"{epic} is not an open Epic"
        raise SequencingError(msg)
    corpus = out_dir / "prd"
    index = out_dir / "index.md"
    paths = write_prds(epics, corpus)
    write_index(graph, epics, paths, index)
    prints = beadgraph.fingerprints(graph.records)
    standing = standing_edges(graph, epic)
    owned = sum(1 for s in standing if s["owned"])
    return {
        "epic": {
            "id": bead.id,
            "title": bead.title,
            "fingerprint": prints.get(bead.id, ""),
            "elaborationState": bead.metadata.get(ELAB_KEY),
            "prdPath": paths[bead.id],
        },
        "standing": standing,
        "corpusDir": str(corpus),
        "indexPath": str(index),
        "summary": {
            "epic": bead.id,
            "openEpics": len(epics),
            "standing": len(standing),
            "owned": owned,
            "handMade": len(standing) - owned,
        },
    }
