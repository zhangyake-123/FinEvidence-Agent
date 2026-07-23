import unittest

from finevidence.agents.planner import PlannerAgent, classify_question, infer_fact_metrics


class PlannerAgentTest(unittest.TestCase):
    def test_plans_metric_calculation(self) -> None:
        plan = PlannerAgent().run(
            "What was Apple gross margin in 2025?",
            ticker="AAPL",
            fiscal_year=2025,
            top_k=5,
        )

        self.assertEqual(plan["question_type"], "metric_calc")
        self.assertEqual(plan["requested_calculations"], ["gross_margin"])
        self.assertEqual(plan["requested_metrics"], ["gross_profit", "revenue"])
        self.assertTrue(plan["requires_tables"])
        self.assertTrue(plan["requires_calculation"])
        self.assertIn("calculate_metrics", plan["steps"])

    def test_plans_trend_analysis(self) -> None:
        plan = PlannerAgent().run("Apple past three years net margin", ticker="AAPL", fiscal_year=2025)

        self.assertEqual(plan["question_type"], "trend_analysis")
        self.assertEqual(plan["requested_calculations"], ["net_margin"])
        self.assertIsNone(plan["requested_periods"])

    def test_plans_interval_improvement_question_as_trend(self) -> None:
        plan = PlannerAgent().run(
            "Between 2023 and 2025, in which year-over-year interval did Apple's gross margin increase the most?",
            ticker="AAPL",
            fiscal_year=2025,
        )

        self.assertEqual(plan["question_type"], "trend_analysis")
        self.assertEqual(plan["requested_calculations"], ["gross_margin"])
        self.assertIsNone(plan["requested_periods"])

    def test_plans_fact_question(self) -> None:
        plan = PlannerAgent().run("What was Microsoft revenue in 2025?", ticker="MSFT", fiscal_year=2025)

        self.assertEqual(plan["question_type"], "fact_qa")
        self.assertEqual(plan["requested_metrics"], ["revenue"])
        self.assertFalse(plan["requires_calculation"])
        self.assertIn("extract_fact_metrics", plan["steps"])

    def test_plans_risk_summary(self) -> None:
        plan = PlannerAgent().run("What supply chain risks did Apple disclose?", ticker="AAPL", fiscal_year=2025)

        self.assertEqual(plan["question_type"], "risk_summary")
        self.assertEqual(plan["requested_metrics"], [])
        self.assertFalse(plan["requires_tables"])
        self.assertIn("rank_text_evidence", plan["steps"])

    def test_helper_functions_match_planner_routes(self) -> None:
        self.assertEqual(classify_question("Apple past three years gross margin"), "trend_analysis")
        self.assertEqual(infer_fact_metrics("Microsoft net income"), {"net_income"})


if __name__ == "__main__":
    unittest.main()
