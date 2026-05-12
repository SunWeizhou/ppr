"""EntityService — CRUD, metadata fetch, and auto-extraction for entities."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from logger_config import get_logger

logger = get_logger(__name__)


class EntityService:
    """Service layer for entity CRUD and metadata synchronization."""

    def __init__(self, state_store):
        self._store = state_store

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_entity_id(
        entity_type: str, name: str, external_ids: Optional[Dict] = None
    ) -> str:
        """Generate a deterministic entity ID.

        Priority: external provider ID > slugified name.
        """
        ext = external_ids or {}

        if entity_type == "scholar":
            if ext.get("semantic_scholar"):
                return f"scholar:s2:{ext['semantic_scholar']}"
            if ext.get("openalex"):
                return f"scholar:openalex:{ext['openalex']}"

        if entity_type in ("journal", "conference"):
            if ext.get("openalex"):
                return f"{entity_type}:openalex:{ext['openalex']}"

        # Fallback: slugified name
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f"{entity_type}:{slug}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        entity_type: str,
        name: str,
        *,
        external_ids: Optional[Dict] = None,
        metadata_json: Optional[Dict] = None,
        aliases: Optional[List[str]] = None,
    ) -> Dict:
        """Get an existing entity by generated ID, or create a new one."""
        entity_id = self._generate_entity_id(entity_type, name, external_ids)

        existing = self._store.get_entity(entity_id)
        if existing:
            return existing

        return self._store.create_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            external_ids=external_ids,
            metadata_json=metadata_json,
        )

    def get(self, entity_id: str) -> Optional[Dict]:
        return self._store.get_entity(entity_id)

    def list_by_type(self, entity_type: str, *, limit: int = 100) -> List[Dict]:
        return self._store.list_entities(entity_type=entity_type, limit=limit)

    def search(self, query: str, *, entity_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        return self._store.list_entities(entity_type=entity_type, search=query, limit=limit)

    def delete(self, entity_id: str) -> bool:
        return self._store.delete_entity(entity_id)

    # ------------------------------------------------------------------
    # Metadata sync
    # ------------------------------------------------------------------

    def sync_metadata(self, entity_id: str) -> Optional[Dict]:
        """Fetch and update metadata from external APIs."""
        entity = self._store.get_entity(entity_id)
        if not entity:
            return None

        entity_type = entity["type"]
        ext_ids = entity.get("external_ids") or {}
        metadata = entity.get("metadata_json") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (TypeError, json.JSONDecodeError):
                metadata = {}

        try:
            if entity_type in ("journal", "conference"):
                fetched = self._fetch_openalex_source(ext_ids)
                if fetched:
                    metadata.update(fetched)
            elif entity_type == "scholar":
                fetched = self._fetch_scholar_metadata(ext_ids)
                if fetched:
                    metadata.update(fetched)
            # fields are user-defined — no external fetch
        except Exception as e:
            logger.warning("Failed to sync metadata for %s: %s", entity_id, e)

        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"

        return self._store.update_entity(entity_id, metadata_json=metadata, last_synced=now)

    def _fetch_openalex_source(self, external_ids: Dict) -> Optional[Dict]:
        """Fetch journal/conference metadata from OpenAlex Sources API."""
        oa_id = external_ids.get("openalex", "")
        if not oa_id:
            return None
        try:
            url = f"https://api.openalex.org/sources/{oa_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "publisher": (data.get("host_organization_name") or ""),
                "issn": (data.get("issn_l") or ""),
                "impact_factor": data.get("summary_stats", {}).get("2yr_mean_citedness"),
                "h_index": data.get("summary_stats", {}).get("h_index"),
                "homepage_url": (data.get("homepage_url") or ""),
                "scope_description": (data.get("description") or ""),
                "works_count": data.get("works_count"),
            }
        except Exception as e:
            logger.debug("OpenAlex source fetch failed: %s", e)
            return None

    def _fetch_scholar_metadata(self, external_ids: Dict) -> Optional[Dict]:
        """Fetch scholar metadata from Semantic Scholar Author API."""
        s2_id = external_ids.get("semantic_scholar", "")
        if not s2_id:
            return None
        try:
            url = (
                f"https://api.semanticscholar.org/graph/v1/author/{s2_id}"
                f"?fields=name,affiliations,hIndex,citationCount,paperCount,homepage"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "affiliations": data.get("affiliations") or [],
                "h_index": data.get("hIndex"),
                "citation_count": data.get("citationCount"),
                "paper_count": data.get("paperCount"),
                "homepage_url": data.get("homepage") or "",
            }
        except Exception as e:
            logger.debug("Semantic Scholar author fetch failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Subscription convenience
    # ------------------------------------------------------------------

    def subscribe(
        self,
        entity_id: str,
        *,
        filters: Optional[Dict] = None,
        research_question_id: Optional[int] = None,
    ) -> Dict:
        """Create a subscription linked to an entity."""
        entity = self._store.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")

        type_map = {
            "journal": "venue",
            "conference": "venue",
            "scholar": "author",
            "field": "field",
        }
        sub_type = type_map.get(entity["type"], "entity")

        filters_json = json.dumps(filters or {}, ensure_ascii=False)

        meta = entity.get("metadata_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (TypeError, json.JSONDecodeError):
                meta = {}

        query_text = ""
        if entity["type"] == "field":
            cats = meta.get("arxiv_categories", [])
            query_text = cats[0] if cats else ""

        return self._store.create_subscription(
            type=sub_type,
            name=entity["name"],
            query_text=query_text,
            entity_id=entity_id,
            filters_json=filters_json,
            research_question_id=research_question_id,
        )

    # ------------------------------------------------------------------
    # Auto-extraction from search results
    # ------------------------------------------------------------------

    def extract_entities_from_results(self, papers: List[Dict]) -> List[Dict]:
        """Extract venue entities from search result papers (non-blocking safe)."""
        created: List[Dict] = []
        seen_venues: set = set()

        for paper in papers:
            venue = (paper.get("venue") or "").strip()
            if not venue or len(venue) <= 2 or venue in seen_venues:
                continue
            seen_venues.add(venue)
            venue_type = self._classify_venue(venue)
            try:
                ext_ids = {}
                paper_ext = paper.get("external_ids") or {}
                if paper_ext.get("openalex_source"):
                    ext_ids["openalex"] = paper_ext["openalex_source"]

                entity = self.get_or_create(
                    entity_type=venue_type,
                    name=venue,
                    external_ids=ext_ids if ext_ids else None,
                )
                created.append(entity)
            except Exception as e:
                logger.debug("Failed to create venue entity for '%s': %s", venue, e)

        return created

    @staticmethod
    def _classify_venue(venue_name: str) -> str:
        """Classify a venue name as journal or conference."""
        conference_patterns = (
            r"\b(neurips|icml|iclr|aaai|cvpr|iccv|eccv|acl|emnlp|naacl"
            r"|sigir|kdd|www|chi|uai|aistats|colt|isit|focs|stoc|soda"
            r"|conference|proceedings|workshop|symposium)\b"
        )
        if re.search(conference_patterns, venue_name, re.IGNORECASE):
            return "conference"
        return "journal"

    # ------------------------------------------------------------------
    # Related entities for profile pages
    # ------------------------------------------------------------------

    def get_related_entities(self, entity_id: str, *, limit: int = 10) -> List[Dict]:
        """Get entities related to the given entity via entity_relations."""
        relations = self._store.list_entity_relations(entity_id)
        related = []
        seen = set()
        for rel in relations[:limit]:
            other_id = rel["target_id"] if rel["source_id"] == entity_id else rel["source_id"]
            if other_id in seen:
                continue
            seen.add(other_id)
            other = self._store.get_entity(other_id)
            if other:
                other["_relation_type"] = rel["relation_type"]
                other["_relation_weight"] = rel["weight"]
                related.append(other)
        return related
