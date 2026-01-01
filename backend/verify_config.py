"""Configuration verification tool."""
import sys
from app.core.config import settings


def main():
    """Verify environment configuration."""

    print("=" * 60)
    print("Werewolf Game Configuration Verification")
    print("=" * 60)
    print()

    # Check providers
    print("Provider Configuration:")
    print("-" * 60)

    if not settings._providers:
        print("❌ ERROR: No providers configured!")
        print("   Please set at least OPENAI_API_KEY in .env file")
        return 1

    for name, provider in settings._providers.items():
        status = "✅" if provider.is_valid() else "❌"
        print(f"{status} {name:20s} - Model: {provider.model}")

    print()

    # Check analysis configuration
    print("Analysis Configuration:")
    print("-" * 60)

    analysis_provider = settings.get_analysis_provider()
    if analysis_provider:
        print(f"✅ Provider: {analysis_provider.name}")
        print(f"   Model: {analysis_provider.model}")
        print(f"   Max Tokens: {analysis_provider.max_tokens}")
    else:
        print("⚠️  WARNING: No analysis provider available")
        print("   Analysis will use fallback mode")

    print(f"   Mode: {settings.ANALYSIS_MODE}")
    print(f"   Language: {settings.ANALYSIS_LANGUAGE}")
    print(f"   Cache: {'Enabled' if settings.ANALYSIS_CACHE_ENABLED else 'Disabled'}")

    # Validate
    is_valid, errors = settings.validate_analysis_config()

    print()
    print("Validation Result:")
    print("-" * 60)

    if is_valid:
        print("✅ Configuration is valid")
        return 0
    else:
        print("❌ Configuration has issues:")
        for error in errors:
            print(f"   - {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
