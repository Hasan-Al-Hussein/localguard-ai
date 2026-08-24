LOCALGUARD AI — WINDOWS QUICK START
===================================

1. Extract the entire ZIP to a normal local folder.
   Do not run it from inside the ZIP preview.

2. Double-click START-LOCALGUARD.cmd.
   The launcher checks the computer and asks before installing missing free
   prerequisites. Windows may display an administrator/UAC confirmation.

3. Keep Docker Desktop open. The first run downloads pinned container images,
   JavaScript packages, and about 1.4 GB of local AI models, then builds the app.
   Depending on the internet connection and CPU, allow roughly 15–40 minutes.
   Later starts are much faster.

4. LocalGuard opens http://localhost:3000 in the default browser.
   Run VIEW-LOCALGUARD-LOGIN.cmd to display the locally generated reviewer login.

5. Double-click STOP-LOCALGUARD.cmd when you want to stop the app. Your local
   database, uploaded documents, and models remain on this computer.

WHAT THE FIRST RUN NEEDS
------------------------

- Windows 10 or Windows 11 (64-bit)
- Internet access for the first download
- Hardware virtualization enabled
- At least 8 GB RAM; 16 GB is recommended
- At least 16 GB free disk space; 25 GB is recommended
- Permission to install PowerShell 7, Docker Desktop, and Node.js 24 LTS

Docker Desktop may require a Windows restart after its first installation. If
that happens, restart the computer, open Docker Desktop, wait for “Engine
running,” and double-click START-LOCALGUARD.cmd again. The setup is resumable.

PRIVACY
-------

The standard runtime binds the web app and API only to this computer. Documents,
database records, prompts, embeddings, and model execution remain local. Random
credentials are generated on first setup and stored only in the local .env file,
which is not included in this ZIP.

This package is an engineering demonstration, not legal advice or a production
compliance system. Read README.md for the full architecture, security boundary,
testing evidence, and limitations.
