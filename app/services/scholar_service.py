"""Scholar management service — CRUD, arXiv fetching, Google Scholar parsing."""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape

from logger_config import get_logger
from utils import safe_load_json

logger = get_logger(__name__)


class ScholarService:
    def __init__(self, scholars_file: str):
        self.scholars_file = scholars_file

    def load(self) -> dict:
        return safe_load_json(self.scholars_file, {"scholars": []})

    def save(self, scholars_data: dict) -> None:
        with open(self.scholars_file, "w", encoding="utf-8") as f:
            json.dump(scholars_data, f, ensure_ascii=False, indent=2)

    def add(self, name, affiliation="", focus="", arxiv_query="", google_scholar="", website="", email="") -> tuple[bool, str | dict]:
        data = self.load()
        for s in data["scholars"]:
            if s["name"].lower() == name.lower():
                return False, "学者已存在"
        scholar = {
            "name": name,
            "affiliation": affiliation,
            "focus": focus,
            "email": email,
            "google_scholar": google_scholar,
            "website": website,
            "arxiv": arxiv_query or f'https://arxiv.org/search/?searchtype=author&query={urllib.parse.quote(name)}',
            "added_at": datetime.now().isoformat(),
        }
        data["scholars"].append(scholar)
        self.save(data)
        return True, scholar

    def update(self, original_name, name, affiliation="", focus="", arxiv_query="", google_scholar="", website="", email="") -> tuple[bool, str]:
        data = self.load()
        original_name = str(original_name or "").strip()
        name = str(name or "").strip()
        if not original_name or not name:
            return False, "缺少学者姓名"
        for scholar in data["scholars"]:
            if scholar["name"].lower() != original_name.lower():
                continue
            scholar.update({
                "name": name, "affiliation": affiliation, "focus": focus,
                "email": email, "google_scholar": google_scholar, "website": website,
                "arxiv": arxiv_query or f'https://arxiv.org/search/?searchtype=author&query={urllib.parse.quote(name)}',
                "updated_at": datetime.now().isoformat(),
            })
            self.save(data)
            return True, scholar
        return False, "学者不存在"

    def remove(self, name) -> tuple[bool, str]:
        data = self.load()
        original_len = len(data["scholars"])
        data["scholars"] = [s for s in data["scholars"] if s["name"].lower() != name.lower()]
        if len(data["scholars"]) == original_len:
            return False, "学者不存在"
        self.save(data)
        return True, "已删除"

    def fetch_papers(self, scholar_name: str, max_results: int = 5) -> list[dict]:
        ssl_context = ssl.create_default_context()
        query = urllib.parse.quote(f'au:"{scholar_name}"')
        url = f"https://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
        papers = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arXiv-Recommender/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                xml_content = response.read().decode("utf-8")
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                link_elem = entry.find("atom:id", ns)
                published_elem = entry.find("atom:published", ns)
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_elem = author.find("atom:name", ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                link = link_elem.text if link_elem is not None else ""
                arxiv_id = link.split("/")[-1] if link else ""
                paper = {
                    "title": title_elem.text.strip() if title_elem is not None else "No Title",
                    "authors": authors,
                    "abstract": (summary_elem.text.strip()[:300] + "..." if summary_elem is not None and len(summary_elem.text) > 300 else (summary_elem.text.strip() if summary_elem else "")),
                    "link": link,
                    "arxiv_id": arxiv_id,
                    "published": published_elem.text[:10] if published_elem is not None else "",
                    "scholar": scholar_name,
                }
                papers.append(paper)
        except Exception as e:
            logger.error(f"Error fetching papers for {scholar_name}: {e}")
        return papers

    def get_all_papers(self, max_per_scholar: int = 3) -> dict:
        data = self.load()
        results = {}
        for scholar in data.get("scholars", []):
            name = scholar["name"]
            papers = self.fetch_papers(name, max_per_scholar)
            if papers:
                results[name] = {"scholar_info": scholar, "papers": papers}
        return results

    @staticmethod
    def parse_google_scholar_url(url: str) -> dict:
        match = re.search(r"user=([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"success": False, "error": "无法从链接中提取学者ID"}
        user_id = match.group(1)
        scholar_url = f"https://scholar.google.com/citations?user={user_id}&hl=en"
        ssl_context = ssl.create_default_context()
        try:
            req = urllib.request.Request(scholar_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as e:
            return {"success": False, "error": f"无法访问: {e}"}
        name_match = re.search(r'<div id="gsc_prf_in">([^<]+)</div>', html)
        aff_match = re.search(r'<div class="gsc_prf_il">([^<]+)</div>', html)
        return {
            "success": True,
            "user_id": user_id,
            "name": unescape(name_match.group(1).strip()) if name_match else "",
            "affiliation": unescape(aff_match.group(1).strip()) if aff_match else "",
        }
