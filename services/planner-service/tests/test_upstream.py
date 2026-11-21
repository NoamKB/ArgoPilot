"""The value checks in upstream.py on their own. The HTTP paths are tested through the API in test_plan.py."""

import math
from fractions import Fraction

import pytest

import upstream


@pytest.mark.parametrize(("value", "expected"), [(0.4, Fraction(2, 5)), (83, Fraction(83)), (1.15, Fraction(115, 100))])
def test_exact_keeps_the_decimal_that_was_sent(value, expected):
    assert upstream.exact(value) == expected


@pytest.mark.parametrize("value", [None, "1.5", True, False, math.nan, math.inf, -math.inf, [1]])
def test_exact_rejects_anything_but_a_finite_number(value):
    with pytest.raises(ValueError):
        upstream.exact(value)


@pytest.mark.parametrize("value", [0, -0.1])
def test_positive_rejects_zero_and_negative(value):
    with pytest.raises(ValueError):
        upstream.positive(value)


def test_non_negative_accepts_zero():
    assert upstream.non_negative(0.0) == 0


@pytest.mark.parametrize("value", [None, True, "31.25", math.nan, math.inf])
def test_coordinate_rejects_anything_but_a_finite_number(value):
    with pytest.raises(ValueError):
        upstream.coordinate(value)


def test_coordinate_is_passed_on_unchanged():
    assert upstream.coordinate(31.25) == 31.25


def test_text_rejects_a_non_string():
    with pytest.raises(TypeError):
        upstream.text(7)
