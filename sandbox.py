from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
import json
from datetime import datetime
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

from GoDokumenter import create_session, derive_sagsnummer, hent_sagsurl, list_case_documents, download_case_file
from SharepointOverforsel import sharepoint_client, opret_destinationsmappe, upload_filer, generer_udleveringslink

import json
from unittest.mock import MagicMock
import os
from robot_framework.process import process
orchestrator_connection = OrchestratorConnection("GoSagsOpretter", os.getenv('OpenOrchestratorSQL'),os.getenv('OpenOrchestratorKey'), None, None, None)

queue_element = MagicMock()
queue_element.data = json.dumps({})


process(orchestrator_connection= orchestrator_connection, queue_element= queue_element)
