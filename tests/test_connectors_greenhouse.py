from aeroapply.connectors.greenhouse import GreenhouseConnector, _infer_remote, _strip_html

FAKE = {
    "id": 12345,
    "title": "  Senior AI Product Manager  ",
    "location": {"name": "Remote - US"},
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
    "updated_at": "2026-05-30T12:00:00-04:00",
    "content": "&lt;p&gt;Build &lt;strong&gt;AI&lt;/strong&gt; products.&lt;/p&gt;",
}


def test_strip_html_unescapes_then_strips_tags():
    assert _strip_html("&lt;p&gt;Hello &amp; bye&lt;/p&gt;") == "Hello & bye"


def test_infer_remote():
    assert _infer_remote("Remote - US") == "remote"
    assert _infer_remote("Hybrid - NYC") == "hybrid"
    assert _infer_remote("New York, NY") is None
    assert _infer_remote(None) is None


def test_normalize_maps_greenhouse_fields():
    [p] = GreenhouseConnector("acme", company="Acme").normalize([FAKE])
    assert p.title == "Senior AI Product Manager"   # trimmed
    assert p.company == "Acme"
    assert p.external_id == "12345"
    assert p.location == "Remote - US"
    assert p.remote_mode == "remote"
    assert p.portal_type == "greenhouse"
    assert p.url == FAKE["absolute_url"]
    assert "Build AI products." in p.description     # HTML stripped
    assert len(p.fingerprint()) == 64
    assert p.posted_at is not None and p.posted_at.year == 2026
