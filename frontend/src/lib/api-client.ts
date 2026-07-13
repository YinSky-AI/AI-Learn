/* ============================================
   API 客户端 - 封装 fetch + JWT Token 管理
   ============================================ */

import type { ApiResponse, ApiError } from "@/types/api";

// API 基础地址
// 浏览器端：使用 localhost:8000/api（Docker 端口映射到宿主机）
// 服务端（SSR）：在 Docker 中使用 backend 容器名
const API_BASE_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api")
    : (process.env.BACKEND_URL || "http://localhost:8000/api");

/** 导出 API_BASE_URL，供 store 直接使用（如 SSE 流式请求） */
export const API_BASE_URL_FOR_CLIENT = API_BASE_URL;

/** Token 存储键名 */
const ACCESS_TOKEN_KEY = "alp_access_token";
const REFRESH_TOKEN_KEY = "alp_refresh_token";

/** 自定义请求配置 */
interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  skipAuth?: boolean;
}

/** 后端业务响应码 */
const SUCCESS_CODES = ["SUCCESS", "000000", 200, "200"];

/** Token 管理工具 */
export const TokenManager = {
  getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens(accessToken: string, refreshToken: string): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.exp * 1000 < Date.now();
    } catch {
      return true;
    }
  },
};

/** 是否正在刷新 Token */
let isRefreshing = false;
/** Token 刷新等待队列 */
let refreshSubscribers: Array<(token: string) => void> = [];

/** 将等待的请求加入队列 */
function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

/** Token 刷新成功后通知队列 */
function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

/** 刷新 Token */
async function refreshAccessToken(): Promise<string> {
  const refreshToken = TokenManager.getRefreshToken();
  if (!refreshToken) {
    throw new Error("没有刷新令牌");
  }

  const response = await fetch(`${API_BASE_URL}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken }),
  });

  if (!response.ok) {
    TokenManager.clearTokens();
    throw new Error("刷新令牌失败");
  }

  const data = await response.json();
  // 后端返回 ApiResponse 包装，实际 token 在 data.data 中
  const tokenData = data.data || data;
  TokenManager.setTokens(tokenData.access_token, tokenData.refresh_token);
  return tokenData.access_token;
}

/** 构建 URL（附加查询参数） */
function buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }
  return url.toString();
}

/** 核心 API 请求函数 */
async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { body, params, skipAuth = false, headers: customHeaders, ...rest } = options;

  // 构建请求头
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(customHeaders as Record<string, string>),
  };

  // 添加 Token
  if (!skipAuth) {
    const token = TokenManager.getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  // 构建请求 URL
  const url = buildUrl(endpoint, params);

  // 发起请求
  let response = await fetch(url, {
    ...rest,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // 处理 401 - 尝试刷新 Token（跳过认证端点，避免登录失败时误跳转）
  const isAuthEndpoint = endpoint.startsWith("/v1/auth/");
  if (response.status === 401 && !skipAuth && !isAuthEndpoint) {
    if (isRefreshing) {
      // 等待刷新完成
      const newToken = await new Promise<string>((resolve) => {
        subscribeTokenRefresh((token) => resolve(token));
      });
      headers["Authorization"] = `Bearer ${newToken}`;
      response = await fetch(url, {
        ...rest,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } else {
      isRefreshing = true;
      try {
        const newToken = await refreshAccessToken();
        isRefreshing = false;
        onTokenRefreshed(newToken);
        headers["Authorization"] = `Bearer ${newToken}`;
        response = await fetch(url, {
          ...rest,
          headers,
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch (error) {
        isRefreshing = false;
        refreshSubscribers = [];
        // 重定向到登录页
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        throw error;
      }
    }
  }

  // 处理非 2xx 响应
  if (!response.ok) {
    let errorData: ApiError;
    try {
      const raw = await response.json();
      // FastAPI 错误格式: { detail: { code, message } } 或 { detail: "..." }
      if (raw.detail && typeof raw.detail === "object") {
        errorData = {
          code: raw.detail.code || response.status,
          message: raw.detail.message || "操作失败",
        };
      } else if (raw.detail && typeof raw.detail === "string") {
        errorData = {
          code: response.status,
          message: raw.detail,
        };
      } else {
        errorData = {
          code: raw.code || response.status,
          message: raw.message || `请求失败 (${response.status})`,
        };
      }
    } catch {
      errorData = {
        code: response.status,
        message: `请求失败 (${response.status})`,
      };
    }
    throw errorData;
  }

  // 解析响应
  const data = (await response.json()) as ApiResponse<T>;

  // 检查业务错误码（后端返回 200 但 code 非 SUCCESS 的情况）
  if (!SUCCESS_CODES.includes(data.code)) {
    const error: ApiError = {
      code: typeof data.code === "number" ? data.code : 400,
      message: data.message || "操作失败",
    };
    throw error;
  }

  return data.data;
}

/** GET 请求 */
export function get<T>(endpoint: string, params?: RequestOptions["params"], options?: Omit<RequestOptions, "body" | "params">): Promise<T> {
  return request<T>(endpoint, { ...options, method: "GET", params });
}

/** POST 请求 */
export function post<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(endpoint, { ...options, method: "POST", body });
}

/** PUT 请求 */
export function put<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(endpoint, { ...options, method: "PUT", body });
}

/** DELETE 请求 */
export function del<T>(endpoint: string, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(endpoint, { ...options, method: "DELETE" });
}

/** PATCH 请求 */
export function patch<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(endpoint, { ...options, method: "PATCH", body });
}

export const apiClient = {
  get,
  post,
  put,
  delete: del,
  patch,
};
export default apiClient;
