import type {
  ChatMessage,
  DecisionBrief,
  InboxItem,
  KnowledgeSearchResponse,
  NodeDetail,
  PlayId,
  Profile,
  Relation,
  RunPlayResult,
  SourceKind,
  WeeklyReport,
  Workbench,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function fetchWorkbench() {
  return request<Workbench>("/v1/workbench");
}

export function fetchNodeDetail(nodeId: string) {
  return request<NodeDetail>(`/v1/graph/nodes/${encodeURIComponent(nodeId)}`);
}

export function searchKnowledge(query: string) {
  return request<KnowledgeSearchResponse>(`/v1/search?q=${encodeURIComponent(query)}`);
}

export function createGoal(title: string, question: string) {
  return request("/v1/goals", {
    method: "POST",
    body: JSON.stringify({ title, question }),
  });
}

export function activateGoal(goalId: string) {
  return request(`/v1/goals/${encodeURIComponent(goalId)}/activate`, { method: "POST" });
}

export function ingestSource(payload: {
  kind?: "markdown" | "pdf" | "url" | "note" | "audio" | "video";
  title?: string;
  text?: string;
  uri?: string | null;
}) {
  return request<InboxItem>("/v1/sources", {
    method: "POST",
    body: JSON.stringify({
      kind: payload.kind ?? "note",
      title: payload.title ?? "",
      text: payload.text ?? "",
      uri: payload.uri ?? null,
    }),
  });
}

export function ingestUpload(
  file: File,
  title?: string,
  onProgress?: (percent: number) => void,
) {
  const body = new FormData();
  body.append("file", file);
  if (title?.trim()) body.append("title", title.trim());
  return new Promise<InboxItem>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/v1/sources/upload");
    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      const raw = xhr.responseText || "";
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(raw) as InboxItem);
        } catch {
          reject(new Error("上传成功但响应无法解析"));
        }
        return;
      }
      reject(new Error(_detailFromBody(raw) || xhr.statusText || "上传失败"));
    };
    xhr.onerror = () => reject(new Error("上传中断，请重试"));
    xhr.send(body);
  });
}

function _detailFromBody(raw: string) {
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* keep raw */
  }
  return raw;
}

export function acceptInbox(id: string) {
  return request<InboxItem>(`/v1/inbox/${id}/accept`, { method: "POST" });
}

export function rejectInbox(id: string) {
  return request<InboxItem>(`/v1/inbox/${id}/reject`, { method: "POST" });
}

export function sendChat(content: string, pinnedNodeIds: string[], expandCrossTopic = false) {
  return request<ChatMessage>("/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      content,
      pinned_node_ids: pinnedNodeIds,
      expand_cross_topic: expandCrossTopic,
    }),
  });
}

export function linkRelation(fromId: string, toId: string, messageId?: string) {
  return request<Relation>("/v1/relations", {
    method: "POST",
    body: JSON.stringify({
      from_id: fromId,
      to_id: toId,
      message_id: messageId ?? null,
    }),
  });
}

export function gradeProbe(probeId: string, payload: { option_id?: string; text?: string }) {
  return request<ChatMessage>(`/v1/probes/${encodeURIComponent(probeId)}/grade`, {
    method: "POST",
    body: JSON.stringify({
      option_id: payload.option_id ?? null,
      text: payload.text ?? null,
    }),
  });
}

export function resolveMisconception(misconceptionId: string) {
  return request(`/v1/misconceptions/${encodeURIComponent(misconceptionId)}/resolve`, {
    method: "POST",
  });
}

export function startReview(claimId?: string) {
  return request<ChatMessage>("/v1/learn/reviews", {
    method: "POST",
    body: JSON.stringify({ claim_id: claimId ?? null }),
  });
}

export function captureLesson(messageId: string, chapterId: string) {
  return request<Relation[]>("/v1/learn/capture", {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, chapter_id: chapterId }),
  });
}

export function composeBrief(pinnedNodeIds: string[], question?: string) {
  return request<DecisionBrief>("/v1/briefs/compose", {
    method: "POST",
    body: JSON.stringify({
      question: question || null,
      pinned_node_ids: pinnedNodeIds,
    }),
  });
}

export function commitBrief(briefId: string, optionId: string, rationale?: string) {
  return request<DecisionBrief>(`/v1/briefs/${briefId}/commit`, {
    method: "POST",
    body: JSON.stringify({ option_id: optionId, rationale }),
  });
}

export function reviewBrief(briefId: string, outcome: string) {
  return request<DecisionBrief>(`/v1/briefs/${briefId}/review`, {
    method: "POST",
    body: JSON.stringify({ outcome }),
  });
}

export function scratchNote(text: string, title?: string) {
  return request<InboxItem>("/v1/notes", {
    method: "POST",
    body: JSON.stringify({ text, title: title ?? "" }),
  });
}

export function runPlay(payload: {
  play_id: PlayId;
  kind?: SourceKind | null;
  title?: string;
  text?: string;
  uri?: string;
  compose_brief?: boolean;
}) {
  return request<RunPlayResult>("/v1/plays/run", {
    method: "POST",
    body: JSON.stringify({
      play_id: payload.play_id,
      kind: payload.kind ?? null,
      title: payload.title ?? "",
      text: payload.text ?? "",
      uri: payload.uri ?? null,
      compose_brief: payload.compose_brief ?? false,
    }),
  });
}

export function confirmHang(claimIds: string[], targetId: string, newName?: string) {
  return request<Relation[]>("/v1/hangs/confirm", {
    method: "POST",
    body: JSON.stringify({
      claim_ids: claimIds,
      target_id: targetId || "",
      new_name: newName || "",
    }),
  });
}

export function mergeConcepts(keepId: string, dropId: string) {
  return request("/v1/concepts/merge", {
    method: "POST",
    body: JSON.stringify({ keep_id: keepId, drop_id: dropId }),
  });
}

export function deprecateClaim(claimId: string) {
  return request(`/v1/claims/${encodeURIComponent(claimId)}/deprecate`, { method: "POST" });
}

export function setClaimLayer(claimId: string, layer: "keep" | "lookup" | null) {
  return request(`/v1/claims/${encodeURIComponent(claimId)}/layer`, {
    method: "POST",
    body: JSON.stringify({ layer }),
  });
}

export function touchClaim(claimId: string) {
  return request(`/v1/claims/${encodeURIComponent(claimId)}/touch`, { method: "POST" });
}

export function saveProfile(profile: Profile) {
  return request<Profile>("/v1/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export function fetchWeeklyReport() {
  return request<WeeklyReport>("/v1/report/weekly");
}
