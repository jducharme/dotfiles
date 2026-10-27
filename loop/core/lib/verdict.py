#!/usr/bin/env python3
"""agent-loop: normalise each reviewer's output and merge it into a round summary.

Standard library only, Python 3.8+ (macOS system python3 is fine).

  verdict.py merge --phase code --round 2 --tag round-2 --tests-exit 0 \
      --run-dir .agent-loop/.runs/004-x/round-2 --reviews-dir specs/004-x/reviews \
      --spec specs/004-x/spec.md --meta "base origin/main @ abc123" gemini codex claude

Exit codes: 0 pass (every reviewer approves, no blocker/major, every AC met, tests green)
            1 changes requested
            2 a reviewer failed to produce a usable verdict
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

SEVERITIES = ["blocker", "major", "minor", "nit"]
BLOCKING = ("blocker", "major")
AC_STATUSES = ["met", "partial", "not_met", "untestable"]
CATEGORIES = ["correctness", "security", "privacy", "tests", "spec-drift",
              "spec-quality", "performance", "maintainability"]
PREFIX = {"gemini": "G", "codex": "C", "claude": "A", "local": "L"}  # custom reviewers use their name
MARKER = "<!-- agent-loop-review -->"


# ---------------------------------------------------------------- parsing

def _json_slice(text):
    """Pull the outermost JSON object out of text that may carry fences or chatter."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        return fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text


def load_raw(path, reviewer=""):
    """Return the reviewer's verdict dict from its raw output file."""
    if not os.path.exists(path):
        raise ValueError("no output file (%s)" % path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    if not raw.strip():
        if reviewer == "gemini":
            raise ValueError("agy printed nothing. Older agy versions drop stdout when it isn't a "
                             "terminal; run `agy update` (1.1.1 or later) and re-run")
        raise ValueError("empty output")
    data = json.loads(_json_slice(raw))
    # claude -p --output-format json wraps the answer:
    #   {"type": "result", "subtype": "success", "is_error": false, "result": "...", ...}
    if isinstance(data, dict) and "verdict" not in data and data.get("type") == "result":
        if data.get("is_error") or str(data.get("subtype") or "success") != "success":
            raise ValueError("claude %s: %s" % (data.get("subtype"), str(data.get("result"))[:600]))
        data = json.loads(_json_slice(data.get("result") or ""))
    # agy --output-format json wraps the answer:
    #   {"status": "SUCCESS", "response": "...", "structured_output": {...}, "error": ..., ...}
    if isinstance(data, dict) and "verdict" not in data and (
            "response" in data or "structured_output" in data or "status" in data or "error" in data):
        status = str(data.get("status") or "SUCCESS").upper()
        if data.get("error") or status != "SUCCESS":
            raise ValueError("agy status %s: %s" % (status, json.dumps(data.get("error"))[:600]))
        if isinstance(data.get("structured_output"), dict):
            data = data["structured_output"]
        else:
            data = json.loads(_json_slice(data.get("response") or ""))
    if not isinstance(data, dict):
        raise ValueError("output is not a JSON object")
    return data


def _enum(value, allowed, default):
    v = str(value or "").strip().lower().replace(" ", "_")
    if v in allowed:
        return v, True
    alt = v.replace("_", "-")
    if alt in allowed:
        return alt, True
    return default, False


def normalise(data, reviewer, round_no, phase):
    verdict, _ = _enum(data.get("verdict"), ["approve", "request_changes"], "request_changes")
    out = {
        "reviewer": reviewer,
        "verdict": verdict,
        "summary": str(data.get("summary") or "").strip(),
        "acceptance_criteria": [],
        "findings": [],
        "missing_tests": [str(t) for t in (data.get("missing_tests") or []) if str(t).strip()],
    }
    for ac in data.get("acceptance_criteria") or []:
        if not isinstance(ac, dict):
            continue
        status, ok = _enum(ac.get("status"), AC_STATUSES, "not_met")
        out["acceptance_criteria"].append({
            "id": str(ac.get("id") or "").strip().upper(),
            "status": status,
            "evidence": str(ac.get("evidence") or "").strip() + ("" if ok else " [unrecognised status]"),
        })
    tag = "S" if phase == "spec" else ""
    for i, f in enumerate(data.get("findings") or [], 1):
        if not isinstance(f, dict):
            continue
        sev, sev_ok = _enum(f.get("severity"), SEVERITIES, "major")
        cat, _ = _enum(f.get("category"), CATEGORIES, "correctness")
        try:
            line = int(f.get("line") or 0)
        except (TypeError, ValueError):
            line = 0
        title = str(f.get("title") or "").strip() or "(untitled)"
        if not sev_ok:
            title = "[unrecognised severity '%s'] %s" % (f.get("severity"), title)
        out["findings"].append({
            "id": "%s%s%d.%d" % (id_prefix(reviewer), tag, round_no, i),
            "severity": sev,
            "category": cat,
            "file": str(f.get("file") or "").strip(),
            "line": line,
            "title": title,
            "detail": str(f.get("detail") or "").strip(),
            "suggested_fix": str(f.get("suggested_fix") or "").strip(),
            "acceptance_criterion": str(f.get("acceptance_criterion") or "").strip().upper(),
        })
    out["findings"].sort(key=lambda x: SEVERITIES.index(x["severity"]))
    return out


def id_prefix(reviewer):
    """G1.2 for gemini, L-DEEPSEEK-1.2 for local/deepseek, XYZ1.2 for a custom reviewer named xyz."""
    if reviewer in PREFIX:
        return PREFIX[reviewer]
    if reviewer.startswith("local-"):
        return "L-%s-" % reviewer[len("local-"):].upper()
    return reviewer.upper()


def spec_ac_ids(spec_path):
    """AC ids the spec *defines*: list items like '- **AC-3**: ...'. Mentions elsewhere (prose,
    HTML comments, test names) don't count, so a stray 'AC-9' can't make a round unpassable."""
    try:
        with open(spec_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    seen = []
    for m in re.finditer(r"(?m)^\s*[-*]\s*\*\*AC-(\d+)\*\*", text):
        ac = "AC-" + m.group(1)
        if ac not in seen:
            seen.append(ac)
    return sorted(seen, key=lambda a: int(a.split("-")[1]))


# ---------------------------------------------------------------- gate

def reviewer_passes(r, ac_ids=()):
    """One reviewer's gate. Every AC declared in the spec must be graded, and graded met:
    an AC the reviewer skipped counts as not met (otherwise an omission would pass vacuously)."""
    if r["verdict"] != "approve":
        return False
    if any(f["severity"] in BLOCKING for f in r["findings"]):
        return False
    if any(a["status"] != "met" for a in r["acceptance_criteria"]):
        return False
    graded = set(a["id"] for a in r["acceptance_criteria"])
    if any(ac not in graded for ac in ac_ids):
        return False
    return True


def log_tail_error(path, limit=300):
    """Last line in a CLI log that looks like an error, so the summary says *why* it failed."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = [l.strip() for l in fh.read().splitlines() if l.strip()]
    except OSError:
        return ""
    hits = [l for l in lines if re.search(r"error|unauthori[sz]ed|denied|not supported|ineligible|login|auth", l, re.I)]
    line = (hits or lines or [""])[-1]
    return line[:limit]


def skipped_checks(run_dir):
    try:
        with open(os.path.join(run_dir, "tests.txt"), encoding="utf-8", errors="replace") as fh:
            return [l.strip() for l in fh if l.startswith("SKIPPED")]
    except OSError:
        return []


# ---------------------------------------------------------------- summary

def _md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_summary(path, args, results, errors, tests_exit, ac_ids, status):
    head = {"pass": "PASS", "changes": "CHANGES REQUESTED", "error": "ERROR"}[status]
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [MARKER, "<!-- agent-loop:status=%s -->" % status, ""]
    L.append("# %s review, round %s: %s" % ("Spec" if args.phase == "spec" else "Code", args.round, head))
    L.append("")
    L.append("%s · %s" % (args.meta, when))
    L.append("")
    if args.phase == "code":
        if tests_exit < 0:
            L.append("**Tests:** not run")
        elif tests_exit == 0:
            skipped = skipped_checks(args.run_dir)
            L.append("**Tests:** passing" + (" (with skips: %s)" % "; ".join(skipped) if skipped else ""))
        else:
            L.append("**Tests:** FAILING (exit %d), which blocks a pass" % tests_exit)
        L.append("")

    L.append("| Reviewer | Verdict | Gate | Blocker | Major | Minor | Nit |")
    L.append("|---|---|---|---|---|---|---|")
    for name in args.reviewers:
        if name in errors:
            L.append("| %s | error | ✗ | | | | |" % name)
            continue
        r = results[name]
        c = {s: sum(1 for f in r["findings"] if f["severity"] == s) for s in SEVERITIES}
        L.append("| %s | %s | %s | %d | %d | %d | %d |" % (
            name, r["verdict"], "✓" if reviewer_passes(r, ac_ids) else "✗",
            c["blocker"], c["major"], c["minor"], c["nit"]))
    L.append("")

    for name in args.reviewers:
        if name in errors:
            L.append("> **%s failed:** %s" % (name, _md(errors[name])))
            L.append("")

    if results:
        L.append("## Acceptance criteria")
        L.append("")
        L.append("| AC | " + " | ".join(n for n in args.reviewers if n in results) + " |")
        L.append("|---|" + "---|" * len([n for n in args.reviewers if n in results]))
        graded = list(ac_ids)
        for r in results.values():
            for a in r["acceptance_criteria"]:
                if a["id"] and a["id"] not in graded:
                    graded.append(a["id"])
        for ac in graded:
            cells = []
            for n in args.reviewers:
                if n not in results:
                    continue
                hit = [a for a in results[n]["acceptance_criteria"] if a["id"] == ac]
                if not hit:
                    cells.append("not graded")
                else:
                    a = hit[0]
                    mark = "✓ met" if a["status"] == "met" else a["status"]
                    cells.append("%s: %s" % (mark, _md(a["evidence"])) if a["evidence"] else mark)
            L.append("| %s | %s |" % (ac, " | ".join(cells)))
        L.append("")

        for n in args.reviewers:
            if n in results and results[n]["summary"]:
                L.append("**%s:** %s" % (n.capitalize(), results[n]["summary"]))
                L.append("")

        allf = [f for n in args.reviewers if n in results for f in results[n]["findings"]]
        allf.sort(key=lambda f: SEVERITIES.index(f["severity"]))
        L.append("## Findings")
        L.append("")
        if not allf:
            L.append("_None._")
            L.append("")
        for f in allf:
            loc = f["file"] + (":%d" % f["line"] if f["file"] and f["line"] else "")
            ac = " · " + f["acceptance_criterion"] if f["acceptance_criterion"] else ""
            L.append("### %s · %s · %s%s%s" % (f["id"], f["severity"], f["category"], ac, (" · `%s`" % loc) if loc else ""))
            L.append("**%s**" % f["title"])
            L.append("")
            if f["detail"]:
                L.append(f["detail"])
                L.append("")
            if f["suggested_fix"]:
                L.append("_Suggested fix:_ " + f["suggested_fix"])
                L.append("")

        missing = []
        for n in args.reviewers:
            if n in results:
                missing += ["(%s) %s" % (n, t) for t in results[n]["missing_tests"]]
        if missing:
            L.append("## Missing tests")
            L.append("")
            L += ["- " + _md(t) for t in missing]
            L.append("")

    if args.phase == "code" and tests_exit > 0:
        tail = os.path.join(args.run_dir, "tests.txt")
        try:
            with open(tail, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()[-40:]
            L += ["## Test output (last 40 lines)", "", "```", *lines, "```", ""]
        except OSError:
            pass

    if status != "pass":
        L.append("---")
        L.append("Next: record a decision for every finding in `log.md` (fix / reject + reason / ask-human), then re-run.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- main

def cmd_merge(args):
    results, errors = {}, {}
    for name in args.reviewers:
        raw = os.path.join(args.run_dir, "%s.out" % name)
        exit_file = os.path.join(args.run_dir, "%s.exit" % name)
        try:
            code = int(open(exit_file).read().strip() or "1")
        except (OSError, ValueError):
            code = 1
        try:
            data = load_raw(raw, name)
            results[name] = normalise(data, name, args.round, args.phase)
            if code != 0:
                # Usable JSON but non-zero exit: keep the verdict, note the exit code.
                results[name]["summary"] += " (CLI exited %d)" % code
        except Exception as exc:  # noqa: BLE001 - surface any failure as a reviewer error
            log = os.path.join(args.run_dir, "%s.log" % name)
            why = log_tail_error(log)
            errors[name] = "%s (exit %d).%s Raw output: %s · log: %s" % (
                exc, code, (" CLI said: `%s`." % why.replace("`", "'")) if why else "", raw, log)

    ac_ids = spec_ac_ids(args.spec)
    if errors:
        status = "error"
    elif args.phase == "code" and args.tests_exit > 0:
        status = "changes"
    elif all(reviewer_passes(results[n], ac_ids) for n in args.reviewers):
        status = "pass"
    else:
        status = "changes"

    # Errors stay in the run dir so they don't burn a round number; real rounds go in reviews/.
    out_dir = args.run_dir if status == "error" else args.reviews_dir
    os.makedirs(out_dir, exist_ok=True)
    for name, r in results.items():
        with open(os.path.join(out_dir, "%s-%s.json" % (args.tag, name)), "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2)
            fh.write("\n")
    summary = os.path.join(out_dir, "%s-summary.md" % args.tag)
    write_summary(summary, args, results, errors, args.tests_exit, ac_ids, status)

    latest = os.path.join(os.path.dirname(os.path.dirname(args.run_dir.rstrip("/"))), "latest-summary.md")
    with open(summary, encoding="utf-8") as src, open(latest, "w", encoding="utf-8") as dst:
        dst.write(src.read())

    sys.stdout.write(open(summary, encoding="utf-8").read())
    sys.stdout.write("\nagent-loop: summary written to %s\n" % summary)
    return {"pass": 0, "changes": 1, "error": 2}[status]


def reviewer_name(value):
    if not re.match(r"^[a-z][a-z0-9_-]*$", value):
        raise argparse.ArgumentTypeError("reviewer names are lowercase letters, digits, _ and -")
    return value


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--phase", choices=["code", "spec"], required=True)
    m.add_argument("--round", type=int, required=True)
    m.add_argument("--tag", required=True)
    m.add_argument("--tests-exit", type=int, default=-1)
    m.add_argument("--run-dir", required=True)
    m.add_argument("--reviews-dir", required=True)
    m.add_argument("--spec", required=True)
    m.add_argument("--meta", default="")
    m.add_argument("reviewers", nargs="+", type=reviewer_name)
    args = p.parse_args(argv)
    return cmd_merge(args)


if __name__ == "__main__":
    sys.exit(main())
