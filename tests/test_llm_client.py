import unittest

from finevidence.llm.client import (
    LLMClientError,
    LiteLLMClient,
    OpenAICompatibleLLMClient,
    OpenAIResponsesLLMClient,
    create_llm_client,
)


class LLMClientFactoryTest(unittest.TestCase):
    def test_creates_openai_responses_client(self) -> None:
        client = create_llm_client(provider="openai", model="gpt-test")

        self.assertIsInstance(client, OpenAIResponsesLLMClient)
        self.assertEqual(client.model, "gpt-test")

    def test_creates_openai_compatible_client(self) -> None:
        client = create_llm_client(
            provider="openai_compatible",
            model="deepseek-chat",
            api_key="test-key",
            base_url="https://example.com/v1",
        )

        self.assertIsInstance(client, OpenAICompatibleLLMClient)
        self.assertEqual(client.model, "deepseek-chat")
        self.assertEqual(client.base_url, "https://example.com/v1")

    def test_creates_litellm_client(self) -> None:
        client = create_llm_client(provider="litellm", model="anthropic/claude-test")

        self.assertIsInstance(client, LiteLLMClient)
        self.assertEqual(client.model, "anthropic/claude-test")

    def test_rejects_unknown_provider(self) -> None:
        with self.assertRaises(LLMClientError):
            create_llm_client(provider="unknown-model-service")


if __name__ == "__main__":
    unittest.main()
