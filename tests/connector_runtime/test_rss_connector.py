from __future__ import annotations

from packages.connector_runtime.models import ConnectorCategory

from packages.adapters.connectors.rss_connector import (
    PUBLIC_RSS_CONNECTOR_REF,
    PUBLIC_RSS_SYNC_CONFIG,
    PublicRssConnectorAdapter,
)


def test_rss_sync_config_is_disabled_by_default() -> None:
    assert PUBLIC_RSS_SYNC_CONFIG.auto_fetch_enabled is False


def test_rss_adapter_parses_rss_feed_to_safe_fetched_page() -> None:
    feed = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <guid>item-001</guid>
      <title>First item</title>
      <description>Public summary only.</description>
      <link>https://example.test/items/1</link>
    </item>
  </channel>
</rss>
"""
    calls: list[str] = []

    def _fake_fetch_text(url: str, headers: dict[str, str]) -> str:
        calls.append(url)
        assert "authorization" not in {k.lower() for k in headers}
        return feed

    adapter = PublicRssConnectorAdapter(feed_url="https://example.test/feed.xml", fetch_text=_fake_fetch_text)
    page = adapter.fetch_page(PUBLIC_RSS_CONNECTOR_REF, cursor=None)

    assert calls == ["https://example.test/feed.xml"]
    assert page.connection_id == "public-rss-connector"
    assert page.next_cursor is None
    assert len(page.items) == 1
    ext_id, title, body = page.items[0]
    assert ext_id
    assert title == "First item"
    assert "Public summary only." in body
    assert "https://example.test/items/1" in body


def test_rss_adapter_parses_atom_feed_to_safe_fetched_page() -> None:
    feed = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <entry>
    <id>tag:example.test,2026:item-42</id>
    <title>Atom headline</title>
    <summary>Atom summary text.</summary>
    <link href="https://example.test/atom/42" />
  </entry>
</feed>
"""

    def _fake_fetch_text(url: str, headers: dict[str, str]) -> str:
        return feed

    adapter = PublicRssConnectorAdapter(feed_url="https://example.test/atom.xml", fetch_text=_fake_fetch_text)
    page = adapter.fetch_page(PUBLIC_RSS_CONNECTOR_REF, cursor=None)

    assert len(page.items) == 1
    _, title, body = page.items[0]
    assert title == "Atom headline"
    assert "Atom summary text." in body
    assert "https://example.test/atom/42" in body


def test_rss_adapter_redacts_secret_like_content() -> None:
    feed = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <guid>item-secret</guid>
      <title>Contains token</title>
      <description>Bearer abcdef should be redacted.</description>
    </item>
  </channel>
</rss>
"""

    def _fake_fetch_text(url: str, headers: dict[str, str]) -> str:
        return feed

    adapter = PublicRssConnectorAdapter(feed_url="https://example.test/feed.xml", fetch_text=_fake_fetch_text)
    page = adapter.fetch_page(PUBLIC_RSS_CONNECTOR_REF, cursor=None)

    _, _, body = page.items[0]
    assert body == "[content redacted: contained secret-like terms]"


def test_rss_adapter_safe_projection_flags() -> None:
    def _fake_fetch_text(url: str, headers: dict[str, str]) -> str:
        return "<rss><channel></channel></rss>"

    adapter = PublicRssConnectorAdapter(feed_url="https://example.test/feed.xml", fetch_text=_fake_fetch_text)
    projection = adapter.safe_projection()

    assert projection["connector_id"] == "public-rss-connector"
    assert projection["category"] == ConnectorCategory.GENERIC_OAUTH
    assert projection["raw_credentials_persisted"] is False
    assert projection["raw_token_persisted"] is False
    assert projection["network_call_started"] is False
    assert projection["auto_fetch_default_enabled"] is False
