# tests/test_gate2_masker.py
from assistant_22b.security.gate2_masker import Gate2Masker


def test_masks_phone_number(pii_text):
    masker = Gate2Masker()
    result = masker.process(pii_text)
    assert "[전화번호]" in result.masked_text
    assert "010-1234-5678" not in result.masked_text
    assert result.was_masked is True


def test_clean_text_not_masked(clean_text):
    masker = Gate2Masker()
    result = masker.process(clean_text)
    assert result.masked_text == clean_text
    assert result.was_masked is False


def test_masked_text_returned_unchanged_when_no_pii():
    masker = Gate2Masker()
    text = "보조금 지급 현황을 보고드립니다."
    result = masker.process(text)
    assert result.was_masked is False


def test_masks_rrn(rrn_text):
    masker = Gate2Masker()
    result = masker.process(rrn_text)
    assert "[주민번호]" in result.masked_text
    assert result.was_masked is True
