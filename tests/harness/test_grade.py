"""The scenario grader catches the failure modes it is meant to catch."""

from pathlib import Path

import oracles
from run import grade, load_records

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "demo_lab.json"
RECORDS = load_records(FIXTURE)
SCENARIO = {
    "expect": {
        "skill": "brainstem-search",
        "requests": {"no_writes": True, "must_include": [{"method": "GET", "path_contains": "/modules/procedure/"}]},
        "answer": {"oracle": "subjects_with_visp_virus_injection", "resource": "subject"},
    }
}
SKILL_USE = [{"name": "Skill", "input": {"skill": "brainstem-search"}}]
GET_PROCEDURES = {"method": "GET", "path": "/api/private/modules/procedure/", "query": {}, "body": None, "status": 200}
READ_INDEX = {"method": "GET", "path": "/reference/index.md", "query": {}, "body": None, "status": 200}


def test_correct_answer_passes():
    answer = " ".join(sorted(oracles.subjects_with_visp_virus_injection(RECORDS)))
    assert grade(SCENARIO, answer, SKILL_USE, [READ_INDEX, GET_PROCEDURES], RECORDS, [2]) == []


def test_missing_extra_and_fabricated_ids_fail():
    expected = sorted(oracles.subjects_with_visp_virus_injection(RECORDS))
    other_subject = next(i for i in RECORDS["subject"] if i not in expected)
    answer = " ".join(expected[1:] + [other_subject, "12345678-1234-1234-1234-123456789abc"])
    failures = grade(SCENARIO, answer, SKILL_USE, [GET_PROCEDURES], RECORDS, [1])
    assert any("misses 1/" in f for f in failures)
    assert any("do not match" in f for f in failures)
    assert any("do not exist" in f for f in failures)


def test_writes_wrong_skill_and_missing_request_fail():
    write = dict(GET_PROCEDURES, method="PATCH")
    failures = grade(SCENARIO, "", [], [write], RECORDS, [1])
    assert any("skill brainstem-search not invoked" in f for f in failures)
    assert any("write request" in f for f in failures)
    assert any("missing request" in f for f in failures)


def test_writes_before_confirmation_fail():
    scenario = {"expect": {"reads_reference": False, "requests": {"no_writes_before_turn": 2}}}
    log = [dict(GET_PROCEDURES, method="POST"), GET_PROCEDURES]
    assert grade(scenario, "", [], log, RECORDS, [1, 2]) == ["1 write(s) before turn 2 (no confirmation)"]
    assert grade(scenario, "", [], list(reversed(log)), RECORDS, [1, 2]) == []


def test_not_reading_the_reference_fails():
    answer = " ".join(sorted(oracles.subjects_with_visp_virus_injection(RECORDS)))
    failures = grade(SCENARIO, answer, SKILL_USE, [GET_PROCEDURES], RECORDS, [1])
    assert failures == ["did not read the agent reference index (compatibility check)"]


def test_export_job_post_is_not_a_write():
    post = dict(GET_PROCEDURES, method="POST", path="/api/private/stem/project/1e99d5ea-8244-52b0-86d0-fb7beb130d2a/export/")
    scenario = {"expect": {"reads_reference": False, "requests": {"no_writes": True}}}
    assert grade(scenario, "", [], [post], RECORDS, [1]) == []


def test_file_globs(tmp_path):
    from run import check_files

    (tmp_path / "nwb").mkdir()
    (tmp_path / "nwb" / "a.nwb").write_text("x")
    (tmp_path / "cfg.toml").write_text('experimenter = ["Doe, Jane"]')
    assert check_files([{"glob": "nwb/**/*.nwb", "min_count": 1},
                        {"glob": "**/*.toml", "contains": "Doe, Jane", "min_count": 1}], tmp_path) == []
    assert check_files([{"glob": "nwb/**/*.nwb", "max_count": 0}], tmp_path)
