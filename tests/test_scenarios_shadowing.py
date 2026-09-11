"""Regression test for a name-shadowing bug in the scenarios API.

``emotionsim/api/scenarios.py`` imported ``list_scenarios`` from
``emotionsim.scenarios.storage`` and called it in the ``GET /api/scenarios/files``
handler -- but the module also defines a route handler with the same name near
the bottom of the file. A module-level ``def`` rebinds the global, so by the
time the handler ran, ``list_scenarios`` resolved to the **route** function,
whose ``db``/``scope`` parameters are ``Depends(...)`` objects:

    async def list_scenarios(skip=0, limit=50,
                             db: AsyncSession = Depends(get_db),
                             scope: TenantScope = Depends(get_tenant))

Calling that with no arguments reaches ``await db.execute(...)`` where ``db`` is
a ``Depends`` instance, so ``GET /api/scenarios/files`` raised a 500 on every
request. No existing test covered that route, so it stayed unnoticed.

The storage helper is now imported as ``list_stored_scenarios``.
"""
from __future__ import annotations

import dis
import inspect


def test_storage_helper_is_aliased_and_reachable():
    """The alias must point at the real storage helper."""
    from emotionsim.api import scenarios
    from emotionsim.scenarios import storage

    assert scenarios.list_stored_scenarios is storage.list_scenarios
    assert inspect.iscoroutinefunction(scenarios.list_stored_scenarios) is False


def test_route_name_still_shadows_the_global():
    """Documents the remaining hazard: the route handler owns the plain name."""
    from emotionsim.api import scenarios

    assert inspect.iscoroutinefunction(scenarios.list_scenarios) is True


def test_list_scenario_files_calls_the_storage_helper():
    """The file-listing handler must not reference the shadowed global."""
    from emotionsim.api import scenarios

    loaded = {
        instr.argval
        for instr in dis.get_instructions(scenarios.list_scenario_files)
        if instr.opname in ("LOAD_GLOBAL", "LOAD_NAME", "LOAD_DEREF")
    }
    assert "list_stored_scenarios" in loaded, (
        "handler does not load the storage helper alias; "
        f"globals loaded were {sorted(loaded)}"
    )
    assert "list_scenarios" not in loaded, (
        "handler still references the module-level name that the route handler "
        "rebinds to itself"
    )
