from framediet.cli import _build_parser


def test_frames_out_dir_short_alias():
    args = _build_parser().parse_args(["frames", "v.mp4", "1.0", "-o", "d"])
    assert args.out_dir == "d"


def test_sheet_timeout_option():
    args = _build_parser().parse_args(["sheet", "v.mp4", "--timeout", "12"])
    assert args.timeout == 12
