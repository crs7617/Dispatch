"""Unit tests for RSS and Atom collection and normalization."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.collectors.rss import RSSCollector
from app.models.news_item import Source


RSS_FEED = b"""<?xml version=\"1.0\"?>
<rss version=\"2.0\"><channel><title>Example</title>
<item><guid>one</guid><title>First entry</title><link>https://example.com/one</link><author>ada@example.com (Ada)</author><pubDate>Tue, 14 Nov 2023 22:13:20 GMT</pubDate></item>
<item><guid>two</guid><title>Second entry</title><link>https://example.com/two</link><pubDate>Wed, 15 Nov 2023 22:13:20 GMT</pubDate></item>
</channel></rss>"""

ATOM_FEED = b"""<?xml version=\"1.0\"?>
<feed xmlns=\"http://www.w3.org/2005/Atom\"><title>Example</title>
<entry><id>atom-one</id><title>Atom entry</title><link href=\"https://example.com/atom\"/><author><name>Ada</name></author><updated>2023-11-14T22:13:20Z</updated></entry>
</feed>"""


class FakeRSSFeedClient:
    """In-memory substitute for RSSFeedClient used by collector tests."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.requested_urls: list[str] = []

    def fetch_feed(self, feed_url: str) -> bytes:
        self.requested_urls.append(feed_url)
        return self.content


class RSSCollectorTests(unittest.TestCase):
    """Verify parsing and normalization without network access."""

    def collect(self, content: bytes, source_name: str = "example"):
        client = FakeRSSFeedClient(content)
        return RSSCollector(client).collect("https://example.com/feed.xml", source_name), client

    def test_normal_rss_entry_maps_to_news_item(self) -> None:
        items, _ = self.collect(RSS_FEED)

        item = items[0]
        self.assertEqual(item.source, Source.RSS)
        self.assertEqual(item.source_id, "example:one")
        self.assertEqual(item.title, "First entry")
        self.assertEqual(item.url, "https://example.com/one")
        self.assertEqual(item.author, "ada@example.com (Ada)")
        self.assertEqual(
            item.published_at,
            datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc),
        )

    def test_multiple_entries_preserve_feed_order_and_optional_fields(self) -> None:
        items, client = self.collect(RSS_FEED)

        self.assertEqual([item.source_id for item in items], ["example:one", "example:two"])
        self.assertIsNone(items[1].author)
        self.assertEqual(client.requested_urls, ["https://example.com/feed.xml"])

    def test_atom_entry_is_normalized(self) -> None:
        items, _ = self.collect(ATOM_FEED, source_name="atom")

        item = items[0]
        self.assertEqual(item.source_id, "atom:atom-one")
        self.assertEqual(item.author, "Ada")
        self.assertEqual(item.published_at, datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc))

    def test_missing_publication_date_is_allowed(self) -> None:
        content = RSS_FEED.replace(
            b"<pubDate>Tue, 14 Nov 2023 22:13:20 GMT</pubDate>", b""
        )
        items, _ = self.collect(content)

        self.assertIsNone(items[0].published_at)

    def test_entry_without_usable_url_is_skipped(self) -> None:
        content = RSS_FEED.replace(
            b"<guid>one</guid>", b"<guid isPermaLink=\"false\">one</guid>"
        ).replace(b"<link>https://example.com/one</link>", b"")
        items, _ = self.collect(content)

        self.assertEqual([item.source_id for item in items], ["example:two"])

    def test_invalid_feed_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.collect(b"this is not a feed")
