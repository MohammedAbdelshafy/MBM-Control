#!/usr/bin/env python3
"""Real tests for the WhatsApp n8n front-desk build. Stdlib only.

(a) Starts webhook_harness.py on localhost, sends a Meta-style verification
    GET with the correct token (asserts the challenge is echoed), then with a
    wrong token (asserts 403).
(b) POSTs a sample inbound WhatsApp message payload; asserts the sender/text
    are parsed and the dry-run outbox contains the correct Graph API payload.
(c) Unit tests for front_desk_logic: stage transitions + escalation triggers.

All assertions must pass. Exits non-zero on the first failure.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 18765
VERIFY_TOKEN = "test-verify-token-123"
SENDER = "15551234567"

passes = []
fails = []


def check(label, condition, detail=""):
    if condition:
        passes.append(label)
        print("PASS:", label)
    else:
        fails.append(label)
        print("FAIL:", label, detail)
        sys.exit(1)


def get(path):
    url = "http://127.0.0.1:%d%s" % (PORT, path)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def post(path, obj):
    url = "http://127.0.0.1:%d%s" % (PORT, path)
    req = urllib.request.Request(
        url, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def whatsapp_payload(sender, text, msg_id="wamid.test1"):
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "entry1", "changes": [{
                "value": {"messaging_product": "whatsapp",
                          "metadata": {"display_phone_number": "15550001111",
                                       "phone_number_id": "pnid"},
                          "messages": [{"from": sender, "id": msg_id,
                                        "timestamp": "1728000000",
                                        "type": "text",
                                        "text": {"body": text}}]},
                "field": "messages"}]}]}


def run_server_tests():
    print("== (a) webhook verification contract ==")
    challenge = "challenge-abc-987"
    qs = urllib.parse.urlencode(
        {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN,
         "hub.challenge": challenge})
    status, body = get("/webhook?" + qs)
    check("verify GET with correct token echoes challenge",
          status == 200 and body == challenge,
          "got %r %r" % (status, body))

    qs_bad = urllib.parse.urlencode(
        {"hub.mode": "subscribe", "hub.verify_token": "wrong-token",
         "hub.challenge": challenge})
    status, _ = get("/webhook?" + qs_bad)
    check("verify GET with wrong token returns 403", status == 403,
          "got %r" % status)

    print("== (b) inbound message parsing + dry-run reply ==")
    status, resp = post("/webhook", whatsapp_payload(SENDER, "hello"))
    check("POST inbound returns 200 ok", status == 200 and resp.get("ok") is True,
          repr(resp))
    r0 = resp["results"][0]
    check("sender parsed", r0["sender"] == SENDER, repr(r0))
    check("stage is qualify_name after first message",
          r0["stage"] == "qualify_name", repr(r0))
    check("reply asks for name", "name" in r0["reply"].lower(), repr(r0["reply"]))
    check("not escalated", r0["escalate"] is False)
    payload = r0["sent"]["payload"]
    check("dry-run flag set", r0["sent"]["dry_run"] is True)
    check("reply payload has whatsapp product",
          payload["messaging_product"] == "whatsapp", repr(payload))
    check("reply payload targets sender", payload["to"] == SENDER, repr(payload))
    check("reply payload carries reply text",
          payload["text"]["body"] == r0["reply"], repr(payload))

    # multi-turn: continue the same conversation through the state machine
    for text, want_stage in [("Omar", "qualify_service"),
                             ("I need cleaning", "qualify_urgency"),
                             ("today please", "done")]:
        status, resp = post("/webhook", whatsapp_payload(SENDER, text))
        r0 = resp["results"][0]
        check("turn %r -> stage %s" % (text, want_stage),
              r0["stage"] == want_stage, repr(r0))

    # escalation keyword
    status, resp = post("/webhook", whatsapp_payload("15559998888", "let me talk to a human"))
    r0 = resp["results"][0]
    check("escalation keyword escalates", r0["escalate"] is True and r0["stage"] == "escalate",
          repr(r0))


def run_logic_tests():
    print("== (c) front_desk_logic unit tests ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "front_desk_logic", os.path.join(HERE, "front_desk_logic.py"))
    logic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(logic)

    st = logic.new_session(SENDER)
    st, reply, esc, stage = logic.process_message(st, "hi")
    check("greet -> qualify_name", stage == "qualify_name" and not esc)

    st, reply, esc, stage = logic.process_message(st, "Layla")
    check("name captured, -> qualify_service",
          stage == "qualify_service" and "Layla" in reply, repr(reply))

    st, reply, esc, stage = logic.process_message(st, "how much does it cost?")
    check("FAQ price answer inline, stage unchanged",
          stage == "qualify_service" and "pricing" in reply.lower(), repr(reply))

    st, reply, esc, stage = logic.process_message(st, "consulting")
    check("service captured, -> qualify_urgency", stage == "qualify_urgency", repr(reply))

    st, reply, esc, stage = logic.process_message(st, "this week")
    check("urgency captured, -> done",
          stage == "done" and st["urgency"] == "this week", repr(st))

    st, reply, esc, stage = logic.process_message(st, "thanks!")
    check("done stays done, offers human", stage == "done" and "human" in reply.lower())

    # escalation triggers
    for kw in ["I want a human", "agent please", "call me tomorrow", "get me a real person"]:
        st2 = logic.new_session("x")
        st2, reply, esc, stage = logic.process_message(st2, kw)
        check("escalation trigger %r" % kw, esc and stage == "escalate", repr(reply))

    # two failed service parses escalate
    st3 = logic.new_session("y")
    st3, _, _, _ = logic.process_message(st3, "hi")
    st3, _, _, _ = logic.process_message(st3, "Omar")
    st3, r1, e1, s1 = logic.process_message(st3, "blargh")
    check("first failed parse asks again", not e1 and s1 == "qualify_service")
    st3, r2, e2, s2 = logic.process_message(st3, "still unclear")
    check("second failed parse escalates", e2 and s2 == "escalate", repr(r2))

    # empty message handled
    st4 = logic.new_session("z")
    st4, reply, esc, stage = logic.process_message(st4, "   ")
    check("empty message handled gracefully", not esc and "repeat" in reply.lower())


def main():
    tmpdir = tempfile.mkdtemp(prefix="wa-harness-")
    outbox = os.path.join(tmpdir, "outbox.jsonl")
    env = dict(os.environ, VERIFY_TOKEN=VERIFY_TOKEN, PORT=str(PORT),
               DRY_RUN="1", OUTBOX_FILE=outbox, PYTHONPATH=HERE)
    proc = subprocess.Popen([sys.executable,
                             os.path.join(HERE, "webhook_harness.py")],
                            env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                get("/webhook?hub.mode=x")
                break
            except Exception:
                time.sleep(0.1)
        else:
            print("FAIL: harness did not start")
            sys.exit(1)
        run_server_tests()
        run_logic_tests()
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    print("\n%d passed, %d failed" % (len(passes), len(fails)))
    if fails:
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
