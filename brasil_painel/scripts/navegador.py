"""Drive headless Chromium over CDP to check interactions (dev tool, no new deps).

Usage:
  python scripts/navegador.py URL SAIDA.png [--js "código"]... [--largura 1280 --altura 900]
      [--espera 8] [--cookie nome=valor]

Each --js runs in the page after it settles (e.g. a click), followed by a short
pause; the screenshot is taken at the end and the value of the last --js printed.
Uses port 9333 (outside the forbidden 8000–8050 / 9000–9050 ranges).
"""

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request

import websockets

PORTA = 9333


async def _rodar(args) -> None:
    async with websockets.connect(_alvo(), max_size=None) as ws:
        contador = 0

        async def cdp(metodo, **params):
            nonlocal contador
            contador += 1
            await ws.send(
                json.dumps({"id": contador, "method": metodo, "params": params})
            )
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == contador:
                    return msg.get("result", {})

        await cdp("Emulation.setDeviceMetricsOverride", width=args.largura, height=args.altura,
                  deviceScaleFactor=1, mobile=args.largura < 600)  # fmt: skip
        for cookie in args.cookie:
            nome, valor = cookie.split("=", 1)
            await cdp("Network.setCookie", name=nome, value=valor, url=args.url)
        await cdp("Page.navigate", url=args.url)
        await asyncio.sleep(args.espera)
        resultado = None
        for codigo in args.js:
            r = await cdp(
                "Runtime.evaluate",
                expression=codigo,
                returnByValue=True,
                awaitPromise=True,
            )
            resultado = r.get("result", {}).get("value")
            await asyncio.sleep(1.5)
        tela = await cdp("Page.captureScreenshot", format="png")
        with open(args.saida, "wb") as f:
            f.write(base64.b64decode(tela["data"]))
        if resultado is not None:
            print(json.dumps(resultado, ensure_ascii=False))  # noqa: T201 - CLI output


def _alvo() -> str:
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json/list") as r:
                paginas = [p for p in json.load(r) if p["type"] == "page"]
            if paginas:
                return paginas[0]["webSocketDebuggerUrl"]
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Chromium não abriu a porta de depuração")


def main() -> None:
    """Entry point."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("url")
    p.add_argument("saida")
    p.add_argument("--js", action="append", default=[])
    p.add_argument("--largura", type=int, default=1280)
    p.add_argument("--altura", type=int, default=900)
    p.add_argument("--espera", type=float, default=8)
    p.add_argument("--cookie", action="append", default=[])
    args = p.parse_args()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as perfil:
        chromium = subprocess.Popen(  # noqa: S603 - fixed local browser binary
            [shutil.which("chromium") or "chromium", "--headless", "--no-sandbox", "--disable-gpu",
             "--hide-scrollbars", f"--remote-debugging-port={PORTA}", f"--user-data-dir={perfil}",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        try:
            asyncio.run(_rodar(args))
        finally:
            chromium.terminate()
            chromium.wait(timeout=10)


if __name__ == "__main__":
    main()
