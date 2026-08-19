Kobo Tailscale Manager v4.2

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
3. L'EXE final apparaît dans dist\KoboTailscaleManager.exe.
