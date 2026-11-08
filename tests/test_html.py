from framediet.toon import slim_html_dom

LONG_PATH = "M0 0 " + "L10 10 " * 20 + "Z"


def test_short_paths_and_following_markup_are_untouched():
    html = '<svg><path d="M0 0z" fill="red"/><text x="1">Visible label that must stay</text><path d="M1 1z"/></svg>'
    assert slim_html_dom(html) == html


def test_long_path_is_replaced_and_neighbours_kept():
    html = f'<path d="{LONG_PATH}" fill="red"/><text>Label</text><path d="M1 1z"/>'
    out = slim_html_dom(html)
    assert out == '<path d="[SVG_PATH]" fill="red"/><text>Label</text><path d="M1 1z"/>'


def test_single_quoted_long_path():
    out = slim_html_dom(f"<path d='{LONG_PATH}' stroke='blue'/>")
    assert out == "<path d=\"[SVG_PATH]\" stroke='blue'/>"


def test_attributes_ending_in_d_are_not_touched():
    html = f'<g id="{LONG_PATH}" data-d="{LONG_PATH}"></g>'
    assert "[SVG_PATH]" not in slim_html_dom(html).split("data-d")[0]


def test_base64_uri_replaced_and_rest_kept():
    html = '<img src="data:image/png;base64,' + "A" * 500 + '" alt="logo"><p>after</p>'
    out = slim_html_dom(html)
    assert out == '<img src="[BASE64_DATA_URI]" alt="logo"><p>after</p>'


def test_script_and_style_bodies_are_omitted():
    out = slim_html_dom("<style>a{b:c}</style><p>x</p><script type=\"m\">let a=1</script>")
    assert out == '<style>[STYLE_CONTENT_OMITTED]</style><p>x</p><script type="m">[SCRIPT_CONTENT_OMITTED]</script>'
