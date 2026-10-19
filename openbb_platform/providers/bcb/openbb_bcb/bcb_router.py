"""BCB Router: commands for BCB datasets without an OpenBB standard model."""

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

router = Router(prefix="", description="Banco Central do Brasil (BCB) data.")


@router.command(
    model="BcbFocus",
    examples=[
        APIEx(parameters={"provider": "bcb"}),
        APIEx(parameters={"provider": "bcb", "indicator": "PIB Total"}),
        APIEx(parameters={"provider": "bcb", "frequency": "selic"}),
    ],
)
async def focus(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get Focus market expectations (Boletim Focus) from the BCB."""
    return await OBBject.from_query(OBBQuery(**locals()))


@router.command(
    model="BcbIfData",
    examples=[
        APIEx(parameters={"provider": "bcb"}),
        APIEx(parameters={"provider": "bcb", "institution": "02217068", "report": 4}),
        APIEx(parameters={"provider": "bcb", "uf": "SP", "period": "202606"}),
    ],
)
async def ifdata(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get IF.data quarterly reports of financial institutions (default: credit cooperatives)."""
    return await OBBject.from_query(OBBQuery(**locals()))
