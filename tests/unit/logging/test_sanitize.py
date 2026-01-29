"""Tests for logging sanitization utilities."""

from blinkb0t.core.logging.sanitize import sanitize_dict, sanitize_string


class TestSanitizeString:
    """Test string sanitization."""

    def test_sanitize_api_key(self):
        """Test API key redaction."""
        text = "API key: sk-abc123def456ghi789jkl012mno345pqr"
        result = sanitize_string(text)
        assert "<REDACTED:API_KEY>" in result
        assert "sk-" not in result

    def test_sanitize_bearer_token(self):
        """Test Bearer token redaction."""
        text = "Authorization: Bearer abc123def456"
        result = sanitize_string(text)
        assert "<REDACTED:BEARER_TOKEN>" in result
        assert "Bearer abc" not in result

    def test_sanitize_email(self):
        """Test email redaction."""
        text = "Contact: user@example.com"
        result = sanitize_string(text)
        assert "<REDACTED:EMAIL>" in result
        assert "@example.com" not in result

    def test_sanitize_phone_us(self):
        """Test US phone number redaction."""
        test_cases = [
            "555-123-4567",
            "(555) 123-4567",
            "5551234567",
            "+1-555-123-4567",
            "+1 (555) 123-4567",
        ]
        for phone in test_cases:
            result = sanitize_string(f"Phone: {phone}")
            assert "<REDACTED:PHONE>" in result, f"Failed to redact: {phone}"
            # Check that original phone is not in result
            assert phone not in result

    def test_sanitize_phone_international(self):
        """Test international phone number redaction."""
        # Note: Current regex doesn't catch all international formats
        # This test documents that limitation
        international_phones = [
            "+44 20 7123 4567",  # UK - currently not matched
            "+33 1 42 86 82 00",  # France - currently not matched
        ]
        # These formats are not currently detected
        # Could be enhanced in future if needed
        for phone in international_phones:
            _ = sanitize_string(f"Phone: {phone}")
            # No assertion - just documenting behavior

    def test_no_false_positives_decimals(self):
        """Test that decimal numbers are NOT redacted as phone numbers."""
        test_cases = [
            "duration: 0.0 seconds",
            "end_s: 5.0",
            "similarity: 0.12345",
            "score: 197.4",
            "energy: 3.5",
            "value: 123.456789",
        ]
        for text in test_cases:
            result = sanitize_string(text)
            assert "<REDACTED:PHONE>" not in result, f"False positive on: {text}"
            assert result == text, f"Text was modified: {text} -> {result}"

    def test_no_false_positives_small_integers(self):
        """Test that small integers are NOT redacted."""
        test_cases = [
            "count: 0",
            "index: 5",
            "rank: 10",
            "section: 3",
        ]
        for text in test_cases:
            result = sanitize_string(text)
            assert "<REDACTED" not in result, f"False positive on: {text}"

    def test_sanitize_ssn(self):
        """Test SSN redaction."""
        text = "SSN: 123-45-6789"
        result = sanitize_string(text)
        assert "<REDACTED:SSN>" in result
        assert "123-45-6789" not in result

    def test_sanitize_credit_card(self):
        """Test credit card redaction."""
        # Only match credit cards with separators to avoid false positives
        test_cases = [
            "4532 1234 5678 9010",
            "4532-1234-5678-9010",
        ]
        for cc in test_cases:
            result = sanitize_string(f"CC: {cc}")
            assert "<REDACTED:CREDIT_CARD>" in result
            # Check that original number is not in result
            assert cc.replace(" ", "").replace("-", "") not in result.replace(" ", "").replace("-", "")

    def test_credit_card_no_false_positives(self):
        """Test that long decimals are NOT redacted as credit cards."""
        test_cases = [
            "similarity: 0.1234567890123456",  # 16 digits after decimal
            "value: 1234567890123456",  # 16 consecutive digits without separators
        ]
        for text in test_cases:
            result = sanitize_string(text)
            assert "<REDACTED:CREDIT_CARD>" not in result, f"False positive on: {text}"


class TestSanitizeDict:
    """Test dictionary sanitization."""

    def test_sanitize_sensitive_keys(self):
        """Test sensitive key redaction."""
        data = {
            "user": "alice",
            "api_key": "sk-secret123",
            "password": "hunter2",
            "normal_field": "visible",
        }
        result = sanitize_dict(data)
        assert result["user"] == "alice"
        assert result["api_key"] == "<REDACTED>"
        assert result["password"] == "<REDACTED>"
        assert result["normal_field"] == "visible"

    def test_sanitize_nested_dict(self):
        """Test nested dictionary sanitization."""
        data = {
            "config": {
                "api_key": "sk-secret",
                "timeout": 30,
            },
            "user": "alice",
        }
        result = sanitize_dict(data)
        assert result["config"]["api_key"] == "<REDACTED>"
        assert result["config"]["timeout"] == 30
        assert result["user"] == "alice"

    def test_sanitize_list_of_strings(self):
        """Test list of strings sanitization."""
        data = {
            "emails": [
                "user@example.com",
                "admin@example.com",
            ],
            "names": ["alice", "bob"],
        }
        result = sanitize_dict(data)
        assert "<REDACTED:EMAIL>" in result["emails"][0]
        assert "<REDACTED:EMAIL>" in result["emails"][1]
        assert result["names"] == ["alice", "bob"]

    def test_sanitize_preserves_numeric_values(self):
        """Test that numeric values in dicts are preserved."""
        data = {
            "duration_s": 197.4,
            "end_s": 5.0,
            "energy_rank": 0.0,
            "similarity": 0.12345,
            "count": 3,
        }
        result = sanitize_dict(data)
        assert result == data, "Numeric values should not be modified"

    def test_sanitize_json_like_structure(self):
        """Test sanitization of JSON-like structures (like LLM logs)."""
        data = {
            "sections": [
                {
                    "duration_s": 10.5,
                    "end_s": 15.0,
                    "energy_rank": 0.8,
                    "start_s": 5.0,
                },
                {
                    "duration_s": 20.0,
                    "end_s": 35.0,
                    "energy_rank": 1.0,
                    "start_s": 15.0,
                },
            ],
            "phone_contact": "555-123-4567",  # This IS a phone and should be redacted
        }
        result = sanitize_dict(data)

        # Numeric values should be preserved
        assert result["sections"][0]["duration_s"] == 10.5
        assert result["sections"][0]["end_s"] == 15.0

        # Actual phone number in string should be redacted
        assert "<REDACTED:PHONE>" in result["phone_contact"]
