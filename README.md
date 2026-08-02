# AI Task Creator

Een kleine desktopapp waarmee je tekst en afbeeldingen opslaat als opeenvolgende taken.

## Installeren en starten

1. Dubbelklik eenmalig op `setup.bat`.
2. Dubbelklik daarna op `run.bat` (met console) of `start.bat` (zonder console).

Of vanuit PowerShell:

```powershell
.\setup.bat
.\run.bat
```

## Windows EXE bouwen

Dubbelklik op `build.bat`. De eerste build installeert PyInstaller in de lokale `.venv`.
Het resultaat staat daarna in `dist\AI Task Creator.exe` en kan zonder Python worden gestart.

## Gebruik

- Kies een projectlocatie.
- Links verschijnen alle bestaande `task_*`-mappen, met de nieuwste bovenaan.
- Klik op een taak om de tekst en afbeeldingen opnieuw te laden.
- Voeg afbeeldingen toe met de knop, een dubbelklik in het lege grid, of `Ctrl+V`.
- Als het klembord tekst bevat, werkt `Ctrl+V` normaal in het tekstveld.
- Verwijder een afbeelding met het rode kruisje rechtsboven.
- `Save new` maakt de volgende oplopende taak met `task.txt` en genummerde afbeeldingen.
- `Update task_xxx` vervangt de geopende taak veilig.
- `Save as new` bewaart de geopende inhoud onder een nieuw, hoger taaknummer.
- `New` wist afbeeldingen en tekst, maar behoudt de projectlocatie.
- De laatst gebruikte projectlocatie wordt bij de volgende start automatisch hersteld.

Sneltoetsen: `Ctrl+S` om op te slaan en `Ctrl+N` voor een nieuwe taak.
