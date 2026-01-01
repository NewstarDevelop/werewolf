"""Test game i18n integration."""
import sys
sys.path.insert(0, 'C:/Code/Werewolf/backend')

from app.models.game import Game, Player
from app.schemas.enums import Role, GamePhase
from app.services.prompts import build_system_prompt, build_context_prompt

print("=" * 60)
print("Testing Game I18n Integration")
print("=" * 60)

# Create test game
game_zh = Game(id="test-zh", language="zh")
game_en = Game(id="test-en", language="en")

# Create test player
player_zh = Player(seat_id=1, role=Role.WEREWOLF, teammates=[2, 3])
player_en = Player(seat_id=1, role=Role.WEREWOLF, teammates=[2, 3])

print("\n1. Testing System Prompt Generation:")
print("-" * 60)

# Test ZH system prompt
system_prompt_zh = build_system_prompt(player_zh, game_zh, language="zh")
print(f"ZH Prompt Length: {len(system_prompt_zh)} chars")
print(f"ZH Contains '游戏规则': {'游戏规则' in system_prompt_zh}")
print(f"ZH Contains '行为准则': {'行为准则' in system_prompt_zh}")
print(f"ZH Contains English template: {'Game Rules' in system_prompt_zh}")

# Test EN system prompt
system_prompt_en = build_system_prompt(player_en, game_en, language="en")
print(f"\nEN Prompt Length: {len(system_prompt_en)} chars")
print(f"EN Contains 'Game Rules': {'Game Rules' in system_prompt_en}")
print(f"EN Contains 'Behavior Guidelines': {'Behavior Guidelines' in system_prompt_en}")
print(f"EN Contains Chinese template: {'游戏规则' in system_prompt_en}")

print("\n2. Testing Context Prompt Generation:")
print("-" * 60)

# Add test game state
game_zh.day = 1
game_zh.phase = GamePhase.DAY_SPEECH
game_en.day = 1
game_en.phase = GamePhase.DAY_SPEECH

# Test ZH context prompt
context_prompt_zh = build_context_prompt(player_zh, game_zh, "speech", language="zh")
print(f"ZH Context Length: {len(context_prompt_zh)} chars")
print(f"ZH Contains '当前游戏状态': {'当前游戏状态' in context_prompt_zh}")
print(f"ZH Contains '存活玩家': {'存活玩家' in context_prompt_zh}")

# Test EN context prompt
context_prompt_en = build_context_prompt(player_en, game_en, "speech", language="en")
print(f"\nEN Context Length: {len(context_prompt_en)} chars")
print(f"EN Contains 'Current Game State': {'Current Game State' in context_prompt_en}")
print(f"EN Contains 'Alive players': {'Alive players' in context_prompt_en}")

print("\n3. Validation Summary:")
print("-" * 60)

issues = []

# Validate ZH prompt
if 'Game Rules' in system_prompt_zh or 'Behavior Guidelines' in system_prompt_zh:
    issues.append("❌ ZH system prompt contains English template text")
else:
    print("✅ ZH system prompt uses Chinese template correctly")

# Validate EN prompt
if '游戏规则' in system_prompt_en or '行为准则' in system_prompt_en:
    issues.append("❌ EN system prompt contains Chinese template text")
else:
    print("✅ EN system prompt uses English template correctly")

# Validate ZH context
if 'Current Game State' in context_prompt_zh:
    issues.append("❌ ZH context prompt contains English headers")
else:
    print("✅ ZH context prompt uses Chinese headers correctly")

# Validate EN context
if '当前游戏状态' in context_prompt_en:
    issues.append("❌ EN context prompt contains Chinese headers")
else:
    print("✅ EN context prompt uses English headers correctly")

print("\n" + "=" * 60)
if issues:
    print("⚠️  Issues Found:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("✅ ALL TESTS PASSED - I18n integration working correctly!")
print("=" * 60)
