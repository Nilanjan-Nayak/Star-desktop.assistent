"""Benchmark test for the 10-section Agent Permanent Skill Set.
Tests language detection, Brain intent analysis, and Planner tool selection for representative commands.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import time
from star_core.config import Config
from star_core.llm import ModelRouter, OllamaClient, OpenRouterClient
from star_core.brain import Brain, Planner
from star_core.tools import default_registry
from star_core.text import detect_language

def run_tests():
    cfg = Config.load()
    local = OllamaClient(cfg.ollama_url, cfg.ollama_model)
    key = cfg.openrouter_api_key
    cloud = OpenRouterClient(key, cfg.openrouter_model) if key else None
    router = ModelRouter(local, cloud, cfg)
    brain = Brain(router, cfg)
    reg = default_registry()
    planner = Planner(router, reg, cfg.roots)

    test_cases = [
        # SECTION 1 & 5: Greetings / Identity / Chat
        {"sec": "SEC 1 & 5: Core / Voice Chat", "query": "kemon acho tumi?", "type": "chat", "expect_intent": "chat", "needs_plan": False},
        {"sec": "SEC 1 & 5: Identity", "query": "tumi ke ar tomar naam ki?", "type": "chat", "expect_intent": "chat", "needs_plan": False},

        # SECTION 2: File & Folder Management
        {"sec": "SEC 2: Save File", "query": "Desktop e ekta notes.txt file a ei data ta save koro: Hello World", "type": "action", "expect_tools": ["write_text"], "needs_plan": True},
        {"sec": "SEC 2: Read File", "query": "Desktop e thaka notes.txt file ta poro ar summary dao", "type": "action", "expect_tools": ["read_text"], "needs_plan": True},
        {"sec": "SEC 2: Find Files", "query": "Downloads folder a sob pdf file khuje ber koro", "type": "action", "expect_tools": ["find_files"], "needs_plan": True},
        {"sec": "SEC 2: Folder Tree", "query": "Desktop folder er list dekhao", "type": "action", "expect_tools": ["list_dir"], "needs_plan": True},

        # SECTION 3: Web Research
        {"sec": "SEC 3: Web Research", "query": "AI agent framework niye web research koro ar data dao", "type": "research", "expect_tools": ["web_search"], "needs_plan": True},
        {"sec": "SEC 3: Compare", "query": "React vs Next.js compare koro table format e", "type": "chat_or_research"},

        # SECTION 4: Web Build & Dev
        {"sec": "SEC 4: Create Website", "query": "Desktop e ekta portfolio website banai deo", "type": "action", "expect_tools": ["write_text", "make_dir"], "needs_plan": True},
        {"sec": "SEC 4: Python Code", "query": "Desktop e ekta python script lekho jeta fibonacci number ber kore", "type": "action", "expect_tools": ["write_text"], "needs_plan": True},

        # SECTION 6: Self-Improvement & Code Management
        {"sec": "SEC 6: Self Code Inspect", "query": "nijer code folder e ki ki file ache khuje ber koro", "type": "action"},

        # SECTION 7: Data Verification
        {"sec": "SEC 7: Data Verify", "query": "ei news ta real kina verify koro: Python 4 release hoye geche", "type": "chat_or_research"},

        # SECTION 8: Multi-Tasking
        {"sec": "SEC 8: Multi-Task", "query": "Desktop e test_proj folder banao ar tar moddhe app.py file likho", "type": "action", "expect_tools": ["make_dir", "write_text"], "needs_plan": True},

        # SECTION 9: Search & Info
        {"sec": "SEC 9: Local Search", "query": "Downloads folder e text file khuje ber koro", "type": "action", "expect_tools": ["find_files"], "needs_plan": True},

        # SECTION 10: Translation & Reporting
        {"sec": "SEC 10: Translation", "query": "ei line ta English e translate koro: ami tomake bhalobashi", "type": "chat", "needs_plan": False},
    ]

    results = []
    print(f"Total Test Cases: {len(test_cases)}")
    print("=" * 60)

    for i, tc in enumerate(test_cases, 1):
        q = tc["query"]
        lang = detect_language(q)
        print(f"\n[{i}/{len(test_cases)}] Testing: '{q}' ({tc['sec']})")
        print(f"    Detected Language: {lang}")
        
        t0 = time.time()
        try:
            analysis = brain.analyze(q, cloud_ok=False)
            dt = time.time() - t0
            print(f"    Analysis ({dt:.2f}s): intent={analysis.intent}, needs_plan={analysis.needs_plan}, risk={analysis.risk}")
            
            passed = True
            reasons = []

            if "needs_plan" in tc and analysis.needs_plan != tc["needs_plan"]:
                # If expecting chat but got plan or vice-versa
                if tc["needs_plan"] is False and analysis.needs_plan is True:
                    passed = False
                    reasons.append(f"Expected needs_plan=False, got True")
                elif tc["needs_plan"] is True and analysis.needs_plan is False:
                    passed = False
                    reasons.append(f"Expected needs_plan=True, got False")

            if analysis.needs_plan:
                t1 = time.time()
                plan = planner.plan(analysis, q, "", "", cloud_ok=False)
                dt_plan = time.time() - t1
                tools_used = [s.tool for s in plan.steps]
                print(f"    Plan ({dt_plan:.2f}s): tools={tools_used}")
                if "expect_tools" in tc:
                    for et in tc["expect_tools"]:
                        if et not in tools_used:
                            passed = False
                            reasons.append(f"Expected tool '{et}' missing in {tools_used}")
            else:
                if analysis.direct_answer:
                    print(f"    Direct Answer: {analysis.direct_answer[:60]}...")
                else:
                    ans = brain.answer(q, lang, cloud_ok=False)
                    print(f"    Generated Answer: {ans[:60]}...")

            status = "PASS" if passed else "FAIL"
            if not passed:
                print(f"    >>> ISSUE: {', '.join(reasons)}")
            results.append({"tc": tc, "passed": passed, "reasons": reasons, "dt": dt})
        except Exception as e:
            print(f"    >>> EXCEPTION: {e}")
            results.append({"tc": tc, "passed": False, "reasons": [str(e)], "dt": 0})

    pass_count = sum(1 for r in results if r["passed"])
    accuracy = (pass_count / len(results)) * 100
    print("\n" + "=" * 60)
    print(f"TEST SUMMARY: {pass_count}/{len(results)} PASSED ({accuracy:.1f}%)")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
