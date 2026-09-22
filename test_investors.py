import unittest
from unittest.mock import patch

import app


class InvestorProfitTests(unittest.TestCase):
    def test_proportional_shares_and_zero_contribution(self):
        investors = [
            {"name": "Kira", "investment": 100},
            {"name": "Goody", "investment": 300},
            {"name": "Thrum", "investment": 0},
        ]
        result = app.allocate_profit(investors, 100)
        self.assertEqual([row["net_profit"] for row in result], [25, 75, 0])
        self.assertNotIn("net_profit", investors[0])

    def test_rounding_reconciles_profits_and_losses(self):
        investors = [{"name": name, "investment": 1} for name in app.DEFAULT_INVESTORS]
        for profit in [1270.08, -42.5, 0.01, -0.01, 0]:
            with self.subTest(profit=profit):
                result = app.allocate_profit(investors, profit)
                self.assertEqual(round(sum(row["net_profit"] for row in result), 2), profit)
                shares = [row["net_profit"] for row in result]
                self.assertLessEqual(round(max(shares) - min(shares), 2), 0.01)

    def test_empty_and_zero_investments(self):
        self.assertEqual(app.allocate_profit([], 0), [])
        self.assertEqual(app.allocate_profit([{"name": "Kira", "investment": 0}], 0)[0]["net_profit"], 0)

    @patch.object(app, "DISCORD_WEBHOOK_URL", "https://example.invalid/mock")
    @patch.object(app.requests, "post")
    def test_discord_summary_then_individual_profit(self, post):
        investors = app.allocate_profit([
            {"name": "Kira", "investment": 100},
            {"name": "Goody", "investment": 300},
        ], 100)
        app.notify_discord({"investment": 400, "net_profit": 100, "investors": investors})
        self.assertEqual(post.call_count, 2)
        self.assertIn("Net Profit: 100.00 gp", post.call_args_list[0].kwargs["json"]["content"])
        details = post.call_args_list[1].kwargs["json"]
        self.assertIn("Kira: 25.00 gp", details["content"])
        self.assertIn("Goody: 75.00 gp", details["content"])
        self.assertEqual(details["allowed_mentions"], {"parse": []})

    @patch.object(app, "DISCORD_WEBHOOK_URL", "https://example.invalid/mock")
    @patch.object(app.requests, "post")
    def test_failed_summary_does_not_send_followup(self, post):
        post.return_value.raise_for_status.side_effect = RuntimeError("Webhook failed")
        app.notify_discord({"investment": 100, "net_profit": 20,
                            "investors": [{"name": "Kira", "net_profit": 20}]})
        self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
