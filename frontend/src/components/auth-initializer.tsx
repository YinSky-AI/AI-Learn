/**
 * 认证初始化组件
 *
 * 功能说明：
 * - 应用启动时检查本地存储的 JWT Token
 * - 验证 Token 是否过期，过期则清除
 * - 尝试恢复用户登录状态（获取用户资料和统计）
 * - 处理 401 未授权错误（清除无效 Token）
 * - 其他错误（限流、网络）保留 Token，下次刷新重试
 * - 无渲染输出（return null）
 */

"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { TokenManager } from "@/lib/api-client";

/**
 * 认证初始化组件
 * @returns null（无渲染）
 */
export function AuthInitializer() {
  const initialized = useRef(false);
  const fetchProfile = useAuthStore((s) => s.fetchProfile);
  const fetchUserStats = useAuthStore((s) => s.fetchUserStats);

  // 应用启动时执行一次认证恢复逻辑
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const token = TokenManager.getAccessToken();
    if (!token) return;

    // 检查 token 是否已过期（简单解析 JWT exp）
    if (TokenManager.isTokenExpired(token)) {
      TokenManager.clearTokens();
      return;
    }

    // 有 token 且未过期，尝试恢复用户状态
    fetchProfile()
      .then(() => {
        // profile 成功，继续获取统计
        return fetchUserStats().catch(() => {});
      })
      .catch((error) => {
        // fetchProfile 失败：判断是否是 token 真正无效（401）
        const isUnauthorized =
          error &&
          typeof error === "object" &&
          "code" in error &&
          (error as { code: number | string }).code === 401;

        if (isUnauthorized) {
          // token 确实无效，清除
          TokenManager.clearTokens();
        }
        // 其他错误（429 限流、网络问题等）不清除 token，下次刷新再重试
      });
  }, [fetchProfile, fetchUserStats]);

  return null;
}
