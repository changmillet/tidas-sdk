"""
Core utilities: base entity, factories, multi-language helpers.
"""

from .base import TidasBaseModel, TidasEntity  # noqa: F401
from .cas_number import is_valid_cas_number  # noqa: F401
from .cas_number import validate_cas_number_check_digit  # noqa: F401
from .factory import *  # noqa: F401,F403
from .multilang import MultiLangList  # noqa: F401
from .process_flow_reference_name import (
    PROCESS_FLOW_REFERENCE_NAME_PROFILE,
    ExactFlowNameEvidence,
    analyze_process_flow_references,
    collect_process_flow_references,
    compose_flow_name,
)
