"""Tests for workspace API endpoints."""
import tempfile
import unittest
from pathlib import Path

import app.routes.api as api_routes
from state_store import StateStore


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.original_api_store = api_routes.STATE_STORE
        api_routes.STATE_STORE = self.store

    def tearDown(self):
        api_routes.STATE_STORE = self.original_api_store
        self.tmp.cleanup()

    def client(self):
        import web_server

        return web_server.app.test_client()

    def test_create_and_list_research_questions(self):
        response = self.client().post(
            "/api/workspaces/questions",
            json={
                "query_text": "conformal prediction under shift",
                "intent_statement": "Find reliable finite-sample methods.",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["question"]["query_text"], "conformal prediction under shift")
        self.assertEqual(payload["question"]["source"], "manual")

        list_response = self.client().get("/api/workspaces/questions")
        self.assertEqual(list_response.status_code, 200)
        questions = list_response.get_json()["questions"]
        self.assertEqual([q["id"] for q in questions], [payload["question"]["id"]])

    def test_create_research_question_rejects_empty_query(self):
        response = self.client().post(
            "/api/workspaces/questions",
            json={"query_text": "   "},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    def test_workspace_stats_endpoint(self):
        question = self.store.create_research_question("causal inference")
        self.store.upsert_queue_item(
            "2604.11111",
            "Deep Read",
            research_question_id=question["id"],
        )

        response = self.client().get(f"/api/workspaces/questions/{question['id']}/stats")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["stats"]["active_reading_count"], 1)

    def test_start_planner_run_endpoint_records_job(self):
        question = self.store.create_research_question("causal inference")

        response = self.client().post(
            f"/api/workspaces/questions/{question['id']}/planner-runs",
            json={"trigger": "manual"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["result"]["status"], "succeeded")

        job = self.store.get_job(payload["result"]["run_id"])
        self.assertEqual(job["job_type"], "workspace_planner")
        self.assertEqual(job["payload_json"]["research_question_id"], question["id"])
