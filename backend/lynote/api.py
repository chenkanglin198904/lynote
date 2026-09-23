from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from lynote.config import settings
from lynote.contracts.models import (
    CaptureLessonRequest,
    ChatRequest,
    CommitBriefRequest,
    ComposeBriefRequest,
    ConfirmHangRequest,
    CreateGoalRequest,
    GradeProbeRequest,
    IngestSourceRequest,
    LinkRelationRequest,
    MergeConceptsRequest,
    Profile,
    ReviewBriefRequest,
    RunPlayRequest,
    ScratchNoteRequest,
    SetClaimLayerRequest,
    StartReviewRequest,
)
from lynote.workspace import get_workspace

router = APIRouter()


@router.post("/v1/notes")
def scratch_note(payload: ScratchNoteRequest):
    try:
        return get_workspace().scratch_note(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/hangs/confirm")
def confirm_hang(payload: ConfirmHangRequest):
    try:
        return get_workspace().confirm_hang(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"node not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/concepts/merge")
def merge_concepts(payload: MergeConceptsRequest):
    try:
        return get_workspace().merge_concepts(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"concept not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/claims/{claim_id}/touch")
def touch_claim(claim_id: str):
    try:
        return get_workspace().touch_claim(claim_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"claim not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/claims/{claim_id}/layer")
def set_claim_layer(claim_id: str, payload: SetClaimLayerRequest):
    try:
        return get_workspace().set_claim_layer(claim_id, payload.layer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"claim not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/claims/{claim_id}/deprecate")
def deprecate_claim(claim_id: str):
    try:
        return get_workspace().deprecate_claim(claim_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"claim not found: {exc}") from exc


@router.get("/v1/profile")
def get_profile():
    return get_workspace().profile


@router.put("/v1/profile")
def put_profile(payload: Profile):
    return get_workspace().update_profile(payload)


@router.get("/v1/report/weekly")
def weekly_report():
    return get_workspace().weekly_report()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lynote"}


@router.post("/v1/plays/run")
def run_play(payload: RunPlayRequest):
    try:
        return get_workspace().run_play(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/workbench")
def get_workbench():
    return get_workspace().workbench()


@router.get("/v1/goals")
def list_goals():
    return list(get_workspace().graph.goals.values())


@router.post("/v1/goals")
def create_goal(payload: CreateGoalRequest):
    try:
        return get_workspace().create_goal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/goals/{goal_id}/activate")
def activate_goal(goal_id: str):
    try:
        return get_workspace().activate_goal(goal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"goal not found: {exc}") from exc


@router.post("/v1/sources")
def ingest_source(payload: IngestSourceRequest):
    try:
        return get_workspace().ingest_source(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/sources/upload")
async def ingest_upload(file: UploadFile = File(...), title: str = Form("")):
    max_upload = settings.ingest_upload_max_bytes
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_upload:
            raise HTTPException(
                status_code=413,
                detail=f"上传文件超过 {max_upload // (1024 * 1024)}MB，拒绝入库",
            )
        chunks.append(chunk)
    try:
        return get_workspace().ingest_upload(file.filename or "upload", b"".join(chunks), title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/graph")
def get_graph():
    return get_workspace().graph.snapshot()


@router.get("/v1/graph/nodes/{node_id}")
def get_node_detail(node_id: str):
    try:
        return get_workspace().node_detail(node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"node not found: {exc}") from exc


@router.post("/v1/relations")
def link_relation(payload: LinkRelationRequest):
    try:
        return get_workspace().link_related(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"node not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/inbox/{item_id}/accept")
def accept_inbox(item_id: str):
    try:
        return get_workspace().accept_inbox(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"inbox item not found: {exc}") from exc


@router.post("/v1/inbox/{item_id}/reject")
def reject_inbox(item_id: str):
    try:
        return get_workspace().reject_inbox(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"inbox item not found: {exc}") from exc


@router.get("/v1/search")
def search_knowledge(q: str = ""):
    return get_workspace().search_knowledge(q)


@router.post("/v1/chat")
def chat(payload: ChatRequest):
    return get_workspace().chat(payload)


@router.post("/v1/probes/{probe_id}/grade")
def grade_probe(probe_id: str, payload: GradeProbeRequest):
    try:
        return get_workspace().grade_probe(probe_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"probe not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/misconceptions/{misconception_id}/resolve")
def resolve_misconception(misconception_id: str):
    try:
        return get_workspace().resolve_misconception(misconception_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"misconception not found: {exc}") from exc


@router.post("/v1/learn/capture")
def capture_lesson(payload: CaptureLessonRequest):
    try:
        return get_workspace().capture_lesson(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"message/chapter not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/learn")
def get_learn():
    return get_workspace().workbench().learn


@router.post("/v1/learn/reviews")
def start_review(payload: StartReviewRequest | None = None):
    try:
        return get_workspace().start_review(payload or StartReviewRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"claim not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/briefs/compose")
def compose_brief(payload: ComposeBriefRequest):
    try:
        return get_workspace().compose_brief(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/briefs/{brief_id}/commit")
def commit_brief(brief_id: str, payload: CommitBriefRequest):
    try:
        return get_workspace().commit_brief(brief_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"brief/option not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/briefs/{brief_id}/review")
def review_brief(brief_id: str, payload: ReviewBriefRequest):
    try:
        return get_workspace().review_brief(brief_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"brief/decision not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
