import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from core.database import get_db  # noqa: E402
from core.security import get_owned_project  # noqa: E402
from services import github_service  # noqa: E402
from services.github_service import (  # noqa: E402
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubRepoDuplicateError,
)


def _mock_response(status_code: int, json_data: dict | None = None, headers: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


class TestGitHubServiceErrors(unittest.TestCase):
    def test_missing_token_raises_auth_error(self):
        with patch.object(github_service, "GITHUB_TOKEN", None):
            with self.assertRaises(GitHubAuthError):
                github_service._get_headers()

        with patch.object(github_service, "GITHUB_TOKEN", github_service.PLACEHOLDER_TOKEN):
            with self.assertRaises(GitHubAuthError):
                github_service._get_headers()

    def test_create_repo_401_raises_auth_error(self):
        with patch.object(github_service, "GITHUB_TOKEN", "ghp_test_token_123456"):
            with patch("services.github_service.requests.post", return_value=_mock_response(401, {"message": "Bad credentials"})):
                with self.assertRaises(GitHubAuthError):
                    github_service.create_github_repo("my-repo")

    def test_create_repo_429_raises_rate_limit_error(self):
        with patch.object(github_service, "GITHUB_TOKEN", "ghp_test_token_123456"):
            resp = _mock_response(429, {"message": "API rate limit exceeded"}, headers={"Retry-After": "45"})
            with patch("services.github_service.requests.post", return_value=resp):
                with self.assertRaises(GitHubRateLimitError) as ctx:
                    github_service.create_github_repo("my-repo")
                self.assertEqual(ctx.exception.retry_after, 45)

    def test_create_repo_422_duplicate_raises_duplicate_error(self):
        with patch.object(github_service, "GITHUB_TOKEN", "ghp_test_token_123456"):
            resp = _mock_response(
                422,
                {
                    "message": "Repository creation failed.",
                    "errors": [{"message": "name already exists on this account"}],
                },
            )
            with patch("services.github_service.requests.post", return_value=resp):
                with self.assertRaises(GitHubRepoDuplicateError):
                    github_service.create_github_repo("existing-repo")

    def test_enable_github_pages_success_and_409(self):
        with patch.object(github_service, "GITHUB_TOKEN", "ghp_test_token_123456"):
            for code in (201, 409):
                with patch("services.github_service.requests.post", return_value=_mock_response(code, {})):
                    url = github_service.enable_github_pages("ToanUser", "lp-1-test")
                    self.assertEqual(url, "https://toanuser.github.io/lp-1-test")


class TestDeployEndpointHeadersAndFlow(unittest.TestCase):
    def setUp(self):
        self.fake_project = {
            "id": 1,
            "user_id": 10,
            "template_id": 1,
            "campaign_name": "Summer Sale",
            "product_name": "Widget",
            "product_description": "Best widget",
            "price": "199000",
            "image_url": "",
            "color_theme": "#4f46e5",
            "repo_url": None,
            "raw_json_data": {},
        }
        self.mock_db = MagicMock()
        insert_res = MagicMock()
        insert_res.lastrowid = 99
        self.mock_db.execute.return_value = insert_res

        main.app.dependency_overrides[get_owned_project] = lambda: dict(self.fake_project)
        main.app.dependency_overrides[get_db] = lambda: self.mock_db
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_deploy_auth_error_preserves_503_and_header(self):
        with patch("api.projects._render_project_html", return_value="<html></html>"):
            with patch("api.projects.create_github_repo", side_effect=GitHubAuthError("Token hết hạn")):
                res = self.client.post("/projects/1/deploy")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.headers.get("X-GitHub-Error"), "auth")

    def test_deploy_rate_limit_preserves_429_and_retry_after(self):
        with patch("api.projects._render_project_html", return_value="<html></html>"):
            with patch("api.projects.create_github_repo", side_effect=GitHubRateLimitError("Rate limit", retry_after=120)):
                res = self.client.post("/projects/1/deploy")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.headers.get("Retry-After"), "120")

    def test_deploy_duplicate_repo_returns_409(self):
        with patch("api.projects._render_project_html", return_value="<html></html>"):
            with patch("api.projects.create_github_repo", side_effect=GitHubRepoDuplicateError("Tên repo đã tồn tại")):
                res = self.client.post("/projects/1/deploy")
        self.assertEqual(res.status_code, 409)

    def test_deploy_success_returns_pages_url_and_commit_sha(self):
        with patch("api.projects._render_project_html", return_value="<html><body>Hi</body></html>"):
            with patch(
                "api.projects.create_github_repo",
                return_value={
                    "name": "lp-1-summer-sale",
                    "full_name": "khanhtoan10/lp-1-summer-sale",
                    "html_url": "https://github.com/khanhtoan10/lp-1-summer-sale",
                },
            ):
                with patch(
                    "api.projects.push_landing_page_assets",
                    return_value={"uploaded_files": ["index.html"], "commit_sha": "abc1234def5678"},
                ):
                    with patch(
                        "api.projects.enable_github_pages",
                        return_value="https://khanhtoan10.github.io/lp-1-summer-sale",
                    ):
                        with patch(
                            "api.projects.wait_for_github_pages_built",
                            return_value={
                                "status": "built",
                                "html_url": "https://khanhtoan10.github.io/lp-1-summer-sale/",
                                "error": None,
                            },
                        ):
                            res = self.client.post("/projects/1/deploy")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["github_pages_url"], "https://khanhtoan10.github.io/lp-1-summer-sale/")
        self.assertEqual(body["data"]["commit_sha"], "abc1234def5678")


if __name__ == "__main__":
    unittest.main()

