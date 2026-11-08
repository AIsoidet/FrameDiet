from framediet.qa import TimeInterval as T, VideoQAReport, classify_intervals


def iv(start, end=None):
    return T(start=start, end=end, duration=None if end is None else end - start)


# Intervals measured on two real channel videos (pixelfx reel 26.45 s; flow.mp4 10.6 s).
REEL_FREEZES = (iv(11.967, 12.5), iv(17.233, 17.833), iv(18.2, 18.867), iv(25.2))
FLOW_FREEZES = (iv(0.3, 0.9), iv(3.2, 3.7), iv(3.7, 4.3))


def test_real_reel_holds_are_notes_not_warnings():
    warnings, notes = classify_intervals((), REEL_FREEZES, 26.453)
    assert warnings == []
    assert any("end card" in note for note in notes)
    assert any("held beats" in note for note in notes)


def test_touching_stills_are_merged_before_judging():
    # flow.mp4: FFmpeg split one 1.1 s still at 3.2-4.3 into two pieces.
    warnings, notes = classify_intervals((), FLOW_FREEZES, 10.6)
    assert len(warnings) == 1 and "00:00:03.200 - 00:00:04.300 (1.10s)" in warnings[0]
    assert "00:00:00.300" in notes[0]


def test_mid_video_freeze_of_one_second_warns():
    warnings, _ = classify_intervals((), (iv(9.0, 10.0),), 20.0)
    assert len(warnings) == 1 and "freeze intervals: 1" in warnings[0]


def test_threshold_is_configurable():
    warnings, _ = classify_intervals((), (iv(9.0, 9.5),), 20.0, freeze_warn_duration=0.4)
    assert warnings
    warnings, _ = classify_intervals((), (iv(9.0, 9.5),), 20.0, freeze_warn_duration=0)
    assert warnings


def test_title_card_at_start_is_note():
    warnings, notes = classify_intervals((), (iv(0.0, 2.0),), 25.0)
    assert warnings == [] and "title or end card" in notes[0]


def test_long_edge_hold_still_warns():
    warnings, _ = classify_intervals((), (iv(15.0),), 20.0)
    assert warnings


def test_static_video_warns():
    warnings, _ = classify_intervals((), (iv(0.0),), 4.0)
    assert warnings


def test_black_flash_mid_video_warns_and_fades_are_notes():
    black = (iv(0.0, 0.5), iv(6.0, 6.3), iv(19.6))
    warnings, notes = classify_intervals(black, (), 20.0)
    assert len(warnings) == 1 and "black intervals: 1" in warnings[0] and "00:00:06.000" in warnings[0]
    assert "fade" in notes[0]


def test_notes_do_not_change_status_and_are_printed():
    report = VideoQAReport(
        file="a.mp4", duration_seconds=10.0, width=2, height=2, fps=30.0, audio_streams=0,
        black_intervals=(), freeze_intervals=(iv(0, 1),), crop_observations=(),
        audio_peak_dbfs=None, clipped_samples=None, warnings=(), notes=("still at start/end",),
    )
    assert report.status == "PASS"
    assert "- note: still at start/end" in report.to_text()
    assert report.as_dict()["notes"] == ["still at start/end"]
