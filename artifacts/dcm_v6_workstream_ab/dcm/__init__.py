"""DCM v6 Workstream A/B + HAR spine + E2E runner (development).

Canonical v5.4.1 was NOT present in this environment and is not modified.
HAR adapter is v6-new, not a hash-verified v5 decoder.
Learning Revision stays LR000000. Predictive claim NONE.
Not optimized DCM 6.0. Host performance is not certified.

Identity is loaded from VERSION.json (see dcm.version).
"""

from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

__version__ = SOFTWARE
__learning_revision__ = LEARNING_REVISION
__predictive_claim__ = PREDICTIVE_CLAIM
__schema_freeze_id__ = "PHASE_BC_SCHEMA_V1_2026-08-25"
__adr__ = "DCM-ADR-V6-001-2026-08-27"
