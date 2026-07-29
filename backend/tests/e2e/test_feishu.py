"""Feishu integration tests."""
import subprocess
import sys

ALL_OK = False

class TestFeishuMessages:
    def test_review_card(self):
        from channels.feishu.messages import build_review_card
        card = build_review_card("r1", "p1", "requirement")
        assert len(card["elements"]) == 3

    def test_review_card_with_content(self):
        from channels.feishu.messages import build_review_card
        card = build_review_card("r1", "p1", "test", "Project", "Content")
        assert card["elements"][3]["actions"][0]["value"]["action"] == "approve"

    def test_status_completed(self):
        from channels.feishu.messages import build_status_card
        card = build_status_card("p1", "stitch", "completed", "Done")
        assert card["header"]["template"] == "green"

    def test_status_failed(self):
        from channels.feishu.messages import build_status_card
        card = build_status_card("p1", "video", "failed", "Error")
        assert card["header"]["template"] == "red"

    def test_status_paused(self):
        from channels.feishu.messages import build_status_card
        card = build_status_card("p1", "review", "paused")
        assert card["header"]["template"] == "yellow"

    def test_import_client(self):
        code = "from channels.feishu.client import FeishuClient; c = FeishuClient(); c.close(); print('OK')"
        r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "OK" in r.stdout

    def test_import_messages(self):
        code = "from channels.feishu.messages import build_review_card; print('OK')"
        r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "OK" in r.stdout

    def test_import_webhook(self):
        code = "from app.api.webhook import router; print('OK')"
        r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "OK" in r.stdout

    def test_message_functionality(self):
        code = (
            "from channels.feishu.messages import build_review_card, build_status_card; "
            "c1 = build_review_card('r','p','t'); assert len(c1['elements']) == 3; "
            "c2 = build_review_card('r','p','t','P','C'); assert c2['elements'][3]['tag'] == 'action'; "
            "c3 = build_status_card('p','s','c'); assert c3['header']['template'] == 'green'; "
            "c4 = build_status_card('p','s','f'); assert c4['header']['template'] == 'red'; "
            "c5 = build_status_card('p','s','p'); assert c5['header']['template'] == 'yellow'; "
            "print('ALL OK')"
        )
        r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0, f"stderr:{r.stderr}"
        assert "ALL OK" in r.stdout, r.stdout