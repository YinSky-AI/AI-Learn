export type TutorStreamEvent = { content?: string; reply?: string; done?: boolean; error?: boolean };

/** Buffers incomplete SSE frames so network chunks cannot corrupt chat output. */
export function createTutorSseParser(onEvent: (event: TutorStreamEvent) => void) {
  let buffer = "";
  return {
    push(chunk: string) {
      buffer += chunk.replace(/\r\n/g, "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const payload = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
        if (!payload) continue;
        let event: TutorStreamEvent;
        try {
          event = JSON.parse(payload) as TutorStreamEvent;
        } catch {
          continue;
        }
        onEvent(event);
      }
    },
    finish() { buffer = ""; },
  };
}
