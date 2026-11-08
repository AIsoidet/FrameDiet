import re
import subprocess
import sys
from pathlib import Path

from framediet.toon import slim_html_dom

CLASSES = " ".join(f"sx-{i:05x}" for i in range(20))
HTML = (
    f'<div class="{CLASSES}" style="color:red;background:url(x.png) no-repeat;margin:0 auto;padding:10px 20px 30px">'
    f'<h1 class="short">Hello world</h1><p class="{CLASSES}">Visible text class="{CLASSES}" stays</p></div>'
)


def test_default_output_unchanged():
    out = slim_html_dom(HTML)
    assert out == HTML


def test_strip_classes_collapses_long_only():
    out = slim_html_dom(HTML, strip_classes=True)
    assert out.count("[CLASSES_OMITTED:20]") == 2
    assert 'class="short"' in out
    assert "sx-00000" not in out.split("Visible")[0]
    assert "style=" in out and "color:red" in out


def test_visible_text_preserved():
    out = slim_html_dom(HTML, strip_classes=True, strip_styles=True)
    assert re.sub(r"<[^>]+>", "", out) == re.sub(r"<[^>]+>", "", HTML)
    assert f'class="{CLASSES}" stays' in out  # text node, not an attribute


def test_strip_styles_and_threshold():
    out = slim_html_dom(HTML, strip_styles=True)
    assert 'style="[STYLE_OMITTED]"' in out
    assert CLASSES in out
    assert slim_html_dom('<a class="a b c">x</a>', strip_classes=True, attr_min_length=3).count("[CLASSES_OMITTED:3]") == 1
    assert slim_html_dom('<a class="a b c">x</a>', strip_classes=True) == '<a class="a b c">x</a>'


def test_data_class_attribute_not_touched():
    html = f'<div data-class="{CLASSES}" class="{CLASSES}">t</div>'
    out = slim_html_dom(html, strip_classes=True)
    assert f'data-class="{CLASSES}"' in out
    assert 'class="[CLASSES_OMITTED:20]"' in out


def test_gt_inside_attribute_and_single_quotes():
    html = f"<div title='a > b' class='{CLASSES}'>ok</div>"
    out = slim_html_dom(html, strip_classes=True)
    assert out == "<div title='a > b' class=\"[CLASSES_OMITTED:20]\">ok</div>"


def test_cli_flags(tmp_path):
    f = tmp_path / "p.html"
    f.write_text(HTML, encoding="utf-8")
    env_src = str(Path(__file__).resolve().parent.parent / "src")
    run = lambda *a: subprocess.run(
        [sys.executable, "-m", "framediet", "html", str(f), *a],
        capture_output=True, text=True, env={"PYTHONPATH": env_src, "PATH": "", "SYSTEMROOT": "C:/Windows"},
    ).stdout
    assert run().strip() == HTML
    assert "[CLASSES_OMITTED:20]" in run("--strip-classes")
