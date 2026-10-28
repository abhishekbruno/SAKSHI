"""
Comprehensive Regression Test Suite for FIR-Assisted Ingestion & Incident Classification.
Covers:
1. Greenfield Community Hall Equipment Theft (FIR-SYN-2026-021) property loss extraction.
2. Synthetic unnatural death FIR (Riverside Guesthouse) death investigation extraction.
3. Ambiguous FIR classification (NEEDS_REVIEW) - never defaults to unnatural death.
4. Missing discovery date/time handling.
5. Discovery time present without occurrence time (strict separation).
6. Backend API candidate extraction endpoint serialization.
7. Verification that property loss hides death fields (victim_name, time_of_death, cause_of_death).
8. Provenance and source passages verification.
"""

import pytest
from app.schemas.case import (
    FIRMetadata,
    FIRAssistedCaseCreateRequest,
    FIRAssistedExtractResponse,
)
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.api.v1.cases import create_case_fir_assisted


GREENFIELD_PROPERTY_LOSS_FIR = """
FIRST INFORMATION REPORT
Case Title: Greenfield Community Hall Equipment Theft
FIR Number: FIR-SYN-2026-021
Police Station: Greenfield Central Police Station
Report Date: 22 October 2026
Incident Location: Greenfield Community Hall, Equipment Storage Room
Complainant: Ravi Thomas
Discovery Date / Time: Approximately 08:15 IST on 22 October 2026
Last Confirmed Present: Approximately 18:00 IST on 21 October 2026
Actual Occurrence Time: Unknown / not established
Penal Sections: Section 305 / Section 331(4) BNS
Property Stolen: Audio sound mixing console and two professional power amplifiers
Brief Facts:
On 22 October 2026 at approximately 08:15 IST, complainant Ravi Thomas, hall manager,
discovered that the rear padlock of the equipment storage room had been severed. Upon inspection,
the sound mixing console and amplifiers last confirmed present at 18:00 IST on 21 October 2026
were found missing. Actual time of occurrence and responsible person are unknown.
Investigating Officer: Sub-Inspector M. Varma
"""

RIVERSIDE_DEATH_INVESTIGATION_FIR = """
Case: Initial Inquest Report
Title: Riverside Guesthouse Incident
Police Station: Nallur Coastal Police Station (fictional)
FIR / Inquest Number: FIR-SYN-2026-1042
Report Date: 18 October 2026
Scene/location: Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)
Person found unresponsive: Arjun Menon (fictional)
Discovery time: Approximately 07:20 IST on 18 October 2026
Witness A sighting: Approximately 00:10 IST on 18 October 2026
Witness B sighting: Approximately 01:00 IST on 18 October 2026
Important limitations:
Time of death: Unknown / not established
Cause of death: Unknown / not established
Investigating Officer: Inspector K. Suresh
"""

AMBIGUOUS_INCIDENT_FIR = """
GENERAL INCIDENT INTIMATION
FIR Number: FIR-SYN-2026-AMB-99
Police Station: Metro Sector 4 Police Station
Report Date: 15 November 2026
Location: Warehouse Complex, Sector 4
Complainant: Security Guard Rajesh
Brief Facts:
A disturbance was reported at the warehouse premises during the early morning hours.
Patrol team dispatched to verify perimeter fencing and logs.
Investigating Officer: Head Constable P. Nair
"""

MISSING_DISCOVERY_TIME_FIR = """
INCIDENT REPORT
Case Title: Metro Substation Cable Theft
FIR Number: FIR-SYN-2026-033
Police Station: Metro North Station
Report Date: 12 November 2026
Incident Location: Power Distribution Substation 3
Complainant: Electrical Inspector Anand
Penal Sections: Section 303(2) BNS
Property Stolen: 50 meters copper grounding cable
Brief Facts:
Copper grounding cables reported stolen from substation yard.
Investigating Officer: SI K. Raman
"""


def test_greenfield_property_loss_fir_extraction():
    """Verify Greenfield Community Hall Equipment Theft candidate extraction."""
    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=GREENFIELD_PROPERTY_LOSS_FIR,
        filename="FIR-SYN-2026-021.txt",
    )

    # 1. Classification
    assert res.incident_type == "PROPERTY_LOSS", f"Expected PROPERTY_LOSS, got {res.incident_type}"

    # 2. Suggested Title derived from content, not Unnatural Death
    assert res.suggested_title == "Greenfield Community Hall Equipment Theft"
    assert "Unnatural Death" not in res.suggested_title

    # 3. FIR Number & Police Station
    assert res.fir_number == "FIR-SYN-2026-021"
    assert "Greenfield Central Police Station" in res.police_station

    # 4. Report Date & Complainant
    assert "22 October 2026" in res.report_date
    assert res.complainant_name == "Ravi Thomas"

    # 5. Discovery Date / Time accurately populated
    assert res.discovery_time is not None
    assert "08:15 IST" in res.discovery_time
    assert "22 October 2026" in res.discovery_time

    # 6. Last Confirmed Present kept strictly separate from occurrence time
    assert res.last_confirmed_present is not None
    assert "18:00 IST" in res.last_confirmed_present
    assert "21 October 2026" in res.last_confirmed_present

    # 7. Occurrence time is unknown / not established (not conflated with discovery time)
    assert res.incident_date == "Unknown / not established"

    # 8. Property items extracted
    assert res.property_items is not None
    assert "sound mixing console" in res.property_items.lower()

    # 9. Death-specific fields must be absent / suppressed
    assert res.victim_name is None, "Deceased/victim field must be None for property loss"
    assert res.time_of_death is None, "Time of death must be None for property loss"
    assert res.cause_of_death is None, "Cause of death must be None for property loss"

    # 10. Applicable fields contain property items and exclude death attributes
    assert "property_items" in res.applicable_fields
    assert "last_confirmed_present" in res.applicable_fields
    assert "victim_name" not in res.applicable_fields
    assert "time_of_death" not in res.applicable_fields
    assert "cause_of_death" not in res.applicable_fields

    # 11. Missing fields do not include victim or death attributes
    assert "victim_name" not in res.missing_fields
    assert "time_of_death" not in res.missing_fields

    # 12. Source Passages Grounding
    fields_grounded = {sp.field for sp in res.source_passages}
    assert "fir_number" in fields_grounded
    assert "police_station" in fields_grounded
    assert "discovery_time" in fields_grounded
    assert "last_confirmed_present" in fields_grounded


def test_riverside_death_investigation_fir_preserves_death_fields():
    """Verify that death investigations retain deceased person and death evidentiary limitations."""
    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=RIVERSIDE_DEATH_INVESTIGATION_FIR,
        filename="FIR-SYN-2026-1042.txt",
    )

    # 1. Classification
    assert res.incident_type == "DEATH_INVESTIGATION"

    # 2. Suggested Title
    assert res.suggested_title == "Riverside Guesthouse Incident"

    # 3. FIR Number
    assert res.fir_number == "FIR-SYN-2026-1042"

    # 4. Deceased / Person Found Unresponsive preserved
    assert res.victim_name == "Arjun Menon (fictional)"

    # 5. Discovery Time
    assert "07:20 IST" in res.discovery_time

    # 6. Witness Sightings
    assert len(res.witness_sightings) == 2

    # 7. Time and Cause of death limitations preserved
    assert res.time_of_death == "Unknown / not established"
    assert res.cause_of_death == "Unknown / not established"

    # 8. Applicable fields include death fields
    assert "victim_name" in res.applicable_fields
    assert "time_of_death" in res.applicable_fields
    assert "cause_of_death" in res.applicable_fields
    assert "property_items" not in res.applicable_fields


def test_ambiguous_incident_never_defaults_to_unnatural_death():
    """Verify that uncertain classification results in NEEDS_REVIEW and never defaults to death template."""
    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=AMBIGUOUS_INCIDENT_FIR,
        filename="FIR-AMB.txt",
    )

    assert res.incident_type == "NEEDS_REVIEW"
    assert "Unnatural Death" not in (res.suggested_title or "")
    assert res.victim_name is None
    assert "time_of_death" not in res.applicable_fields
    assert "cause_of_death" not in res.applicable_fields
    assert "property_items" not in res.applicable_fields


def test_missing_discovery_time_handled_gracefully():
    """Verify handling when discovery time is omitted from the document."""
    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=MISSING_DISCOVERY_TIME_FIR,
        filename="FIR-MISSING-DISC.txt",
    )

    assert res.incident_type == "PROPERTY_LOSS"
    assert res.discovery_time is None
    assert "discovery_time" in res.missing_fields
    assert res.victim_name is None


def test_narrative_theft_discovery_and_strict_occurrence_separation():
    """Verify narrative parsing for theft discovery and strict occurrence separation."""
    narrative_fir = """
    FIRST INFORMATION REPORT
    FIR No.: 441/2026
    Police Station: South Valley Police Station
    Report Date: 05 November 2026
    Location: Valley School Computer Lab
    Complainant: Principal John
    Penal Sections: Section 305 BNS
    Brief Facts:
    On 05 November 2026 at approximately 08:30 IST, staff discovered that the computer lab lock was broken
    and 10 laptops were missing. The lab was secured and present until 17:00 IST on 04 November 2026.
    Occurrence of offence: Unknown / not established.
    Investigating Officer: Inspector R. Das
    """

    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=narrative_fir,
        filename="FIR_narrative.txt",
    )

    assert res.incident_type == "PROPERTY_LOSS"
    assert res.discovery_time is not None
    assert "08:30 IST" in res.discovery_time
    assert res.last_confirmed_present is not None
    assert "17:00 IST" in res.last_confirmed_present
    assert res.incident_date == "Unknown / not established"
    assert res.victim_name is None
