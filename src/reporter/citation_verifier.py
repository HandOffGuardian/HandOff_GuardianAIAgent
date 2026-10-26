"""
citation_verify.py
Purpose: Ensure all evidence citations in the final report tie back to actual source records.
"""


class CitationVerifier:
    @staticmethod
    def verify_citations(report: dict, evidence_bundle: dict) -> bool:
        """Return whether every report citation points to a collected record.

        The current repository contract uses ``evidence`` and ``evidence_id``;
        the legacy fixture contract used ``records`` and ``record_id``. Both
        are accepted, while malformed or absent bundles fail closed.
        """
        if not isinstance(report, dict) or not isinstance(evidence_bundle, dict):
            return False
        records = evidence_bundle.get("evidence", evidence_bundle.get("records"))
        if not isinstance(records, list):
            return False
        valid_ids = {
            record.get("evidence_id", record.get("record_id"))
            for record in records
            if isinstance(record, dict)
        }
        raw_cited_ids = report.get("evidence_ids", [])
        if not isinstance(raw_cited_ids, list):
            return False
        cited_ids = list(raw_cited_ids)
        for key in ("conflicts", "findings"):
            items = report.get(key, [])
            if not isinstance(items, list):
                return False
            for item in items:
                if not isinstance(item, dict):
                    return False
                refs = item.get("evidence_ids", [])
                if not isinstance(refs, (list, tuple)):
                    return False
                cited_ids.extend(refs)
        return all(isinstance(evidence_id, str) and evidence_id in valid_ids for evidence_id in cited_ids)
