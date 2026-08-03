"""Functions for reading files out of an existing GO case ("Udleveringsmappen")
created by OverførFilerTilGo, without attempting any PDF conversion.

The "Udleveringsmappe" is not a folder — it is a GO case created via GO's own
REST API (see OverførFilerTilGo/Funktioner.py: create_case). Udleveringsmappelink
is the URL to that case, and its documents already live in the case's
"Dokumenter" list (some already converted to PDF by GO, some not).

Listing/downloading follows the same proven, live pattern already used
elsewhere in this codebase to read an existing GO case's document list
(Dokumentliste/robot_framework/HentFilerOpretMapper.py) and to fetch document
bytes by DocID (OverførFilerTilGo/Funktioner.py: fetch_document_bytes) — not a
hand-rolled SharePoint folder walk.
"""

import json
import time
import xml.etree.ElementTree as ET

import requests
from requests_ntlm import HttpNtlmAuth


def create_session(username, password):
    """Creates an NTLM-authenticated session for talking to GO's REST API.
    Same pattern as OverførFilerTilGo/Funktioner.py: create_session.
    """
    session = requests.Session()
    session.auth = HttpNtlmAuth(username, password)
    return session


def derive_sagsnummer(udleveringsmappelink):
    """Extracts the bare GO case number (e.g. 'AKT-2026-001234') from the stored
    Udleveringsmappelink.

    Same extraction OverførFilerTilGo/robot_framework/process.py uses to delete
    a previous delivery case: UdleveringsSagsID = Udleveringsmappelink.rsplit("/")[-1]
    """
    return udleveringsmappelink.rsplit("/")[-1]


def hent_sagsurl(go_api_url, sagsnummer, session):
    """Looks up the case's SharePoint-relative URL (e.g. 'cases/AKT/AKT-2026-001234/')
    via GO's own case-metadata API.

    Same call as Dokumentliste/robot_framework/HentFilerOpretMapper.py:28-43.
    """
    url = f"{go_api_url}/_goapi/Cases/Metadata/{sagsnummer}"
    response = session.get(url, timeout=500)
    response.raise_for_status()

    metadata_xml = json.loads(response.text).get("Metadata")
    xdoc = ET.fromstring(metadata_xml)
    return xdoc.attrib.get("ows_CaseUrl")


def list_case_documents(go_api_url, sagsnummer, sags_url, session, orchestrator_connection=None):

    session.headers.update({"Content-Type": "application/json"})

    endelse = sagsnummer.rsplit('-', 1)[-1]
    relative_dokumenter_path = f"/{sags_url.rstrip('/')}/Dokumenter"
    encoded_path = relative_dokumenter_path.replace('/', '%2F')
    list_url = f"%27{encoded_path}%27"

    counter_url = f"{go_api_url}/{sags_url}/_goapi/Administration/GetLeftMenuCounter/{endelse}"
    response = session.get(counter_url)
    response.raise_for_status()
    view_ids_array = json.loads(response.text)

    all_items_view_id = None
    for item in view_ids_array:
        if item.get("ListName") == "Dokumenter" and (item.get("ViewName") or "").lower() == "udgaaende.aspx":
            all_items_view_id = item.get("ViewId")
            break

    if not all_items_view_id:
        raise ValueError("Ingen ViewId fundet for Udgaaende.aspx på Dokumenter-listen.")

    documents = {}
    firstrun = True
    more_pages = True
    next_href = None

    while more_pages:
        url = f"{go_api_url}/{sags_url}/_api/web/GetList(@listUrl)/RenderListDataAsStream"

        if not firstrun:
            url_with_query = f"{url}?@listUrl={list_url}{next_href.replace('?', '&')}"
            response = session.post(url_with_query, timeout=500)
        else:

            query_params = f"?@listUrl={list_url}&View={all_items_view_id}"
            response = session.post(url + query_params, timeout=500)
        response.raise_for_status()

        dokumentliste_json = json.loads(response.text)
        rows = dokumentliste_json.get("Row", [])
        next_href = dokumentliste_json.get("NextHref")
        more_pages = "NextHref" in dokumentliste_json

        for row in rows:
            doc_id = row.get("DocID")
            if not doc_id:
                # Folder pseudo-rows (e.g. the category subfolders themselves)
                # have no DocID - skip them, we only want actual documents.
                continue
            documents[str(doc_id)] = row.get("FileLeafRef")

        firstrun = False

    return [{"doc_id": doc_id, "name": name} for doc_id, name in documents.items()]


def download_case_file(go_api_url, doc_id, session, max_retries=30, retry_interval=5):

    url = f"{go_api_url}/_goapi/Documents/DocumentBytes/{doc_id}"
    byte_result = None
    for _ in range(max_retries):
        try:
            response = session.get(url, timeout=180)
            response.raise_for_status()
            if b"HTTP Error 503. The service is unavailable." in response.content:
                time.sleep(retry_interval)
                continue
            byte_result = response.content
            break
        except Exception:
            time.sleep(retry_interval)
    return byte_result
