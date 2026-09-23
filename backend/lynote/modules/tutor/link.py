"""Human-confirmed related_to. Code writes the edge; the model does not invent nodes."""

from __future__ import annotations

from lynote.contracts.models import ChatMessage, GroundedAnswer, GroundedRef, Relation, TransferRef
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.layers import _has_opposition
from lynote.modules.tutor.grounded import _claim_ref, _render

_LINKABLE = {"claim", "concept"}
_BLOCKING = {"about", "related_to", "contradicts", "supports"}


def write_related_to(store: InMemoryGraphStore, from_id: str, to_id: str) -> Relation:
    if from_id == to_id:
        raise ValueError("不能把节点标成和自己相关")
    left = store.as_node(from_id)
    right = store.as_node(to_id)
    if left is None:
        raise KeyError(from_id)
    if right is None:
        raise KeyError(to_id)
    if left.kind not in _LINKABLE or right.kind not in _LINKABLE:
        raise ValueError("只能把图上已有的概念或主张标成相关，不能发明节点")
    for rel in store.relations.values():
        if {rel.from_id, rel.to_id} != {from_id, to_id}:
            continue
        if rel.type == "related_to":
            return rel
        if rel.type in _BLOCKING:
            raise ValueError("这两个节点已经有边")
    relation = Relation(
        id=new_id("rel"),
        from_id=from_id,
        to_id=to_id,
        type="related_to",
    )
    return store.upsert_relation(relation)


def apply_confirmed_link(
    message: ChatMessage,
    relation: Relation,
    store: InMemoryGraphStore,
) -> ChatMessage:
    grounded = message.grounded
    if grounded is None:
        return message
    other_id = _other_end(grounded, relation)
    extra = _ref_for(store, other_id)
    related = list(grounded.related)
    if extra is not None and all(ref.id != extra.id for ref in related):
        related.append(extra)
    transfers = list(grounded.transfers)
    extra_claim = store.claims.get(other_id) if extra is not None and extra.kind == "claim" else None
    if extra_claim is not None and _has_opposition(store, extra_claim):
        if all(item.to_id != extra_claim.id for item in transfers):
            anchor = next((ref for ref in list(grounded.direct) + list(grounded.lookup) if ref.kind == "claim"), None)
            if anchor is not None:
                transfers.append(
                    TransferRef(
                        from_id=anchor.id,
                        from_label=anchor.label,
                        to_id=extra_claim.id,
                        to_label=extra_claim.text,
                        path_ids=[anchor.id, extra_claim.id],
                        reason="同一类取舍",
                    )
                )
    updated = grounded.model_copy(
        update={
            "related": related,
            "unlinked": False,
            "link_candidates": [],
            "transfers": transfers,
        }
    )
    claim_ids = list(message.claim_ids)
    if extra is not None and extra.kind == "claim" and extra.id not in claim_ids:
        claim_ids.append(extra.id)
    return message.model_copy(
        update={
            "grounded": updated,
            "content": _render(_question_from_content(message.content), updated),
            "claim_ids": claim_ids,
        }
    )


def _other_end(grounded: GroundedAnswer, relation: Relation) -> str:
    direct_ids = {ref.id for ref in grounded.direct} | {ref.id for ref in grounded.lookup}
    if relation.from_id in direct_ids:
        return relation.to_id
    if relation.to_id in direct_ids:
        return relation.from_id
    return relation.to_id


def _ref_for(store: InMemoryGraphStore, node_id: str) -> GroundedRef | None:
    claim = store.claims.get(node_id)
    if claim is not None:
        return _claim_ref(claim, "related_to")
    node = store.as_node(node_id)
    if node is None:
        return None
    return GroundedRef(id=node.id, kind=node.kind, label=node.label, relation="related_to")


def _question_from_content(content: str) -> str:
    prefix = "针对「"
    if content.startswith(prefix) and "」" in content:
        return content[len(prefix) : content.index("」")]
    return ""
