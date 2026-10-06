from typing import List, Dict, Any, Tuple
from collections import defaultdict
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.core.logging import logger

SOURCE_PRIORITY: Dict[str, int] = {
    "accela": 1,      # Most complete: contractor licenses, detailed inspections
    "energov": 2,
    "socrata": 3,     # Good: open data feeds
    "shovels": 4,
    "cad": 5,
}


def get_source_priority(source_system: str) -> int:
    return SOURCE_PRIORITY.get(source_system.lower(), 99)


def deduplicate_permits_in_memory(
    permits: List[DepoiiNormalizedPermitSchema]
) -> Tuple[List[DepoiiNormalizedPermitSchema], int]:
    """
    Deduplicates a list of normalized permits in-memory using the composite key:
    (raw_permit_number, jurisdiction, issue_date)

    When duplicates exist (e.g. Dallas Socrata vs Dallas Accela for the same permit),
    the permit with the highest source priority wins (lowest integer priority).

    Returns:
        (deduplicated_permits, duplicate_count)
    """
    groups: Dict[Tuple[str, str, str], List[DepoiiNormalizedPermitSchema]] = defaultdict(list)

    for permit in permits:
        # Standardize key components for robust matching
        norm_number = permit.raw_permit_number.strip().upper()
        norm_jur = permit.jurisdiction.strip().upper()
        key = (norm_number, norm_jur, permit.issue_date)
        groups[key].append(permit)

    deduped: List[DepoiiNormalizedPermitSchema] = []
    duplicate_count = 0

    for key, candidates in groups.items():
        if len(candidates) > 1:
            duplicate_count += len(candidates) - 1
            # Sort by source priority ascending (1 = highest priority)
            candidates.sort(key=lambda p: get_source_priority(p.source_system))
            winner = candidates[0]
            logger.info(
                f"[Dedup] Resolved duplicate for permit {key[0]} in {key[1]}: "
                f"kept {winner.source_system} over {[c.source_system for c in candidates[1:]]}"
            )
            deduped.append(winner)
        else:
            deduped.append(candidates[0])

    return deduped, duplicate_count
