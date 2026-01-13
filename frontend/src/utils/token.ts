/**
 * JWT Token 管理工具
 * 用于存储、获取和管理玩家认证 token
 *
 * 安全说明：使用 sessionStorage，页面刷新保持登录，但关闭标签页后失效。
 * 包含过期时间检查。
 */

const TOKEN_KEY = 'werewolf_token';
const EXPIRY_KEY = 'werewolf_token_expiry';
const DEFAULT_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * 保存 JWT token
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
 * 获取 JWT token
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
 * 获取认证请求头
 * @returns 包含 Authorization header 的对象，如果没有 token 则返回空对象
 */
export function getAuthHeader(): HeadersInit {
  const token = getToken();

  if (!token) {
    return {};
  }

  return {
    'Authorization': \`Bearer \${token}\`
  };
}

// User authentication (persistent across sessions)
// DEPRECATED: The following functions are deprecated as the app now uses
// HttpOnly cookies exclusively for security. Keeping for backward compatibility
// but should not be used in new code.
const USER_TOKEN_KEY = 'user_auth_token';

/**
 * @deprecated Use HttpOnly cookies instead. This function is kept for cleanup only.
 * Save user authentication token (localStorage for persistence).
 */
export function saveUserToken(token: string): void {
  console.warn('saveUserToken is deprecated. Application uses HttpOnly cookies for authentication.');
  if (!token) return;
  localStorage.setItem(USER_TOKEN_KEY, token);
}

/**
 * @deprecated Use HttpOnly cookies instead. This function is kept for cleanup only.
 * Get user authentication token.
 */
export function getUserToken(): string | null {
  console.warn('getUserToken is deprecated. Application uses HttpOnly cookies for authentication.');
  return localStorage.getItem(USER_TOKEN_KEY);
}

/**
 * Clear user authentication token.
 * Note: Still needed for cleanup during logout.
 */
export function clearUserToken(): void {
  localStorage.removeItem(USER_TOKEN_KEY);
}

/**
 * Decode JWT token payload.
 * @deprecated Token validation should be done server-side with HttpOnly cookies.
 */
export function decodeToken(token: string): any | null {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

/**
 * Check if token is expired.
 * @deprecated Token validation should be done server-side with HttpOnly cookies.
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload || !payload.exp) return true;
  return Date.now() >= payload.exp * 1000;
}

/**
 * Get user auth header for API requests.
 * @deprecated Use credentials: 'include' for cookie-based auth instead.
 */
export function getUserAuthHeader(): HeadersInit {
  const token = getUserToken();
  if (!token || isTokenExpired(token)) {
    clearUserToken();
    return {};
  }
  return {
    'Authorization': \`Bearer \${token}\`
  };
}
