import pathlib, tempfile
from MBM.LeadEngine.intelligence.topview_adapter import TopviewAdapter
from MBM.LeadEngine.intelligence.skysnail_adapter import SkySnailAdapter
from MBM.LeadEngine.intelligence.jobs import JobStore

def test_topview_without_key_blocks_not_fabricates():
    store = JobStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
    tv = TopviewAdapter(api_key="", store=store)
    job = tv.create_generation_job(hook="Hook A", script="Script body", opportunity_id="opp_1")
    assert job.status == "BLOCKED"
    assert job.errorCode == "NOT_CONFIGURED"
    # idempotency: second call returns same inputHash job not a new fabrication
    job2 = tv.create_generation_job(hook="Hook A", script="Script body", opportunity_id="opp_1")
    assert job2.id == job.id

def test_skysnail_without_key_returns_no_variants():
    store = JobStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
    ss = SkySnailAdapter(api_key="", store=store)
    ss.variant_path = pathlib.Path(tempfile.mktemp(suffix=".json"))
    variants = ss.generate_variants(source_asset_id="clip1", topic="Test topic", count=3)
    assert variants == []

def test_skysnail_variant_persistence_roundtrip():
    import json
    store = JobStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
    ss = SkySnailAdapter(api_key="fake", store=store)
    tmp = pathlib.Path(tempfile.mktemp(suffix=".json"))
    ss.variant_path = tmp
    # inject normalized variants via private helper
    fake_data = {"data": [{"id": "v1", "url": "https://cdn/x.jpg"}, {"id": "v2", "url": "https://cdn/y.jpg"}]}
    vs = ss._normalize_variants(fake_data, "src1", "youtube", "exp1")
    ss._persist_variants(vs)
    ss.record_result("v1", ctr=0.12, views=1000)
    content = json.loads(tmp.read_text(encoding="utf-8"))
    v1 = next(x for x in content if x["variantId"] == "v1")
    assert v1["status"] == "measured"
    assert v1["metrics"]["ctr"] == 0.12
