import type { GraphNode, NodeKind, Relation } from "./types";

export type MindNode = {
  id: string;
  kind: NodeKind;
  label: string;
  subtitle?: string | null;
  children: MindNode[];
};

export type LaidOutNode = {
  id: string;
  x: number;
  y: number;
  depth: number;
  childCount: number;
  descendantCount: number;
};

const NODE_H = 92;
const NODE_W = 240;
const GAP_Y = 18;
const GAP_X = 72;

export function buildMindForest(nodes: GraphNode[], relations: Relation[]): MindNode[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const parentOf = new Map<string, { id: string; score: number }>();

  const wouldCycle = (childId: string, parentId: string) => {
    let cursor: string | undefined = parentId;
    const seen = new Set<string>();
    while (cursor) {
      if (cursor === childId) return true;
      if (seen.has(cursor)) return true;
      seen.add(cursor);
      cursor = parentOf.get(cursor)?.id;
    }
    return false;
  };

  const consider = (childId: string, parentId: string, score: number) => {
    if (!byId.has(childId) || !byId.has(parentId) || childId === parentId) return;
    if (wouldCycle(childId, parentId)) return;
    const current = parentOf.get(childId);
    if (!current || score > current.score) {
      parentOf.set(childId, { id: parentId, score });
    }
  };

  for (const rel of relations) {
    const from = byId.get(rel.from_id);
    const to = byId.get(rel.to_id);
    if (!from || !to) continue;
    if (rel.type === "belongs_to") {
      consider(rel.from_id, rel.to_id, 100);
      continue;
    }
    if (rel.type === "evidenced_by") {
      if (from.kind === "claim" && to.kind === "source") consider(to.id, from.id, 85);
      if (to.kind === "claim" && from.kind === "source") consider(from.id, to.id, 85);
      continue;
    }
    if (rel.type === "decides") {
      if (from.kind === "decision" && to.kind === "goal") consider(from.id, to.id, 90);
      if (to.kind === "decision" && from.kind === "goal") consider(to.id, from.id, 90);
      continue;
    }
    if (rel.type !== "about") continue;
    if (from.kind === "misconception" && to.kind === "claim") {
      consider(from.id, to.id, 95);
      continue;
    }
    if (to.kind === "misconception" && from.kind === "claim") {
      consider(to.id, from.id, 95);
      continue;
    }
    if (to.kind === "concept" && from.kind !== "concept") {
      consider(from.id, to.id, from.kind === "claim" ? 80 : 70);
    } else if (from.kind === "concept" && to.kind === "goal") {
      consider(from.id, to.id, 90);
    } else if (from.kind === "goal" && to.kind === "concept") {
      consider(to.id, from.id, 90);
    } else if (to.kind === "goal" && from.kind !== "goal") {
      consider(from.id, to.id, 40);
    }
  }

  const children = new Map<string, string[]>();
  for (const node of nodes) children.set(node.id, []);
  for (const [childId, parent] of parentOf) {
    children.get(parent.id)?.push(childId);
  }

  const kindOrder: Record<NodeKind, number> = {
    goal: 0,
    concept: 1,
    decision: 2,
    claim: 3,
    misconception: 4,
    source: 5,
  };
  const sortIds = (ids: string[]) =>
    ids.sort((a, b) => {
      const left = byId.get(a);
      const right = byId.get(b);
      if (!left || !right) return a.localeCompare(b);
      return kindOrder[left.kind] - kindOrder[right.kind] || left.label.localeCompare(right.label, "zh");
    });

  const visit = (id: string, trail: Set<string>): MindNode => {
    const node = byId.get(id)!;
    const kids = trail.has(id) ? [] : sortIds([...(children.get(id) ?? [])]);
    const nextTrail = new Set(trail);
    nextTrail.add(id);
    return {
      id: node.id,
      kind: node.kind,
      label: node.label,
      subtitle: node.subtitle,
      children: kids.map((childId) => visit(childId, nextTrail)),
    };
  };

  let roots = nodes.filter((node) => !parentOf.has(node.id)).map((node) => node.id);
  const goalRoot = roots.find((id) => byId.get(id)?.kind === "goal");
  if (goalRoot) {
    for (const rootId of roots) {
      if (rootId !== goalRoot) consider(rootId, goalRoot, 10);
    }
    const rebuilt = new Map<string, string[]>();
    for (const node of nodes) rebuilt.set(node.id, []);
    for (const [childId, parent] of parentOf) {
      rebuilt.get(parent.id)?.push(childId);
    }
    for (const [id, list] of rebuilt) children.set(id, list);
    roots = [goalRoot];
  } else {
    roots = sortIds(roots);
  }

  return roots.filter((id) => byId.has(id)).map((id) => visit(id, new Set()));
}

export function countDescendants(node: MindNode): number {
  return node.children.reduce((sum, child) => sum + 1 + countDescendants(child), 0);
}

export function defaultCollapsedIds(forest: MindNode[], totalNodes: number): Set<string> {
  const collapsed = new Set<string>();
  if (totalNodes <= 10) return collapsed;
  const walk = (node: MindNode, depth: number) => {
    if (depth >= 1 && node.children.length > 0) collapsed.add(node.id);
    for (const child of node.children) walk(child, depth + 1);
  };
  for (const root of forest) walk(root, 0);
  return collapsed;
}

export function layoutMindForest(
  forest: MindNode[],
  collapsed: Set<string>,
  forcedOpen: Set<string>,
): LaidOutNode[] {
  const placed: LaidOutNode[] = [];
  let yCursor = 24;

  const layout = (node: MindNode, depth: number, y: number): number => {
    const open = forcedOpen.has(node.id) || !collapsed.has(node.id);
    const childCount = node.children.length;
    const descendantCount = countDescendants(node);
    if (!open || childCount === 0) {
      placed.push({
        id: node.id,
        x: 32 + depth * (NODE_W + GAP_X),
        y,
        depth,
        childCount,
        descendantCount,
      });
      return NODE_H;
    }
    let childY = y;
    const childHeights: number[] = [];
    for (const child of node.children) {
      const height = layout(child, depth + 1, childY);
      childHeights.push(height);
      childY += height + GAP_Y;
    }
    const span = childHeights.reduce((sum, height) => sum + height, 0) + GAP_Y * (childCount - 1);
    const selfY = y + Math.max(0, span / 2 - NODE_H / 2);
    placed.push({
      id: node.id,
      x: 32 + depth * (NODE_W + GAP_X),
      y: selfY,
      depth,
      childCount,
      descendantCount,
    });
    return Math.max(span, NODE_H);
  };

  for (const root of forest) {
    const height = layout(root, 0, yCursor);
    yCursor += height + 36;
  }
  return placed;
}

export function collectTreeEdges(forest: MindNode[]): Array<{ parentId: string; childId: string }> {
  const edges: Array<{ parentId: string; childId: string }> = [];
  const walk = (node: MindNode) => {
    for (const child of node.children) {
      edges.push({ parentId: node.id, childId: child.id });
      walk(child);
    }
  };
  for (const root of forest) walk(root);
  return edges;
}

export function findMindNode(forest: MindNode[], id: string): MindNode | null {
  const walk = (node: MindNode): MindNode | null => {
    if (node.id === id) return node;
    for (const child of node.children) {
      const hit = walk(child);
      if (hit) return hit;
    }
    return null;
  };
  for (const root of forest) {
    const hit = walk(root);
    if (hit) return hit;
  }
  return null;
}

export function pathToNode(forest: MindNode[], id: string): MindNode[] | null {
  const walk = (node: MindNode, trail: MindNode[]): MindNode[] | null => {
    const next = [...trail, node];
    if (node.id === id) return next;
    for (const child of node.children) {
      const hit = walk(child, next);
      if (hit) return hit;
    }
    return null;
  };
  for (const root of forest) {
    const hit = walk(root, []);
    if (hit) return hit;
  }
  return null;
}

const GRID_COLS = 3;
const GRID_NODE_H = 88;
const GRID_NODE_W = 220;
const GRID_GAP_X = 28;
const GRID_GAP_Y = 32;
const GRID_TRAIL_GAP = 22;

export function layoutFocusGrid(forest: MindNode[], focusId: string | null): LaidOutNode[] {
  const root = forest[0];
  if (!root) return [];
  const targetId = focusId && findMindNode(forest, focusId) ? focusId : root.id;
  const path = pathToNode(forest, targetId) ?? [root];
  const trail = path.length <= 3 ? path : path.slice(path.length - 3);
  const focus = trail[trail.length - 1];
  const gridWidth = GRID_COLS * GRID_NODE_W + (GRID_COLS - 1) * GRID_GAP_X;
  const centerX = 40 + gridWidth / 2 - GRID_NODE_W / 2;
  const placed: LaidOutNode[] = [];

  trail.forEach((node, depth) => {
    placed.push({
      id: node.id,
      x: centerX,
      y: 16 + depth * (GRID_NODE_H + GRID_TRAIL_GAP),
      depth,
      childCount: node.children.length,
      descendantCount: countDescendants(node),
    });
  });

  const childTop = 16 + trail.length * (GRID_NODE_H + GRID_TRAIL_GAP) + 8;
  focus.children.forEach((child, index) => {
    const col = index % GRID_COLS;
    const row = Math.floor(index / GRID_COLS);
    placed.push({
      id: child.id,
      x: 40 + col * (GRID_NODE_W + GRID_GAP_X),
      y: childTop + row * (GRID_NODE_H + GRID_GAP_Y),
      depth: trail.length,
      childCount: child.children.length,
      descendantCount: countDescendants(child),
    });
  });
  return placed;
}

export function parentInPath(forest: MindNode[], id: string): string | null {
  const path = pathToNode(forest, id);
  if (!path || path.length < 2) return null;
  return path[path.length - 2]?.id ?? null;
}

export function nodeMatches(node: { label: string; subtitle?: string | null; id: string }, query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return false;
  return [node.label, node.subtitle ?? "", node.id].join(" ").toLowerCase().includes(needle);
}

export function ancestorsOfIds(forest: MindNode[], ids: Set<string>): Set<string> {
  const forced = new Set<string>();
  if (ids.size === 0) return forced;
  const walk = (node: MindNode, trail: string[]): boolean => {
    const hit = ids.has(node.id) || node.children.some((child) => walk(child, [...trail, node.id]));
    if (hit) {
      for (const id of trail) forced.add(id);
      forced.add(node.id);
    }
    return hit;
  };
  for (const root of forest) walk(root, []);
  return forced;
}
