"""CVM provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_cvm.models.fund_daily import CvmFundDailyFetcher
from openbb_cvm.models.funds import CvmFundsFetcher

cvm_provider = Provider(
    name="cvm",
    website="https://dados.cvm.gov.br",
    description="""CVM (Comissão de Valores Mobiliários) open data: investment fund
registry (RCVM 175 classes) and daily fund reports (quota, net assets, flows).""",
    fetcher_dict={
        "CvmFunds": CvmFundsFetcher,
        "CvmFundDaily": CvmFundDailyFetcher,
    },
    repr_name="CVM",
)
