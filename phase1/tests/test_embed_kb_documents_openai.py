import unittest


from scripts.embed_kb_documents_openai import vector_literal


class TestEmbedKbDocumentsOpenAI(unittest.TestCase):
    def test_vector_literal_format(self) -> None:
        s = vector_literal([1.0, -2.5, 0.0])
        self.assertTrue(s.startswith("["))
        self.assertTrue(s.endswith("]"))
        self.assertIn(",", s)
        self.assertIn("-2.50000000", s)

