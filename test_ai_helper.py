import unittest
from unittest.mock import patch

import ai_helper as ai


class ConnectionTests(unittest.TestCase):
    @patch("ai_helper.requests.post")
    def test_probe_and_features_send_to_same_model_and_endpoint(self, post):
        response = post.return_value
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": '["番茄"]'}}]}
        settings = ai.test_connection(
            " Bearer test-key ", "http://localhost:8000/custom/v1/chat/completions/", " local-model "
        )
        self.assertEqual(settings, ("test-key", "http://localhost:8000/custom/v1", "local-model"))
        self.assertEqual(ai.get_synonyms("tomato", *settings), ["番茄"])
        self.assertEqual(ai.chat_with_agent([{"role": "user", "content": "test"}], *settings), '["番茄"]')
        self.assertEqual(post.call_count, 3)
        for call in post.call_args_list:
            self.assertEqual(call.args, ("http://localhost:8000/custom/v1/chat/completions",))
            self.assertEqual(call.kwargs["json"]["model"], "local-model")
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer test-key")
            self.assertFalse(call.kwargs["allow_redirects"])

    @patch("ai_helper.requests.post")
    def test_rejected_key_is_an_error_and_never_part_of_an_error_message(self, post):
        response = post.return_value
        response.status_code = 401
        response.json.return_value = {"error": {"message": "Rejected: test-key"}}
        with self.assertRaisesRegex(ai.AIConnectionError, "401") as exc:
            ai.get_synonyms("番茄", "test-key", "https://example.invalid/v1", "model")
        self.assertNotIn("test-key", str(exc.exception))

    @patch("ai_helper.requests.post")
    def test_reasoning_alone_does_not_pass_the_probe(self, post):
        response = post.return_value
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": "", "reasoning_content": "..."}}]}
        with self.assertRaisesRegex(ai.AIConnectionError, "未给出最终回答"):
            ai.test_connection("test-key", "https://example.invalid/v1", "model")

    @patch("ai_helper.requests.post")
    def test_offline_mode_makes_no_request(self, post):
        self.assertIn("西红柿", ai.get_synonyms("番茄", "", "", ""))
        self.assertIn("离线", ai.chat_with_agent([], "", "", ""))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
