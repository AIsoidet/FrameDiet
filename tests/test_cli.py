from framediet.cli import _build_parser


def test_frames_out_dir_short_alias():
    args = _build_parser().parse_args(["frames", "v.mp4", "1.0", "-o", "d"])
    assert args.out_dir == "d"
