"""IBGE Router: commands for IBGE datasets without an OpenBB standard model."""

from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.example import APIEx
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query as OBBQuery
from openbb_core.app.router import Router

router = Router(prefix="", description="IBGE data.")


@router.command(
    model="IbgeAggregates",
    examples=[
        APIEx(parameters={"provider": "ibge", "table": 1737, "variables": "63,2265"}),
        APIEx(parameters={"provider": "ibge", "table": 6381, "periods": "-4"}),
    ],
)
async def aggregates(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get SIDRA aggregate tables from the IBGE (IPCA, GDP, unemployment...)."""
    return await OBBject.from_query(OBBQuery(**locals()))
