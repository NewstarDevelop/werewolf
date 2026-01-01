"""
测试提示词优化后的功能
验证：1. 预言家查验历史表格生成
     2. 女巫药水状态表格生成
     3. 投票逻辑链模板生成
     4. 狼人协同战术清单生成
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompts import build_system_prompt, build_context_prompt
from app.models.game import Game, Player
from app.schemas.enums import Role, GamePhase

def create_mock_game():
    """创建模拟游戏状态"""
    game = Game(id="test-001", language="zh")
    game.day = 2
    game.phase = GamePhase.DAY_SPEECH

    # 创建9个玩家
    for i in range(1, 10):
        role = Role.VILLAGER
        if i in [2, 4, 8]:  # 狼人
            role = Role.WEREWOLF
        elif i == 5:  # 预言家
            role = Role.SEER
        elif i == 1:  # 女巫
            role = Role.WITCH
        elif i == 3:  # 猎人
            role = Role.HUNTER

        player = Player(seat_id=i, role=role, is_ai=True)

        # 狼人队友关系
        if role == Role.WEREWOLF:
            player.teammates = [2, 4, 8]
            player.teammates.remove(i)

        game.players[i] = player

    # 预言家查验历史（关键测试点）
    game.players[5].verified_players = {
        9: True,   # 第1晚查验9号 - 狼人
        1: False,  # 第2晚查验1号 - 好人
    }

    # 女巫药水状态
    game.players[1].has_save_potion = False  # 解药已用
    game.players[1].has_poison_potion = True  # 毒药未用

    # 设置部分玩家已出局
    game.players[9].is_alive = False  # 9号出局
    game.players[6].is_alive = False  # 6号出局

    return game

def test_seer_verification_table():
    """测试1：预言家查验历史表格"""
    print("\n" + "="*60)
    print("测试1：预言家查验历史表格生成")
    print("="*60)

    game = create_mock_game()
    player = game.players[5]  # 预言家

    # 生成查验阶段提示词
    prompt = build_context_prompt(player, game, "verify")

    # 验证关键内容
    checks = [
        ("包含表格标题", "你的查验历史" in prompt),
        ("包含表格头", "| 夜晚 | 查验对象 | 结果 | 当前状态 |" in prompt),
        ("包含第1晚记录", "第1晚" in prompt and "9号" in prompt),
        ("包含第2晚记录", "第2晚" in prompt and "1号" in prompt),
        ("包含严格规则", "禁止凭记忆" in prompt),
        ("包含自检机制", "我确定是第几晚查验的谁吗" in prompt),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False

    # 显示生成的表格片段
    if "你的查验历史" in prompt:
        start = prompt.index("你的查验历史")
        end = prompt.index("可选目标", start) if "可选目标" in prompt[start:] else start + 500
        print(f"\n生成的表格片段：\n{prompt[start:end][:300]}...")

    return all_passed

def test_witch_potion_table():
    """测试2：女巫药水状态表格"""
    print("\n" + "="*60)
    print("测试2：女巫药水状态表格生成")
    print("="*60)

    game = create_mock_game()
    player = game.players[1]  # 女巫
    game.night_kill_target = 3  # 今晚3号被刀

    # 生成救人阶段提示词
    prompt = build_context_prompt(player, game, "witch_save")

    checks = [
        ("包含药水状态标题", "你的药水状态" in prompt),
        ("包含表格头", "| 药水类型 | 剩余数量 | 状态说明 |" in prompt),
        ("显示解药已用", "0瓶（已使用）" in prompt),
        ("显示毒药可用", "1瓶（可用）" in prompt),
        ("包含严格规则", "决策前必须确认" in prompt),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False

    # 显示生成的表格片段
    if "你的药水状态" in prompt:
        start = prompt.index("你的药水状态")
        end = start + 400
        print(f"\n生成的表格片段：\n{prompt[start:end]}...")

    return all_passed

def test_vote_logic_template():
    """测试3：投票逻辑链模板"""
    print("\n" + "="*60)
    print("测试3：投票强制逻辑链模板生成")
    print("="*60)

    game = create_mock_game()
    player = game.players[2]  # 狼人

    # 生成投票阶段提示词
    prompt = build_context_prompt(player, game, "vote")

    checks = [
        ("包含决策表标题", "投票决策表" in prompt),
        ("包含6步验证法", "6步验证法" in prompt),
        ("包含证据要求", "证据1（可核查的事实）" in prompt and "证据2" in prompt),
        ("包含推断结论", "推断结论" in prompt),
        ("包含反证检验", "反证检验" in prompt),
        ("包含最终决策", "最终决策" in prompt),
        ("禁止单点否定", "禁止因为单一错误就全盘否定" in prompt),
        ("提供示例", "5号在第2天说" in prompt),  # 检查是否有具体示例
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False

    return all_passed

def test_wolf_strategy_list():
    """测试4：狼人协同战术清单"""
    print("\n" + "="*60)
    print("测试4：狼人协同战术清单生成")
    print("="*60)

    game = create_mock_game()
    game.phase = GamePhase.NIGHT_WEREWOLF_CHAT  # 狼人夜间讨论
    player = game.players[2]  # 狼人

    # 生成狼人讨论阶段提示词
    prompt = build_context_prompt(player, game, "speech")

    checks = [
        ("包含战术清单标题", "必须讨论的战术清单" in prompt or "战术优先级清单" in prompt),
        ("优先级1: 逻辑漏洞识别", "优先级1" in prompt and "逻辑漏洞识别" in prompt),
        ("包含击杀目标讨论", "击杀目标" in prompt or "今晚刀谁" in prompt),
        ("包含演戏策略", "明天白天的分工策略" in prompt or "演戏策略" in prompt),
        ("包含票型伪装", "票型伪装" in prompt or "分票" in prompt),
        ("强调避免暴露", "避免白天暴露关系" in prompt),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False

    return all_passed

def test_system_prompt_enhancement():
    """测试5：系统提示词强化"""
    print("\n" + "="*60)
    print("测试5：系统提示词强化验证")
    print("="*60)

    game = create_mock_game()
    player = game.players[5]  # 预言家

    # 生成系统提示词
    prompt = build_system_prompt(player, game)

    checks = [
        ("包含强制逻辑链验证", "强制逻辑链验证" in prompt),
        ("包含三步验证法", "三步验证法" in prompt),
        ("包含列举证据要求", "列举证据" in prompt and "至少 2 条" in prompt),
        ("包含推断结论", "推断结论" in prompt),
        ("包含反证检验", "反证检验" in prompt),
        ("包含违规自检", "违规自检" in prompt or "如果你发现自己" in prompt),
        ("禁止单点否定", "禁止因为单一错误就全盘否定" in prompt),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False

    return all_passed

def test_verified_players_order():
    """测试6：验证 verified_players 的顺序问题（Code Review 发现的风险）"""
    print("\n" + "="*60)
    print("测试6：查验历史顺序准确性验证")
    print("="*60)

    game = create_mock_game()
    player = game.players[5]  # 预言家

    # 关键测试：验证字典遍历顺序
    # Python 3.7+ 字典是插入有序的
    player.verified_players = {
        9: True,   # 应该显示为第1晚
        1: False,  # 应该显示为第2晚
        3: False,  # 应该显示为第3晚（新增）
    }

    prompt = build_context_prompt(player, game, "verify")

    # 检查顺序
    idx_9 = prompt.find("| 第1晚 | 9号")
    idx_1 = prompt.find("| 第2晚 | 1号")
    idx_3 = prompt.find("| 第3晚 | 3号")

    checks = [
        ("9号显示为第1晚", idx_9 > 0),
        ("1号显示为第2晚", idx_1 > 0),
        ("3号显示为第3晚", idx_3 > 0),
        ("顺序正确 (9 < 1 < 3)", idx_9 < idx_1 < idx_3 if idx_9 > 0 and idx_1 > 0 and idx_3 > 0 else False),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {check_name}")
        if not result:
            all_passed = False
            print(f"    调试信息: idx_9={idx_9}, idx_1={idx_1}, idx_3={idx_3}")

    if not all_passed:
        print("\n⚠️ 警告：查验历史顺序可能不准确！")
        print("   这是 Code Review 中发现的潜在问题。")
        print("   建议：在 Player 模型中使用有序列表存储查验历史。")

    return all_passed

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("狼人杀 AI 提示词优化 - 功能测试")
    print("="*60)

    results = []

    results.append(("预言家查验历史表格", test_seer_verification_table()))
    results.append(("女巫药水状态表格", test_witch_potion_table()))
    results.append(("投票逻辑链模板", test_vote_logic_template()))
    results.append(("狼人协同战术清单", test_wolf_strategy_list()))
    results.append(("系统提示词强化", test_system_prompt_enhancement()))
    results.append(("查验历史顺序准确性", test_verified_players_order()))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {test_name}")

    print("\n" + "-"*60)
    print(f"总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！优化实施成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要修复。")
        return 1

if __name__ == "__main__":
    exit(main())
