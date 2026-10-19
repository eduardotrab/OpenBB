"""CVM Router: commands for CVM open data."""

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

router = Router(prefix="", description="CVM open data.")


@router.command(
    model="CvmFunds",
    examples=[APIEx(parameters={"provider": "cvm", "search": "sicoob"})],
)
async def funds(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Search the CVM investment fund class registry (RCVM 175)."""
    return await OBBject.from_query(OBBQuery(**locals()))


@router.command(
    model="CvmFundDaily",
    examples=[APIEx(parameters={"provider": "cvm", "cnpj": "00.017.024/0001-53"})],
)
async def fund_daily(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get daily fund reports from the CVM: quota, net assets, flows, shareholders."""
    return await OBBject.from_query(OBBQuery(**locals()))
