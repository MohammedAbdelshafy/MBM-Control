from MBM.GLM.swarm_supervisor import JarvisSwarmSupervisor


def test_swarm_manifest_has_core_system_jobs():
    supervisor = JarvisSwarmSupervisor()
    ids = {job["job_id"] for job in supervisor.manifest()}
    assert {"SWARM-GTM-AUDIT", "SWARM-DIALER-AUDIT", "SWARM-SOCIAL-AUDIT",
            "SWARM-REVENUE-AUDIT", "SWARM-DATA-INTEGRITY"} <= ids


def test_mutating_job_is_approval_gated():
    supervisor = JarvisSwarmSupervisor()
    result = supervisor.dispatch("SWARM-APPROVED-IMPLEMENT")
    assert result.status == "WAITING_FOR_JARVIS_APPROVAL"


def test_read_only_sweep_never_contains_mutating_job():
    supervisor = JarvisSwarmSupervisor()
    results = supervisor.run_read_only_sweep()
    assert results
    assert all(r.job_id != "SWARM-APPROVED-IMPLEMENT" for r in results)
