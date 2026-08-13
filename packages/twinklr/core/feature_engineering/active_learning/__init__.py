"""Active learning for taxonomy quality improvement.

Entry points for the review → correction → reclassification loop; see
:mod:`twinklr.core.feature_engineering.active_learning.pipeline`.
"""

from twinklr.core.feature_engineering.active_learning.applier import CorrectionApplier
from twinklr.core.feature_engineering.active_learning.batch_builder import ReviewBatchBuilder
from twinklr.core.feature_engineering.active_learning.oracle import TaxonomyReviewOracle
from twinklr.core.feature_engineering.active_learning.pipeline import (
    CORRECTIONS_FILE_NAME,
    apply_corrections_file,
    load_corrections_file,
    merge_corrections_into_config,
    signatures_from_batch,
    signatures_from_phrases,
)
from twinklr.core.feature_engineering.active_learning.sampler import (
    UncertaintySampler,
    candidate_id_for,
)

__all__ = [
    "CORRECTIONS_FILE_NAME",
    "CorrectionApplier",
    "ReviewBatchBuilder",
    "TaxonomyReviewOracle",
    "UncertaintySampler",
    "apply_corrections_file",
    "candidate_id_for",
    "load_corrections_file",
    "merge_corrections_into_config",
    "signatures_from_batch",
    "signatures_from_phrases",
]
