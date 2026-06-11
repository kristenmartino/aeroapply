from aeroapply.sourcing.geocoding import Geocoder, normalize_location


def test_normalize_strips_mode_words_and_expands_state():
    assert normalize_location("Hybrid - Tampa, FL") == "tampa, fl"
    assert normalize_location("Tampa, Florida") == "tampa, fl"
    assert normalize_location("Remote - San Francisco, CA, USA") == "san francisco, ca"
    assert normalize_location("  WEST PALM BEACH , fl ") == "west palm beach, fl"


def test_normalize_returns_empty_for_placeless_strings():
    assert normalize_location("Remote") == ""
    assert normalize_location("Anywhere") == ""
    assert normalize_location(None) == ""
    assert normalize_location("") == ""


def test_static_geocode_resolves_known_city_and_misses_unknown():
    g = Geocoder()
    assert g.geocode("West Palm Beach, FL") is not None
    assert g.geocode("Hybrid - Tampa, FL") == g.geocode("Tampa, Florida")  # normalize to same
    assert g.geocode("Nowhereville, ZZ") is None  # no static entry, no fallback


def test_geocode_caches_and_calls_fallback_once_per_string():
    calls: list[str] = []

    def fallback(key: str):
        calls.append(key)
        return (1.0, 2.0)

    g = Geocoder(static={}, fallback=fallback)
    assert g.geocode("Smalltown, ND") == (1.0, 2.0)
    assert g.geocode("Smalltown, ND") == (1.0, 2.0)   # cache hit, no second call
    assert g.geocode("smalltown,  north dakota") == (1.0, 2.0)  # normalizes to same key
    assert calls == ["smalltown, nd"]


def test_fallback_only_consulted_on_static_miss():
    calls: list[str] = []

    def fallback(key: str):
        calls.append(key)
        return (0.0, 0.0)

    g = Geocoder(fallback=fallback)  # default static table
    g.geocode("Seattle, WA")  # in the static table -> fallback not used
    assert calls == []


def test_fallback_failure_is_swallowed():
    def boom(key: str):
        raise RuntimeError("network down")

    g = Geocoder(static={}, fallback=boom)
    assert g.geocode("Anytown, KS") is None  # error -> None, never raises
