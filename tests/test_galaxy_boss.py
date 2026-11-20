"""Void Sentinel boss fight: phase selection."""

import pytest

import galaxy_keeper as gk

PHASES = gk._SENTINEL["phases"]
HP_MAX = gk._SENTINEL["hp_max"]


@pytest.mark.parametrize("hp, index", [
    (HP_MAX, 0),
    (int(HP_MAX * 0.66), 0),
    (int(HP_MAX * 0.65), 1),
    (int(HP_MAX * 0.31), 1),
    (int(HP_MAX * 0.30), 2),
    (1, 2),
])
def test_phase_follows_remaining_hp(hp, index):
    """Phases 2 and 3 used to be unreachable: phase 1 always won."""
    assert gk._boss_phase(hp) is PHASES[index]
