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


def test_optimizer_wires_iterations_as_the_primary_stop_condition():
    """--iterations must reach GEPA's own iteration-count stop condition, not
    just the evaluation-count budget, or it silently does nothing.
    """
    from autoresearch import optimize

    src = inspect.getsource(optimize.run)

    assert "max_candidate_proposals=iterations" in src
    assert "max_metric_calls=budget" in src


def test_optimizer_points_claude_at_the_pinning_proxy_on_the_openrouter_path():
    """Setting agent_path()=='openrouter' without this would still send the
    agent's traffic straight to the real Anthropic API with an
    OpenRouter-shaped model string, which fails outright.
    """
    from autoresearch import optimize

    src = inspect.getsource(optimize.run)

    assert 'os.environ["ANTHROPIC_BASE_URL"] = proxy.base_url' in src
    assert "orproxy.Pin(config.openrouter_agent_key())" in src
    # The proxy discards whatever key Claude Code sends and substitutes the
    # real OpenRouter one, so a placeholder is fine -- but it must be set,
    # or Claude Code refuses to start at all.
    assert 'os.environ.setdefault("ANTHROPIC_API_KEY"' in src


def test_background_and_objective_never_quote_a_real_question_verbatim():
    """A hardcoded example question in BACKGROUND/_objective_text would leak
    into the reflection prompt on every run, regardless of which questions
    happen to land in the held-out set for a given holdout fraction. This
    caught `hospitals-rhode-island` sitting in BACKGROUND once already.
    """
    from autoresearch import optimize, questions as qmod

    bank = qmod.load()
    haystacks = [optimize.BACKGROUND, optimize._objective_text("tool"),
                 optimize._objective_text("prompt"), optimize._objective_text("wide")]

    for question in bank:
        for haystack in haystacks:
            assert question.question not in haystack, (
                f"{question.id!r}'s text appears verbatim in a prompt template"
            )


def test_wide_lever_gets_its_own_objective_not_the_prompt_levers():
    """_objective_text() used to be a two-way if/else, so any lever that
    wasn't literally 'tool' silently fell into the prompt-lever wording --
    asking the proposer to rewrite instructions when 'wide' is actually
    rewriting Python source too. Caught by reconstructing the actual final
    prompt text end to end, not by reading the branch in isolation.
    """
    from autoresearch import optimize

    wide = optimize._objective_text("wide")

    assert "source" in wide
    assert wide != optimize._objective_text("prompt")
