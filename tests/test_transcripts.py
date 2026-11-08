"""Transcript compaction: WhisperX-shaped input with unaligned words and speakers."""
from framediet.transcripts import compress_whisper

WHISPERX = {
    "segments": [
        {
            "start": 0.5,
            "end": 4.2,
            "text": "In 2014 it cost 13.60",
            "speaker": "SPEAKER_00",
            "words": [
                {"word": "In", "start": 0.5, "end": 0.7, "score": 0.9},
                {"word": "2014", "start": 0.8, "end": 1.3, "score": 0.8},
                {"word": "13.60"},
                {"word": "half", "start": 2.0},
            ],
        }
    ]
}


def test_unaligned_word_is_not_given_zero_time():
    out = compress_whisper(WHISPERX)
    assert '"13.60"[?]' in out
    assert "[0-0]" not in out


def test_partial_timing_marks_only_missing_side():
    assert "half[2000-?]" in compress_whisper(WHISPERX)


def test_header_explains_question_mark_only_when_used():
    assert "?=no timing in source" in compress_whisper(WHISPERX).splitlines()[0]
    clean = {"segments": [{"start": 0, "end": 1, "words": [{"word": "hi", "start": 0, "end": 1}]}]}
    assert "?=" not in compress_whisper(clean).splitlines()[0]


def test_segment_speaker_is_kept():
    assert "[500-4200 SPEAKER_00]" in compress_whisper(WHISPERX)


def test_aligned_words_unchanged():
    out = compress_whisper(WHISPERX)
    assert "In[500-700]" in out and '"2014"[800-1300]' in out
