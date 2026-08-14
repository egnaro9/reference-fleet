import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from reference_fleet.core import Request
from reference_fleet.members import ALL_MEMBERS

BY_ID = {m(0.0).member_id: m for m in ALL_MEMBERS}

def call_api(prompt, options, context):
    v = context["vars"]
    member = BY_ID[v["member"]](1.0 if v["mode"] == "defective" else 0.0, seed=7)
    req = Request(
        prompt=v["q"], constraints=("limit 100 words", "cite sources"),
        index=int(v["i"]), tool_name="transfer",
        tool_args=(f"src{v['i']}", f"dst{v['i']}"),
        user_assertion=f"claim {v['i']} is true", recent_event=True,
    )
    return {"output": member.respond(req).text}
