Kobo Tailscale Manager v1.00

Fonctions
- Détection automatique des Kobo USB sous Windows
- Sélecteur de liseuse
- Lecture firmware, kernel, numéro de série, Model ID et endpoint
- Détection de l'état Tailscale et des fichiers NickelMenu accessibles par USB
- API endpoint éditable avec sauvegarde automatique de Kobo eReader.conf
- Clé Tailscale auth optionnelle, visible et conservée uniquement en mémoire jusqu'à la fermeture de l'application
- GO = installation neuve OU mise à jour
- Restore Kobo config = restauration de l'endpoint et suppression de l'intégration au redémarrage
- Full uninstall = suppression complète de l'intégration et de l'état Tailscale
- Installe NickelMenu si absent
- Installe Tailscale ARM 1.98.10 si absent
- Paquets NickelMenu et Tailscale embarqués pour une installation hors ligne sur la Kobo
- Authentification automatique via auth key si fournie
- Menu NickelMenu : Tailscale - 10 min / Status / Start / Stop / Login
- Sélection des entrées NickelMenu à afficher
- Éjection USB automatique optionnelle
- Aucun autostart permanent par défaut

Sécurité / limites
- Détection du modèle par eLabel, numéro de série, fichier version et configuration Kobo.
- Les modèles reconnus utilisant un firmware compatible ne sont pas limités à la Clara Colour.
- Bloque firmware 5.x.
- La clé Tailscale est écrite temporairement sur la Kobo puis supprimée après authentification réussie.
- Une sauvegarde Kobo eReader.conf.kts-backup est créée avant modification.

Compilation Windows
1. Installer Python 3.12 avec Tcl/Tk.
2. Clic droit sur build_exe.ps1 > Exécuter avec PowerShell (ou depuis un terminal PowerShell).
3. L'EXE final apparaît dans dist\KoboTailscaleManager-v1.00.exe.

Features

- Automatic detection of USB-connected Kobo eReaders on Windows
- eReader selector
- Reads firmware version, kernel, serial number, Model ID, and API endpoint
- Detects Tailscale status and NickelMenu files accessible over USB
- Editable API endpoint with automatic backup of `Kobo eReader.conf`
- Optional Tailscale auth key, visible and kept in memory only until the application is closed
- "GO" = fresh installation OR update
- "Restore Kobo Config" = restores the endpoint and removes the integration on reboot
- "Full Uninstall" = completely removes the integration and Tailscale state
- Installs NickelMenu if not already installed
- Installs Tailscale ARM 1.98.10 if not already installed
- NickelMenu and Tailscale packages are bundled for offline installation on the Kobo
- Automatic authentication using the auth key, if provided
- NickelMenu entries: `Tailscale - 10 min` / `Status` / `Start` / `Stop` / `Login`
- Selectable NickelMenu entries
- Optional automatic USB ejection
- No permanent autostart by default

Security / Limitations

- Model detection using eLabel, serial number, version file, and Kobo configuration
- Recognized models running compatible firmware are not limited to the Clara Colour
- Firmware 5.x is blocked
- The Tailscale auth key is temporarily written to the Kobo and deleted after successful authentication
- A `Kobo eReader.conf.kts-backup` backup is created before any modification

Windows Build

1. Install Python 3.12 with Tcl/Tk.
2. Right-click `build_exe.ps1` and select **Run with PowerShell** (or run it from a PowerShell terminal).
3. The final executable will be created at: dist\KoboTailscaleManager-v1.00.exe

Licence
- Le code propre à Kobo Tailscale Manager est distribué sous licence MIT (voir LICENSE).
- NickelMenu et Tailscale conservent leurs licences respectives (voir THIRD_PARTY_NOTICES.md).

License
- Kobo Tailscale Manager's own code is distributed under the MIT License (see LICENSE).
- NickelMenu and Tailscale retain their respective licenses (see THIRD_PARTY_NOTICES.md).
