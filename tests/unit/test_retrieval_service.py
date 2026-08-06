import pytest

from services.document.retrieval_service import (
    cosine_distance_to_similarity,
)


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (0.0, 1.0),
        (0.25, 0.75),
        (0.5, 0.5),
        (1.0, 0.0),
    ],
)
def test_cosine_distance_conversion(
    distance: float,
    expected: float,
) -> None:
    assert cosine_distance_to_similarity(distance) == expected


def test_similarity_is_clamped_to_zero() -> None:
    assert cosine_distance_to_similarity(2.0) == 0.0


def test_similarity_is_clamped_to_one() -> None:
    assert cosine_distance_to_similarity(-1.0) == 1.0
