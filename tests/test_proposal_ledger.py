"""optimize.py::ProposalLedger -- correlating GEPA's callback events into
proposals.jsonl without a live GEPA run.

These call the callback methods directly, in the same order GEPA's engine
fires them (on_proposal_start -> on_proposal_end -> on_candidate_accepted or
on_candidate_rejected), since that's the actual contract this class is
written against -- see its docstring for exactly which events, and why.
"""

from __future__ import annotations

import json

from autoresearch.optimize import ProposalLedger


def test_an_accepted_proposal_is_recorded_with_its_diff(tmp_path):
    path = tmp_path / "proposals.jsonl"
    ledger = ProposalLedger(path)

    ledger.on_proposal_start({"iteration": 1, "parent_candidate": {"cli.py": "old code\n"}})
    ledger.on_proposal_end({
        "iteration": 1,
        "new_instructions": {"cli.py": "new code\n"},
        "prompts": {"cli.py": "the full reflection prompt"},
        "raw_lm_outputs": {"cli.py": "```\nnew code\n```"},
    })
    ledger.on_candidate_accepted({"iteration": 1, "new_candidate_idx": 3, "new_score": 0.9,
                                  "parent_ids": [0]})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["iteration"] == 1
    assert row["component"] == "cli.py"
    assert row["accepted"] is True
    assert row["score_after"] == 0.9
    assert row["parent_text"] == "old code\n"
    assert row["new_text"] == "new code\n"
    assert row["prompt"] == "the full reflection prompt"
    assert row["raw_lm_output"] == "```\nnew code\n```"
    assert "-old code" in row["diff"]
    assert "+new code" in row["diff"]


def test_a_rejected_proposal_is_recorded_too_not_just_accepted_ones(tmp_path):
    path = tmp_path / "proposals.jsonl"
    ledger = ProposalLedger(path)

    ledger.on_proposal_start({"iteration": 2, "parent_candidate": {"skill.md": "v1"}})
    ledger.on_proposal_end({
        "iteration": 2,
        "new_instructions": {"skill.md": "v2, worse"},
        "prompts": {"skill.md": "prompt"},
        "raw_lm_outputs": {"skill.md": "v2, worse"},
    })
    ledger.on_candidate_rejected({"iteration": 2, "old_score": 0.8, "new_score": 0.6,
                                  "reason": "New subsample score not better"})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["accepted"] is False
    assert rows[0]["score_before"] == 0.8
    assert rows[0]["score_after"] == 0.6


def test_multiple_proposals_in_one_iteration_pair_in_arrival_order(tmp_path):
    path = tmp_path / "proposals.jsonl"
    ledger = ProposalLedger(path)

    ledger.on_proposal_start({"iteration": 5, "parent_candidate": {"a.py": "first-parent"}})
    ledger.on_proposal_end({
        "iteration": 5, "new_instructions": {"a.py": "first-new"},
        "prompts": {"a.py": "p1"}, "raw_lm_outputs": {"a.py": "r1"},
    })
    ledger.on_proposal_start({"iteration": 5, "parent_candidate": {"a.py": "second-parent"}})
    ledger.on_proposal_end({
        "iteration": 5, "new_instructions": {"a.py": "second-new"},
        "prompts": {"a.py": "p2"}, "raw_lm_outputs": {"a.py": "r2"},
    })

    ledger.on_candidate_rejected({"iteration": 5, "old_score": 0.5, "new_score": 0.4, "reason": "x"})
    ledger.on_candidate_accepted({"iteration": 5, "new_candidate_idx": 1, "new_score": 0.7,
                                  "parent_ids": [0]})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["parent_text"] == "first-parent"
    assert rows[0]["accepted"] is False
    assert rows[1]["parent_text"] == "second-parent"
    assert rows[1]["accepted"] is True


def test_a_proposal_never_matched_to_an_outcome_is_simply_not_written(tmp_path):
    """No on_proposal_end for this iteration at all -- e.g. reflection
    returned no text updates, which optimize.py's own logging already
    treats as "no proposal happened" (see reflective_mutation.py). Nothing
    to log, and nothing should crash trying to.
    """
    path = tmp_path / "proposals.jsonl"
    ledger = ProposalLedger(path)

    ledger.on_candidate_rejected({"iteration": 9, "old_score": 0.5, "new_score": 0.5, "reason": "no proposal"})

    assert not path.exists() or path.read_text() == ""


def test_no_rationale_field_is_invented(tmp_path):
    """The reflection prompt tells the model not to explain itself, so this
    stays diff-only -- confirms nothing here manufactures a "why" that was
    never asked for or given.
    """
    path = tmp_path / "proposals.jsonl"
    ledger = ProposalLedger(path)

    ledger.on_proposal_start({"iteration": 1, "parent_candidate": {"cli.py": "old"}})
    ledger.on_proposal_end({
        "iteration": 1, "new_instructions": {"cli.py": "new"},
        "prompts": {"cli.py": "p"}, "raw_lm_outputs": {"cli.py": "new"},
    })
    ledger.on_candidate_accepted({"iteration": 1, "new_candidate_idx": 1, "new_score": 1.0, "parent_ids": [0]})

    row = json.loads(path.read_text().splitlines()[0])
    assert "rationale" not in row
