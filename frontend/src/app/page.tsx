/**
 * 根页面入口
 *
 * 功能说明：
 * - 应用访问根路径 "/" 时自动重定向到首页 "/home"
 * - 作为 Next.js App Router 的默认入口页面
 */

import { redirect } from "next/navigation";

/**
 * 根页面组件
 * @returns 执行服务端重定向到 /home
 */
export default function RootPage() {
  // 默认重定向到首页
  redirect("/home");
}
