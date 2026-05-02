import os
import tempfile
import unittest

from database import DatabaseManager


class DatabaseManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_featured_message_lifecycle_and_stats(self):
        added = self.db.add_featured_message(
            guild_id=100,
            thread_id=200,
            message_id=300,
            author_id=400,
            author_name="Author",
            featured_by_id=500,
            featured_by_name="Curator",
            reason="Useful",
            bot_message_id=600,
        )
        duplicate = self.db.add_featured_message(
            guild_id=100,
            thread_id=200,
            message_id=301,
            author_id=400,
            author_name="Author",
            featured_by_id=501,
            featured_by_name="Other",
        )

        self.assertTrue(added)
        self.assertFalse(duplicate)
        self.assertTrue(self.db.is_already_featured(200, 400))

        featured_info = self.db.get_featured_message_by_id(300, 200)
        self.assertEqual(featured_info["author_name"], "Author")
        self.assertEqual(featured_info["bot_message_id"], 600)

        stats = self.db.get_user_stats(400, 100)
        self.assertEqual(stats["featured_count"], 1)
        self.assertEqual(stats["featuring_count"], 0)

        curator_stats = self.db.get_user_stats(500, 100)
        self.assertEqual(curator_stats["featured_count"], 0)
        self.assertEqual(curator_stats["featuring_count"], 1)

        self.assertTrue(self.db.remove_featured_message(300, 200))
        self.assertFalse(self.db.is_already_featured(200, 400))
        self.assertFalse(self.db.remove_featured_message(300, 200))

    def test_records_and_referral_ranking_are_paginated(self):
        for index in range(3):
            self.db.add_featured_message(
                guild_id=100,
                thread_id=200 + index,
                message_id=300 + index,
                author_id=400 + index,
                author_name=f"Author {index}",
                featured_by_id=500,
                featured_by_name="Curator",
                reason=f"Reason {index}",
            )

        records, total_pages = self.db.get_user_referral_records(500, 100, page=1, per_page=2)
        self.assertEqual(len(records), 2)
        self.assertEqual(total_pages, 2)

        ranking, ranking_pages = self.db.get_referral_ranking(100, page=1, per_page=10)
        self.assertEqual(ranking_pages, 1)
        self.assertEqual(ranking[0]["user_id"], 500)
        self.assertEqual(ranking[0]["referral_count"], 3)

        all_messages, all_pages = self.db.get_all_featured_messages(100, page=1, per_page=2)
        self.assertEqual(len(all_messages), 2)
        self.assertEqual(all_pages, 2)

    def test_booklist_entries_links_and_whitelist(self):
        self.db.ensure_user_booklists(400)
        ok, message = self.db.add_post_to_booklist(
            user_id=400,
            list_id=0,
            thread_guild_id=100,
            thread_id=200,
            thread_title="Thread title",
            thread_url="https://discord.com/channels/100/200",
            review="Nice",
        )

        self.assertTrue(ok, message)
        duplicate_ok, _ = self.db.add_post_to_booklist(
            user_id=400,
            list_id=0,
            thread_guild_id=100,
            thread_id=200,
            thread_title="Thread title",
            thread_url="https://discord.com/channels/100/200",
        )
        self.assertFalse(duplicate_ok)

        booklist = self.db.get_user_booklist(400, 0)
        self.assertEqual(booklist["post_count"], 1)
        self.assertEqual(booklist["entries"][0]["review"], "Nice")

        self.db.set_user_booklist_thread_url(400, 100, "https://discord.com/channels/100/200")
        self.assertEqual(
            self.db.get_user_booklist_thread_url(400, 100),
            "https://discord.com/channels/100/200",
        )
        self.assertEqual(self.db.get_booklist_thread_owner(100, 200), 400)

        self.db.set_booklist_thread_whitelist(100, 900)
        self.assertEqual(self.db.get_booklist_thread_whitelist(100), 900)
        self.db.clear_booklist_thread_whitelist(100)
        self.assertIsNone(self.db.get_booklist_thread_whitelist(100))

        affected = self.db.clear_all_booklist_thread_links_in_guild(100)
        self.assertEqual(affected, 1)
        self.assertIsNone(self.db.get_booklist_thread_owner(100, 200))


if __name__ == "__main__":
    unittest.main()
