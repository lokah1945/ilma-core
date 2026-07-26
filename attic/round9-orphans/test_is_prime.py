import pytest
from is_prime import is_prime


class TestIsPrime:

    # ── Normal cases ──────────────────────────────────────────────────────
    @pytest.mark.parametrize(
        "prime",
        [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 7919, 104729],
    )
    def test_primes_return_true(self, prime):
        assert is_prime(prime) is True

    @pytest.mark.parametrize(
        "composite",
        [4, 6, 8, 9, 10, 12, 15, 21, 25, 49, 100, 1000, 7921],
    )
    def test_composites_return_false(self, composite):
        assert is_prime(composite) is False

    @pytest.mark.parametrize(
        "n",
        [
            # negative integers
            -1,
            -2,
            -3,
            -10,
            -7919,
            # zero and one
            0,
            1,
        ],
    )
    def test_values_less_than_two_return_false(self, n):
        assert is_prime(n) is False

    def test_large_prime(self):
        # a known large prime (Mersenne prime exponent)
        assert is_prime(2_147_483_647) is True

    def test_large_composite(self):
        assert is_prime(2_147_483_645) is False

    def test_float_representing_integer_prime(self):
        assert is_prime(17.0) is True

    def test_float_representing_integer_composite(self):
        assert is_prime(100.0) is False

    def test_float_representing_integer_less_than_two(self):
        assert is_prime(-5.0) is False
        assert is_prime(0.0) is False
        assert is_prime(1.0) is False

    def test_string_representing_integer_prime(self):
        assert is_prime("13") is True

    def test_string_representing_integer_composite(self):
        assert is_prime("25") is False

    def test_string_representing_negative(self):
        assert is_prime("-7") is False

    # ── Edge cases around sqrt boundary ───────────────────────────────────
    def test_square_of_prime(self):
        assert is_prime(49) is False  # 7*7
        assert is_prime(121) is False  # 11*11

    def test_product_of_two_large_primes(self):
        # 7919 * 7927 is composite; check edge where candidate crosses limit
        assert is_prime(7919 * 7927) is False

    def test_number_one_less_than_prime_square(self):
        # 48 is 49-1, composite
        assert is_prime(48) is False

    def test_number_one_more_than_prime_square(self):
        # 50 is 49+1, composite
        assert is_prime(50) is False

    # ── Boolean handling ──────────────────────────────────────────────────
    def test_boolean_true(self):
        assert is_prime(True) is False

    def test_boolean_false(self):
        assert is_prime(False) is False

    # ── Error handling ────────────────────────────────────────────────────
    def test_non_integral_float_raises_value_error(self):
        with pytest.raises(ValueError):
            is_prime(3.14)

    def test_non_integral_float_zero_fraction(self):
        with pytest.raises(ValueError):
            is_prime(17.5)

    def test_complex_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime(complex(2, 3))

    def test_list_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime([11])

    def test_dict_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime({"a": 1})

    def test_unconvertible_string_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime("hello")

    def test_string_with_float_format_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime("3.14")

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError):
            is_prime(None)

    # ── Fast-path branches ────────────────────────────────────────────────
    def test_even_primes_below_four(self):
        # 2 is the only even prime
        assert is_prime(2) is True
        # all other evens are composite
        assert is_prime(4) is False
        assert is_prime(6) is False

    def test_multiples_of_three_below_nine(self):
        # 3 is prime, 6 even, 9 composite
        assert is_prime(3) is True
        assert is_prime(9) is False

    # ── Very large integer ─────────────────────────────────────────────────
    def test_very_large_prime(self):
        # A known 20-digit prime (2**61 - 1 is prime)
        assert is_prime(2_305_843_009_213_693_951) is True

    def test_very_large_composite(self):
        # 2**61 is even, thus composite
        assert is_prime(2_305_843_009_213_693_952) is False

    # ── Custom class with __int__ ─────────────────────────────────────────
    def test_custom_class_with_int_conversion(self):
        class IntLike:
            def __init__(self, val):
                self.val = val

            def __int__(self):
                return self.val

        assert is_prime(IntLike(17)) is True
        assert is_prime(IntLike(10)) is False

    def test_custom_class_without_int_raises_type_error(self):
        class NoInt:
            pass

        with pytest.raises(TypeError):
            is_prime(NoInt())