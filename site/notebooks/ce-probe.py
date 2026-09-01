"""The probe for open question 1.

Everything Tier 0 promises rests on one request working: a marimo island, running Pyodide,
inside MkDocs Material, on the real host, posting to the Compiler Explorer API and getting a
GIMPLE dump back. This notebook is that request and nothing else.

It runs twice. Once at build time in ordinary CPython, where it renders the page you see
before the runtime starts and never touches the network, and once in the browser when a
reader presses the button.
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import sys
    import time

    import marimo as mo

    # Pyodide reports itself as emscripten. Nothing else does, and this is the only
    # difference between the two places this notebook runs.
    IN_BROWSER = sys.platform == "emscripten"

    COMPILER = "cg162"
    URL = f"https://godbolt.org/api/compiler/{COMPILER}/compile"
    ARGS = "-O2 -fdump-tree-ssa=stderr"
    return ARGS, COMPILER, IN_BROWSER, URL, json, mo, time


@app.cell
def _(COMPILER, IN_BROWSER, mo):
    mo.md(
        f"""
    Runtime is **{"Pyodide, in your browser" if IN_BROWSER else "not started yet"}**.
    Target is Compiler Explorer's `{COMPILER}`, which is GCC 16.2 on x86-64 Linux.
    Nothing here is proxied and nothing is recorded, the request goes straight from this
    page to `godbolt.org`.
    """
    )
    return


@app.cell
def _(mo):
    # L1, the one program the whole book keeps coming back to. Change it to anything.
    L1 = """int f (int n)
{
  int s = 0;
  for (int i = 0; i < n; i++)
    s += i;
  return s;
}
"""

    program = mo.ui.code_editor(value=L1, language="c", label="The program to compile")
    program
    return (program,)


@app.cell
def _(mo):
    go = mo.ui.run_button(label="Compile it on Compiler Explorer")
    go
    return (go,)


@app.cell
async def _(ARGS, IN_BROWSER, URL, go, json, mo, program, time):
    async def compile_it(source: str) -> dict:
        """One POST. In the browser this is `pyfetch`, which is what the question is about."""
        body = json.dumps(
            {
                "source": source,
                "options": {
                    "userArguments": ARGS,
                    "filters": {"execute": False, "labels": True, "commentOnly": True},
                },
                "lang": "c",
                "allowStoreCodeDebug": True,
            }
        )
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if IN_BROWSER:
            from pyodide.http import pyfetch

            response = await pyfetch(URL, method="POST", headers=headers, body=body)
            return await response.json()

        # Build time. There is no answer to give here and no request to make, because CI is
        # never allowed to call the live API. The page renders in its before state instead.
        raise RuntimeError("not in a browser")

    result, elapsed, failure = None, 0.0, None
    if go.value:
        started = time.time()
        try:
            result = await compile_it(program.value)
        except Exception as exc:  # noqa: BLE001
            failure = f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - started

    verdict = mo.md("Press the button. Starting Pyodide takes a few seconds the first time.")
    if failure:
        verdict = mo.md(f"**The request failed.** `{failure}`")
    elif result is not None:
        dump = "\n".join(line.get("text", "") for line in result.get("stderr", []))
        verdict = mo.md(
            f"""
    **It worked.** Exit code {result.get("code")}, {len(dump)} bytes of dump,
    {elapsed:.2f} seconds including the round trip.

    ```c
    {chr(10).join(dump.splitlines()[:24])}
    ```
    """
        )
    verdict
    return


if __name__ == "__main__":
    app.run()
