"""Public synthetic canary transport fault; never included in the image."""
import os
import sys

try:
    import atexit
    import hashlib
    import json
    import threading
    import time

    MODE = "constructed-primary-400-v1"
    RUNNER = "/app/pr_agent/servers/github_action_runner.py"
    HOST = "generativelanguage.googleapis.com"
    PRIMARY = "/v1alpha/models/gemini-3.8-flash:generateContent"
    FALLBACK = "/v1alpha/models/gemini-3.5-flash-lite:generateContent"
    _INSTALLED = False
    _STATE = {"primary": 0, "fallback": 0, "fallback_status": None}
    _LOCK = threading.Lock()


    class CanaryStop(BaseException):
        """Bypass native API-error retry handlers with a fixed, safe error."""


    def _event(kind, **fields):
        print("CANARY_TRANSPORT " + json.dumps({
            "kind": kind, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns(),
            **fields,
        }, sort_keys=True), flush=True)


    def _stop(code):
        _event("stop", code=code)
        raise CanaryStop("CANARY_STOP:" + code) from None


    def _classify(request):
        """Return generation kind; no request value is copied into a log."""
        url = request.url
        path = url.path
        is_generation = "generatecontent" in path.lower()
        if not is_generation:
            return None
        if (request.method != "POST" or url.scheme != "https" or
                url.host != HOST or url.port not in (None, 443) or
                url.query or url.fragment or url.userinfo):
            _stop("GENERATION_ROUTE")
        if path == PRIMARY and url.raw_path == PRIMARY.encode("ascii"):
            return "primary"
        if path == FALLBACK and url.raw_path == FALLBACK.encode("ascii"):
            return "fallback"
        _stop("GENERATION_MODEL")


    def _body_witness(request):
        try:
            body = request.content
            if not isinstance(body, bytes) or not body:
                _stop("GENERATION_BODY")
            parsed = json.loads(body)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("contents"), list) or not parsed["contents"]:
                _stop("GENERATION_BODY")
        except CanaryStop:
            raise
        except BaseException:
            _stop("GENERATION_BODY")
        return {"body_bytes": len(body), "body_sha256": hashlib.sha256(body).hexdigest()}


    def _finish():
        if _STATE != {"primary": 1, "fallback": 1, "fallback_status": 200}:
            _event("incomplete", primary=_STATE["primary"], fallback=_STATE["fallback"],
                   fallback_status=_STATE["fallback_status"])
            os._exit(78)
        _event("transport_complete", primary=1, fallback=1, fallback_status=200)


    def install():
        """Install once in the exact native child, without any model-method patch."""
        global _INSTALLED
        if os.environ.get("PR_AGENT_CANARY_TRANSPORT") != MODE or sys.argv[0] != RUNNER:
            _stop("ACTIVATION")
        if _INSTALLED:
            _stop("DUPLICATE_INSTALL")
        import httpx
        original_send = httpx.AsyncClient.send

        async def send(client, request, *args, **kwargs):
            try:
                kind = _classify(request)
            except CanaryStop:
                raise
            except BaseException:
                _stop("HOOK_FAILURE")
            if kind is None:
                return await original_send(client, request, *args, **kwargs)
            try:
                witness = _body_witness(request)
                # No await before reservation: concurrent calls cannot share a slot.
                with _LOCK:
                    if kind == "primary":
                        if _STATE["primary"] or _STATE["fallback"]:
                            _stop("PRIMARY_COUNT")
                        _STATE["primary"] = 1
                    else:
                        if _STATE["primary"] != 1 or _STATE["fallback"]:
                            _stop("FALLBACK_ORDER_COUNT")
                        _STATE["fallback"] = 1
                _event("primary_injected" if kind == "primary" else "fallback_dispatch",
                       ordinal=1 if kind == "primary" else 2, method="POST", host=HOST,
                       path=PRIMARY if kind == "primary" else FALLBACK, **witness)
                if kind == "primary":
                    return httpx.Response(400, json={"error": {
                        "code": 400, "status": "INVALID_ARGUMENT",
                        "message": "Explicit synthetic canary primary transport fault",
                    }}, request=request)
                try:
                    response = await original_send(client, request, *args, **kwargs)
                except BaseException:
                    _stop("FALLBACK_TRANSPORT")
                status = response.status_code
                if type(status) is not int or not 100 <= status <= 599:
                    _stop("FALLBACK_RESPONSE_TYPE")
                _STATE["fallback_status"] = status
                _event("fallback_response", ordinal=2, status=status)
                if status != 200:
                    _stop("FALLBACK_STATUS")
                return response
            except CanaryStop:
                raise
            except BaseException:
                _stop("HOOK_FAILURE")

        httpx.AsyncClient.send = send
        _INSTALLED = True
        atexit.register(_finish)
        _event("installed", mode=MODE)


    # The alias parent has argv[0] == '-c' and must remain unpatched. An explicit
    # alias-parent preflight rejects a wholly missing startup file before exec.
    if os.environ.get("PR_AGENT_CANARY_TRANSPORT") == MODE and sys.argv[0] == RUNNER:
        try:
            install()
        except BaseException:
            _event("startup_failed", code="INSTALL")
            os._exit(78)

except BaseException:
    if (os.environ.get("PR_AGENT_CANARY_TRANSPORT") == "constructed-primary-400-v1"
            and sys.argv[0] == "/app/pr_agent/servers/github_action_runner.py"):
        os.write(2, b"CANARY_STARTUP_FAILED\n")
        os._exit(78)
    raise
