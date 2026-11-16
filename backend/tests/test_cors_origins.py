"""Tests for CORS origin regex and allowed origins."""

import re
import pytest
from app.core.config import settings


def test_cors_origin_regex_pattern():
    pattern = re.compile(settings.CORS_ORIGIN_REGEX)

    # Valid Vercel preview origins matching the regex
    assert pattern.match("https://zynova-karuppusamy2.vercel.app")
    assert pattern.match("https://zynova-f3bwfxck4-karuppusamy2.vercel.app")
    assert pattern.match("https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app")
    assert pattern.match("https://zynova-feature-123-karuppusamy2.vercel.app")

    # Invalid origins that MUST be rejected
    assert not pattern.match("https://zynova-evil.vercel.app")
    assert not pattern.match("https://evil.com")
    assert not pattern.match("https://zynovaapp-attacker-karuppusamy.vercel.app")
    assert not pattern.match("https://zynovaapp.vercel.app")  # Handled by exact CORS_ORIGINS list, not regex
    assert not pattern.match("http://zynova-f3bwfxck4-karuppusamy2.vercel.app")  # Insecure HTTP
    assert not pattern.match("https://zynova-karuppusamy2.vercel.app.evil.com")  # Domain injection attempt


def test_cors_exact_origins_list():
    # Verify exact production Vercel domain is present
    assert "https://zynovaapp.vercel.app" in settings.CORS_ORIGINS
    assert "https://www.intellidev.in" in settings.CORS_ORIGINS
    assert "https://zynova.intellidev.in" in settings.CORS_ORIGINS
    assert "https://zenova.intellidev.in" in settings.CORS_ORIGINS
