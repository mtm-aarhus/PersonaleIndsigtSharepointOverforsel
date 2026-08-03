"""Functions for uploading files into a new Sharepoint destination folder and
generating a time-limited, password-protected delivery link for it.

Authentication and folder-creation follow the same cert-based app-only pattern
as Dokumentliste/robot_framework/HentFilerOpretMapper.py. The sharing-link
logic is ported from the live code path in
Python_Aktbob2_FromFilarkivToSharePoint/SharePointUploader.py
(get_sharepoint_folder_links), shortened to only the time-limited/
password-protected "Flexible" link (the separate no-expiration anonymous link
from that reference is not needed here).
"""

import random
import re
import string
from datetime import datetime, timedelta, timezone

from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.sharing.links.kind import SharingLinkKind
from office365.sharepoint.sharing.role import Role


def sanitize_folder_name(folder_name):
    """Sanitizes a folder name to be safe for Sharepoint.
    Copied verbatim from Dokumentliste/robot_framework/HentFilerOpretMapper.py.
    """
    pattern = r'[.,~#%&*{}\[\]\\:<>?/+|$¤£€\"\t]'
    folder_name = re.sub(pattern, "", folder_name)
    folder_name = re.sub(r"\s+", " ", folder_name).strip()
    return folder_name


def sharepoint_client(orchestrator_connection, sharepoint_url):
    """Authenticates to Sharepoint using an Azure AD app-only certificate,
    the same credential pattern as Dokumentliste/robot_framework/HentFilerOpretMapper.py
    (credentials "SharePointCert" and "SharePointAPI").
    """
    certification = orchestrator_connection.get_credential("SharePointCert")
    api = orchestrator_connection.get_credential("SharePointAPI")

    cert_credentials = {
        "tenant": api.username,
        "client_id": api.password,
        "thumbprint": certification.username,
        "cert_path": certification.password
    }

    return ClientContext(sharepoint_url).with_client_certificate(**cert_credentials)


def opret_destinationsmappe(ctx, sharepoint_url, caseid, personale_sags_titel):
    """Creates a single, flat destination folder for the case under
    Delte dokumenter/Udleveringsmapper, following the same
    .folders.add()/execute_query() pattern as HentFilerOpretMapper.py.
    """
    parent_folder_name = sharepoint_url.split(".com")[-1] + f"/Delte dokumenter/Udleveringsmapper"
    mappe_navn = sanitize_folder_name(f"{caseid} - {personale_sags_titel} - Personaleaktindsigtsanmodning")

    if len(mappe_navn) > 395:
        mappe_navn = mappe_navn[:390] + "(...)"

    root_folder = ctx.web.get_folder_by_server_relative_url(parent_folder_name)
    case_folder = root_folder.folders.add(mappe_navn)
    ctx.execute_query()
    return case_folder


def upload_filer(ctx, case_folder, files):
    """Uploads a list of {"name": ..., "content": <bytes>} into the destination folder."""
    for file in files:
        case_folder.upload_file(file["name"], file["content"])
        ctx.execute_query()


def generer_udleveringslink(case_folder, expiration_days=30):
    """Generates a time-limited, password-protected Sharepoint sharing link for
    the given folder.

    Ported from the live code in
    Python_Aktbob2_FromFilarkivToSharePoint/SharePointUploader.py:
    get_sharepoint_folder_links (the SharingLinkKind.Flexible branch).

    Returns (link, password).
    """
    expiration_date = (datetime.now(timezone.utc) + timedelta(days=expiration_days)).strftime("%Y-%m-%dT%H:%M:%S%z")
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    result = case_folder.share_link(
        link_kind=SharingLinkKind.Flexible,
        expiration=expiration_date,
        password=password,
        role=Role.View
    ).execute_query()

    link = result.value.sharingLinkInfo.Url
    return link, password
