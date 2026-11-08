import pytest

from framediet.toon import slim_html_dom, to_toon


def test_uniform_array_is_tabular():
    data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    assert to_toon(data, name="rows") == "rows[2]{id,name}:\n  1,a\n  2,b"


def test_non_uniform_array_keeps_all_fields():
    data = [{"id": 1}, {"id": 2, "extra": "x"}]
    out = to_toon(data, name="rows")
    assert "extra" in out
    assert "{id}" not in out


def test_primitive_array_inline():
    assert to_toon([1, 2, 3], name="n") == "n[3]: 1,2,3"


def test_ambiguous_strings_are_quoted():
    out = to_toon({"a": "true", "b": "42", "c": "x,y", "d": ""})
    assert 'a: "true"' in out
    assert 'b: "42"' in out
    assert 'c: "x,y"' in out
    assert 'd: ""' in out


def test_non_finite_float_becomes_null():
    assert to_toon({"x": float("nan")}) == "x: null"


def test_precision_rounds_floats():
    assert to_toon({"x": 1.23456}, precision=2) == "x: 1.23"


def test_negative_precision_rejected():
    with pytest.raises(ValueError):
        to_toon({"x": 1}, precision=-1)


def test_non_string_keys_rejected():
    with pytest.raises(ValueError):
        to_toon({1: "a"})


def test_nested_object_indents():
    assert to_toon({"a": {"b": 1}}) == "a:\n  b: 1"


def test_html_slimming_replaces_payloads():
    html = (
        "<div><svg><path d=\"" + "M0 0 L1 1 " * 20 + "\"/></svg>"
        "<img src=\"data:image/png;base64,AAAA\"/>"
        "<script>alert(1)</script><style>a{b:c}</style></div>"
    )
    out = slim_html_dom(html)
    assert "[SVG_PATH]" in out
    assert "[BASE64_DATA_URI]" in out
    assert "alert(1)" not in out
    assert "a{b:c}" not in out
