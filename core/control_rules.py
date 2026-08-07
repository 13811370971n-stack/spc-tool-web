"""
Western Electric Rules (Nelson Rules) - 8 out-of-control tests.
Based on AIAG SPC Reference Manual.

Each test function returns a list of indices where the rule is violated.
"""

import numpy as np
from typing import List, Set


def test_1_beyond_3sigma(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 1: One point beyond 3σ from center line.
    (Beyond UCL or below LCL)
    """
    violations = []
    for i in range(len(data)):
        if not np.isnan(data[i]):
            if data[i] > ucl or data[i] < lcl:
                violations.append(i)
    return violations


def test_2_nine_same_side(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 2: 9 points in a row on the same side of the center line.
    """
    violations = []
    n = len(data)
    if n < 9:
        return violations

    for i in range(n - 8):
        segment = data[i:i + 9]
        if np.any(np.isnan(segment)):
            continue
        if np.all(segment > cl) or np.all(segment < cl):
            violations.extend(range(i, i + 9))

    return sorted(set(violations))


def test_3_six_trending(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 3: 6 points in a row steadily increasing or decreasing.
    """
    violations = []
    n = len(data)
    if n < 6:
        return violations

    for i in range(n - 5):
        segment = data[i:i + 6]
        if np.any(np.isnan(segment)):
            continue
        diffs = np.diff(segment)
        if np.all(diffs > 0) or np.all(diffs < 0):
            violations.extend(range(i, i + 6))

    return sorted(set(violations))


def test_4_fourteen_alternating(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 4: 14 points in a row alternating up and down.
    """
    violations = []
    n = len(data)
    if n < 14:
        return violations

    for i in range(n - 13):
        segment = data[i:i + 14]
        if np.any(np.isnan(segment)):
            continue
        diffs = np.diff(segment)
        # Check alternating sign
        signs = np.sign(diffs)
        if np.all(signs[:-1] != signs[1:]) and np.all(signs != 0):
            violations.extend(range(i, i + 14))

    return sorted(set(violations))


def test_5_two_of_three_beyond_2sigma(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 5: 2 out of 3 consecutive points beyond 2σ from center line (same side).
    """
    violations = []
    n = len(data)
    if n < 3:
        return violations

    sigma = (ucl - cl) / 3.0
    upper_2s = cl + 2 * sigma
    lower_2s = cl - 2 * sigma

    for i in range(n - 2):
        segment = data[i:i + 3]
        if np.any(np.isnan(segment)):
            continue
        # Check upper side
        above_2s = np.sum(segment > upper_2s)
        if above_2s >= 2:
            violations.extend(range(i, i + 3))
        # Check lower side
        below_2s = np.sum(segment < lower_2s)
        if below_2s >= 2:
            violations.extend(range(i, i + 3))

    return sorted(set(violations))


def test_6_four_of_five_beyond_1sigma(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 6: 4 out of 5 consecutive points beyond 1σ from center line (same side).
    """
    violations = []
    n = len(data)
    if n < 5:
        return violations

    sigma = (ucl - cl) / 3.0
    upper_1s = cl + sigma
    lower_1s = cl - sigma

    for i in range(n - 4):
        segment = data[i:i + 5]
        if np.any(np.isnan(segment)):
            continue
        # Check upper side
        above_1s = np.sum(segment > upper_1s)
        if above_1s >= 4:
            violations.extend(range(i, i + 5))
        # Check lower side
        below_1s = np.sum(segment < lower_1s)
        if below_1s >= 4:
            violations.extend(range(i, i + 5))

    return sorted(set(violations))


def test_7_fifteen_within_1sigma(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 7: 15 points in a row within 1σ of center line (stratification/hugging).
    """
    violations = []
    n = len(data)
    if n < 15:
        return violations

    sigma = (ucl - cl) / 3.0
    upper_1s = cl + sigma
    lower_1s = cl - sigma

    for i in range(n - 14):
        segment = data[i:i + 15]
        if np.any(np.isnan(segment)):
            continue
        if np.all((segment >= lower_1s) & (segment <= upper_1s)):
            violations.extend(range(i, i + 15))

    return sorted(set(violations))


def test_8_eight_beyond_1sigma_both_sides(data: np.ndarray, cl: float, ucl: float, lcl: float) -> List[int]:
    """
    Test 8: 8 points in a row beyond 1σ on BOTH sides of center line (mixture).
    """
    violations = []
    n = len(data)
    if n < 8:
        return violations

    sigma = (ucl - cl) / 3.0
    upper_1s = cl + sigma
    lower_1s = cl - sigma

    for i in range(n - 7):
        segment = data[i:i + 8]
        if np.any(np.isnan(segment)):
            continue
        # All points must be beyond 1σ (either side)
        beyond = (segment > upper_1s) | (segment < lower_1s)
        if np.all(beyond):
            violations.extend(range(i, i + 8))

    return sorted(set(violations))


# ─── Master Test Runner ────────────────────────────────────────────────────────

ALL_TESTS = {
    1: test_1_beyond_3sigma,
    2: test_2_nine_same_side,
    3: test_3_six_trending,
    4: test_4_fourteen_alternating,
    5: test_5_two_of_three_beyond_2sigma,
    6: test_6_four_of_five_beyond_1sigma,
    7: test_7_fifteen_within_1sigma,
    8: test_8_eight_beyond_1sigma_both_sides,
}


def run_tests(data: np.ndarray, cl: float, ucl: float, lcl: float,
              enabled_tests: List[int] = None) -> dict:
    """
    Run specified out-of-control tests.

    Parameters
    ----------
    data : np.ndarray
        1D array of chart statistics (Xbar values, R values, etc.)
    cl : float
        Center line value
    ucl : float
        Upper control limit
    lcl : float
        Lower control limit
    enabled_tests : list of int, optional
        Which tests to run (1-8). Default: all 8 tests.

    Returns
    -------
    dict
        {test_number: [list of violating indices]}
        Only tests with violations are included.
    """
    if enabled_tests is None:
        enabled_tests = list(range(1, 9))

    results = {}
    for test_num in enabled_tests:
        if test_num in ALL_TESTS:
            violations = ALL_TESTS[test_num](data, cl, ucl, lcl)
            if violations:
                results[test_num] = violations

    return results


def get_all_violation_indices(test_results: dict) -> Set[int]:
    """Get all unique violation indices across all tests."""
    all_indices = set()
    for indices in test_results.values():
        all_indices.update(indices)
    return all_indices
