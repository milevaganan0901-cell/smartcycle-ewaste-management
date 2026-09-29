"""SmartCycle API test suite - dependency free.

Runs against a real running backend and the real SQLite database. It uses only
the standard library, so no test framework is required:

    python -m app.scripts.run_api_tests
    python -m app.scripts.run_api_tests --base-url http://127.0.0.1:8000 --unit
    python -m app.scripts.run_api_tests --unit-only

Admin checks are skipped unless an admin credential is supplied:

    ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.scripts.run_api_tests

The suite creates its own throwaway users/devices/pickups. It never modifies
pre-existing data and never prints a secret.
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

_passed = 0
_failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  {GREEN}PASS{RESET} {name}")
    else:
        _failed.append(f"{name} {detail}".strip())
        print(f"  {RED}FAIL{RESET} {name} {DIM}{detail}{RESET}")


def section(title: str) -> None:
    print(f"\n{YELLOW}{title}{RESET}")


def _summarize() -> int:
    """Print the pass/fail tally and return a process exit code."""
    print()
    if _failed:
        print(f"{RED}{len(_failed)} check(s) failed{RESET} / {_passed} passed")
        for failure in _failed:
            print(f"  {RED}- {failure}{RESET}")
        return 1
    print(f"{GREEN}All {_passed} checks passed{RESET}")
    return 0


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def call(self, method: str, path: str, body=None, token: str | None = None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urlopen(request) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except HTTPError as error:
            raw = error.read()
            try:
                return error.code, (json.loads(raw) if raw else None)
            except json.JSONDecodeError:
                return error.code, raw.decode()

    def token_for(self, email: str, password: str):
        status, body = self.call("POST", "/api/auth/login", {"email": email, "password": password})
        return (body["access_token"] if status == 200 else None)


def register(client: Client, name: str, email: str, password: str):
    return client.call(
        "POST",
        "/api/auth/register",
        {"name": name, "email": email, "password": password, "confirm_password": password},
    )


def submit_device(
    client: Client,
    token: str | None,
    brand: str,
    model: str,
    price: int = 60000,
    age: int = 2,
):
    return client.call(
        "POST",
        "/api/devices",
        {
            "device_category": "Laptop",
            "brand": brand,
            "model": model,
            "age": age,
            "condition": "Good",
            "working_status": "Fully Working",
            "physical_damage": "None",
            "accessories": "Original box and cable",
            "original_purchase_price": price,
            "location": "Test City, Test State",
        },
        token=token,
    )


def run_valuation_unit_checks(print_summary: bool = True) -> int:
    """In-process checks for the rule-based estimator and the ML fallback path.

    These exercise the service layer directly, so every failure mode of the ML
    path (absent model, corrupt model, non-numeric prediction, negative ratio)
    can be forced without restarting the API or touching the database.
    """
    section("Rule-based estimator (standalone)")
    from app.services.valuation import ValuationInput, estimate_device_value, value_device

    base = dict(
        device_category="Laptop",
        brand="Acme",
        age=3,
        condition="Good",
        working_status="Fully Working",
        physical_damage="None",
        original_purchase_price=80000,
    )
    rules = estimate_device_value(ValuationInput(**base))
    check("rule-based estimator returns a positive value",
          rules.estimated_purchase_value > 0, str(rules.estimated_purchase_value))
    check("rule-based method is labelled",
          rules.valuation_method == "rule_based", rules.valuation_method)
    check("refurbished value is derived from the estimate",
          rules.potential_refurbished_value != rules.estimated_purchase_value,
          str(rules.potential_refurbished_value))
    check("recycled value is derived from the estimate",
          rules.potential_recycled_value != rules.estimated_purchase_value,
          str(rules.potential_recycled_value))
    check("recycled value is not above the estimate",
          rules.potential_recycled_value <= rules.estimated_purchase_value,
          f"{rules.potential_recycled_value} vs {rules.estimated_purchase_value}")

    no_price = estimate_device_value(ValuationInput(**{**base, "original_purchase_price": None}))
    check("rule-based estimator works without a purchase price",
          no_price.estimated_purchase_value > 0, str(no_price.estimated_purchase_value))

    broken = estimate_device_value(ValuationInput(**{**base, "working_status": "Not Working"}))
    check("a non-working device is valued below a working one",
          broken.estimated_purchase_value < rules.estimated_purchase_value,
          f"{broken.estimated_purchase_value} vs {rules.estimated_purchase_value}")

    check("value_device works with no ML model present",
          value_device(ValuationInput(**base)).estimated_purchase_value > 0)

    section("ML model load and prediction")
    from app.services import ml_valuation

    ml_valuation.reset_model_cache()
    model_present = ml_valuation.is_model_available()
    print(f"  {DIM}trained model present in this checkout: {model_present}{RESET}")

    if model_present:
        prediction = ml_valuation.predict_estimated_value(ValuationInput(**base))
        check("ML prediction returns a usable value",
              prediction is not None and prediction > 0, str(prediction))
        via_entry = value_device(ValuationInput(**base))
        check("value_device prefers ML when the model is available",
              via_entry.valuation_method == "ml", via_entry.valuation_method)
        check("ML value stays within a sane band of the reference price",
              0 < via_entry.estimated_purchase_value <= 80000 * 1.5,
              str(via_entry.estimated_purchase_value))
    else:
        check("value_device falls back to rules with no model on disk",
              value_device(ValuationInput(**base)).valuation_method == "rule_based")

    section("Stage 4B: distribution guard and prediction sanity")
    if model_present:
        age_range = ml_valuation.model_age_range()
        check("the model reports the age range it was trained on",
              age_range is not None and age_range[1] >= age_range[0], str(age_range))

        if age_range:
            inside = ValuationInput(**{**base, "age": age_range[1]})
            outside = ValuationInput(**{**base, "age": age_range[1] + 5})
            check("an age inside the trained range is priced by the model",
                  ml_valuation.predict_estimated_value(inside) is not None)
            check("an age beyond the trained range is refused by the model",
                  ml_valuation.predict_estimated_value(outside) is None)
            check("that submission is valued by the rule-based estimator",
                  value_device(outside).valuation_method == "rule_based")
            # A tree is constant past its outermost split, so without the guard
            # an old device would be quoted the same as the boundary age.
            flat = {
                age: ml_valuation.predict_estimated_value(ValuationInput(**{**base, "age": age}))
                for age in (age_range[1] + 5, age_range[1] + 15, age_range[1] + 30)
            }
            check("an out-of-range age never returns a flat, inflated ML price",
                  all(v is None for v in flat.values()), str(flat))

        # Brand is free text in the Sell Device form, so an unseen brand must not
        # silently downgrade the ML path. It carries ~0.3% of model importance.
        unseen_brand = value_device(ValuationInput(**{**base, "brand": "Totally New Brand"}))
        check("an unseen free-text brand is still priced by the model",
              unseen_brand.valuation_method == "ml", unseen_brand.valuation_method)

        # A category/condition the model never saw IS material, so it is refused.
        for label, payload in (
            ("condition", {**base, "condition": "Mint"}),
            ("working_status", {**base, "working_status": "Sort of works"}),
            ("device_category", {**base, "device_category": "Hovercraft"}),
        ):
            result = value_device(ValuationInput(**payload))
            check(f"an unseen {label} falls back to the rule-based estimator",
                  result.valuation_method == "rule_based", result.valuation_method)
            check(f"the unseen {label} still yields a positive estimate",
                  result.estimated_purchase_value > 0, str(result.estimated_purchase_value))

        # A missing optional price must not stop the model from being used.
        no_price = value_device(ValuationInput(**{**base, "original_purchase_price": None}))
        check("a submission with no purchase price is still valued by the model",
              no_price.estimated_purchase_value > 0, str(no_price.estimated_purchase_value))

        # Every returned estimate must be finite, non-negative and sane relative
        # to the reference the estimator itself would have used.
        from app.services.ml_valuation import _reference_value as rule_reference

        sane = True
        for category, age, condition in (
            ("Laptop", 1, "Excellent"), ("Smartphone", 9, "Not Working"),
            ("Printer", 5, "Fair"), ("Television", 3, "Good"),
            ("Accessories", 0, "Excellent"), ("Monitor", 7, "Poor"),
        ):
            for price in (None, 1000, 250000):
                item = ValuationInput(
                    device_category=category, brand="Apple", age=age, condition=condition,
                    working_status="Fully Working", physical_damage="None",
                    original_purchase_price=price,
                )
                out = value_device(item)
                reference = rule_reference(item)
                value = out.estimated_purchase_value
                if not (
                    isinstance(value, (int, float))
                    and value == value
                    and 0 < value <= max(reference * 1.5, 500)
                ):
                    sane = False
                    print(f"      {DIM}unsane: {category} age={age} {condition} "
                          f"price={price} -> {value} (ref {reference}){RESET}")
        check("every estimate is finite, positive and within a sane band of its reference",
              sane)

        derived_ok = True
        for category, age, condition in (
            ("Laptop", 2, "Good"), ("Smartphone", 6, "Not Working"), ("Printer", 0, "Excellent"),
        ):
            out = value_device(ValuationInput(
                device_category=category, brand="Apple", age=age, condition=condition,
                working_status="Fully Working", physical_damage="None",
                original_purchase_price=None,
            ))
            if not (
                out.potential_refurbished_value > 0 and out.potential_recycled_value > 0
                and out.potential_recycled_value <= out.estimated_purchase_value
            ):
                derived_ok = False
        check("refurbished and recycled values are always present, positive and consistent",
              derived_ok)

    section("ML failure modes fall back to the rule-based estimator")
    # The failures below are deliberate. The service logs every one of them
    # server-side, which is the behaviour we want, but the tracebacks would
    # otherwise bury the check results.
    logging.disable(logging.CRITICAL)
    real_path = ml_valuation.VALUATION_MODEL_PATH
    backup = real_path.with_name(real_path.name + ".unittest-backup")
    if real_path.exists():
        real_path.replace(backup)
    try:
        ml_valuation.reset_model_cache()
        check("missing model -> is_model_available() is False",
              ml_valuation.is_model_available() is False)
        check("missing model -> predict returns None",
              ml_valuation.predict_estimated_value(ValuationInput(**base)) is None)
        check("missing model -> value_device still values the device",
              value_device(ValuationInput(**base)).valuation_method == "rule_based")
        check("missing model -> rule-based value is unchanged",
              value_device(ValuationInput(**base)).estimated_purchase_value
              == rules.estimated_purchase_value)

        real_path.write_bytes(b"this is not a joblib pipeline")
        ml_valuation.reset_model_cache()
        check("corrupt model -> is_model_available() is False",
              ml_valuation.is_model_available() is False)
        check("corrupt model -> value_device still values the device",
              value_device(ValuationInput(**base)).valuation_method == "rule_based")
    finally:
        real_path.unlink(missing_ok=True)
        if backup.exists():
            backup.replace(real_path)
        ml_valuation.reset_model_cache()
    check("model restored after the failure-mode tests",
          ml_valuation.is_model_available() == model_present)

    if model_present:

        class BadRatio:
            def predict(self, _rows):
                return [float("nan")]

        class NegativeRatio:
            def predict(self, _rows):
                return [-4.0]

        class Exploding:
            def predict(self, _rows):
                raise RuntimeError("simulated pipeline failure")

        for label, stub in (("NaN ratio", BadRatio()),
                            ("negative ratio", NegativeRatio()),
                            ("raising pipeline", Exploding())):
            original = ml_valuation._pipeline
            ml_valuation._pipeline = stub
            try:
                check(f"{label} -> value_device falls back to rules",
                      value_device(ValuationInput(**base)).valuation_method == "rule_based")
            finally:
                ml_valuation._pipeline = original
    logging.disable(logging.NOTSET)

    if print_summary:
        # Standalone mode owns its own summary; main() prints a combined one.
        return _summarize()
    return 0


def run_chat_unit_checks(print_summary: bool = True) -> int:
    """In-process checks for the SmartCycle AI assistant.

    The Gemini provider is stubbed throughout, so nothing here makes a network
    call and no API key is needed. Covered: request validation, the router's
    not-configured path, pass-through of a successful answer, and the guarantee
    that any provider failure can only ever produce the one fixed safe message.
    """
    section("AI assistant - request validation (no provider call)")
    from pydantic import ValidationError
    from app.schemas.chat import MAX_MESSAGE_LENGTH, ChatRequest

    question = "How does SmartCycle value a device?"
    check("a normal question is accepted", ChatRequest(message=question).message == question)

    rejected = (
        ("an empty message", ""),
        ("a whitespace-only message", "   \t  \n "),
        (f"a message over {MAX_MESSAGE_LENGTH} characters", "x" * (MAX_MESSAGE_LENGTH + 1)),
    )
    for label, bad in rejected:
        try:
            ChatRequest(message=bad)
            check(f"{label} is rejected", False, "it was accepted")
        except ValidationError:
            check(f"{label} is rejected", True)

    try:
        ChatRequest(message="hi", unexpected="field")
        check("an unexpected field is rejected", False, "it was accepted")
    except ValidationError:
        check("an unexpected field is rejected", True)

    at_limit = "y" * MAX_MESSAGE_LENGTH
    check(f"a message of exactly {MAX_MESSAGE_LENGTH} characters is accepted",
          len(ChatRequest(message=at_limit).message) == MAX_MESSAGE_LENGTH)

    section("AI assistant - provider stubbed (no key, no network)")
    from fastapi import HTTPException
    from app.api.routers.chat import chat as chat_route
    from app.services import gemini_service

    class StubInteraction:
        def __init__(self, text: str) -> None:
            self.output_text = text

    class StubInteractions:
        def __init__(self, text=None, error=None) -> None:
            self.text, self.error, self.seen = text, error, {}

        def create(self, **kwargs):
            self.seen = kwargs
            if self.error is not None:
                raise self.error
            return StubInteraction(self.text)

    class StubClient:
        def __init__(self, text=None, error=None) -> None:
            self.interactions = StubInteractions(text=text, error=error)

    def with_stub(client, key, action):
        """Run `action` against a stubbed provider and a chosen key state."""
        saved = (gemini_service._get_client, gemini_service.GEMINI_API_KEY,
                 gemini_service.is_configured)
        gemini_service._get_client = lambda: client
        gemini_service.GEMINI_API_KEY = key
        gemini_service.is_configured = lambda: bool(key)
        try:
            return action()
        finally:
            (gemini_service._get_client, gemini_service.GEMINI_API_KEY,
             gemini_service.is_configured) = saved

    # A successful answer is passed through untouched, and the grounding that
    # keeps the assistant honest is actually sent to the provider.
    answer = "SmartCycle estimates a device's value from its age, condition and working status."
    stub = StubClient(text=answer)
    replied = with_stub(stub, "stub-key", lambda: chat_route(ChatRequest(message=question)))
    check("a valid question returns the assistant's answer", replied.response == answer, replied.response[:40])
    check("the user's question reaches the provider", stub.interactions.seen.get("input") == question)
    check("the configured model is the one requested",
          stub.interactions.seen.get("model") == gemini_service.GEMINI_MODEL,
          str(stub.interactions.seen.get("model")))
    sent_instruction = stub.interactions.seen.get("system_instruction") or ""
    check("the SmartCycle system instruction is sent", "SmartCycle AI Assistant" in sent_instruction)
    check("the system instruction carries the contact details",
          "milevaganan0901@gmail.com" in sent_instruction and "+91 86376 12496" in sent_instruction)
    check("the system instruction forbids invented prices and pickup promises",
          "Never invent prices" in sent_instruction and "pickup time" in sent_instruction)

    # A missing key is an operator problem, so the router answers 503.
    try:
        with_stub(None, "", lambda: chat_route(ChatRequest(message="hi")))
        check("a missing API key is reported as unavailable", False, "no error was raised")
    except HTTPException as error:
        check("a missing API key is reported as unavailable", error.status_code == 503,
              f"got {error.status_code}")

    # The failures below are deliberate. The service logs each one server-side,
    # which is the behaviour we want, but the tracebacks would bury the results.
    logging.disable(logging.CRITICAL)
    try:
        for label, error in (
            ("a rate limit", RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")),
            ("an unavailable API", RuntimeError("503 Service Unavailable")),
            ("a network failure", OSError("connection reset by peer")),
            ("a timeout", TimeoutError("the read operation timed out")),
        ):
            got = with_stub(StubClient(error=error), "stub-key",
                            lambda: chat_route(ChatRequest(message="hi")))
            check(f"{label} -> the safe fallback message",
                  got.response == gemini_service.UNAVAILABLE_MESSAGE)

        for label, blank in (("an empty answer", ""), ("a whitespace-only answer", "  \n ")):
            got = with_stub(StubClient(text=blank), "stub-key",
                            lambda: chat_route(ChatRequest(message="hi")))
            check(f"{label} -> the safe fallback message",
                  got.response == gemini_service.UNAVAILABLE_MESSAGE)

        section("AI assistant - no key or internals reach the caller")
        secret = "AIzaSyTESTKEY0000doNotLeak0000000000"
        probes = (
            ("a provider exception",
             with_stub(StubClient(error=RuntimeError(f"rejected key {secret} on db postgresql://u:p@h/db")),
                       "stub-key", lambda: gemini_service.generate_reply("hi"))),
            ("the not-configured message",
             with_stub(None, "", lambda: gemini_service.NOT_CONFIGURED_MESSAGE)),
            ("the safe fallback",
             with_stub(StubClient(error=RuntimeError("boom")), "stub-key",
                       lambda: gemini_service.generate_reply("hi"))),
            ("a successful answer",
             with_stub(StubClient(text="A normal helpful answer."), "stub-key",
                       lambda: gemini_service.generate_reply("hi"))),
        )
        forbidden = (secret, "GEMINI_API_KEY", "GEMINI_MODEL", "Traceback", 'File "',
                     "/Users/", "postgresql://", "JWT_SECRET", "neon.tech", "google.genai",
                     "sys.argv", "sqlite")
        for label, text in probes:
            leaked = [token for token in forbidden if token in text]
            check(f"{label} exposes no key, env var, traceback, or database detail",
                  not leaked, ", ".join(leaked))
    finally:
        logging.disable(logging.NOTSET)

    if print_summary:
        return _summarize()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.scripts.run_api_tests")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD", ""))
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Also run in-process valuation/ML-fallback checks (no server needed).",
    )
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run only the in-process checks, without touching a running server.",
    )
    args = parser.parse_args()

    if args.unit_only:
        run_valuation_unit_checks(print_summary=False)
        run_chat_unit_checks(print_summary=False)
        return _summarize()

    client = Client(args.base_url)

    print(f"{DIM}SmartCycle API test suite -> {args.base_url}{RESET}")

    status, health = client.call("GET", "/api/v1/health")
    if status != 200:
        print(f"{RED}Backend is not reachable at {args.base_url}. Start it first.{RESET}")
        return 2
    check("backend is reachable", True, f"health={health}")

    stamp = uuid.uuid4().hex[:10]
    # Not a credential: this is a throwaway password for the two accounts this
    # run creates, whose email addresses carry the random stamp above. It is
    # never reused for anything and no real account uses it. Admin checks take
    # their password from --admin-password / $ADMIN_PASSWORD instead.
    password = "TestSuite123!"
    a_email, b_email = f"suite-a-{stamp}@example.com", f"suite-b-{stamp}@example.com"

    created: dict[str, object] = {"devices": [], "pickups": []}

    # ---------------------------------------------------------------- auth
    section("Authentication (1-3)")
    status, user_a = register(client, "Suite User A", a_email, password)
    check("register User A", status == 201, f"got {status}")
    status, user_b = register(client, "Suite User B", b_email, password)
    check("register User B", status == 201, f"got {status}")
    check("new user defaults to the user role", (user_a or {}).get("role") == "user", str((user_a or {}).get("role")))
    check("registration never returns a password hash", "password" not in json.dumps(user_a or {}).lower())

    status, dup = register(client, "Duplicate", a_email, password)
    check("duplicate email rejected", status == 400, f"got {status}")
    status, body = client.call(
        "POST", "/api/auth/register",
        {"name": "Bad", "email": "not-an-email", "password": password, "confirm_password": password},
    )
    check("invalid email rejected", status == 422, f"got {status}")
    status, body = client.call(
        "POST", "/api/auth/register",
        {"name": "Weak", "email": f"weak-{stamp}@example.com", "password": "abc", "confirm_password": "abc"},
    )
    check("weak password rejected", status == 422, f"got {status}")
    status, body = client.call(
        "POST", "/api/auth/register",
        {"name": "Mismatch", "email": f"mis-{stamp}@example.com", "password": password, "confirm_password": "Other123!"},
    )
    check("password confirmation mismatch rejected", status == 422, f"got {status}")

    token_a = client.token_for(a_email, password)
    token_b = client.token_for(b_email, password)
    check("login User A issues a token", bool(token_a))
    check("login User B issues a token", bool(token_b))
    status, body = client.call("POST", "/api/auth/login", {"email": a_email, "password": "wrong-password"})
    check("wrong password gives a generic 401", status == 401 and body.get("detail") == "Incorrect email or password", str(body))
    status, body = client.call("POST", "/api/auth/login", {"email": f"ghost-{stamp}@example.com", "password": password})
    check("unknown email gives the same generic 401", status == 401 and body.get("detail") == "Incorrect email or password", str(body))

    status, me = client.call("GET", "/api/auth/me", token=token_a)
    check("GET /api/auth/me with a valid token", status == 200 and me.get("email") == a_email, f"got {status}")
    check("current user never exposes a password", "password" not in json.dumps(me or {}).lower())
    check("current user without a token is 401", client.call("GET", "/api/auth/me")[0] == 401)
    check("current user with a garbage token is 401", client.call("GET", "/api/auth/me", token="a.b.c")[0] == 401)

    # ----------------------------------------------------------- devices
    section("Devices and tracking (4-6)")
    status, device_a = submit_device(client, token_a, "TestBrand", f"ModelA-{stamp}", 70000)
    check("User A submits a device", status == 201, f"got {status}")
    status, device_b = submit_device(client, token_b, "TestBrand", f"ModelB-{stamp}", 50000)
    check("User B submits a device", status == 201, f"got {status}")
    created["devices"] = [device_a, device_b]
    if status != 201:
        print(f"{RED}Cannot continue without devices.{RESET}")
        return 1
    check("tracking ID is generated server-side", str(device_a.get("tracking_id", "")).startswith("EW-"), str(device_a.get("tracking_id")))
    check("device gets a tracking ID", bool(device_a.get("tracking_id")))

    status, fetched = client.call("GET", f"/api/devices/{device_a['tracking_id']}")
    check("track-device lookup by tracking ID", status == 200 and fetched["id"] == device_a["id"], f"got {status}")
    check("unknown tracking ID is 404", client.call("GET", "/api/devices/EW-1999-0000")[0] == 404)

    status, body = client.call(
        "POST", "/api/devices",
        {"device_category": "Laptop", "brand": "X", "model": "Y", "age": -5, "condition": "Good",
         "working_status": "Fully Working", "location": "Nowhere"},
    )
    check("negative age rejected", status == 422, f"got {status}")
    status, body = client.call("POST", "/api/devices", {"device_category": "Laptop"})
    check("incomplete device body rejected", status == 422, f"got {status}")

    # ---------------------------------------------------------- valuation
    section("Valuation and ML (7)")
    value = device_a.get("estimated_purchase_value")
    check("estimated value is numeric", isinstance(value, (int, float)), str(type(value)))
    check("estimated value is non-negative and finite", isinstance(value, (int, float)) and value == value and value >= 0)
    check("valuation_method is reported", device_a.get("valuation_method") in {"ml", "rule_based"}, str(device_a.get("valuation_method")))
    check("refurbished value present", isinstance(device_a.get("potential_refurbished_value"), (int, float)))
    check("recycled value present", isinstance(device_a.get("potential_recycled_value"), (int, float)))

    # Stage 4B: the estimate must survive persistence unchanged, and the API must
    # never fail a submission just because the ML path did.
    status, refetched = client.call("GET", f"/api/devices/{device_a['tracking_id']}")
    check("valuation is persisted and returned identically on re-read",
          status == 200
          and refetched["estimated_purchase_value"] == device_a["estimated_purchase_value"]
          and refetched["valuation_method"] == device_a["valuation_method"],
          f"{refetched.get('estimated_purchase_value')} vs {device_a.get('estimated_purchase_value')}")
    check("the persisted estimate is positive and sane against the reference price",
          0 < refetched["estimated_purchase_value"] <= 70000 * 1.5,
          str(refetched["estimated_purchase_value"]))
    check("no confidence percentage or certainty claim is returned",
          not any(
              key for key in refetched
              if any(word in key.lower() for word in ("confidence", "certainty", "guarantee"))
          ),
          str(sorted(refetched)))

    # An in-range and an out-of-range submission must both be accepted, and both
    # must return a valid valuation. The second exercises the Stage 4B guard.
    status, in_range = submit_device(client, token_a, "Apple", f"InRange-{stamp}", 90000, age=4)
    check("an in-range submission is accepted", status == 201, f"got {status}")
    if status == 201:
        check("an in-range submission yields a positive estimate",
              in_range["estimated_purchase_value"] > 0)
    status, out_of_range = submit_device(client, token_a, "Apple", f"Ancient-{stamp}", 90000, age=22)
    check("an out-of-range submission is still accepted (not rejected by the guard)",
          status == 201, f"got {status}")
    if status == 201:
        check("an out-of-range submission yields a positive estimate",
              out_of_range["estimated_purchase_value"] > 0,
              str(out_of_range["estimated_purchase_value"]))
        check("an out-of-range submission is valued by the rule-based estimator",
              out_of_range["valuation_method"] == "rule_based",
              out_of_range["valuation_method"])

    # Invalid input must be rejected by validation, before any valuation runs.
    for label, payload in (
        ("a negative age", {"device_category": "Laptop", "brand": "A", "model": "M", "age": -1,
                            "condition": "Good", "working_status": "Fully Working", "location": "X"}),
        ("a negative purchase price", {"device_category": "Laptop", "brand": "A", "model": "M", "age": 2,
                                       "condition": "Good", "working_status": "Fully Working",
                                       "original_purchase_price": -500, "location": "X"}),
        ("a missing required field", {"device_category": "Laptop", "brand": "A", "age": 2,
                                      "condition": "Good", "working_status": "Fully Working",
                                      "location": "X"}),
        ("a blank brand", {"device_category": "Laptop", "brand": "   ", "model": "M", "age": 2,
                           "condition": "Good", "working_status": "Fully Working", "location": "X"}),
    ):
        check(f"invalid input is rejected: {label}",
              client.call("POST", "/api/devices", payload, token=token_a)[0] == 422)

    # ------------------------------------------------------------- pickups
    section("Pickup workflow (8-10)")
    slot = "9:00 AM – 12:00 PM"
    pickup_date = (date.today() + timedelta(days=3)).isoformat()
    status, pickup_a = client.call(
        "POST", "/api/pickups",
        {"device_id": device_a["id"], "pickup_address": "1 Test Street, Test City 111111",
         "preferred_date": pickup_date, "preferred_time_slot": slot},
        token=token_a,
    )
    check("User A requests pickup for their own device", status == 201, f"got {status}")
    if status == 201:
        created["pickups"].append(pickup_a)
    status, dup_pickup = client.call(
        "POST", "/api/pickups",
        {"device_id": device_a["id"], "pickup_address": "1 Test Street, Test City 111111",
         "preferred_date": pickup_date, "preferred_time_slot": slot},
        token=token_a,
    )
    check("duplicate pickup for the same device is 409", status == 409, f"got {status}")
    check("pickup for a past date is 422", client.call(
        "POST", "/api/pickups",
        {"device_id": device_b["id"], "pickup_address": "2 Test Street, Test City 111111",
         "preferred_date": (date.today() - timedelta(days=1)).isoformat(), "preferred_time_slot": slot},
        token=token_b,
    )[0] == 422)
    check("pickup with an invalid time slot is 422", client.call(
        "POST", "/api/pickups",
        {"device_id": device_b["id"], "pickup_address": "2 Test Street, Test City 111111",
         "preferred_date": pickup_date, "preferred_time_slot": "7:00 AM – 8:00 AM"},
        token=token_b,
    )[0] == 422)
    status, pickup_b = client.call(
        "POST", "/api/pickups",
        {"device_id": device_b["id"], "pickup_address": "2 Test Street, Test City 111111",
         "preferred_date": pickup_date, "preferred_time_slot": "12:00 PM – 3:00 PM"},
        token=token_b,
    )
    check("User B requests pickup for their own device", status == 201, f"got {status}")
    if status == 201:
        created["pickups"].append(pickup_b)

    # ------------------------------------------------- ownership isolation
    section("Ownership isolation (11-13)")
    status, mine_a = client.call("GET", "/api/users/me/devices", token=token_a)
    check("User A sees their own devices", status == 200 and any(d["id"] == device_a["id"] for d in mine_a), f"got {status}")
    check("User A cannot see User B's device", not any(d["id"] == device_b["id"] for d in mine_a))
    status, mine_b = client.call("GET", "/api/users/me/devices", token=token_b)
    check("User B sees their own device", status == 200 and any(d["id"] == device_b["id"] for d in mine_b), f"got {status}")
    check("User B cannot see User A's device", not any(d["id"] == device_a["id"] for d in mine_b))

    check("User A cannot create a pickup for User B's device", client.call(
        "POST", "/api/pickups",
        {"device_id": device_b["id"], "pickup_address": "3 Sneaky Road, Test City 111111",
         "preferred_date": pickup_date, "preferred_time_slot": slot},
        token=token_a,
    )[0] == 404)
    user_a_pickups = client.call("GET", "/api/pickups/my", token=token_a)[1] or []
    user_b_pickups = client.call("GET", "/api/pickups/my", token=token_b)[1] or []
    check("User A's pickup list contains only their own pickups",
          all(p["device_id"] == device_a["id"] for p in user_a_pickups),
          str([p["device_id"] for p in user_a_pickups]))
    check("User B's pickup list contains only their own pickups",
          all(p["device_id"] == device_b["id"] for p in user_b_pickups),
          str([p["device_id"] for p in user_b_pickups]))
    if user_b_pickups and user_a_pickups:
        check("User A cannot read User B's pickup by id",
              client.call("GET", f"/api/pickups/{user_b_pickups[0]['id']}", token=token_a)[0] == 404)
        check("User B cannot read User A's pickup by id",
              client.call("GET", f"/api/pickups/{user_a_pickups[0]['id']}", token=token_b)[0] == 404)
    else:
        check("User A cannot read User B's pickup by id", False, "no pickup rows available to test")
        check("User B cannot read User A's pickup by id", False, "no pickup rows available to test")

    # ------------------------------------------------------ admin + authz
    section("Admin authorization (14-17)")
    admin_paths = ["/api/admin/dashboard", "/api/admin/users", "/api/admin/devices",
                   "/api/admin/pickups", "/api/admin/valuation-model"]
    check("normal user is blocked from every admin endpoint",
          all(client.call("GET", p, token=token_a)[0] == 403 for p in admin_paths))
    check("anonymous caller is blocked from admin endpoints",
          all(client.call("GET", p)[0] == 401 for p in admin_paths))
    check("normal user cannot update a device status", client.call(
        "PATCH", f"/api/admin/devices/{device_a['id']}/status", {"status": "Collected"}, token=token_a
    )[0] == 403)
    check("normal user cannot update a pickup status", client.call(
        "PATCH", f"/api/admin/pickups/{pickup_a['id']}/status", {"status": "Scheduled"}, token=token_a
    )[0] == 403)
    check("anonymous caller cannot update a device status", client.call(
        "PATCH", f"/api/admin/devices/{device_a['id']}/status", {"status": "Collected"}
    )[0] == 401)
    check("the full device list is no longer public", client.call("GET", "/api/devices")[0] == 401)
    check("anonymous caller cannot delete a device", client.call(
        "DELETE", f"/api/devices/{device_a['tracking_id']}"
    )[0] == 401)
    check("a normal user cannot delete their own device", client.call(
        "DELETE", f"/api/devices/{device_a['tracking_id']}", token=token_a
    )[0] == 403)
    check("user B cannot delete user A's device", client.call(
        "DELETE", f"/api/devices/{device_a['tracking_id']}", token=token_b
    )[0] == 403)
    check("the device survived every delete attempt",
          client.call("GET", f"/api/devices/{device_a['tracking_id']}")[0] == 200)

    if args.admin_password:
        admin_token = client.token_for(args.admin_email, args.admin_password)
        check("admin can sign in", bool(admin_token))
        if admin_token:
            check("admin reaches every admin endpoint",
                  all(client.call("GET", p, token=admin_token)[0] == 200 for p in admin_paths))
            check("admin user list never exposes a password", "password" not in json.dumps(
                client.call("GET", "/api/admin/users", token=admin_token)[1]).lower())
            status, updated = client.call(
                "PATCH", f"/api/admin/devices/{device_a['id']}/status", {"status": "Inspection"}, token=admin_token
            )
            check("admin updates a device status", status == 200 and updated["status"] == "Inspection", f"got {status}")
            check("status update leaves the valuation untouched",
                  updated.get("estimated_purchase_value") == device_a.get("estimated_purchase_value"))
            check("status update leaves the owner untouched", updated.get("id") == device_a["id"])
            check("invalid device status is 422", client.call(
                "PATCH", f"/api/admin/devices/{device_a['id']}/status", {"status": "Teleported"}, token=admin_token
            )[0] == 422)
            check("unknown device id is 404", client.call(
                "PATCH", "/api/admin/devices/99999999/status", {"status": "Collected"}, token=admin_token
            )[0] == 404)
            status, updated_pickup = client.call(
                "PATCH", f"/api/admin/pickups/{pickup_a['id']}/status", {"status": "Scheduled"}, token=admin_token
            )
            check("admin updates a pickup status", status == 200 and updated_pickup["status"] == "Scheduled", f"got {status}")
            check("invalid pickup status is 422", client.call(
                "PATCH", f"/api/admin/pickups/{pickup_a['id']}/status", {"status": "Delivered"}, token=admin_token
            )[0] == 422)

            # propagation
            status, tracked = client.call("GET", f"/api/devices/{device_a['tracking_id']}")
            check("owner sees the admin status change via tracking lookup",
                  tracked.get("status") == "Inspection", str(tracked.get("status")))
            status, owner_devices = client.call("GET", "/api/users/me/devices", token=token_a)
            check("owner dashboard reflects the admin status change",
                  any(d["id"] == device_a["id"] and d["status"] == "Inspection" for d in owner_devices))
            status, owner_pickups = client.call("GET", "/api/pickups/my", token=token_a)
            check("owner pickup list reflects the admin status change",
                  any(p["id"] == pickup_a["id"] and p["status"] == "Scheduled" for p in owner_pickups))

            section("Model status (admin only)")
            status, info = client.call("GET", "/api/admin/valuation-model", token=admin_token)
            check("admin can read model status", status == 200, f"got {status}")
            check("model info is a boolean", isinstance((info or {}).get("model_available"), bool))
    else:
        print(f"  {DIM}skipped admin tests: pass --admin-password{RESET}")

    # ----------------------------------------------- admin delete + cascade
    admin_token = client.token_for(args.admin_email, args.admin_password) if args.admin_password else None
    if admin_token:
        section("Admin delete and cascade (19)")
        status, doomed = submit_device(client, token_a, "TestBrand", f"Doomed-{stamp}", 30000)
        if status == 201:
            status, doomed_pickup = client.call(
                "POST", "/api/pickups",
                {"device_id": doomed["id"], "pickup_address": "8 Test Street, Test City 111111",
                 "preferred_date": pickup_date, "preferred_time_slot": slot},
                token=token_a,
            )
            check("a pickup exists for the device about to be deleted", status == 201, f"got {status}")
            check("admin deletes a device", client.call(
                "DELETE", f"/api/devices/{doomed['tracking_id']}", token=admin_token
            )[0] == 204)
            check("the deleted device is gone", client.call(
                "GET", f"/api/devices/{doomed['tracking_id']}")[0] == 404)
            if status == 201:
                check("its pickup request was cascaded away, not orphaned", client.call(
                    "GET", f"/api/pickups/{doomed_pickup['id']}", token=token_a)[0] == 404)
            check("deleting an unknown tracking ID is 404", client.call(
                "DELETE", "/api/devices/EW-1999-0000", token=admin_token)[0] == 404)

    # ------------------------------------------------- valuation unit tests
    if args.unit:
        run_valuation_unit_checks(print_summary=False)
        run_chat_unit_checks(print_summary=False)

    # -------------------------------------------------------------- summary
    section("Summary")
    print(f"  {DIM}This run created {len(created['devices'])} devices and "
          f"{len(created['pickups'])} pickup requests. There is no delete endpoint for "
          f"pickups, so they are left in place as audit evidence; re-running creates new "
          f"timestamped test users.{RESET}")

    return _summarize()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except URLError as error:
        print(f"{RED}Could not reach the backend: {error}{RESET}")
        raise SystemExit(2) from error
