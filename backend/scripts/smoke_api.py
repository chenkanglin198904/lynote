import json
import urllib.request


def req(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


item = req(
    "POST",
    "http://127.0.0.1:8000/v1/sources",
    {
        "kind": "note",
        "title": "主张层比文件夹更重要",
        "text": "笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。个人知识图谱应该拒绝营销稿。",
    },
)
print("ingest", item["verdict"], item["status"])

accepted = req("POST", f"http://127.0.0.1:8000/v1/inbox/{item['id']}/accept")
print("accept", accepted["status"])

rejected = req("POST", "http://127.0.0.1:8000/v1/inbox/inbox_listicle/reject")
print("reject", rejected["status"])

chat = req(
    "POST",
    "http://127.0.0.1:8000/v1/chat",
    {"content": "先全量入库再清理行不行？", "pinned_node_ids": []},
)
print("chat_claims", ",".join(chat["claim_ids"]))

brief = req(
    "POST",
    "http://127.0.0.1:8000/v1/briefs/brief_week/commit",
    {"option_id": "opt_graph_thin", "rationale": "先打穿筛选和主张层"},
)
print("commit", brief["id"])

workbench = req("GET", "http://127.0.0.1:8000/v1/workbench")
decision = next(node for node in workbench["graph"]["nodes"] if node["kind"] == "decision")
print("decision_status", decision["status"])
