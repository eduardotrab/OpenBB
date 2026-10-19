"""Receita Federal Router."""

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

router = Router(prefix="", description="Receita Federal do Brasil data.")


@router.command(
    model="ReceitaRevenue",
    examples=[
        APIEx(parameters={"provider": "receita", "uf": "SP", "tax": "IRPF"}),
    ],
)
async def revenue(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get monthly federal tax revenue by state (arrecadação federal)."""
    return await OBBject.from_query(OBBQuery(**locals()))
