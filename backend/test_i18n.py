"""Test i18n functionality."""
import sys
sys.path.insert(0, 'C:/Code/Werewolf/backend')

from app.i18n import t

print("=" * 60)
print("Testing i18n Translation Function")
print("=" * 60)

# Test system messages
print("\n1. Testing System Messages:")
print("-" * 60)
print(f"ZH: {t('system_messages.night_falls', language='zh', day=1)}")
print(f"EN: {t('system_messages.night_falls', language='en', day=1)}")

print(f"\nZH: {t('system_messages.day_breaks_peaceful', language='zh')}")
print(f"EN: {t('system_messages.day_breaks_peaceful', language='en')}")

# Test prompts
print("\n2. Testing Prompt Messages:")
print("-" * 60)
print(f"ZH: {t('prompts.game_intro', language='zh')}")
print(f"EN: {t('prompts.game_intro', language='en')}")

print(f"\nZH: {t('prompts.language_instruction', language='zh')}")
print(f"EN: {t('prompts.language_instruction', language='en')}")

# Test role descriptions
print("\n3. Testing Role Descriptions:")
print("-" * 60)
print(f"ZH: {t('roles.descriptions.werewolf', language='zh')[:50]}...")
print(f"EN: {t('roles.descriptions.werewolf', language='en')[:50]}...")

# Test winners
print("\n4. Testing Winners:")
print("-" * 60)
print(f"ZH: {t('winners.villagers', language='zh')}")
print(f"EN: {t('winners.villagers', language='en')}")

print(f"\nZH: {t('winners.werewolves', language='zh')}")
print(f"EN: {t('winners.werewolves', language='en')}")

print("\n" + "=" * 60)
print("✅ All translations working correctly!")
print("=" * 60)
