from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.collector.adapter import CommunityNotAccessibleError
from app.collector.taptap_adapter import TapTapWebApiAdapter


def _mock_response(status_code: int, json_body: dict | None = None, text: str = "") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.headers = {"content-type": "application/json; charset=utf-8"} if json_body else {"content-type": "text/plain"}
    if json_body is not None:
        r.json.return_value = json_body
        r.text = json.dumps(json_body)
    else:
        r.json.side_effect = ValueError("no json")
        r.text = text
    return r


def _make_app_detail_response(group_id: int = 162908) -> dict:
    return {
        "success": True,
        "data": {
            "list": [
                {
                    "type": "moment",
                    "moment": {
                        "id_str": "111",
                        "group": {"id": group_id, "app_id": 139029, "title": "测试社区"},
                    },
                }
            ]
        },
    }


def _make_by_group_response(moment_id: str, topic_title: str, topic_summary: str, group_id: int = 162908,
                             is_elite: bool | None = None, is_official: bool | None = None,
                             author_name: str = "作者A") -> dict:
    moment = {
        "id_str": moment_id,
        "created_time": 1700000000,
        "author": {"user": {"name": author_name}},
        "topic": {"id_str": f"topic-{moment_id}", "title": topic_title, "summary": topic_summary},
        "stat": {"feedback_status": 3, "ups": 5},
        "group": {"id": group_id, "title": "测试社区"},
    }
    if is_elite is not None:
        moment["is_elite"] = is_elite
    if is_official is not None:
        moment["is_official"] = is_official
    return {"success": True, "data": {"list": [{"type": "moment", "moment": moment}]}}


def _make_adapter_with_mock_client() -> tuple[TapTapWebApiAdapter, MagicMock]:
    client = MagicMock(spec=httpx.Client)
    adapter = TapTapWebApiAdapter(client)
    return adapter, client


class TestDiscoverGroupId:
    def test_discover_success(self):
        adapter, client = _make_adapter_with_mock_client()
        client.get.return_value = _mock_response(200, _make_app_detail_response(162908))
        gid = adapter._discover_group_id("139029")
        assert gid == "162908"

    def test_discover_empty_list(self):
        adapter, client = _make_adapter_with_mock_client()
        client.get.return_value = _mock_response(200, {"success": True, "data": {"list": []}})
        gid = adapter._discover_group_id("139029")
        assert gid is None

    def test_discover_404(self):
        adapter, client = _make_adapter_with_mock_client()
        client.get.return_value = _mock_response(404, text="not found")
        gid = adapter._discover_group_id("999999")
        assert gid is None


class TestFetchPostList:
    def test_with_cached_group_id(self):
        adapter, client = _make_adapter_with_mock_client()
        client.get.return_value = _mock_response(200, _make_by_group_response("m1", "标题1", "摘要1"))
        items = adapter.fetch_post_list("app:139029", 5, group_id="162908")
        assert len(items) == 1
        assert items[0]["taptap_post_id"] == "m1"
        assert items[0]["group_id"] == "162908"

    def test_auto_discover_group_id(self):
        adapter, client = _make_adapter_with_mock_client()
        responses = [
            _mock_response(200, _make_app_detail_response(162908)),
            _mock_response(200, _make_by_group_response("m1", "标题1", "摘要1")),
        ]
        client.get.side_effect = responses
        items = adapter.fetch_post_list("app:139029", 5)
        assert len(items) == 1
        assert items[0]["group_id"] == "162908"

    def test_discover_failure_raises(self):
        adapter, client = _make_adapter_with_mock_client()
        client.get.return_value = _mock_response(200, {"success": True, "data": {"list": []}})
        with pytest.raises(CommunityNotAccessibleError, match="group_id"):
            adapter.fetch_post_list("app:999999", 5)

    def test_pagination_stops_on_empty(self):
        adapter, client = _make_adapter_with_mock_client()
        responses = [
            _mock_response(200, _make_by_group_response("m1", "t1", "s1")),
            _mock_response(200, {"success": True, "data": {"list": []}}),
        ]
        client.get.side_effect = responses
        items = adapter.fetch_post_list("app:139029", 50, group_id="162908")
        assert len(items) == 1

    def test_pagination_respects_limit(self):
        adapter, client = _make_adapter_with_mock_client()
        page1 = {"success": True, "data": {"list": [
            {"type": "moment", "moment": {"id_str": f"m{i}", "topic": {"id_str": f"t{i}", "title": f"t{i}", "summary": "s"}, "group": {"id": 162908}}}
            for i in range(20)
        ]}}
        page2 = {"success": True, "data": {"list": [
            {"type": "moment", "moment": {"id_str": f"m{i}", "topic": {"id_str": f"t{i}", "title": f"t{i}", "summary": "s"}, "group": {"id": 162908}}}
            for i in range(20, 25)
        ]}}
        client.get.side_effect = [_mock_response(200, page1), _mock_response(200, page2)]
        items = adapter.fetch_post_list("app:139029", 25, group_id="162908")
        assert len(items) == 25


class TestFetchPostDetail:
    def test_normal_parse(self):
        adapter, _ = _make_adapter_with_mock_client()
        post_ref = {
            "taptap_post_id": "m1",
            "raw_url": "https://www.taptap.cn/moment/m1",
            "_moment": _make_by_group_response("m1", "标题A", "摘要A", is_elite=True, is_official=False)["data"]["list"][0]["moment"],
            "group_id": "162908",
        }
        fp = adapter.fetch_post_detail(post_ref)
        assert fp.title == "标题A"
        assert fp.content == "摘要A"
        assert fp.author == "作者A"
        assert fp.topic_id == "topic-m1"
        assert fp.is_elite is True
        assert fp.is_official is False
        assert fp.group_id == "162908"
        assert fp.like_count == 5

    def test_empty_summary(self):
        adapter, _ = _make_adapter_with_mock_client()
        m = _make_by_group_response("m1", "标题", "", author_name="")["data"]["list"][0]["moment"]
        del m["stat"]
        post_ref = {"taptap_post_id": "m1", "raw_url": "u", "_moment": m}
        fp = adapter.fetch_post_detail(post_ref)
        assert fp.content == ""
        assert fp.title == "标题"
        assert fp.author == ""
        assert fp.reply_count == 0
        assert fp.like_count == 0

    def test_missing_topic_and_elite(self):
        adapter, _ = _make_adapter_with_mock_client()
        m = {"id_str": "m1", "created_time": 1700000000, "author": {}}
        post_ref = {"taptap_post_id": "m1", "raw_url": "u", "_moment": m}
        fp = adapter.fetch_post_detail(post_ref)
        assert fp.title == "(无标题)"
        assert fp.content == ""
        assert fp.topic_id == ""
        assert fp.is_elite is False
        assert fp.is_official is False
        assert fp.group_id == ""

    def test_empty_moment(self):
        adapter, _ = _make_adapter_with_mock_client()
        post_ref = {"taptap_post_id": "m1", "raw_url": "u", "_moment": {}, "_item": {}}
        fp = adapter.fetch_post_detail(post_ref)
        assert fp.title == "(无标题)"
        assert fp.author == ""


class TestParseCommunityId:
    def test_topic_url(self):
        adapter, _ = _make_adapter_with_mock_client()
        assert adapter.parse_community_id("https://www.taptap.cn/app/139029/topic") == "app:139029"

    def test_plain_app_url(self):
        adapter, _ = _make_adapter_with_mock_client()
        assert adapter.parse_community_id("https://www.taptap.cn/app/139029") == "app:139029"
