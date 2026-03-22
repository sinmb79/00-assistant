# tests/test_gate1_classifier.py
from assistant_22b.security.gate1_classifier import Gate1Classifier


def test_clean_text_is_public():
    clf = Gate1Classifier()
    result = clf.classify("이 문서는 교정이 필요합니다.")
    assert result.sensitivity == "public"
    assert result.detected_pii == []


def test_phone_number_is_internal(pii_text):
    clf = Gate1Classifier()
    result = clf.classify(pii_text)
    assert result.sensitivity == "internal"
    assert "전화번호" in result.detected_pii


def test_email_is_internal():
    clf = Gate1Classifier()
    result = clf.classify("담당자 이메일: kim@example.go.kr")
    assert result.sensitivity == "internal"
    assert "이메일" in result.detected_pii


def test_rrn_is_confidential(rrn_text):
    clf = Gate1Classifier()
    result = clf.classify(rrn_text)
    assert result.sensitivity == "confidential"
    assert "주민번호" in result.detected_pii


def test_rrn_overrides_phone():
    """When both RRN and phone are present, confidential wins."""
    clf = Gate1Classifier()
    text = "주민번호: 850101-1234567, 전화: 010-9999-0000"
    result = clf.classify(text)
    assert result.sensitivity == "confidential"
    assert "주민번호" in result.detected_pii
    assert "전화번호" in result.detected_pii


def test_bank_account_is_internal():
    clf = Gate1Classifier()
    result = clf.classify("계좌번호: 110-123456-78901")
    assert result.sensitivity == "internal"
    assert "계좌번호" in result.detected_pii
