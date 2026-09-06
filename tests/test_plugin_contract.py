from dcm.sports.common.plugin import REGISTRY, UNSUPPORTED, lookup, selection_state


def test_unknown_family_fail_closed():
    assert selection_state("quidditch", "IQA", "goals") == UNSUPPORTED


def test_cfl_not_automatically_production_reboot():
    assert lookup("gridiron") is not None
    assert "CFL" in lookup("gridiron").leagues
    assert "CFL_REBOOT" in lookup("gridiron").known_unsupported


def test_boxing_not_ufc():
    m = lookup("combat")
    assert "BOXING_AS_UFC" in m.known_unsupported


def test_every_family_has_path_unit():
    assert len(REGISTRY) >= 12
    for m in REGISTRY.values():
        assert m.path_unit
        assert m.leagues


def test_no_generic_esports_model():
    m = lookup("esports")
    assert m.production_state == UNSUPPORTED
    assert "CS2" in m.leagues
