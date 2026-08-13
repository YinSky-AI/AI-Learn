from app.domain.equation_verifier import TransitionFeature, verify_solution_steps


def test_verifier_accepts_equivalent_solution_steps():
    """Treating valid expansion and balancing as invalid must make this test fail."""

    result = verify_solution_steps(
        ["2(x+1)=10", "2x+2=10", "2x=8", "x=4"]
    )

    assert result.first_invalid_transition is None
    assert result.parse_error_step is None
    assert len(result.parsed_steps) == 4


def test_verifier_locates_the_first_invalid_transition():
    """Continuing past or misindexing the first invalid transition must make this fail."""

    result = verify_solution_steps(
        ["2(x+1)=10", "2x+2=10", "2x=12", "x=6"]
    )

    assert result.first_invalid_transition == 1
    assert result.parse_error_step is None


def test_verifier_reports_parse_error_without_inventing_an_invalid_transition():
    """Treating unsafe syntax as mathematical evidence must make this test fail."""

    result = verify_solution_steps(["2x=8", "x.__class__=4", "x=4"])

    assert result.first_invalid_transition is None
    assert result.parse_error_step == 1
    assert len(result.parsed_steps) == 1


def test_verifier_exposes_distribution_attempt_feature():
    """Losing the structural signal for a bad expansion must make this test fail."""

    result = verify_solution_steps(["2(x+1)=10", "2x+1=10"])

    assert result.first_invalid_transition == 0
    assert TransitionFeature.DISTRIBUTION_ATTEMPT in result.features


def test_verifier_exposes_move_terms_attempt_feature():
    """Losing the structural signal for a bad term transfer must make this fail."""

    result = verify_solution_steps(["2x+3=7", "2x=10"])

    assert TransitionFeature.MOVE_TERMS_ATTEMPT in result.features


def test_verifier_does_not_invent_move_terms_feature_for_unrelated_two_side_changes():
    """Classifying arbitrary two-side edits as term transfer must make this fail."""

    result = verify_solution_steps(["2x+3=7", "3x+3=8"])

    assert TransitionFeature.MOVE_TERMS_ATTEMPT not in result.features


def test_verifier_exposes_combine_like_terms_attempt_feature():
    """Losing the structural signal for bad collection must make this fail."""

    result = verify_solution_steps(["2x+3x=10", "4x=10"])

    assert TransitionFeature.COMBINE_LIKE_TERMS_ATTEMPT in result.features


def test_verifier_exposes_coefficient_normalization_attempt_feature():
    """Losing the structural signal for a bad final division must make this fail."""

    result = verify_solution_steps(["2x=8", "x=8"])

    assert TransitionFeature.COEFFICIENT_NORMALIZATION_ATTEMPT in result.features


def test_verifier_exposes_one_side_changed_feature():
    """Missing a one-sided balance change must make this test fail."""

    result = verify_solution_steps(["2x+2=10", "2x+3=10"])

    assert TransitionFeature.ONE_SIDE_CHANGED in result.features


def test_verifier_handles_empty_and_single_step_evidence():
    """Requiring a transition when none exists must make this test fail."""

    assert verify_solution_steps([]).first_invalid_transition is None
    assert verify_solution_steps(["x=4"]).first_invalid_transition is None
