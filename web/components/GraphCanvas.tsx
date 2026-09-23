"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphNode, NodeKind, Relation } from "@/lib/types";
import {
  ancestorsOfIds,
  buildMindForest,
  collectTreeEdges,
  findMindNode,
  layoutFocusGrid,
  parentInPath,
  pathToNode,
} from "@/lib/mindmap";
import { KnowledgeSearch } from "./KnowledgeSearch";
import { emptyCopy } from "@/lib/copy";

const KIND_LABEL: Record<NodeKind, string> = {
  goal: "主题",
  concept: "概念",
  claim: "主张",
  decision: "决策",
  source: "来源",
  misconception: "误区",
};

type CanvasData = {
  kind: NodeKind;
  label: string;
  subtitle?: string | null;
  pinned: boolean;
  selected: boolean;
  matched: boolean;
  dimmed: boolean;
  childCount: number;
  descendantCount: number;
  expanded: boolean;
};

type CanvasNode = Node<CanvasData>;

function LyNode({ data }: NodeProps<CanvasNode>) {
  const tone =
    data.kind === "claim"
      ? "border-gold/70"
      : data.kind === "decision"
        ? "border-moss/70"
        : data.kind === "goal"
          ? "border-haze/70"
          : data.kind === "misconception"
            ? "border-clay/70"
            : "border-line";
  return (
    <div
      className={`w-[220px] border bg-raised px-3 py-2 ${tone} ${
        data.selected ? "ring-2 ring-gold" : data.pinned ? "ring-1 ring-gold/60" : ""
      } ${data.matched ? "bg-gold/15" : ""} ${data.dimmed ? "opacity-35" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-line !bg-muted" />
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted">{KIND_LABEL[data.kind]}</p>
        {data.childCount > 0 ? (
          <span className="shrink-0 text-[10px] text-gold">{data.descendantCount} 项</span>
        ) : null}
      </div>
      <p className="mt-1 line-clamp-3 text-sm leading-5">{data.label}</p>
      {data.subtitle ? <p className="mt-1 truncate text-[11px] text-muted">{data.subtitle}</p> : null}
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-line !bg-muted" />
    </div>
  );
}

const nodeTypes = { lynote: LyNode };

export function GraphCanvas({
  graph,
  pinned,
  selectedId,
  drillId = null,
  onSelect,
  onDrill,
  onTogglePin,
}: {
  graph: { nodes: GraphNode[]; edges: Relation[] };
  pinned: string[];
  selectedId: string | null;
  drillId?: string | null;
  onSelect: (id: string) => void;
  onDrill: (id: string | null) => void;
  onTogglePin: (id: string) => void;
}) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner
        graph={graph}
        pinned={pinned}
        selectedId={selectedId}
        drillId={drillId}
        onSelect={onSelect}
        onDrill={onDrill}
        onTogglePin={onTogglePin}
      />
    </ReactFlowProvider>
  );
}

function GraphCanvasInner({
  graph,
  pinned,
  selectedId,
  drillId,
  onSelect,
  onDrill,
  onTogglePin,
}: {
  graph: { nodes: GraphNode[]; edges: Relation[] };
  pinned: string[];
  selectedId: string | null;
  drillId?: string | null;
  onSelect: (id: string) => void;
  onDrill: (id: string | null) => void;
  onTogglePin: (id: string) => void;
}) {
  const [hitIds, setHitIds] = useState<string[]>([]);
  const [focusTick, setFocusTick] = useState(0);
  const { fitView } = useReactFlow();
  const graphKey = useMemo(
    () => graph.nodes.map((node) => node.id).sort().join("|"),
    [graph.nodes],
  );

  const forest = useMemo(() => buildMindForest(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const rootId = forest[0]?.id ?? null;
  const activeDrill = drillId && findMindNode(forest, drillId) ? drillId : rootId;
  const trail = useMemo(
    () => (activeDrill ? pathToNode(forest, activeDrill) ?? [] : []),
    [forest, activeDrill],
  );

  useEffect(() => {
    setHitIds([]);
  }, [graphKey]);

  const rememberHits = useCallback((ids: string[]) => {
    setHitIds(ids);
  }, []);

  const locate = useCallback(
    (id: string, pathIds: string[]) => {
      onSelect(id);
      const parent = pathIds[pathIds.length - 2] ?? pathIds[0] ?? id;
      const node = findMindNode(forest, id);
      onDrill(node && node.children.length > 0 ? id : parent);
      setFocusTick((tick) => tick + 1);
    },
    [onSelect, onDrill, forest],
  );

  const laidOut = useMemo(() => layoutFocusGrid(forest, activeDrill), [forest, activeDrill]);
  const visible = useMemo(() => new Set(laidOut.map((item) => item.id)), [laidOut]);
  const byId = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const forcedOpen = useMemo(() => {
    const ids = new Set(hitIds);
    if (selectedId) ids.add(selectedId);
    return ancestorsOfIds(forest, ids);
  }, [forest, hitIds, selectedId]);

  const nodes: CanvasNode[] = useMemo(() => {
    const searching = hitIds.length > 0;
    return laidOut.map((item) => {
      const node = byId.get(item.id);
      const matched = searching && hitIds.includes(item.id);
      return {
        id: item.id,
        type: "lynote",
        position: { x: item.x, y: item.y },
        selected: selectedId === item.id,
        data: {
          kind: node?.kind ?? "concept",
          label: node?.label ?? item.id,
          subtitle: node?.subtitle,
          pinned: pinned.includes(item.id),
          selected: selectedId === item.id,
          matched,
          dimmed: searching && !matched && !forcedOpen.has(item.id),
          childCount: item.childCount,
          descendantCount: item.descendantCount,
          expanded: true,
        },
      };
    });
  }, [laidOut, byId, pinned, selectedId, hitIds, forcedOpen]);

  const edges: Edge[] = useMemo(() => {
    const tree = collectTreeEdges(forest).filter(
      (edge) => visible.has(edge.parentId) && visible.has(edge.childId),
    );
    const treeKeys = new Set(tree.map((edge) => `${edge.parentId}->${edge.childId}`));
    const extra = graph.edges.filter((rel) => {
      if (!visible.has(rel.from_id) || !visible.has(rel.to_id)) return false;
      if (treeKeys.has(`${rel.from_id}->${rel.to_id}`) || treeKeys.has(`${rel.to_id}->${rel.from_id}`)) {
        return rel.type === "contradicts";
      }
      return rel.type === "contradicts" || rel.type === "supports";
    });
    return [
      ...tree.map((edge) => ({
        id: `tree-${edge.parentId}-${edge.childId}`,
        source: edge.parentId,
        target: edge.childId,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#9a8d7c" },
        style: { stroke: "#6d6458" },
      })),
      ...extra.map((rel) => ({
        id: rel.id,
        source: rel.from_id,
        target: rel.to_id,
        label: rel.type,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: rel.type === "contradicts" ? "#c45c4a" : "#9a8d7c",
        },
        style: {
          stroke: rel.type === "contradicts" ? "#c45c4a" : "#6d6458",
          strokeDasharray: rel.type === "contradicts" ? "5 4" : undefined,
        },
        labelStyle: { fill: "#9a8d7c", fontSize: 10 },
      })),
    ];
  }, [forest, visible, graph.edges]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fitView({ padding: 0.18, duration: 220 });
    }, 40);
    return () => window.clearTimeout(timer);
  }, [graphKey, activeDrill, focusTick, laidOut.length, fitView]);

  const parentId = activeDrill ? parentInPath(forest, activeDrill) : null;
  const trailLabel = trail.map((node) => node.label).join(" / ");

  return (
    <section className="relative h-full min-h-0 bg-ink">
      <div className="absolute left-4 right-4 top-3 z-10 flex flex-wrap items-center gap-2">
        <KnowledgeSearch onLocate={locate} onHits={rememberHits} />
        <button
          type="button"
          className="border border-line px-2 py-1 text-[11px] text-muted hover:border-gold hover:text-gold"
          onClick={() => onDrill(rootId)}
        >
          总览
        </button>
        <button
          type="button"
          disabled={!parentId}
          className="border border-line px-2 py-1 text-[11px] text-muted hover:border-gold hover:text-gold disabled:opacity-40"
          onClick={() => parentId && onDrill(parentId)}
        >
          上一级
        </button>
        <p className="max-w-xl truncate text-[11px] text-muted">
          {trailLabel || "主题在上，下一层分排。点有子项的节点进入下一级，兄弟层会收起。"}
        </p>
      </div>
      {graph.nodes.length <= 1 ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center p-8">
          <p className="max-w-sm text-center text-sm leading-6 text-muted">{emptyCopy.noGraph}</p>
        </div>
      ) : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        fitView
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          onSelect(node.id);
          onDrill(node.id);
        }}
        onNodeDoubleClick={(_, node) => onTogglePin(node.id)}
        minZoom={0.2}
        maxZoom={1.5}
        className="pt-12"
      >
        <Background color="#3b342b" gap={22} />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          maskColor="rgba(18,16,14,0.72)"
          nodeColor="#8a7a64"
          className="!bg-panel !border-line"
        />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
    </section>
  );
}
