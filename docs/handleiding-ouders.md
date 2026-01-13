# Magister koppelen met Claude: Handleiding voor ouders

Met deze koppeling kun je Claude vragen stellen over het schoolleven van je kind, zoals "Wat heeft Emma deze week voor huiswerk?" of "Hoe staan de cijfers ervoor?" Claude haalt de informatie dan direct uit Magister.

---

## Wat heb je nodig?

- Een computer (Windows of Mac)
- De Claude Desktop app (gratis te downloaden)
- Inloggegevens voor het Magister ouderportaal van je kind's school

---

## Stap 1: Claude Desktop installeren

1. Ga naar [claude.ai/download](https://claude.ai/download)
2. Klik op **Download voor Windows** of **Download voor Mac**
3. Open het gedownloade bestand en volg de installatie
4. Open de Claude app en log in met je account (of maak er een aan)

---

## Stap 2: De Magister-koppeling installeren

### Op Windows:

1. Open de **Opdrachtprompt** (zoek naar "cmd" in het startmenu)
2. Kopieer en plak dit commando en druk op Enter:

```
pip install magister-cli
```

3. Wacht tot de installatie klaar is (je ziet "Successfully installed...")
4. **Belangrijk:** Voer nu dit commando uit om het pad te vinden:

```
where magister-mcp
```

5. **Kopieer het volledige pad dat verschijnt** (bijvoorbeeld: `C:\Users\Johan\AppData\Local\Programs\Python\Python312\Scripts\magister-mcp.exe`)

### Op Mac:

1. Open de **Terminal** (zoek via Spotlight met Cmd+Spatie)
2. Kopieer en plak dit commando en druk op Enter:

```
pip3 install magister-cli
```

3. Wacht tot de installatie klaar is
4. **Belangrijk:** Voer nu dit commando uit om het pad te vinden:

```
which magister-mcp
```

5. **Kopieer het volledige pad dat verschijnt** (bijvoorbeeld: `/Users/johan/.local/bin/magister-mcp`)

> **Foutmelding?** Als je een fout krijgt dat pip niet gevonden is, moet je eerst Python installeren. Ga naar [python.org/downloads](https://python.org/downloads) en download de nieuwste versie. **Let op:** Vink tijdens de installatie "Add Python to PATH" aan!

---

## Stap 3: Claude koppelen aan Magister

Nu moeten we Claude vertellen dat de Magister-koppeling bestaat. **Dit is de belangrijkste stap!**

### Op Windows:

1. Open Verkenner en ga naar: `C:\Users\[JOUWNAAM]\AppData\Roaming\Claude\`

   > **Tip:** AppData is een verborgen map. Typ `%appdata%\Claude` in de adresbalk en druk Enter.

2. Open het bestand `claude_desktop_config.json` met Kladblok
   - Als het bestand niet bestaat, maak het aan

3. **Vervang de inhoud met dit** (gebruik het pad dat je in stap 2 hebt gekopieerd):

```json
{
  "mcpServers": {
    "magister": {
      "command": "C:\\Users\\JOUWNAAM\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\magister-mcp.exe"
    }
  }
}
```

> **Let op:** Vervang het pad met het pad dat JIJ in stap 2 hebt gevonden! En gebruik dubbele backslashes `\\` in plaats van enkele `\`.

4. Sla het bestand op en sluit Kladblok

### Op Mac:

1. Open Finder
2. Druk op **Cmd + Shift + G** en typ: `~/Library/Application Support/Claude/`
3. Open `claude_desktop_config.json` met TextEdit
   - Als het bestand niet bestaat, maak het aan

4. **Vervang de inhoud met dit** (gebruik het pad dat je in stap 2 hebt gekopieerd):

```json
{
  "mcpServers": {
    "magister": {
      "command": "/Users/jouwnaam/.local/bin/magister-mcp"
    }
  }
}
```

> **Let op:** Vervang het pad met het pad dat JIJ in stap 2 hebt gevonden!

5. Sla op en sluit TextEdit

---

## Stap 4: Playwright browser installeren

De Magister-koppeling heeft een browser nodig voor het inloggen. Open de Opdrachtprompt (Windows) of Terminal (Mac) en voer uit:

```
playwright install chromium
```

---

## Stap 5: Claude herstarten

1. Sluit de Claude Desktop app **volledig** af:
   - **Windows:** Klik met rechts op het Claude-icoon in de taakbalk (rechtsonder) → Afsluiten
   - **Mac:** Klik op Claude in de menubalk → Quit Claude

2. Open Claude Desktop opnieuw

3. **Controleer of het werkt:** Je zou in Claude een klein stekker-icoontje moeten zien. Als je daarop klikt, zou "magister" in de lijst moeten staan.

---

## Stap 6: Schoolcode instellen (optioneel maar handig)

Je kunt de schoolcode van je kind's school vast instellen, zodat je die niet elke keer hoeft te noemen.

1. Open de Opdrachtprompt (Windows) of Terminal (Mac)
2. Typ dit commando en druk op Enter:

```
magister config set school SCHOOLCODE
```

Vervang `SCHOOLCODE` met de code van jullie school (bijvoorbeeld `vsvonh`)

> **Schoolcode vinden:** Dit is het eerste deel van het Magister-adres. Als de school `montessori-amsterdam.magister.net` gebruikt, dan is de code `montessori-amsterdam`.

Als je dit niet doet, kun je de schoolcode ook meegeven in je vraag aan Claude, bijvoorbeeld: *"Wat is het huiswerk? (school: vsvonh)"*

---

## Stap 7: Inloggen bij Magister

De eerste keer dat je iets vraagt over school, moet je inloggen:

1. Vraag Claude iets over school, bijvoorbeeld: *"Wat is het huiswerk voor deze week?"*
2. Er opent automatisch een browservenster met de Magister-inlogpagina
3. Log in zoals je normaal zou doen op het ouderportaal
4. Na het inloggen sluit het venster vanzelf
5. Claude heeft nu toegang en beantwoordt je vraag

> **Let op:** Je moet ongeveer elke 2 uur opnieuw inloggen. Claude vraagt dit automatisch wanneer nodig.

---

## Voorbeeldvragen die je kunt stellen

Nu kun je Claude van alles vragen over school:

### Huiswerk:
- "Wat heeft [naam kind] deze week voor huiswerk?"
- "Zijn er toetsen gepland?"
- "Wat moet er af voor wiskunde?"

### Cijfers:
- "Hoe staan de cijfers ervoor?"
- "Wat zijn de laatste cijfers?"
- "Hoe gaat het met Nederlands?"

### Rooster:
- "Hoe ziet het rooster er morgen uit?"
- "Zijn er lessen uitgevallen?"
- "Hoe laat begint school vrijdag?"

### Berichten:
- "Zijn er nieuwe berichten van school?"
- "Wat staat er in de laatste mail van de mentor?"

---

## Problemen oplossen

### "Claude reageert niet op mijn vraag over school"

Controleer of je in Claude Desktop zit (niet op de website claude.ai). De Magister-koppeling werkt alleen in de desktop-app.

### "spawn magister-mcp ENOENT" foutmelding

Dit betekent dat Claude het magister-mcp programma niet kan vinden. Controleer:

1. Heb je stap 2 correct uitgevoerd? Voer `where magister-mcp` (Windows) of `which magister-mcp` (Mac) uit om het pad te vinden.
2. Heb je het **volledige pad** in het configuratiebestand gezet? Niet alleen `magister-mcp` maar het complete pad zoals `C:\Users\...\magister-mcp.exe`
3. Op Windows: gebruik dubbele backslashes `\\` in het pad

### "Het inlogvenster verschijnt niet"

1. Heb je `playwright install chromium` uitgevoerd?
2. Sluit Claude volledig af en open het opnieuw.

### "Ik krijg een foutmelding over het configuratiebestand"

Controleer of de tekst exact klopt:
- Alle aanhalingstekens moeten "rechte" aanhalingstekens zijn, niet "gekrulde"
- De accolades `{ }` moeten goed geopend en gesloten zijn
- Het pad moet correct zijn (kopieer het exact uit de terminal)

### "pip wordt niet herkend"

Python is niet (goed) geïnstalleerd. Download Python opnieuw van [python.org](https://python.org) en vink tijdens installatie aan: **"Add Python to PATH"**

---

## Privacy en veiligheid

- Alle gegevens blijven lokaal op jouw computer
- Claude slaat geen schoolgegevens op in de cloud
- Je Magister-wachtwoord wordt niet door Claude opgeslagen
- De sessie verloopt automatisch na ongeveer 2 uur

---

**Hulp nodig?** Stel je vraag op [github.com/kieranaudeDev/magister-cli/issues](https://github.com/kieranaudeDev/magister-cli/issues)
