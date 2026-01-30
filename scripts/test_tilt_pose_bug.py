"""Test script to verify tilt_pose handling bug."""

import logging
import sys

from twinklr.core.config.poses import TiltPose
from twinklr.core.sequencer.moving_heads.handlers.geometry.role_pose import RolePoseHandler

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def test_tilt_pose_as_enum():
    """Test passing TiltPose enum (how it actually gets passed)."""
    logger.info("=" * 80)
    logger.info("TEST 1: Passing TiltPose as ENUM (actual behavior)")
    logger.info("=" * 80)

    handler = RolePoseHandler()

    try:
        result = handler.resolve(
            fixture_id="test",
            role="OUTER_LEFT",
            params={
                "pan_pose_by_role": {},
                "tilt_pose": TiltPose.CROWD,  # Enum object
            },
            calibration={},
        )
        logger.info(f"✓ SUCCESS: tilt_norm = {result.tilt_norm}")
        logger.info(f"  Expected: {TiltPose.CROWD.norm_value}")
        return result.tilt_norm == TiltPose.CROWD.norm_value
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        return False


def test_tilt_pose_as_string():
    """Test passing TiltPose as string (what handler expects)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Passing TiltPose as STRING (handler expects)")
    logger.info("=" * 80)

    handler = RolePoseHandler()

    try:
        result = handler.resolve(
            fixture_id="test",
            role="OUTER_LEFT",
            params={
                "pan_pose_by_role": {},
                "tilt_pose": "CROWD",  # String
            },
            calibration={},
        )
        logger.info(f"✓ SUCCESS: tilt_norm = {result.tilt_norm}")
        logger.info(f"  Expected: {TiltPose.CROWD.norm_value}")
        return result.tilt_norm == TiltPose.CROWD.norm_value
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        return False


def test_different_poses():
    """Test various tilt poses."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Different TiltPose values")
    logger.info("=" * 80)

    handler = RolePoseHandler()

    test_cases = [
        (TiltPose.HORIZON, 0.5),
        (TiltPose.CROWD, 0.3),
        (TiltPose.SKY, 0.7),
    ]

    results = []
    for pose, expected_norm in test_cases:
        try:
            result = handler.resolve(
                fixture_id="test",
                role="OUTER_LEFT",
                params={"tilt_pose": pose},
                calibration={},
            )
            success = abs(result.tilt_norm - expected_norm) < 0.01
            status = "✓" if success else "✗"
            logger.info(
                f"{status} {pose.value}: tilt_norm={result.tilt_norm:.2f}, expected={expected_norm:.2f}"
            )
            results.append(success)
        except Exception as e:
            logger.error(f"✗ {pose.value}: FAILED - {e}")
            results.append(False)

    return all(results)


def main():
    """Run all tests."""
    test1 = test_tilt_pose_as_enum()
    test2 = test_tilt_pose_as_string()
    test3 = test_different_poses()

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Test 1 (Enum): {'✓ PASS' if test1 else '✗ FAIL'}")
    logger.info(f"Test 2 (String): {'✓ PASS' if test2 else '✗ FAIL'}")
    logger.info(f"Test 3 (Various): {'✓ PASS' if test3 else '✗ FAIL'}")

    if test1 and test2 and test3:
        logger.info("\n✅ All tests passed!")
        return 0
    else:
        logger.error("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
