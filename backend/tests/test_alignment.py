import pytest
from backend.services.alignment import AlignmentService

def test_netflix_compliance():
    service = AlignmentService()

    # Test case 1: Long segment that needs splitting
    segments = [{
        "start": 0.0,
        "end": 10.0,
        "text": "这是一个非常非常长的句子，它肯定会超过每行最大字符数的限制，因此我们需要将其分割成更短的片段以符合Netflix的标准，确保观众能够轻松阅读。"
    }]

    # Assuming max_cpl=20 (low enough to force split)
    compliant = service.check_netflix_compliance(segments, max_cpl=20, max_cps=20)

    assert len(compliant) > 1
    for seg in compliant:
        assert len(seg['text']) <= 20
        assert seg['start'] < seg['end']

    # Check total duration roughly matches
    total_duration = compliant[-1]['end'] - compliant[0]['start']
    assert abs(total_duration - 10.0) < 0.1

def test_cps_calculation():
    service = AlignmentService()
    segments = [{
        "start": 0.0,
        "end": 1.0,
        "text": "快快快快快快快快快快" # 10 chars in 1s -> 10 CPS
    }]
    compliant = service.check_netflix_compliance(segments, max_cps=5)

    # Should still be 1 segment but logged warning (we don't check logs here easily but check calculation)
    assert len(compliant) == 1
    assert compliant[0]['cps'] == 10.0

def test_export_formats():
    service = AlignmentService()
    segments = [
        {"start": 0.0, "end": 2.5, "text": "Hello World"},
        {"start": 3.0, "end": 5.123, "text": "Second Line"}
    ]

    srt = service.to_srt(segments)
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "Hello World" in srt

    vtt = service.to_vtt(segments)
    assert "WEBVTT" in vtt
    assert "00:00:03.000 --> 00:00:05.123" in vtt

    ass = service.to_ass(segments)
    assert "[Script Info]" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:02.50,Default,,0,0,0,,Hello World" in ass
