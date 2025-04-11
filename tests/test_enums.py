import unittest

from axone.enums import Method


class TestAxoneEnums(unittest.TestCase):
    def test_int_in_method(self) -> None:
        self.assertEqual(0 in Method, True)
        self.assertEqual(1 in Method, True)
        self.assertEqual(2 in Method, False)

    def test_from_value(self) -> None:
        self.assertEqual(Method.from_value(0), Method.SOCKET)
        self.assertEqual(Method.from_value(1), Method.SHARED_MEMORY)
        with self.assertRaises(ValueError):
            Method.from_value(2)


if __name__ == '__main__':
    unittest.main()
