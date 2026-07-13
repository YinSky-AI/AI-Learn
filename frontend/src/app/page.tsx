import { redirect } from "next/navigation";

export default function RootPage() {
  // 默认重定向到首页
  redirect("/home");
}
