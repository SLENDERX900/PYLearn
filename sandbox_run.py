"""Restricted Python execution for the learning playground (stdout capture, timeout)."""

from __future__ import annotations

import concurrent.futures
import contextlib
import io

_ALLOWED_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
}


def _exec_user_code(code: str, out: io.StringIO) -> None:
    with contextlib.redirect_stdout(out):
        ns: dict[str, object] = {"__builtins__": _ALLOWED_BUILTINS}
        exec(compile(code, "<playground>", "exec"), ns, ns)


def run_python_sandbox(code: str, *, timeout_sec: float = 5.0) -> tuple[str, str | None]:
    """
    Run Python in a restricted namespace. Returns (captured stdout, error message or None).
    """
    if not code.strip():
        return "", None

    buf = io.StringIO()

    def _run() -> str | None:
        try:
            _exec_user_code(code, buf)
        except Exception as exc:  # noqa: BLE001 — surface learner errors
            return f"{type(exc).__name__}: {exc}"
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run)
        try:
            err = fut.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            return "", f"Execution timed out after {timeout_sec:.0f}s. Try a shorter script."
        except Exception as exc:  # noqa: BLE001
            return buf.getvalue(), f"{type(exc).__name__}: {exc}"

    return buf.getvalue(), err
