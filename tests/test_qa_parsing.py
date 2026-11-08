from framediet.qa import (
    _parse_audio_metrics,
    _parse_black_events,
    _parse_crop_observations,
    _parse_fps,
    _parse_freeze_events,
)

BLACK = (
    "[blackdetect @ 0x1] black_start:7.35 black_end:7.55 black_duration:0.2\n"
    "[blackdetect @ 0x1] black_start:14 black_end:14.2 black_duration:0.2\n"
)

FREEZE = (
    "[freezedetect @ 0x2] lavfi.freezedetect.freeze_start: 3.5\n"
    "[freezedetect @ 0x2] lavfi.freezedetect.freeze_duration: 1.0\n"
    "[freezedetect @ 0x2] lavfi.freezedetect.freeze_end: 4.5\n"
)


def test_black_intervals():
    events = _parse_black_events(BLACK)
    assert [(e.start, e.end, e.duration) for e in events] == [
        (7.35, 7.55, 0.2),
        (14.0, 14.2, 0.2),
    ]


def test_black_without_end_is_open_ended():
    events = _parse_black_events("black_start:9.5")
    assert events[0].start == 9.5 and events[0].end is None


def test_freeze_start_duration_end_are_merged():
    events = _parse_freeze_events(FREEZE)
    assert len(events) == 1
    assert (events[0].start, events[0].end, events[0].duration) == (3.5, 4.5, 1.0)


def test_freeze_end_without_start_does_not_crash():
    assert len(_parse_freeze_events("freeze_end: 4.5")) == 1


def test_crop_observations_are_deduplicated():
    log = "crop=1080:1920:0:0\ncrop=1080:1920:0:0\ncrop=1080:1800:0:60"
    assert len(_parse_crop_observations(log)) == 2


def test_audio_metrics():
    log = "Peak level dB: -3.2\nNumber of clipped samples: 0\nPeak level dB: 1.0\nNumber of clipped samples: 12"
    assert _parse_audio_metrics(log) == (1.0, 12)


def test_audio_silence_is_minus_inf():
    peak, _ = _parse_audio_metrics("Peak level dB: -inf")
    assert peak == float("-inf")


def test_audio_missing_is_none():
    assert _parse_audio_metrics("nothing here") == (None, None)


def test_fps_parsing():
    assert _parse_fps({"avg_frame_rate": "30000/1001"}) == 30000 / 1001
    assert _parse_fps({"avg_frame_rate": "0/0"}) is None
    assert _parse_fps({}) is None
