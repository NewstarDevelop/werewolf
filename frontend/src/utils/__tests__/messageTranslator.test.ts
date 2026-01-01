import { describe, it, expect, vi } from 'vitest';
import { translateSystemMessage, translateActionMessage } from '../messageTranslator';

describe('Message Translator', () => {
  const mockT = vi.fn((key, params) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  });

  it('should translate known system message patterns', () => {
    const message = '天亮了，昨晚是平安夜。';
    const result = translateSystemMessage(message, mockT);
    expect(result).toBe('game:system_messages.day_peaceful');
    expect(mockT).toHaveBeenCalledWith('game:system_messages.day_peaceful');
  });

  it('should translate system message with parameters', () => {
    const message = '天亮了，昨晚1号死了。';
    const result = translateSystemMessage(message, mockT);
    expect(result).toBe('game:system_messages.day_death:{"id":"1"}');
    expect(mockT).toHaveBeenCalledWith('game:system_messages.day_death', { id: '1' });
  });

  it('should return original message if no pattern matches', () => {
    const message = 'Unknown message from server';
    const result = translateSystemMessage(message, mockT);
    expect(result).toBe(message);
  });

  it('should translate known action message patterns', () => {
    const message = '请选择要查验的玩家';
    const result = translateActionMessage(message, mockT);
    expect(result).toBe('game:action_messages.seer_select_verify');
  });

  it('should translate action message with parameters', () => {
    const message = '今晚5号被杀，是否使用解药？';
    const result = translateActionMessage(message, mockT);
    expect(result).toBe('game:action_messages.witch_save_prompt:{"id":"5"}');
  });

  it('should handle partially matching but distinct messages', () => {
    // Example: Witch has poison vs no poison
    const msg1 = '你没有可用的毒药...';
    const res1 = translateActionMessage(msg1, mockT);
    expect(res1).toBe('game:action_messages.witch_no_poison');
  });
});
