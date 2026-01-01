/**
 * Player utility functions - generate and store player ID
 */

/**
 * 生成唯一的玩家ID
 * 优先使用 crypto.randomUUID，如果不可用则使用 fallback 实现
 */
function generatePlayerId(): string {
  // 检查 crypto.randomUUID 是否可用（需要 HTTPS 或 localhost）
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  // Fallback: 简单的 UUID v4 实现
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * 获取或创建玩家ID（存储在localStorage）
 */
export function getPlayerId(): string {
  const STORAGE_KEY = 'werewolf_player_id';

  let playerId = localStorage.getItem(STORAGE_KEY);

  if (!playerId) {
    playerId = generatePlayerId();
    localStorage.setItem(STORAGE_KEY, playerId);
  }

  return playerId;
}

/**
 * 获取玩家昵称（存储在localStorage）
 */
export function getNickname(): string | null {
  return localStorage.getItem('werewolf_player_nickname');
}

/**
 * 设置玩家昵称
 */
export function setNickname(nickname: string): void {
  localStorage.setItem('werewolf_player_nickname', nickname);
}

/**
 * 清除玩家数据（用于测试或重置）
 */
export function clearPlayerData(): void {
  localStorage.removeItem('werewolf_player_id');
  localStorage.removeItem('werewolf_player_nickname');
}
