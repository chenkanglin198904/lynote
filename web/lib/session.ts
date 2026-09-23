import type { ChatMessage } from "./types";

export function messageLane(message: ChatMessage): "learn" | "decision" {
  if (message.lane === "decision" || message.lane === "learn") return message.lane;
  if (
    !message.grounded &&
    !message.probe &&
    (message.content.startsWith("已把决策") || message.content.startsWith("已把事后"))
  ) {
    return "decision";
  }
  return "learn";
}

export function messagesInLane(
  messages: ChatMessage[],
  lane: "learn" | "decision",
  goalId: string | null,
) {
  return messages.filter((item) => {
    if (messageLane(item) !== lane) return false;
    if (!goalId) return !item.goal_id;
    return !item.goal_id || item.goal_id === goalId;
  });
}
