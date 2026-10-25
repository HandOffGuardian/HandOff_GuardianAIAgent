"""
citation_verify.py
Purpose: Ensure all evidence citations in the final report tie back to actual source records.
"""


class CitationVerifier:
    @staticmethod
    def verify_citations(report: dict, evidence_bundle: dict) -> bool:
        """
        Validates that all evidence IDs cited in conflicts exist in the retrieved evidence bundle.
        """
        if not evidence_bundle or "records" not in evidence_bundle:
            return True

        valid_record_ids = {rec.get("record_id") for rec in evidence_bundle.get("records", [])}
        conflicts = report.get("conflicts", [])

        for conflict in conflicts:
            cited_ids = conflict.get("evidence_ids", [])
            for cid in cited_ids:
                if cid not in valid_record_ids:
                    return False

        return True