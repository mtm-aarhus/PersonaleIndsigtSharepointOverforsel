# OverførFilerTilSharepoint

OpenOrchestrator-proces der lytter på køen `PersonalemappeAktindsigtSharepointOverførsel`.

Ved kø-besked henter processen de dokumenter, der allerede ligger i den GO-sag
("Udleveringsmappen") som `OverførFilerTilGo` har oprettet, uden at forsøge
PDF-konvertering, og lægger dem over i en ny mappe i Sharepoint. Herefter
genereres et tidsbegrænset, adgangskodebeskyttet delingslink til mappen, og
link + adgangskode skrives tilbage på sagen i databasen (`dbo.cases`), så det
kan indsættes i "Send svar til ansøger"-trinnet i personaleindsigt-webappen.

