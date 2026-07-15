"""
OCPI 2.2.1 module - CPO (Charge Point Operator) interface for roaming.
Enables integration with eMSPs like TNG for EV charging roaming.
"""

from .aion import router as aion_router
from .router import router

__all__ = ["router", "aion_router"]
