"""Verify report evidence references against the Evidence Agent bundle."""


class CitationVerifier:
    @staticmethod
    def verify_citations(report: dict, evidence_bundle: dict) -> bool:
        if not isinstance(report, dict) or not isinstance(evidence_bundle, dict):
            return False

        records = evidence_bundle.get("evidence", evidence_bundle.get("records"))
        if not isinstance(records, list):
            return False
        record_ids = set()
        for record in records:
            if not isinstance(record, dict):
                return False
            record_id = record.get("evidence_id", record.get("record_id"))
            if isinstance(record_id, str) and record_id:
                record_ids.add(record_id)

        for section in ("findings", "conflicts"):
            entries = report.get(section, [])
            if not isinstance(entries, list):
                return False
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                cited_ids = entry.get("evidence_ids", [])
                if not isinstance(cited_ids, (list, tuple)):
                    return False
                if any(not isinstance(item, str) or item not in record_ids for item in cited_ids):
                    return False
        return True
