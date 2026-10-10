"""
RAG Pipeline for CivicAssist Greenfield Municipal Corporation.
Handles data normalization, chunking, vector indexing, and grounded retrieval.
"""

import os
import json
import csv
import re
from typing import List, Dict, Any, Optional
from src.embeddings import EmbeddingEngine
from src.vector_store import VectorStore
from src.schemas import SourceCitation

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

class MunicipalRAGPipeline:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.embeddings_engine = EmbeddingEngine()
        self.vector_store = VectorStore(dimension=384, similarity_threshold=0.22)
        self.waste_records: List[Dict[str, Any]] = []
        self.permit_records: List[Dict[str, Any]] = []
        self.event_records: List[Dict[str, Any]] = []
        self._load_and_index_all_data()

    def _load_and_index_all_data(self):
        docs = []

        # 1. Load waste schedule
        waste_path = os.path.join(self.data_dir, "waste_schedule.json")
        if os.path.exists(waste_path):
            with open(waste_path, "r", encoding="utf-8") as f:
                self.waste_records = json.load(f)

            for item in self.waste_records:
                zone = item.get("zone", "")
                area = item.get("area", "")
                days = ", ".join(item.get("pickup_days", []))
                time_slot = item.get("pickup_time", "")
                waste_type = item.get("waste_type", "")
                instructions = item.get("special_instructions", "")
                contact = item.get("contact_information", "")

                text_content = (
                    f"Municipal Waste Management Schedule for {zone} ({area}).\n"
                    f"Waste Types Collected: {waste_type}.\n"
                    f"Scheduled Pickup Days: {days}.\n"
                    f"Collection Hours: {time_slot}.\n"
                    f"Special Guidelines: {instructions}.\n"
                    f"Contact: {contact}."
                )

                docs.append({
                    "source_file": "waste_schedule.json",
                    "record_id": zone,
                    "domain": "waste",
                    "title": f"Waste Collection - {zone} ({area})",
                    "text": text_content,
                    "original_record": item
                })

        # 2. Load permits
        permits_path = os.path.join(self.data_dir, "permits.csv")
        if os.path.exists(permits_path):
            with open(permits_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.permit_records = list(reader)

            for item in self.permit_records:
                pid = item.get("permit_id", "")
                ptype = item.get("permit_type", "")
                desc = item.get("description", "")
                reqs = item.get("requirements", "")
                docs_req = item.get("documents", "")
                fee = item.get("fee", "")
                proc_time = item.get("processing_time", "")
                method = item.get("application_method", "")
                office = item.get("office", "")
                contact = item.get("contact", "")

                text_content = (
                    f"Municipal Permit: {ptype} (ID: {pid}).\n"
                    f"Overview: {desc}.\n"
                    f"Eligibility & Requirements: {reqs}.\n"
                    f"Required Documents: {docs_req}.\n"
                    f"Official Municipal Fee: {fee}.\n"
                    f"Processing Time: {proc_time}.\n"
                    f"How to Apply: {method}.\n"
                    f"Department Office: {office} | Contact: {contact}."
                )

                docs.append({
                    "source_file": "permits.csv",
                    "record_id": pid,
                    "domain": "permits",
                    "title": f"Permit: {ptype}",
                    "text": text_content,
                    "original_record": item
                })

        # 3. Load events
        events_path = os.path.join(self.data_dir, "events.json")
        if os.path.exists(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                self.event_records = json.load(f)

            for item in self.event_records:
                eid = item.get("event_id", "")
                name = item.get("name", "")
                cat = item.get("category", "")
                date = item.get("date", "")
                start = item.get("start_time", "")
                end = item.get("end_time", "")
                loc = item.get("location", "")
                desc = item.get("description", "")
                org = item.get("organizer", "")
                outdoor = "Outdoor Event" if item.get("outdoor") else "Indoor Event"

                text_content = (
                    f"Municipal Event: {name} (ID: {eid}).\n"
                    f"Category: {cat} ({outdoor}).\n"
                    f"Date: {date} from {start} to {end}.\n"
                    f"Location: {loc}.\n"
                    f"Details: {desc}.\n"
                    f"Organized by: {org}."
                )

                docs.append({
                    "source_file": "events.json",
                    "record_id": eid,
                    "domain": "events",
                    "title": f"City Event: {name}",
                    "text": text_content,
                    "original_record": item
                })

        # Embed and index
        if docs:
            texts = [d["text"] for d in docs]
            embeddings = self.embeddings_engine.embed_texts(texts)
            self.vector_store.add_documents(docs, embeddings)

    def retrieve(self, query: str, top_k: int = 3, domain: Optional[str] = None) -> List[SourceCitation]:
        """
        Retrieves top_k relevant documents for the citizen query.
        Applies hybrid boosting for explicit entity matches (e.g. Zone A, City Marathon, Building Permit).
        """
        query_emb = self.embeddings_engine.embed_query(query)
        citations = self.vector_store.similarity_search(query_emb, top_k=top_k * 4)

        if domain:
            filtered = [c for c in citations if c.domain == domain]
            if filtered:
                citations = filtered

        # Data-driven entity boosting dynamically derived from loaded records:
        q_lower = query.lower()
        q_tokens = set(re.findall(r"\b[a-z0-9_-]+\b", q_lower))

        for c in citations:
            score_boost = 0.0
            orig = c.metadata or {}

            # 1. Dynamic Waste boost (zone name, zone letter, or area keywords)
            if c.domain == "waste":
                zone_val = str(c.record_id or orig.get("zone", "")).lower()
                area_val = str(orig.get("area", "")).lower()

                zone_tokens = set(re.findall(r"\b[a-z0-9_-]+\b", zone_val))
                area_tokens = set(re.findall(r"\b[a-z0-9_-]+\b", area_val)) - {"and", "the", "of", "in"}

                if zone_val in q_lower or (zone_tokens and zone_tokens.issubset(q_tokens)):
                    score_boost += 0.55
                elif area_tokens and area_tokens.intersection(q_tokens):
                    score_boost += 0.45

            # 2. Dynamic Event boost (derived directly from event name & location in data/events.json)
            elif c.domain == "events":
                event_name = str(orig.get("name", c.title)).lower()
                loc_name = str(orig.get("location", "")).lower()

                stop_words = {"city", "the", "and", "of", "at", "for", "in", "a", "an", "annual", "series"}
                name_tokens = {w for w in re.findall(r"\b[a-z0-9_-]+\b", event_name) if len(w) > 2 and w not in stop_words}
                loc_tokens = {w for w in re.findall(r"\b[a-z0-9_-]+\b", loc_name) if len(w) > 3 and w not in stop_words}

                overlap = name_tokens.intersection(q_tokens)
                loc_overlap = loc_tokens.intersection(q_tokens)

                if len(overlap) >= 2 or (len(name_tokens) == 1 and len(overlap) == 1):
                    score_boost += 0.50
                elif len(overlap) == 1:
                    score_boost += 0.45
                elif loc_overlap:
                    score_boost += 0.35

            # 3. Dynamic Permit boost (derived directly from permit type & description in data/permits.csv)
            elif c.domain == "permits":
                ptype = str(orig.get("permit_type", c.title)).lower()
                pid = str(c.record_id or orig.get("permit_id", "")).lower()

                stop_words = {"permit", "license", "application", "and", "the", "for", "of", "in", "to", "a"}
                ptype_tokens = {w for w in re.findall(r"\b[a-z0-9_-]+\b", ptype) if len(w) > 2 and w not in stop_words}

                desc = str(orig.get("description", "")).lower()
                desc_tokens = {w for w in re.findall(r"\b[a-z0-9_-]+\b", desc) if len(w) > 3 and w not in stop_words}

                if pid and pid in q_lower:
                    score_boost += 0.60
                else:
                    overlap = ptype_tokens.intersection(q_tokens)
                    desc_overlap = desc_tokens.intersection(q_tokens)
                    if len(overlap) >= 2:
                        score_boost += 0.50
                    elif len(overlap) == 1:
                        score_boost += 0.45
                    elif len(desc_overlap) >= 2:
                        score_boost += 0.35

            c.relevance_score = min(1.0, c.relevance_score + score_boost)

        # Re-sort with boost
        citations.sort(key=lambda x: x.relevance_score, reverse=True)
        return citations[:top_k]

    def get_waste_by_zone(self, zone_name: str) -> Optional[Dict[str, Any]]:
        target = zone_name.strip().lower()
        # Normalization: e.g. "a" -> "zone a", "zone-a" -> "zone a"
        if not target.startswith("zone") and len(target) == 1 and target.isalpha():
            target = f"zone {target}"
        target = target.replace("-", " ")

        for r in self.waste_records:
            rz = r.get("zone", "").lower().replace("-", " ")
            if rz == target:
                return r
            # Also check area
            if target in r.get("area", "").lower():
                return r
        return None

    def get_event_by_name(self, name_snippet: str) -> Optional[Dict[str, Any]]:
        target = name_snippet.strip().lower()
        # Direct word overlap
        words = set(re.findall(r"\w+", target))
        best_match = None
        best_score = 0

        for r in self.event_records:
            r_name = r.get("name", "").lower()
            if target in r_name:
                return r
            r_words = set(re.findall(r"\w+", r_name))
            common = len(words.intersection(r_words))
            if common > best_score and common >= 2:
                best_score = common
                best_match = r

        return best_match

    def get_all_events(self) -> List[Dict[str, Any]]:
        return self.event_records

    def get_all_permits(self) -> List[Dict[str, Any]]:
        return self.permit_records

    def get_all_waste_zones(self) -> List[Dict[str, Any]]:
        return self.waste_records
