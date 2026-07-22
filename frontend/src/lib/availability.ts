export type AvailabilityState =
  | "pending"
  | "ready"
  | "empty"
  | "failed"
  | "offline-cached"
  | "updating"
  | "installable";

export function availabilityMessage(state: AvailabilityState): string {
  switch (state) {
    case "ready": return "内容已更新";
    case "offline-cached": return "当前使用离线缓存";
    case "updating": return "正在更新内容";
    case "installable": return "可以安装到设备";
    case "empty": return "暂无可用内容";
    case "failed": return "加载失败，请重试";
    default: return "正在加载内容";
  }
}
