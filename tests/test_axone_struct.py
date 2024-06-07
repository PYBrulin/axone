import time
import unittest

from axone.axone_struct import AxoneStruct, AxoneTopic, standard_data_decoding, standard_data_encoding

# Required to disable error reporting for long lines
# flake8: noqa


class ATopicPassedToAxone(AxoneTopic):
    pass
    # a: bool = True
    # b: int = 0
    # c: int = 1
    # d: int = 2
    # e: float = 1.23456789
    # f: float = 1e9
    # g: float = 0.00001357
    # h: str = "hello"

    # xyz: SubMessage = SubMessage()

    # an_decently_long_attribute_name: str = "world"
    # # an_overly_long_attribute_name_that_should_raise_an_error_if_attempted_to_be_encoded_but_yeah_let_s_try_it_anyway_gosh_this_is_longer_than_i_expected_what_a_long_name_i_must_be_crazy_to_have_thought_of_this: (  # noqa: E501
    # #     str
    # # ) = "!"

    # a_callable: callable = lambda x: 1 + 1

    # def _update_message(self) -> None:
    #     return f"Hello message_callback from topic_published_rate_func {2 * time.time()}"

    # message_callback: str = _update_message

    # # def print_within(self, input_string) -> None:
    # #     print(input_string)


class TestAxoneStruct(unittest.TestCase):
    def test_pack_bool(self):
        topic = ATopicPassedToAxone()
        topic.a = True
        topic.b = False
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.a, True)
        self.assertEqual(topic_decoded.b, False)

    def test_pack_int(self):
        topic = ATopicPassedToAxone()
        topic.c = 1
        topic.d = 2
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.c, 1)
        self.assertEqual(topic_decoded.d, 2)

    def test_pack_float(self):
        topic = ATopicPassedToAxone()
        topic.e = 1.23456789
        topic.f = 1e9
        topic.g = 0.00001357
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.e, 1.23456789)
        self.assertEqual(topic_decoded.f, 1e9)
        self.assertEqual(topic_decoded.g, 0.00001357)

    def test_pack_str(self):
        topic = ATopicPassedToAxone()
        topic.h = "hello"
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.h, "hello")

    def test_pack_submessage(self):
        topic = ATopicPassedToAxone()
        topic.xyz = AxoneStruct()
        topic.xyz.x = 1
        topic.xyz.y = 2.3
        topic.xyz.z = "hello"
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.xyz.x, 1)
        self.assertEqual(topic_decoded.xyz.y, 2.3)
        self.assertEqual(topic_decoded.xyz.z, "hello")

    def test_pack_long_attribute_name(self):
        topic = ATopicPassedToAxone()
        topic.an_decently_long_attribute_name = "world"
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(topic_decoded.an_decently_long_attribute_name, "world")

    def test_pack_too_long_attribute_name(self):
        topic = ATopicPassedToAxone()
        topic.an_overly_long_attribute_name_that_should_raise_an_error_if_attempted_to_be_encoded_but_yeah_let_s_try_it_anyway_gosh_this_is_longer_than_i_expected_what_a_long_name_i_must_be_crazy_to_have_thought_of_this = (
            "world"
        )

        # Ensure the encoding raises an error
        with self.assertRaises(ValueError):
            topic.encode()

    # def test_pack_callable(self):
    #     topic = ATopicPassedToAxone()
    #     topic.a_callable = lambda x: 1 + 1
    #     encoded_message = topic.encode()

    #     # Decode
    #     topic_decoded = AxoneStruct()
    #     topic_decoded.decode(encoded_message)
    #     self.assertEqual(topic_decoded.a_callable(1), 2)

    def test_pack_message_callback(self):
        now = time.time()
        topic = ATopicPassedToAxone()
        topic.message_callback = f"Hello message_callback from topic_published_rate_func {2 * now}"
        encoded_message = topic.encode()

        # Decode
        topic_decoded = AxoneStruct()
        topic_decoded.decode(encoded_message)
        self.assertEqual(
            topic_decoded.message_callback,
            f"Hello message_callback from topic_published_rate_func {2 * now}",
        )


class TestStandardDataEncoding(unittest.TestCase):
    def test_encode_single_attribute(self):
        # Test bool
        self.assertEqual(standard_data_encoding(a=True), b'\x01\x00\x00\x00n1sa?\x01')
        # Test int
        self.assertEqual(standard_data_encoding(b=1), b'\x01\x00\x00\x00n1sbi\x01\x00\x00\x00')
        # Test float
        self.assertEqual(standard_data_encoding(c=1.0), b'\x01\x00\x00\x00n1scd\x00\x00\x00\x00\x00\x00\xf0?')
        # Test str
        self.assertEqual(standard_data_encoding(d='hello'), b'\x01\x00\x00\x00n1sdn5shello')

    def test_encode_multiple_attributes(self):
        print(standard_data_encoding(a=True, b=1, c=1.0, d='hello'))
        self.assertEqual(
            standard_data_encoding(a=True, b=1, c=1.0, d='hello'),
            b'\x04\x00\x00\x00n1sa?\x01n1sbi\x01\x00\x00\x00n1scd\x00\x00\x00\x00\x00\x00\xf0?n1sdn5shello',
        )

    def test_encode_empty_attribute(self) -> None:
        self.assertEqual(standard_data_encoding(a=None), b'\x01\x00\x00\x00n1sax\x00')

    def test_encode_long_string_value(self):
        with self.assertRaises(ValueError):
            standard_data_encoding(a='a' * 128)

    def test_encode_unsupported_type(self):
        with self.assertRaises(ValueError):
            standard_data_encoding(a=[])

    def test_decode_single_attribute(self):
        # Test bool
        self.assertEqual(standard_data_decoding(b'\x01\x00\x00\x00n1sa?\x01'), {'a': True})
        # Test int
        self.assertEqual(standard_data_decoding(b'\x01\x00\x00\x00n1sbi\x01\x00\x00\x00'), {'b': 1})
        # Test float
        self.assertEqual(standard_data_decoding(b'\x01\x00\x00\x00n1scd\x00\x00\x00\x00\x00\x00\xf0?'), {'c': 1.0})
        # Test str
        self.assertEqual(standard_data_decoding(b'\x01\x00\x00\x00n1sdn5shello'), {'d': 'hello'})

    def test_decode_multiple_attributes(self):
        self.assertEqual(
            standard_data_decoding(
                b'\x04\x00\x00\x00n1sa?\x01n1sbi\x01\x00\x00\x00n1scd\x00\x00\x00\x00\x00\x00\xf0?n1sdn5shello'
            ),
            {'a': True, 'b': 1, 'c': 1.0, 'd': 'hello'},
        )

    def test_decode_empty_attribute(self) -> None:
        self.assertEqual(standard_data_decoding(b'\x01\x00\x00\x00n1sax\x00'), {'a': None})

    def test_decode_unsupported_type(self):
        with self.assertRaises(ValueError):
            standard_data_decoding(b'\x01\x00\x00\x00A\x01')


if __name__ == '__main__':
    unittest.main()
