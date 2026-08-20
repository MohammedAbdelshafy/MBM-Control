from MBM.LeadEngine.qualification_runner import qualify_leads


def test_qualification_runner_reports_passes_and_rejections_without_mutation():
    report = qualify_leads([
        {
            "contact_name": "Dr Ada Lovelace",
            "phone": "+12148901234",
            "source": "CMS NPI Registry",
        },
        {
            "contact_name": "Test Contact",
            "phone": "+12148901234",
            "source": "CMS NPI Registry",
        },
    ])

    assert report["status"] == "success"
    assert report["inputs"]["lead_count"] == 2
    assert report["outputs"]["passed_count"] == 1
    assert report["outputs"]["rejected_count"] == 1
    assert report["outputs"]["results"][0]["passed"] is True
    assert report["outputs"]["results"][1]["passed"] is False
    assert "name:fake_name_marker:test" in report["outputs"]["results"][1]["rejection_reasons"]


def test_qualification_runner_can_include_original_leads_for_delivery_reports():
    lead = {
        "contact_name": "Dr Grace Hopper",
        "phone": "+12148901235",
        "source": "NPI",
    }

    report = qualify_leads([lead], include_leads=True)

    assert report["outputs"]["results"][0]["lead"] == lead
