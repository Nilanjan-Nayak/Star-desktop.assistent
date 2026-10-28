import urllib.request
import urllib.parse
import re

q = "AI agent framework"
url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(q)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", errors="ignore")
    results = []
    # DuckDuckGo HTML format: <a class="result__snippet" ...>...</a> and <a class="result__url" ...>...</a>
    for snippet_match in re.finditer(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.S):
        clean_snip = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
        results.append(clean_snip)
    print("Found snippets:", len(results))
    if results:
        print("First snippet:", results[0][:150])
except Exception as e:
    print("Error:", e)
