"""Old simulator results remain in SQLite without unbounded process memory."""

from sqlmodel import Session
import pytest

import main
from persistence.repository import Repository
from tests.test_simulation_admission import _owned_admission_engine


@pytest.fixture
def storage(tmp_path_factory):
    with _owned_admission_engine(tmp_path_factory, 'job-cache') as owner:
        yield owner.engine


def test_restore_keeps_recent_jobs_and_db_fallback_for_older_results(storage):
    engine = storage
    original = dict(main.SIM_JOBS)
    try:
        with Session(engine) as session:
            repo = Repository(session)
            for index in range(23):
                repo.save_simulation_job({
                    "job_id": f"cache-{index:02d}", "status": "completed",
                    "completed_matches": 1, "total_matches": 1,
                    "started_at": float(index), "finished_at": float(index),
                    "result": {"matches": 1},
                })
            repo.save_simulation_job({
                "job_id": "old-running", "status": "running",
                "completed_matches": 0, "total_matches": 1, "started_at": -1.0,
            })
            assert len(repo.list_simulation_jobs(limit=20)) == 20
            assert [row.id for row in repo.list_unfinished_simulation_jobs()] == ["old-running"]

            main._restore_simulation_jobs(repo)
            assert len(main.SIM_JOBS) == main.SIM_JOBS_CACHE_LIMIT
            assert "cache-00" not in main.SIM_JOBS
            assert main.simulate_batch_status("cache-00", repo)["result"] == {"matches": 1}
            assert main.simulate_batch_status("old-running", repo)["status"] == "failed"
    finally:
        main.SIM_JOBS.clear()
        main.SIM_JOBS.update(original)


def test_prune_preserves_running_job_while_trimming_terminal_history():
    original = dict(main.SIM_JOBS)
    try:
        main.SIM_JOBS.clear()
        for index in range(23):
            main.SIM_JOBS[f"done-{index}"] = {
                "job_id": f"done-{index}", "status": "completed", "finished_at": float(index),
            }
        main.SIM_JOBS["active"] = {"job_id": "active", "status": "running", "started_at": -1.0}
        with main.SIM_JOBS_LOCK:
            main._prune_simulation_jobs()
        assert len(main.SIM_JOBS) == main.SIM_JOBS_CACHE_LIMIT + 1
        assert "active" in main.SIM_JOBS
        assert "done-0" not in main.SIM_JOBS
    finally:
        main.SIM_JOBS.clear()
        main.SIM_JOBS.update(original)
