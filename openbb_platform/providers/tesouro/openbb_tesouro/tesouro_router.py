"""Tesouro Router: commands for Tesouro Nacional datasets."""

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

router = Router(prefix="", description="Tesouro Nacional data.")


@router.command(
    model="TesouroDireto",
    examples=[
        APIEx(parameters={"provider": "tesouro"}),
        APIEx(parameters={"provider": "tesouro", "bond": "IPCA+"}),
    ],
)
async def direto(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get Tesouro Direto daily rates and prices of Brazilian government bonds."""
    return await OBBject.from_query(OBBQuery(**locals()))
