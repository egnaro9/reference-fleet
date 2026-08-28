"""Gate liveness: every publication-path refusal must PROVE it can fire.

Doctrine (the verifying-guardrails lesson): a gate that has only ever seen
clean input is indistinguishable from a gate that never ran. Each test here
feeds a CORRUPTED input and asserts the refusal fires, paired with a
happy-path twin proving the same gate stays quiet on clean input.
"""

import importlib.util
import json
import pathlib
import subprocess
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("run_audit", ROOT / "audit" / "run_audit.py")
run_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_audit)


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(repo), *args],
        capture_output=True, text=True, check=True)


@pytest.fixture
def code_repo(tmp_path):
    """A minimal repo whose HEAD commit touches a stamped CODE path."""
    (tmp_path / "reference_fleet").mkdir()
    (tmp_path / "reference_fleet" / "core.py").write_text("x = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "code")
    return tmp_path


# --------------------------------------------------------------------------
# Gate 1: the dirty-tree stamp refusal.
def test_dirty_tree_refuses_to_stamp(code_repo):
    (code_repo / "reference_fleet" / "core.py").write_text("x = 2\n")
    with pytest.raises(RuntimeError, match="refusing to stamp a dirty tree"):
        run_audit.stamp_code_commit(code_repo)


def test_clean_tree_stamps_the_code_commit(code_repo):
    expected = _git(code_repo, "log", "-1", "--format=%h").stdout.strip()
    assert run_audit.stamp_code_commit(code_repo) == expected


def test_board_only_dirt_is_allowed(code_repo):
    # board/ is the audit's OUTPUT; a dirty board must not block its own stamp
    (code_repo / "board").mkdir()
    (code_repo / "board" / "results.json").write_text("{}")
    assert run_audit.stamp_code_commit(code_repo)


# --------------------------------------------------------------------------
# Gate 2: the missing-code-commit-stamp refusal.
def test_no_code_commit_refuses_to_stamp(tmp_path):
    (tmp_path / "README.md").write_text("no stamped path ever committed\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "docs only")
    with pytest.raises(RuntimeError, match="no code commit"):
        run_audit.stamp_code_commit(tmp_path)


# --------------------------------------------------------------------------
# Gate 3: the partial-promptfoo-results refusal.
def _pf_data(members, n, drop=0):
    results = [{"vars": {"member": m, "mode": mode, "i": str(i)},
                "success": True, "gradingResult": {"pass": True}}
               for m in members for mode in ("clean", "defective") for i in range(n)]
    return {"results": {"results": results[:-drop] if drop else results}}


def test_partial_promptfoo_output_refuses_to_publish():
    with pytest.raises(RuntimeError, match="partial board"):
        run_audit.parse_promptfoo_results(_pf_data(["m1"], 3, drop=1), ["m1"], 3)


def test_errored_rows_count_toward_partial():
    data = _pf_data(["m1"], 2)
    data["results"]["results"][0]["gradingResult"] = None  # a real error, not a grade
    with pytest.raises(RuntimeError, match="partial board"):
        run_audit.parse_promptfoo_results(data, ["m1"], 2)


def test_full_promptfoo_output_parses_every_cell():
    res = run_audit.parse_promptfoo_results(_pf_data(["m1", "m2"], 3), ["m1", "m2"], 3)
    assert len(res) == 12 and res[("m1", "clean", 0)] is True


# --------------------------------------------------------------------------
# Gate 4: the stale-out.json guard — a leftover file must never grade a run.
def test_stale_out_json_cannot_grade_a_failed_run(tmp_path, monkeypatch):
    work = tmp_path / "pf"
    work.mkdir()
    (work / "out.json").write_text(json.dumps(_pf_data(["m1"], 1)))  # stale, complete

    def fake_run(cmd, **kw):  # the npx run dies without producing out.json
        return types.SimpleNamespace(stdout="", stderr="worker died")

    monkeypatch.setattr(run_audit.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="promptfoo produced no output"):
        run_audit.run_promptfoo(["m1"], 1, work=work)
    assert not (work / "out.json").exists()  # the stale file was destroyed, not read


def test_fresh_out_json_is_what_grades_the_run(tmp_path, monkeypatch):
    work = tmp_path / "pf"
    work.mkdir()
    (work / "out.json").write_text(json.dumps(_pf_data(["stale-member"], 9)))
    fresh = _pf_data(["m1"], 2)

    def fake_run(cmd, **kw):
        assert not (pathlib.Path(kw["cwd"]) / "out.json").exists()  # gone BEFORE the run
        (pathlib.Path(kw["cwd"]) / "out.json").write_text(json.dumps(fresh))
        return types.SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(run_audit.subprocess, "run", fake_run)
    res = run_audit.run_promptfoo(["m1"], 2, work=work)
    assert set(res) == {("m1", mode, i) for mode in ("clean", "defective")
                        for i in range(2)}


# --------------------------------------------------------------------------
# Gate 5: the JS provider's missing-fleet-response throw, driven by real node.
def _drive_provider(tmp_path, responses, member="m1", mode="clean", i="0"):
    (tmp_path / "fleet_provider.js").write_text(run_audit.PROMPTFOO_PROVIDER)
    (tmp_path / "responses.json").write_text(json.dumps(responses))
    ctx = json.dumps({"vars": {"member": member, "mode": mode, "i": i}})
    driver = (
        "const P = require(" + json.dumps(str(tmp_path / "fleet_provider.js")) + ");"
        "new P().callApi('q', " + ctx + ")"
        ".then(r => process.stdout.write('OK:' + r.output))"
        ".catch(e => { process.stderr.write('THREW:' + e.message); process.exit(42); });")
    return subprocess.run(["node", "-e", driver], capture_output=True, text=True)


def test_provider_throws_on_a_missing_fleet_response(tmp_path):
    proc = _drive_provider(tmp_path, {"m1|clean|1": "ANSWER(q)"})  # key 0 absent
    assert proc.returncode == 42
    assert "THREW:missing fleet response for m1|clean|0" in proc.stderr


def test_provider_returns_the_recorded_response_when_present(tmp_path):
    proc = _drive_provider(tmp_path, {"m1|clean|0": "ANSWER(question 0)"})
    assert proc.returncode == 0
    assert proc.stdout == "OK:ANSWER(question 0)"


# --------------------------------------------------------------------------
# Gate 6: the VAC bundle's freshness coupling. board/vac/ is DERIVED —
# aggregates from the rows, sha256s from the artifact bytes — so the same
# byte-diff re-run that guards results.json guards the manifest: each tamper
# twin proves the re-emit diverges from the lie; the clean twin proves an
# honest manifest re-emits byte-identically (the gate stays quiet).
def _mini_result():
    return {"schema": 1, "protocol": "paired: test protocol",
            "fleet_commit": "abc1234", "rows": [
                {"suite": "s1", "member": "m1", "n": 4, "detected": 2,
                 "detection_rate": 0.5, "false_alarms": 1,
                 "false_alarm_rate": 0.25, "engine": "e1"},
                {"suite": "s1", "member": "m2", "n": 4, "detected": 4,
                 "detection_rate": 1.0, "false_alarms": 0,
                 "false_alarm_rate": 0.0, "engine": "e1"},
                {"suite": "s2", "member": "m1", "n": 2, "detected": 1,
                 "detection_rate": 0.5, "false_alarms": 0,
                 "false_alarm_rate": 0.0, "engine": "e2"},
            ]}


def _mini_raw():
    """Raw lines matching _mini_result row for row. 3.2 refuses a row with no
    raw lines and a raw group with no row alike, and emit_vac now splits both
    by suite, so the two must agree."""
    out = []
    for r in _mini_result()["rows"]:
        for i in range(r["n"]):
            det = i < r["detected"]
            clean = i >= r["false_alarms"]
            out.append({"suite": r["suite"], "member": r["member"], "i": i,
                        "defective_failed": det, "clean_passed": clean,
                        "detected": det and clean})
    return out


def _emit(board, result, raw=None):
    (board / "results.json").write_text(json.dumps(result, indent=1))
    raw = _mini_raw() if raw is None else raw
    (board / "raw_results.jsonl").write_text(
        "\n".join(json.dumps(r, separators=(",", ":")) for r in raw) + "\n")
    run_audit.emit_vac(result, raw, board=board)
    return (board / "vac" / "vac.json").read_bytes()


def test_summary_is_a_pure_function_of_each_suites_own_rows():
    """Now keyed by DERIVED scope, two levels deep, every field suite_*.

    The old shape nested under `suites` and put `rows` at the top; neither
    could bind at 0.2. `rows` and `suites` are gone entirely: no per-suite
    check recomputes them, so they are non-claims rather than rehomed."""
    result = _mini_result()
    splits = run_audit.split_by_suite(result, _mini_raw())
    s = run_audit.vac_summary(splits)
    assert s == run_audit.vac_summary(
        run_audit.split_by_suite(result, _mini_raw()))   # same in, same out
    assert set(s) == {"s1", "s2"}
    assert s["s1"] == {"suite_members": 2, "suite_n": 8, "suite_detected": 6,
                       "suite_false_alarms": 1, "suite_detection_rate": 0.75,
                       "suite_false_alarm_rate": 0.125}
    assert not any(k in s for k in ("rows", "suites")), \
        "board-level values are deliberate non-claims at 0.2"
    drifted = json.loads(json.dumps(result))
    drifted["rows"][0]["detected"] += 1  # one row moves -> the summary moves
    assert run_audit.vac_summary(
        run_audit.split_by_suite(drifted, _mini_raw())) != s


def test_the_emitter_refuses_a_member_level_claim():
    """The quiet hazard. member_detection_rate EXISTS in the 0.2 pool, so a
    member value would BIND and the bundle would verify while asserting a
    per-member number this board does not mean to make. Shape guards would
    not catch it: it is the right depth under the right scope."""
    man = {"results": {"checks": [{"aggregate": "s1.json"}],
                       "summary": {"s1": {"member_detection_rate": 1.0}}}}
    with pytest.raises(ValueError, match="not a suite_. field"):
        run_audit._refuse_unpublishable_summary(man)


def test_the_emitter_refuses_a_summary_deeper_than_scope_field():
    man = {"results": {"checks": [{"aggregate": "s1.json"}],
                       "summary": {"s1": {"suite_holes": {"blind": 2}}}}}
    with pytest.raises(ValueError, match="nests deeper"):
        run_audit._refuse_unpublishable_summary(man)


def test_manifest_pins_the_stamp_and_the_real_artifact_bytes(tmp_path):
    vac = json.loads(_emit(tmp_path, _mini_result()))
    assert vac["protocol"]["issuer_commit"] == "abc1234" \
        == vac["replay"]["issuer_commit"] \
        == vac["protocol"]["hashes"]["fleet_commit"]
    import hashlib
    # evidence is now the per-suite splits, sorted; results.json is no longer
    # VAC evidence at all, because a whole-board check is what merged the
    # suites into one pool
    assert [e["path"] for e in vac["evidence"]] == [
        "s1.json", "s1.jsonl", "s2.json", "s2.jsonl"]
    for e in vac["evidence"]:
        assert e["sha256"] == hashlib.sha256(
            (tmp_path / e["path"]).read_bytes()).hexdigest()
    assert vac["claim"]["limitations"]  # non-claims are mandatory (SPEC 2.1)


def test_clean_re_emit_is_byte_identical(tmp_path):
    result = _mini_result()
    first = _emit(tmp_path, result)
    run_audit.emit_vac(result, _mini_raw(), board=tmp_path)
    assert (tmp_path / "vac" / "vac.json").read_bytes() == first  # gate stays quiet


def test_wrong_artifact_sha256_is_caught_by_the_re_emit(tmp_path):
    result = _mini_result()
    _emit(tmp_path, result)
    vac = json.loads((tmp_path / "vac" / "vac.json").read_text())
    assert vac["evidence"][0]["sha256"] != "0" * 64
    vac["evidence"][0]["sha256"] = "0" * 64  # a published lie about the bytes
    (tmp_path / "vac" / "vac.json").write_text(json.dumps(vac, indent=1))
    tampered = (tmp_path / "vac" / "vac.json").read_bytes()
    run_audit.emit_vac(result, _mini_raw(), board=tmp_path)  # freshness re-run
    assert (tmp_path / "vac" / "vac.json").read_bytes() != tampered  # git diff fires


def test_drifted_aggregate_is_caught_by_the_re_emit(tmp_path):
    result = _mini_result()
    _emit(tmp_path, result)
    vac = json.loads((tmp_path / "vac" / "vac.json").read_text())
    vac["results"]["summary"]["s1"]["suite_detected"] += 1  # re-authored
    (tmp_path / "vac" / "vac.json").write_text(json.dumps(vac, indent=1))
    tampered = (tmp_path / "vac" / "vac.json").read_bytes()
    run_audit.emit_vac(result, _mini_raw(), board=tmp_path)
    assert (tmp_path / "vac" / "vac.json").read_bytes() != tampered
