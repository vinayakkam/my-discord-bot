"""World generation must be stable: a system is the same every time it is seen."""

import galaxy_keeper as gk
from tests.test_galaxy_render import isolated_galaxy  # noqa: F401  (autouse fixture)


def test_a_system_is_identical_on_first_and_later_generation():
    """The first lookup of a sector's biome used to reseed the RNG midway,
    so the first scan of a new region listed different planets."""
    for x, y in [(1, 7), (60, 61), (-120, 33), (7, -205)]:
        gk._world.clear()                      # sector never seen before
        first = gk.generate_system(x, y)
        again = gk.generate_system(x, y)       # biome now cached
        assert first == again, (x, y)
