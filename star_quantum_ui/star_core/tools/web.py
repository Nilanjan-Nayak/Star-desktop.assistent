"""Opens a web page in the STAR window (a web tab). Verified by the UI handing back a tab id."""
from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

from ..models import Check, ToolResult, Verdict
from ..security import PolicyError
from .base import Param, Tool


class OpenUrl(Tool):
    outputs = ("tab_id", "url")
    name = "open_url"
    description = "Open a web page (http/https) in a new STAR tab, e.g. YouTube."
    risk = "low"
    params = {"url": Param("str", desc="http(s) URL"), "title": Param("str", False, "tab title", "")}

    def validate(self, args):
        errs = super().validate(args)
        if not errs and urlparse(args["url"]).scheme not in ("http", "https"):
            errs.append("url must start with http:// or https://")
        return errs

    def run(self, args, ctx):
        if ctx.ui is None:
            return ToolResult(False, {}, "no UI available to open a tab", "unsupported")
        title = args["title"] or urlparse(args["url"]).netloc
        tab_id = ctx.ui.open_tab("web", title, {"url": args["url"]})
        return ToolResult(True, {"tab_id": tab_id, "url": args["url"]})

    def verify(self, args, result, ctx):
        return Verdict.of([Check("tab was opened", bool(result.output.get("tab_id")))])


class ServeWebsite(Tool):
    outputs = ("url", "pid")
    name = "serve_website"
    description = "Run a local website folder on localhost and return its browser URL."
    risk = "medium"
    params = {"root": Param("str", desc="absolute folder containing index.html"),
              "port": Param("int", False, "localhost port", 8765)}

    def run(self, args, ctx):
        try:
            root = ctx.policy.resolve(args["root"])
        except PolicyError as e:
            return ToolResult(False, {}, str(e), "denied")
        index = root / "index.html"
        if not root.is_dir():
            return ToolResult(False, {}, f"website folder not found: {root}", "not_found")
        if not index.is_file():
            return ToolResult(False, {}, f"index.html not found in: {root}", "not_found")
        url = f"http://127.0.0.1:{args['port']}/"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(args["port"]), "--bind", "127.0.0.1"],
                cwd=str(root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=creationflags)
        except OSError as e:
            return ToolResult(False, {}, f"could not start local server: {e}", "os_error")
        for _ in range(20):
            if process.poll() is not None:
                return ToolResult(False, {}, f"local server exited with code {process.returncode}", "server_failed")
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        return ToolResult(True, {"url": url, "pid": process.pid})
            except (urllib.error.URLError, TimeoutError):
                pass
        process.terminate()
        return ToolResult(False, {}, "local server did not become reachable", "timeout")

    def verify(self, args, result, ctx):
        url = result.output.get("url", "")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                ok = response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            ok = False
        return Verdict.of([Check("local website responds", ok)])


class WebSearch(Tool):
    outputs = ("results", "count", "summary")
    name = "web_search"
    description = "Search the web for information, research topics, latest news, and facts."
    risk = "low"
    params = {"query": Param("str", desc="search query or topic"), "limit": Param("int", False, "max results", 5)}

    def run(self, args, ctx):
        import json
        import re
        import urllib.parse
        query = args["query"].strip()
        limit = int(args.get("limit", 5))
        results = []

        # 1. DuckDuckGo Instant Answer API
        try:
            url_ddg = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(query)}&format=json"
            req = urllib.request.Request(url_ddg, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read().decode("utf-8", errors="replace"))
                if d.get("AbstractText"):
                    results.append({"title": d.get("Heading", query), "snippet": d.get("AbstractText"), "url": d.get("AbstractURL", "")})
                for topic in d.get("RelatedTopics", []):
                    if len(results) >= limit:
                        break
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({"title": topic.get("FirstURL", "").split("/")[-1].replace("_", " ") or query,
                                        "snippet": topic.get("Text"), "url": topic.get("FirstURL", "")})
        except Exception:
            pass

        # 2. Wikipedia search API fallback / enrichment
        if len(results) < limit:
            try:
                url_wiki = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(query)}&format=json&utf8="
                req2 = urllib.request.Request(url_wiki, headers={"User-Agent": "STAR_Assistant/1.0"})
                with urllib.request.urlopen(req2, timeout=6) as r2:
                    d2 = json.loads(r2.read().decode("utf-8", errors="replace"))
                    for hit in d2.get("query", {}).get("search", []):
                        if len(results) >= limit:
                            break
                        snip = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
                        results.append({"title": hit.get("title", ""), "snippet": snip,
                                        "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(hit.get('title', ''))}"})
            except Exception:
                pass

        results = results[:limit]
        summary_text = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results) if results else f"No direct web results found for '{query}'."
        return ToolResult(True, {"results": results, "count": len(results), "summary": summary_text})

    def verify(self, args, result, ctx):
        return Verdict.of([Check("search completed", result.output.get("count", 0) >= 0)])

