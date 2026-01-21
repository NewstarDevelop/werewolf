/**
 * JWT Token 管理工具
 *
 * SECURITY NOTE (2026-01-21):
 * This module is being deprecated. The application now uses HttpOnly cookies
 * for user authentication. Token storage in sessionStorage is only used for
 * legacy game room tokens during the migration period.
 *
 * Migration plan:
 * 1. User auth: Now uses HttpOnly cookies (handled by backend)
 * 2. Game room tokens: Still uses sessionStorage (will migrate to one-time tickets)
 * 3. All deprecated functions will be removed after migration complete
 *
 * DO NOT use getAuthHeader() for user authentication.
 * Use credentials: 'include' in fetch requests instead.
 */

const TOKEN_KEY = 'werewolf_token';
const EXPIRY_KEY = 'werewolf_token_expiry';
const DEFAULT_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * 保存 JWT token (用于游戏房间认证)
 * @deprecated Will be replaced by one-time tickets
 * @param token - JWT token 字符串
 * @param expiresIn - 过期时间（毫秒），默认 24 小时
 */
export function saveToken(token: string, expiresIn: number = DEFAULT_EXPIRY_MS): void {
  if (!token) {
    console.warn('Attempted to save empty token');
    return;
  }
  const expiryTime = Date.now() + expiresIn;
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(EXPIRY_KEY, expiryTime.toString());
}

/**
 * 获取 JWT token (用于游戏房间认证)
 * @deprecated Will be replaced by one-time tickets
 * @returns JWT token 或 null（如果不存在或已过期）
 */
export function getToken(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiry = sessionStorage.getItem(EXPIRY_KEY);

  if (!token || !expiry) return null;

  if (Date.now() > parseInt(expiry, 10)) {
    clearToken();
    return null;
  }

  return token;
}

/**
 * 清除存储的 JWT token
 */
export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EXPIRY_KEY);
}

/**
 * 获取认证请求头 (仅用于游戏房间认证)
 *
 * @deprecated For user auth, use credentials: 'include' instead.
 * This is only for legacy game room tokens during migration.
 *
 * @returns 包含 Authorization header 的对象，如果没有 token 则返回空对象
 */
export function getAuthHeader(): HeadersInit {
  const token = getToken();

  if (!token) {
    return {};
  }

  return {
    'Authorization': `Bearer ${token}`
  };
}

// =============================================================================
// DEPRECATED FUNCTIONS - DO NOT USE IN NEW CODE
// These are kept only for cleanup during logout
// =============================================================================

const USER_TOKEN_KEY = 'user_auth_token';

/**
 * @deprecated Application uses HttpOnly cookies. This is kept for cleanup only.
 */
export function saveUserToken(_token: string): void {
  console.warn('saveUserToken is deprecated. Application uses HttpOnly cookies.');
  // No-op: Do not store tokens in localStorage
}

/**
 * @deprecated Application uses HttpOnly cookies. This is kept for cleanup only.
 */
export function getUserToken(): string | null {
  console.warn('getUserToken is deprecated. Application uses HttpOnly cookies.');
  // Return null - auth is now cookie-based
  return null;
}

/**
 * Clear user authentication token from localStorage.
 * This is still needed for cleanup during logout to remove any legacy tokens.
 */
export function clearUserToken(): void {
  localStorage.removeItem(USER_TOKEN_KEY);
}

/**
 * @deprecated Token validation should be done server-side.
 */
export function decodeToken(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

/**
 * @deprecated Token validation should be done server-side.
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  return Date.now() >= payload.exp * 1000;
}

/**
 * @deprecated Use credentials: 'include' for cookie-based auth instead.
 */
export function getUserAuthHeader(): HeadersInit {
  console.warn('getUserAuthHeader is deprecated. Use credentials: "include" instead.');
  return {};
}
