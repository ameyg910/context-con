import time
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from vendor_review.config import Settings
from vendor_review.crustdata import Crustdata
from vendor_review.store import Ledger


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        crustdata_api_key=SecretStr("test-secret-not-real"),
        session_credits=Decimal("10"),
    )
    ledger = Ledger(tmp_path / "ledger.sqlite", settings)
    ledger.session("a")
    yield settings, ledger
    ledger.close()


def fixture_client(settings, ledger, handler):
    client = Crustdata(
        settings, ledger, event=lambda _: None, transport=httpx.MockTransport(handler)
    )
    client.access = {
        "endpoints": [
            {
                "path": path,
                "status": "enabled",
                "base_credits": price,
                "effective_rate_limit_rpm": 300,
                "fields": {"enabled": ["basic_info"], "disabled": []},
            }
            for path, price in (
                ("/company/identify", 0.2),
                ("/company/enrich", 2),
                ("/web/search/live", 1),
                ("/web/enrich/live", 1),
            )
        ]
    }
    client.balance = Decimal("50")
    return client


def execute(client, name="identify_company", args=None, turn="t", key="k"):
    return client.execute(
        name,
        args if args is not None else {"identifier": "example.com"},
        "a",
        turn,
        key,
        time.monotonic() + 10,
    )


MATCH = [
    {
        "matched_on": "example.com",
        "match_type": "domain",
        "matches": [
            {
                "confidence_score": 1,
                "company_data": {
                    "crustdata_company_id": 123,
                    "basic_info": {"name": "Example", "primary_domain": "example.com"},
                },
            }
        ],
    }
]
