"""Version-pinned REST adapter. Only fixed, read-only tools can dispatch requests."""

import json
import time
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import ValidationError

from vendor_review.discovery import DOCUMENTED_FREE, CompanySearch, company_search_body
from vendor_review.evidence import compact, validate_response
from vendor_review.people import (
    PeopleSearch,
    PersonEnrich,
    PostSearch,
    filter_paths,
    people_body,
    premium_total,
    project_professional_data,
)
from vendor_review.schemas import Enrich, executable_tools, request_body
from vendor_review.store import LimitError

API_ROOT = "https://api.crustdata.com"
API_VERSION = "2025-11-01"


def credit_header(response):
    try:
        value = Decimal(response.headers["X-Credits-Used"])
        return value if value.is_finite() and value >= 0 else None
    except (KeyError, InvalidOperation):
        return None


class Crustdata:
    def __init__(self, settings, ledger, event=print, transport=None):
        self.settings, self.ledger, self.event = settings, ledger, event
        self.http = httpx.Client(
            base_url=API_ROOT,
            follow_redirects=False,
            transport=transport,
            headers={
                "Authorization": "Bearer " + settings.crustdata_api_key.get_secret_value(),
                "x-api-version": API_VERSION,
            },
            timeout=settings.request_seconds,
        )
        self.access = None
        self.balance = None
        self.blocked = False
        self.denied_paths = set()

    def close(self):
        self.http.close()

    def preflight(self, thread, turn, deadline):
        for name in ("account_access", "account_credits"):
            result = self.execute(name, {}, thread, turn, "preflight:" + turn + name, deadline)
            if result["status"] != "ok":
                return result
        return {
            "status": "ok",
            "message": "Local REST access checked; paid tools still require budget",
        }

    def price(self, path, value):
        if not self.access or self.balance is None or self.blocked:
            raise LimitError("Run successful account preflight before paid tools")
        if path in self.denied_paths:
            raise LimitError("This endpoint was denied; use an authorized evidence path instead")
        entry = next((x for x in self.access["endpoints"] if x.get("path") == path), None)
        if not entry or entry.get("status") != "enabled":
            raise LimitError("Endpoint not enabled for this account/key")
        if path in DOCUMENTED_FREE:
            # Officially documented free; an observed charge above zero blocks paid dispatch.
            rpm = entry.get("effective_rate_limit_rpm")
            return Decimal(0), 5 if rpm is None else rpm
        if "base_credits" not in entry:
            raise LimitError("No authoritative account price; refusing unknown spend")
        price = Decimal(str(entry["base_credits"]))
        if isinstance(value, (PeopleSearch, PersonEnrich, PostSearch)):
            body = people_body(value)
            requested = body["fields"]
            disabled = (entry.get("fields") or {}).get("disabled", [])
            if any(
                field == blocked or field.startswith(blocked + ".")
                for field in requested
                for blocked in disabled
            ):
                raise LimitError("Selected professional fields are not enabled for this account")
            price += premium_total(entry.get("premium_fields"), requested)
            price += premium_total(
                entry.get("premium_filters"), filter_paths(body.get("filters", {}))
            )
            price *= body.get("limit", 1)
        if isinstance(value, CompanySearch):
            body = company_search_body(value)
            disabled = (entry.get("fields") or {}).get("disabled", [])
            if any(
                field == blocked or field.startswith(blocked + ".")
                for field in body["fields"]
                for blocked in disabled
            ):
                raise LimitError("Selected company fields are not enabled for this account")
            price += premium_total(entry.get("premium_fields"), body["fields"])
            price += premium_total(
                entry.get("premium_filters"), filter_paths(body.get("filters", {}))
            )
            price *= body["limit"]
        if isinstance(value, Enrich):
            disabled = entry.get("fields", {}).get("disabled", [])
            if any(field in disabled for field in value.fields):
                raise LimitError("Requested enrichment group is disabled")
            # Base-only groups are exposed; account-specific premiums are still included.
            for premium in entry.get("premium_fields") or []:
                if any(
                    premium["field"] == field or premium["field"].startswith(field + ".")
                    for field in value.fields
                ):
                    price += Decimal(str(premium["credits"]))
        if not price.is_finite() or price < 0 or price > self.balance:
            raise LimitError("Invalid price or insufficient checked account balance")
        rpm = entry.get("effective_rate_limit_rpm")
        return price, 5 if rpm is None else rpm

    def execute(self, name, args, thread, turn, call_key, deadline):
        prior = self.ledger.prior(thread, call_key)
        if prior:
            if prior["result"]:
                return json.loads(prior["result"])
            return {
                "status": "unknown",
                "operation_id": prior["id"],
                "message": "Prior dispatch outcome unknown; reservation retained; no automatic replay",
            }
        op = None
        charge = None
        try:
            if time.monotonic() >= deadline:
                raise LimitError("Turn deadline reached")
            if not self.settings.crustdata_api_key.get_secret_value():
                raise LimitError("CRUSTDATA_API_KEY is missing")
            specs = executable_tools()
            if name not in specs:
                raise LimitError("Tool is not allowlisted")
            schema, method, path, _ = specs[name]
            value = schema.model_validate(args)
            is_free = method == "GET" or path in DOCUMENTED_FREE
            # Documented-free POSTs still go through price() for the enablement check.
            price, rpm = (Decimal(0), 300) if method == "GET" else self.price(path, value)
            wait = self.ledger.rate_wait(path, rpm, (self.access or {}).get("token_limit_rpm"))
            if wait:
                # Never hide a long wait inside a tool/model turn. No automatic retries.
                raise LimitError(f"Local rate window full; retry in {wait:.0f}s on a later turn")
            op = self.ledger.reserve(thread, turn, call_key, "tool", name, path, price)
            self.event(f"tool start {name} op={op} reserved={price} credits")
            started = time.monotonic()
            timeout = min(self.settings.request_seconds, max(0.1, deadline - started))
            with self.http.stream(
                method,
                path,
                json=(
                    people_body(value)
                    if isinstance(value, (PeopleSearch, PersonEnrich, PostSearch))
                    else request_body(value)
                )
                if method == "POST"
                else None,
                timeout=timeout,
            ) as response:
                charge = credit_header(response)
                # Metadata endpoints are documented free; absence of their header is not unknown spend.
                if is_free and charge is None:
                    charge = Decimal(0)
                details = {
                    "http_status": response.status_code,
                    "provider_request_id": response.headers.get("X-Request-Id"),
                    "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                    "rate_limit_reset": response.headers.get("X-RateLimit-Reset"),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "actual_charge_source": "X-Credits-Used"
                    if "X-Credits-Used" in response.headers
                    else "documented_free"
                    if is_free
                    else "unknown",
                }
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 2_000_000 or time.monotonic() >= deadline:
                        result = {
                            "status": "capture_incomplete",
                            "operation_id": op,
                            "message": "Response exceeded size/deadline bound; evidence unusable",
                        }
                        self.ledger.finish(
                            op, "capture_incomplete", result, charge, details=details
                        )
                        return result
                    chunks.append(chunk)
                try:
                    raw = json.loads(b"".join(chunks))
                except (ValueError, UnicodeError):
                    raw = {"capture_error": "Non-JSON response; not treated as evidence"}
                if isinstance(value, (PeopleSearch, PersonEnrich, PostSearch)):
                    raw = project_professional_data(raw)
                artifact = self.ledger.artifact(op, raw)
                ok = response.is_success and validate_response(name, raw)
                if ok and name == "account_access":
                    self.access = raw
                if ok and name == "account_credits":
                    self.balance = Decimal(str(raw["account"]["credits"]))
                if charge is not None and self.balance is not None and not is_free:
                    self.balance = max(Decimal(0), self.balance - charge)
                if response.status_code in {401, 402}:
                    self.blocked = True
                if response.status_code == 403:
                    self.denied_paths.add(path)
                status = "ok" if ok else "provider_error"
                if (
                    ok
                    and name == "fetch_page"
                    and any(not page.get("success") or not page.get("content") for page in raw)
                ):
                    status = "partial"
                if (
                    ok
                    and name == "web_search"
                    and (not raw["success"] or raw.get("metadata", {}).get("failed_pages"))
                ):
                    status = "partial"
                if (
                    ok
                    and name in {"identify_company", "enrich_company", "enrich_person"}
                    and not any(row["matches"] for row in raw)
                ):
                    status = "no_match"
                result = {
                    "status": status,
                    "operation_id": op,
                    "artifact_id": artifact,
                    "api_path": path,
                    "api_version": API_VERSION,
                    "retrieved_at_unix": time.time(),
                    "actual_credits": str(charge) if charge is not None else None,
                    "charge_status": "observed" if charge is not None else "unknown_reserved",
                    "data": compact(name, raw, getattr(value, "url", None))
                    if ok
                    else {
                        "http_status": response.status_code,
                        "message": "API/schema failure; no retry. Inspect local artifact.",
                    },
                }
                if charge is not None and charge > price:
                    self.blocked = True
                    result["budget_warning"] = (
                        "Observed charge exceeded reservation; further paid dispatch blocked"
                    )
                result = self.settings.redact(result)
                self.ledger.finish(op, result["status"], result, charge, details=details)
                self.event(
                    f"tool finish {name} status={result['status']} actual={result['actual_credits']} "
                    f"remaining={self.ledger.summary(thread)['remaining_credits']}"
                )
                return result
        except (LimitError, ValidationError) as exc:
            message = (
                str(exc)
                if isinstance(exc, LimitError)
                else "Invalid tool arguments; schema rejected"
            )
            result = {"status": "denied", "message": message}
            if isinstance(exc, ValidationError):
                result["schema_errors"] = [
                    {
                        "field": list(error["loc"]),
                        "type": error["type"],
                        "bounds": {
                            key: value
                            for key, value in (error.get("ctx") or {}).items()
                            if key in {"le", "ge", "max_length", "min_length"}
                        },
                    }
                    for error in exc.errors()
                ]
            try:
                op = self.ledger.reserve(thread, turn, call_key, "tool", name)
                result["operation_id"] = op
                self.ledger.finish(op, "denied", result, actual=0)
            except LimitError:
                pass
            self.event(f"tool denied {name}: {message}")
            return result
        except Exception as exc:
            # Exception strings may contain URLs, request headers or credentials.
            result = {
                "status": "unknown",
                "operation_id": op,
                "message": f"{type(exc).__name__}; outcome/charge unknown, no automatic retry",
            }
            if op:
                self.ledger.finish(op, "unknown", result, actual=charge)
            self.event(f"tool failed {name}: {result['message']}")
            return result
