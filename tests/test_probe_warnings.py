from framediet.probe import stream_warnings


def test_constant_rate_no_warning():
    assert stream_warnings({"avg_frame_rate": "30/1", "r_frame_rate": "30/1"}) == []


def test_ntsc_rates_are_not_flagged():
    assert stream_warnings({"avg_frame_rate": "30000/1001", "r_frame_rate": "30000/1001"}) == []


def test_variable_frame_rate_is_flagged():
    notes = stream_warnings({"avg_frame_rate": "1080/59", "r_frame_rate": "30/1"})
    assert len(notes) == 1 and "variable frame rate" in notes[0]


def test_rotation_from_side_data():
    notes = stream_warnings({"side_data_list": [{"rotation": -90}]})
    assert notes and "rotation=270" in notes[0]


def test_rotation_from_legacy_tag():
    notes = stream_warnings({"tags": {"rotate": "90"}})
    assert notes and "rotation=90" in notes[0]


def test_zero_rotation_and_bad_rates_are_quiet():
    assert stream_warnings({"side_data_list": [{"rotation": 0}], "avg_frame_rate": "0/0", "r_frame_rate": "N/A"}) == []
