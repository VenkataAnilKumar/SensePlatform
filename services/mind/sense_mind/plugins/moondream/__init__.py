"""
Moondream plugin for Sense Mind.

This plugin provides Moondream 3 vision capabilities including object detection,
visual question answering, and captioning.
"""

from sense_mind.plugins.moondream.detection.moondream_cloud_processor import (
    CloudDetectionProcessor,
)
from sense_mind.plugins.moondream.detection.moondream_local_processor import (
    LocalDetectionProcessor,
)
from sense_mind.plugins.moondream.detection.moondream_video_track import (
    MoondreamVideoTrack,
)
from sense_mind.plugins.moondream.vlm.moondream_cloud_vlm import CloudVLM
from sense_mind.plugins.moondream.vlm.moondream_local_vlm import LocalVLM


__path__ = __import__("pkgutil").extend_path(__path__, __name__)

__all__ = [
    "CloudDetectionProcessor",
    "CloudVLM",
    "LocalVLM",
    "LocalDetectionProcessor",
    "MoondreamVideoTrack",
]
