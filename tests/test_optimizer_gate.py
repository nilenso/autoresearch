import inspect


def test_optimizer_sabotage_gate_passes_before_paid_runs():
    from autoresearch.optimize import run_sabotage_gate

    run_sabotage_gate()


def test_optimizer_runs_sabotage_gate_before_preflight_or_gepa():
    from autoresearch import optimize

    src = inspect.getsource(optimize.run)

    assert src.index("run_sabotage_gate()") < src.index("config.preflight")
    assert src.index("run_sabotage_gate()") < src.index("oa.optimize_anything")


def test_train_and_held_out_questions_never_overlap():
    """Guards the one thing standing between a correct run and a silent
    copy-paste bug: split() must never hand the same question to both sides.
    """
    from autoresearch import questions as qmod

    bank = qmod.load()
    for holdout in (0.2, 1 / 3, 0.5):
        train, val = qmod.split(bank, holdout)
        assert not ({q.id for q in train} & {q.id for q in val})


def test_optimizer_passes_train_as_dataset_and_val_as_valset():
    """A swapped dataset=/valset= kwarg would defeat held-out grading and
    look identical to a passing run otherwise — catch it in source, since
    nothing at runtime would.
    """
    from autoresearch import optimize

    src = inspect.getsource(optimize.run)

    assert "dataset=train," in src
    assert "valset=val," in src
    assert src.index("dataset=train,") < src.index("valset=val,")


def test_background_and_objective_never_quote_a_real_question_verbatim():
    """A hardcoded example question in BACKGROUND/_objective_text would leak
    into the reflection prompt on every run, regardless of which questions
    happen to land in the held-out set for a given holdout fraction. This
    caught `hospitals-rhode-island` sitting in BACKGROUND once already.
    """
    from autoresearch import optimize, questions as qmod

    bank = qmod.load()
    haystacks = [optimize.BACKGROUND, optimize._objective_text("tool"),
                 optimize._objective_text("prompt")]

    for question in bank:
        for haystack in haystacks:
            assert question.question not in haystack, (
                f"{question.id!r}'s text appears verbatim in a prompt template"
            )
