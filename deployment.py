from __future__ import annotations

import os
import sys


def is_cloud_deployment() -> bool:
    return os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud"


def supports_native_picker() -> bool:
    return sys.platform == "darwin" and not is_cloud_deployment()
