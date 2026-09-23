"""Workspace facade. Keeps module boundaries explicit."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from lynote.config import settings
from lynote.contracts.models import (
    CaptureLessonRequest,
    ChatMessage,
    ChatRequest,
    CommitBriefRequest,
    ComposeBriefRequest,
    ConfirmHangRequest,
    CreateGoalRequest,
    DecisionBrief,
    Goal,
    GradeProbeRequest,
    GraphSnapshot,
    HangProposal,
    InboxItem,
    IngestSourceRequest,
    KnowledgeSearchResponse,
    LinkRelationRequest,
    MergeConceptsRequest,
    Misconception,
    NodeDetail,
    PlayId,
    PracticeStat,
    Profile,
    Relation,
    ReviewBriefRequest,
    RunPlayRequest,
    RunPlayResult,
    ScratchNoteRequest,
    StartReviewRequest,
    TopicLearn,
    Workbench,
)
from lynote.modules.brief.service import BriefService, bind_brief
from lynote.modules.extract.service import ExtractService
from lynote.modules.gate.service import GateService
from lynote.modules.graph.factory import build_graph_store
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.inspect import inspect_node
from lynote.modules.graph.maintain import deprecate_claim, merge_concepts
from lynote.modules.graph.persist import load_workspace_state, save_workspace_state
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.ingest.service import IngestService
from lynote.modules.learn.crosstopic import find_cross_topic
from lynote.modules.learn.hang import confirm_hang, propose_hangs, prune_proposal
from lynote.modules.learn.industry import apply_industry_hints
from lynote.modules.learn.outline import capture_to_chapter, compose_outline
from lynote.modules.learn.pack import attach_pack, set_layer_override
from lynote.modules.learn.plays import catalog, compose_play_context, get_play, next_hint, normalize_kind
from lynote.modules.learn.prior import find_prior_decisions
from lynote.modules.learn.report import compose_weekly_report
from lynote.modules.learn.service import (
    apply_gap_boost,
    compose_learn,
    rank_inbox,
    record_practice,
    record_use,
    start_review_message,
)
from lynote.modules.learn.today import compose_today
from lynote.modules.retrieve.context import context_still_active
from lynote.modules.retrieve.search import search_knowledge as search_topic
from lynote.modules.retrieve.service import RetrieveService
from lynote.modules.tutor.grounded import compose_grounded_answer
from lynote.modules.tutor import misconceptions as misc
from lynote.modules.tutor.link import apply_confirmed_link, write_related_to
from lynote.modules.tutor.probe import grade_probe_answer
from lynote import seed


class Workspace:
    def __init__(
        self,
        *,
        graph: InMemoryGraphStore | None = None,
        gate: GateService | None = None,
        extract: ExtractService | None = None,
        retrieve: RetrieveService | None = None,
        briefing: BriefService | None = None,
        ingest: IngestService | None = None,
        persist: bool | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        self.graph = graph if graph is not None else build_graph_store()
        self.ingest = ingest or IngestService()
        self.gate = gate or GateService()
        self.extract = extract or ExtractService()
        self.retrieve = retrieve or RetrieveService()
        self.briefing = briefing or BriefService()
        self.inbox: dict[str, InboxItem] = {}
        self.messages: list[ChatMessage] = []
        self.brief: DecisionBrief | None = None
        self.practice: dict[str, PracticeStat] = {}
        self.profile = Profile()
        self.hangs: list[HangProposal] = []
        self.brief_touched_at: datetime | None = None
        self.brief_touched_goal_id: str | None = None
        self.layer_overrides: dict[str, str] = {}
        self.play_context_id: PlayId | None = None
        self.play_context_at: datetime | None = None
        self.play_context_goal_id: str | None = None
        self._state_path = (
            Path(state_path)
            if state_path is not None
            else settings.resolve_data_path(settings.workspace_state_path)
        )
        self._persist_enabled = (
            persist
            if persist is not None
            else settings.graph_backend.strip().lower() not in {"", "memory"}
        )
        self._boot()

    def _boot(self) -> None:
        if self._persist_enabled and not self.graph.is_empty():
            loaded = load_workspace_state(self._state_path)
            self.inbox, self.messages, self.brief, self.practice, self.profile, self.hangs = loaded[:6]
            self.brief_touched_at = _parse_touched(loaded[6] if len(loaded) > 6 else None)
            self.brief_touched_goal_id = loaded[7] if len(loaded) > 7 else None
            self.layer_overrides = dict(loaded[8]) if len(loaded) > 8 else {}
            ctx = loaded[9] if len(loaded) > 9 else None
            if ctx:
                play_id = ctx.get("play_id")
                self.play_context_id = play_id if play_id in {"read_article", "after_meeting"} else None
                self.play_context_at = _parse_touched(ctx.get("at"))
                self.play_context_goal_id = ctx.get("goal_id") or None
            self.retrieve.sync(self.graph)
            self._bind_unscoped_sources()
            if self.brief is None:
                self.brief = self.compose_brief(ComposeBriefRequest(), count_as_today=False)
                self._save_state()
            return
        self._load_seed()
        self.retrieve.sync(self.graph)
        self.brief = self.compose_brief(ComposeBriefRequest(), count_as_today=False)
        self._save_state()

    def _load_seed(self) -> None:
        self.graph.upsert_goal(seed.GOAL.model_copy(deep=True))
        for source in seed.SOURCES:
            self.graph.upsert_source(source.model_copy(deep=True))
        for concept in seed.CONCEPTS:
            self.graph.upsert_concept(concept.model_copy(deep=True))
        for claim in seed.CLAIMS:
            self.graph.upsert_claim(claim.model_copy(deep=True))
        self.graph.upsert_decision(seed.DECISION.model_copy(deep=True))
        for relation in seed.RELATIONS:
            self.graph.upsert_relation(relation.model_copy(deep=True))
        for item in seed.INBOX:
            copied = item.model_copy(deep=True)
            self.inbox[copied.id] = copied
        self.messages = [message.model_copy(deep=True) for message in seed.MESSAGES]

    def _save_state(self) -> None:
        if not self._persist_enabled:
            return
        save_workspace_state(
            self._state_path,
            self.inbox,
            self.messages,
            self.brief,
            self.practice,
            self.profile,
            self.hangs,
            brief_touched_at=self.brief_touched_at.isoformat() if self.brief_touched_at else None,
            brief_touched_goal_id=self.brief_touched_goal_id,
            layer_overrides=self.layer_overrides,
            play_context=(
                {
                    "play_id": self.play_context_id,
                    "at": self.play_context_at.isoformat() if self.play_context_at else "",
                    "goal_id": self.play_context_goal_id or "",
                }
                if self.play_context_id
                else None
            ),
        )

    def workbench(self) -> Workbench:
        goal = self._active_goal()
        graph = self.graph.neighborhood(goal.id) if goal else self.graph.snapshot()
        allowed = {node.id for node in graph.nodes}
        inbox = [
            item
            for item in self.inbox.values()
            if not allowed or item.source_id in allowed
        ]
        learn = self._learn(allowed)
        inbox = rank_inbox(inbox, self.graph, learn.gaps)
        for item in inbox:
            self.inbox[item.id] = item
        self.hangs = [item for item in (prune_proposal(item, self.graph) for item in self.hangs) if item]
        self.hangs = [
            attach_pack(item, self.graph, self.practice, self.layer_overrides) for item in self.hangs
        ]
        return Workbench(
            goals=list(self.graph.goals.values()),
            inbox=inbox,
            graph=graph,
            brief=self._brief_for_goal(goal),
            messages=self.messages,
            learn=learn,
            outline=compose_outline(
                self.graph,
                goal.id if goal else None,
                practice=self.practice,
                overrides=self.layer_overrides,
            ),
            hangs=self.hangs,
            today=compose_today(
                self.graph,
                inbox=inbox,
                learn=learn,
                goal=goal,
                allowed_ids=allowed if goal is not None else None,
                brief_touched_at=self.brief_touched_at,
                brief_touched_goal_id=self.brief_touched_goal_id,
            ),
            profile=self.profile,
            plays=catalog(),
            play_context=self._play_context(),
        )

    def create_goal(self, payload: CreateGoalRequest) -> Goal:
        title = payload.title.strip()
        question = payload.question.strip() or title
        if not title:
            raise ValueError("主题名称不能空")
        self._pause_active_goals()
        goal = Goal(
            id=new_id("goal"),
            title=title,
            question=question,
            status="active",
        )
        saved = self.graph.upsert_goal(goal)
        self._compose_for_active_goal(use_model=False)
        self._save_state()
        return saved

    def activate_goal(self, goal_id: str) -> Goal:
        goal = self.graph.goals.get(goal_id)
        if goal is None:
            raise KeyError(goal_id)
        if goal.status != "active":
            self._pause_active_goals()
            goal.status = "active"
            self.graph.upsert_goal(goal)
        self._compose_for_active_goal(use_model=False)
        self._save_state()
        return goal

    def node_detail(self, node_id: str) -> NodeDetail:
        return inspect_node(self.graph, node_id)

    def ingest_source(self, payload: IngestSourceRequest) -> InboxItem:
        source = self.ingest.ingest(payload)
        self.graph.upsert_source(source)
        self._bind_nodes_to_active_goal([source.id])
        item = self.gate.evaluate(
            source,
            self.graph.active_goals(),
            [src.title for src in self.graph.sources.values() if src.id != source.id],
        )
        item = apply_gap_boost(item, source, self._learn().gaps)
        self.inbox[item.id] = item
        self._save_state()
        return item

    def ingest_upload(self, filename: str, data: bytes, title: str = "") -> InboxItem:
        source = self.ingest.ingest_upload(filename, data, title)
        self.graph.upsert_source(source)
        self._bind_nodes_to_active_goal([source.id])
        item = self.gate.evaluate(
            source,
            self.graph.active_goals(),
            [src.title for src in self.graph.sources.values() if src.id != source.id],
        )
        item = apply_gap_boost(item, source, self._learn().gaps)
        self.inbox[item.id] = item
        self._save_state()
        return item

    def scratch_note(self, payload: ScratchNoteRequest) -> InboxItem:
        text = payload.text.strip()
        if len(text) < 8:
            raise ValueError("随手记至少写一句完整的经验")
        title = (payload.title or "").strip() or next(
            (line.strip() for line in text.splitlines() if line.strip()),
            "随手记",
        )[:40]
        return self.ingest_source(IngestSourceRequest(kind="note", title=title, text=text))

    def run_play(self, payload: RunPlayRequest) -> RunPlayResult:
        if self._active_goal() is None:
            raise ValueError("还没有学习主题。先在今日桌面点「新建主题」。")
        play = get_play(payload.play_id)
        kind = normalize_kind(play.id, payload.kind)
        if play.id == "read_article" and payload.compose_brief:
            raise ValueError("读完这篇不会打开决策简报。过闸后在下一步里接受并挂上。")
        if play.id == "after_meeting" and kind == "note":
            item = self.scratch_note(ScratchNoteRequest(text=payload.text, title=payload.title))
        else:
            item = self.ingest_source(
                IngestSourceRequest(
                    kind=kind,
                    title=payload.title,
                    text=payload.text,
                    uri=payload.uri,
                )
            )
        self._set_play_context(play.id)
        brief = None
        if payload.compose_brief:
            brief = self.compose_brief(ComposeBriefRequest(use_model=False), count_as_today=True)
        return RunPlayResult(
            play=play,
            inbox=item,
            brief=brief,
            next_hint=next_hint(play.id, item, composed=brief is not None),
        )

    def accept_inbox(self, item_id: str) -> InboxItem:
        item = self._inbox(item_id)
        source = self.graph.sources[item.source_id]
        result = self.extract.extract(source, self.graph)
        created = result.claim_ids
        self._bind_nodes_to_active_goal([source.id])
        self.retrieve.sync(self.graph)
        item.status = "accepted"
        self.inbox[item.id] = item
        goal = self._active_goal()
        claim_ids = [cid for cid in created if cid in self.graph.claims]
        proposal = propose_hangs(
            self.graph,
            claim_ids=claim_ids,
            source_id=source.id,
            inbox_id=item.id,
            goal_id=goal.id if goal else None,
            proposed_names=result.proposed_names,
        )
        if proposal:
            proposal = apply_industry_hints(
                self.graph,
                proposal,
                goal=goal,
                profile=self.profile,
            )
            self.hangs = [item for item in self.hangs if item.source_id != source.id]
            self.hangs.append(proposal)
        self._save_state()
        return item

    def reject_inbox(self, item_id: str) -> InboxItem:
        item = self._inbox(item_id)
        item.status = "rejected"
        self.inbox[item.id] = item
        self._save_state()
        return item

    def chat(self, payload: ChatRequest) -> ChatMessage:
        user = self._stamp(
            ChatMessage(id=new_id("msg"), role="user", content=payload.content),
            "learn",
        )
        self.messages.append(user)
        goal = self._active_goal()
        goal_id = goal.id if goal else None
        pins = list(payload.pinned_node_ids)
        pins.extend(misc.force_pin_ids(self.graph, payload.content, goal_id=goal_id))
        boost = 0.12 if self.profile.prefer_own_notes else 0.0
        allowed = None if payload.expand_cross_topic else self._topic_scope(pins)
        subgraph = self.retrieve.retrieve(
            payload.content,
            self.graph,
            pins,
            allowed_node_ids=allowed,
            own_note_boost=boost,
            skip_candidates=self.profile.skip_candidates,
            practice=self.practice,
            play_id=self._active_play_id(),
        )
        if not payload.expand_cross_topic:
            subgraph = self._clip_to_active_topic(subgraph, pins)
        subgraph, related = misc.merge_related(
            self.graph, subgraph, payload.content, goal_id=goal_id
        )
        answer = compose_grounded_answer(
            payload.content,
            subgraph,
            self.graph,
            pins,
            practice=self.practice,
            overrides=self.layer_overrides,
        )
        answer = misc.attach_refs(answer, misc.as_refs(self.graph, related))
        if answer.grounded is not None:
            extras: dict = {
                "prior_decisions": find_prior_decisions(self.graph, payload.content),
            }
            if not payload.expand_cross_topic:
                excluded = {node.id for node in subgraph.nodes}
                extras["cross_topic"] = find_cross_topic(self.graph, payload.content, excluded)
                if extras["cross_topic"]:
                    extras["unknowns"] = list(answer.grounded.unknowns) + [
                        f"其他主题里还有 {len(extras['cross_topic'])} 条相关主张。勾选「也搜其他主题」才展开，不会默默混进直答。"
                    ]
            answer = answer.model_copy(
                update={"grounded": answer.grounded.model_copy(update=extras)}
            )
        answer = self._stamp(answer, "learn")
        self.messages.append(answer)
        self._save_state()
        return answer

    def grade_probe(self, probe_id: str, payload: GradeProbeRequest) -> ChatMessage:
        for index, message in enumerate(self.messages):
            if message.probe is None or message.probe.id != probe_id:
                continue
            graded = grade_probe_answer(message, payload, self.graph)
            graded = self._apply_misconception(graded)
            self._apply_practice(graded)
            self.messages[index] = graded
            self._save_state()
            return graded
        raise KeyError(probe_id)

    def resolve_misconception(self, item_id: str) -> Misconception:
        try:
            saved = misc.resolve_misconception(self.graph, item_id)
        except KeyError as exc:
            raise KeyError(item_id) from exc
        self._save_state()
        return saved

    def start_review(self, payload: StartReviewRequest | None = None) -> ChatMessage:
        learn = self._learn()
        claim_id = (payload.claim_id if payload else None) or (
            learn.reviews[0].claim_id if learn.reviews else None
        )
        if not claim_id:
            raise ValueError("没有到期的巩固题")
        answer = start_review_message(
            self.graph,
            claim_id=claim_id,
            practice=self.practice,
            overrides=self.layer_overrides,
        )
        answer = self._stamp(answer, "learn")
        self.messages.append(answer)
        self._save_state()
        return answer

    def search_knowledge(self, query: str) -> KnowledgeSearchResponse:
        goal = self._active_goal()
        return search_topic(
            query,
            self.graph,
            allowed_ids=self._topic_scope(),
            goal_id=goal.id if goal else None,
            practice=self.practice,
            overrides=self.layer_overrides,
            play_id=self._active_play_id(),
        )

    def link_related(self, payload: LinkRelationRequest) -> Relation:
        if self.graph.as_node(payload.from_id) is None:
            raise KeyError(payload.from_id)
        if self.graph.as_node(payload.to_id) is None:
            raise KeyError(payload.to_id)
        allowed = self._topic_scope()
        if allowed is not None and (
            payload.from_id not in allowed or payload.to_id not in allowed
        ):
            raise ValueError("只能连接当前主题里已有的节点")
        relation = write_related_to(self.graph, payload.from_id, payload.to_id)
        if payload.message_id:
            for index, message in enumerate(self.messages):
                if message.id != payload.message_id or message.grounded is None:
                    continue
                self.messages[index] = apply_confirmed_link(message, relation, self.graph)
                break
        self._save_state()
        return relation

    def capture_lesson(self, payload: CaptureLessonRequest) -> list[Relation]:
        message = next((item for item in self.messages if item.id == payload.message_id), None)
        if message is None:
            raise KeyError(payload.message_id)
        cited = []
        if message.grounded:
            cited = list(message.grounded.direct) + list(message.grounded.lookup)
        claim_ids = [ref.id for ref in cited if ref.kind == "claim"]
        if not claim_ids:
            claim_ids = list(message.claim_ids)
        written = capture_to_chapter(
            self.graph,
            chapter_id=payload.chapter_id,
            claim_ids=claim_ids,
        )
        self._record_uses([rel.from_id for rel in written])
        self._save_state()
        return written

    def confirm_hang(self, payload: ConfirmHangRequest) -> list:
        new_name = (payload.new_name or "").strip()
        target_id = (payload.target_id or "").strip()
        allowed: set[str] = set()
        if new_name:
            for item in self.hangs:
                if set(payload.claim_ids) & set(item.claim_ids):
                    allowed.update(item.proposed_names)
        goal = self._active_goal()
        written = confirm_hang(
            self.graph,
            payload.claim_ids,
            target_id,
            new_name=new_name,
            allowed_names=allowed,
            goal_id=goal.id if goal else None,
        )
        self.retrieve.sync(self.graph)
        next_hangs = []
        for item in self.hangs:
            pruned = prune_proposal(item, self.graph)
            if pruned:
                next_hangs.append(pruned)
        self.hangs = next_hangs
        self._record_uses([rel.from_id for rel in written])
        self._save_state()
        return written

    def merge_concepts(self, payload: MergeConceptsRequest):
        kept = merge_concepts(self.graph, payload.keep_id, payload.drop_id)
        self.retrieve.sync(self.graph)
        self._save_state()
        return kept

    def deprecate_claim(self, claim_id: str):
        saved = deprecate_claim(self.graph, claim_id)
        self.retrieve.sync(self.graph)
        self._save_state()
        return saved

    def set_claim_layer(self, claim_id: str, layer: str | None):
        self.layer_overrides = set_layer_override(
            self.graph,
            self.layer_overrides,
            claim_id,
            layer if layer in {"keep", "lookup"} else None,
        )
        self._save_state()
        return {"id": claim_id, "layer": self.layer_overrides.get(claim_id)}

    def touch_claim(self, claim_id: str) -> dict[str, str | int | None]:
        claim = self.graph.claims.get(claim_id)
        if claim is None:
            raise KeyError(claim_id)
        if claim.status in {"candidate", "deprecated"}:
            raise ValueError("未确认或过时的主张不能加固")
        self._record_uses([claim_id])
        self._save_state()
        goal = self._active_goal()
        key = f"{goal.id}:{claim_id}" if goal else ""
        stat = self.practice.get(key)
        return {
            "id": claim_id,
            "use_count": stat.use_count if stat else 0,
            "next_review_at": stat.next_review_at if stat else None,
        }

    def update_profile(self, payload: Profile) -> Profile:
        self.profile = payload
        self._save_state()
        return self.profile

    def weekly_report(self):
        learn = self._learn()
        return compose_weekly_report(
            self.graph,
            inbox=list(self.inbox.values()),
            learn=learn,
        )

    def compose_brief(self, payload: ComposeBriefRequest, *, count_as_today: bool = True) -> DecisionBrief:
        goal = self._active_goal()
        if goal is None:
            goal = next(iter(self.graph.goals.values()), None)
        question = (payload.question or (goal.question if goal else "")).strip()
        if not question:
            raise ValueError("没有当前问题，无法生成简报")
        subgraph = self.retrieve.retrieve(
            question,
            self.graph,
            self._pins_with_goal(payload.pinned_node_ids),
            allowed_node_ids=self._topic_scope(payload.pinned_node_ids),
            own_note_boost=0.12 if self.profile.prefer_own_notes else 0.0,
            skip_candidates=self.profile.skip_candidates,
            practice=self.practice,
            play_id=self._active_play_id(),
        )
        subgraph = self._clip_to_active_topic(subgraph, payload.pinned_node_ids)
        if goal is not None and not any(node.kind == "claim" for node in subgraph.nodes):
            topic = self.graph.neighborhood(goal.id)
            if any(node.kind == "claim" for node in topic.nodes):
                subgraph = topic
        draft = next(
            (
                decision
                for decision in self.graph.decisions.values()
                if decision.status == "draft" and (goal is None or decision.goal_id == goal.id)
            ),
            None,
        )
        brief_id = None
        if self.brief and draft and self.brief.decision_id == draft.id:
            brief_id = self.brief.id
        self.brief = self.briefing.compose(
            question,
            subgraph,
            self.graph,
            goal=goal,
            decision=draft,
            brief_id=brief_id,
            use_model=payload.use_model,
        )
        priors = find_prior_decisions(
            self.graph,
            question,
            exclude_id=self.brief.decision_id if self.brief else None,
        )
        self.brief = self.brief.model_copy(update={"prior_decisions": priors})
        if count_as_today:
            self.brief_touched_at = datetime.now(timezone.utc)
            self.brief_touched_goal_id = goal.id if goal is not None else None
        self._save_state()
        return self.brief

    def commit_brief(self, brief_id: str, payload: CommitBriefRequest) -> DecisionBrief:
        if self.brief is None or self.brief.id != brief_id:
            raise KeyError(brief_id)
        self.brief = self.briefing.commit(
            self.brief,
            payload.option_id,
            payload.rationale,
            self.graph,
        )
        chosen = next(
            option
            for option in self.brief.options
            if option.id == payload.option_id
        )
        self.messages.append(
            self._stamp(
                ChatMessage(
                    id=new_id("msg"),
                    role="assistant",
                    content=f"已把决策写回图谱：选择「{chosen.label}」。这条 Decision 现在是 committed，后续复盘要补 outcome。",
                    claim_ids=chosen.supporting_claim_ids,
                ),
                "decision",
            )
        )
        self._record_uses(chosen.supporting_claim_ids)
        self._save_state()
        return self.brief

    def review_brief(self, brief_id: str, payload: ReviewBriefRequest) -> DecisionBrief:
        if self.brief is None or self.brief.id != brief_id:
            raise KeyError(brief_id)
        self.brief = self.briefing.review(self.brief, payload.outcome, self.graph)
        decision = self.graph.decisions[self.brief.decision_id]
        chosen_label = next(
            (option.label for option in decision.options if option.id == decision.chosen_option_id),
            decision.question,
        )
        self.messages.append(
            self._stamp(
                ChatMessage(
                    id=new_id("msg"),
                    role="assistant",
                    content=(
                        f"已把事后结果写回图谱。当时选的是「{chosen_label}」。"
                        f"Decision 现在是 reviewed：{self.brief.outcome}"
                    ),
                    claim_ids=list(self.brief.evidence_claim_ids),
                ),
                "decision",
            )
        )
        self._save_state()
        return self.brief

    def _apply_misconception(self, graded: ChatMessage) -> ChatMessage:
        grade = graded.grade
        if grade is None:
            return graded
        goal = self._active_goal()
        if goal is None:
            return graded
        if grade.verdict == "correct":
            misc.note_correct(self.graph, grade.target_claim_id, goal_id=goal.id)
            return graded
        item = misc.record_from_grade(self.graph, grade, goal_id=goal.id)
        if item is None:
            return graded
        grade = grade.model_copy(update={"misconception_id": item.id})
        return graded.model_copy(
            update={"grade": grade, "misconceptions": misc.as_refs(self.graph, [item])}
        )

    def _apply_practice(self, graded: ChatMessage) -> None:
        grade = graded.grade
        goal = self._active_goal()
        if grade is None or goal is None:
            return
        record_practice(
            self.practice,
            goal_id=goal.id,
            claim_id=grade.target_claim_id,
            verdict=grade.verdict,
        )

    def _record_uses(self, claim_ids: list[str]) -> None:
        goal = self._active_goal()
        if goal is None:
            return
        seen: set[str] = set()
        for claim_id in claim_ids:
            if claim_id in seen:
                continue
            seen.add(claim_id)
            claim = self.graph.claims.get(claim_id)
            if claim is None or claim.status in {"candidate", "deprecated"}:
                continue
            record_use(self.practice, goal_id=goal.id, claim_id=claim_id)

    def _set_play_context(self, play_id: PlayId) -> None:
        goal = self._active_goal()
        self.play_context_id = play_id
        self.play_context_at = datetime.now(timezone.utc)
        self.play_context_goal_id = goal.id if goal else None
        self._save_state()

    def _active_play_id(self) -> PlayId | None:
        goal = self._active_goal()
        return context_still_active(
            self.play_context_id,
            self.play_context_at,
            self.play_context_goal_id,
            active_goal_id=goal.id if goal else None,
        )

    def _play_context(self):
        play_id = self._active_play_id()
        if play_id is None or self.play_context_at is None:
            return None
        return compose_play_context(play_id, self.play_context_at.isoformat())

    def _learn(self, allowed: set[str] | None = None) -> TopicLearn:
        goal = self._active_goal()
        if allowed is None:
            if goal is None:
                allowed = None
            else:
                allowed = {node.id for node in self.graph.neighborhood(goal.id).nodes}
        return compose_learn(
            self.graph,
            self.practice,
            goal_id=goal.id if goal else None,
            allowed_ids=allowed,
        )

    def _inbox(self, item_id: str) -> InboxItem:
        try:
            return self.inbox[item_id]
        except KeyError as exc:
            raise KeyError(item_id) from exc

    def _active_goal(self) -> Goal | None:
        return next((item for item in self.graph.goals.values() if item.status == "active"), None)

    def _stamp(self, message: ChatMessage, lane: str) -> ChatMessage:
        goal = self._active_goal()
        return message.model_copy(
            update={"lane": lane, "goal_id": goal.id if goal else None}
        )

    def _brief_for_goal(self, goal: Goal | None) -> DecisionBrief | None:
        if self.brief is None:
            return None
        decision = self.graph.decisions.get(self.brief.decision_id)
        if goal is not None and decision is not None and decision.goal_id and decision.goal_id != goal.id:
            return None
        return bind_brief(self.brief, decision)

    def _compose_for_active_goal(self, *, use_model: bool) -> None:
        goal = self._active_goal()
        if goal is None:
            self.brief = None
            return
        try:
            self.brief = self.compose_brief(
                ComposeBriefRequest(question=goal.question, use_model=use_model),
                count_as_today=False,
            )
        except Exception:
            self.brief = None

    def _pause_active_goals(self) -> None:
        for existing in list(self.graph.goals.values()):
            if existing.status == "active":
                existing.status = "paused"
                self.graph.upsert_goal(existing)

    def _topic_scope(self, extra_ids: list[str] | None = None) -> list[str] | None:
        extra = list(extra_ids or [])
        goal = self._active_goal()
        if goal is None:
            return extra or None
        ids = {node.id for node in self.graph.neighborhood(goal.id).nodes}
        ids.update(extra)
        return list(ids)

    def _clip_to_active_topic(self, subgraph: GraphSnapshot, extra_ids: list[str]) -> GraphSnapshot:
        goal = self._active_goal()
        if goal is None:
            return subgraph
        allowed = {node.id for node in self.graph.neighborhood(goal.id).nodes}
        allowed.update(extra_ids)
        nodes = [node for node in subgraph.nodes if node.id in allowed]
        kept = {node.id for node in nodes}
        edges = [edge for edge in subgraph.edges if edge.from_id in kept and edge.to_id in kept]
        return GraphSnapshot(nodes=nodes, edges=edges)

    def _pins_with_goal(self, pinned_node_ids: list[str]) -> list[str]:
        pins = list(pinned_node_ids)
        goal = self._active_goal()
        if goal and goal.id not in pins:
            pins.insert(0, goal.id)
        return pins

    def _bind_nodes_to_active_goal(self, node_ids: list[str]) -> None:
        goal = self._active_goal()
        if goal is None:
            return
        existing = {(rel.from_id, rel.to_id, rel.type) for rel in self.graph.relations.values()}
        for node_id in node_ids:
            if not node_id or node_id == goal.id:
                continue
            key = (node_id, goal.id, "about")
            if key in existing:
                continue
            self.graph.upsert_relation(
                Relation(
                    id=new_id("rel"),
                    from_id=node_id,
                    to_id=goal.id,
                    type="about",
                )
            )
            existing.add(key)

    def _bind_unscoped_sources(self) -> None:
        goal_ids = set(self.graph.goals)
        scoped: set[str] = set()
        for rel in self.graph.relations.values():
            if rel.to_id in goal_ids:
                scoped.add(rel.from_id)
            if rel.from_id in goal_ids:
                scoped.add(rel.to_id)
        orphans = [source.id for source in self.graph.sources.values() if source.id not in scoped]
        self._bind_nodes_to_active_goal(orphans)


def _parse_touched(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


_workspace: Workspace | None = None


def get_workspace() -> Workspace:
    global _workspace
    if _workspace is None:
        _workspace = Workspace()
    return _workspace
