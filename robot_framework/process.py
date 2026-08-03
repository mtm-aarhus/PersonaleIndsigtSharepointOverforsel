from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
import json
from datetime import datetime
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

from GoDokumenter import create_session, derive_sagsnummer, hent_sagsurl, list_case_documents, download_case_file
from SharepointOverforsel import sharepoint_client, opret_destinationsmappe, upload_filer, generer_udleveringslink


def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    specific_content = json.loads(queue_element.data)

    go_api_url = orchestrator_connection.get_constant("GOApiURL").value
    sharepoint_url = orchestrator_connection.get_constant("AktindsigtPersonalemapperSharepointURL").value
    go_api_login = orchestrator_connection.get_credential("GOAktApiUser")
    go_username = go_api_login.username
    go_password = go_api_login.password

    caseid = specific_content.get('caseid')
    personale_sags_titel = specific_content.get('PersonaleSagsTitel')
    udleveringsmappelink = specific_content.get('Udleveringsmappelink')

    orchestrator_connection.log_info(f'Overfører sag {caseid} til Sharepoint')

    # 1 - Hent dokumenterne fra GO-sagen ("Udleveringsmappen"), som de er (ingen PDF-konvertering)
    session = create_session(go_username, go_password)
    sagsnummer = derive_sagsnummer(udleveringsmappelink)
    sags_url = hent_sagsurl(go_api_url, sagsnummer, session)
    documents = list_case_documents(go_api_url, sagsnummer, sags_url, session, orchestrator_connection)
    orchestrator_connection.log_info(f'Fandt {len(documents)} dokumenter i udleveringsmappen')

    files = []
    for document in documents:
        content = download_case_file(go_api_url, document["doc_id"], session)
        if content is None:
            orchestrator_connection.log_info(f'Kunne ikke hente dokument {document["doc_id"]} ({document["name"]}) - springer over')
            continue
        files.append({"name": document["name"], "content": content})

    # 2 - Opret destinationsmappe i Sharepoint og upload filerne
    ctx = sharepoint_client(orchestrator_connection, sharepoint_url)
    case_folder = opret_destinationsmappe(ctx, sharepoint_url, caseid, personale_sags_titel)
    upload_filer(ctx, case_folder, files)
    orchestrator_connection.log_info(f'{len(files)} filer overført til Sharepoint')

    # 3 - Generer tidsbegrænset, adgangskodebeskyttet udleveringslink
    link, password = generer_udleveringslink(case_folder, expiration_days=30)

    # 4 - Skriv link + adgangskode tilbage på sagen
    orchestrator_connection.log_info('Logging info to database')
    SQL_SERVER = orchestrator_connection.get_constant('SqlServer').value
    DATABASE_NAME = "AktindsigterPersonalemapper"

    odbc_str = (
        "DRIVER={SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={DATABASE_NAME};"
        "Trusted_Connection=yes;"
    )
    odbc_str_quoted = quote_plus(odbc_str)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={odbc_str_quoted}", future=True)

    sql = text("""
        UPDATE dbo.cases
        SET sharepoint_udleveringslink = :link,
            sharepoint_udleveringslink_password = :password,
            last_run_transfer_sharepoint = :ts
        WHERE aktid = :caseid
    """)

    with engine.begin() as conn:
        result = conn.execute(sql, {
            "link": link,
            "password": password,
            "ts": datetime.now(),
            "caseid": str(caseid)
        })
        if result.rowcount == 0:
            orchestrator_connection.log_info(f"⚠️ Ingen sag fundet med aktid={caseid}")
        else:
            orchestrator_connection.log_info(f"✅ Opdateret sag {caseid} med Sharepoint-udleveringslink")
