import numpy as np

from generator.generate_accounts import monthly_signup_probabilities


def test_probability_sum():
    probabilities = monthly_signup_probabilities(24, 0.02)
    assert np.isclose(probabilities.sum(), 1.0)


def test_probability_length():
    probabilities = monthly_signup_probabilities(24, 0.02)
    assert len(probabilities) == 24


def test_zero_growth():
    probabilities = monthly_signup_probabilities(4, 0.0)
    np.testing.assert_allclose(probabilities, np.full(4, 0.25))


def test_positive_growth():
    probabilities = monthly_signup_probabilities(24, 0.02)
    assert np.all(np.diff(probabilities) > 0)