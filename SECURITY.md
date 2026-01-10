# Beveiligingsbeleid

## Ondersteunde versies

| Versie | Ondersteund |
|--------|-------------|
| 0.1.x  | :white_check_mark: |

## Beveiligingskwetsbaarheden melden

**Meld beveiligingsproblemen NIET via publieke GitHub issues.**

Als je een beveiligingskwetsbaarheid ontdekt:

1. **Email**: Stuur een email naar de maintainer (zie profiel)
2. **Beschrijf**: Het probleem en mogelijke impact
3. **Reproduceer**: Stappen om het probleem te reproduceren
4. **Wacht**: Geef ons tijd om het probleem op te lossen voordat je het publiek maakt

We streven ernaar om binnen 48 uur te reageren op beveiligingsmeldingen.

## Beveiligingsmaatregelen

### Authenticatie

- OAuth tokens worden veilig opgeslagen in de system keychain (via `keyring`)
- Browser sessiedata wordt opgeslagen met beperkte permissies (0700/0600)
- Geen wachtwoorden worden opgeslagen - authenticatie gebeurt via browser

### Data opslag

- Configuratie: `~/.config/magister-cli/`
- Browser data: `~/.config/magister-cli/browser_data/`
- Alle bestanden hebben restrictieve permissies

### Netwerk

- Alleen HTTPS verbindingen naar `*.magister.net`
- School codes worden gevalideerd om SSRF te voorkomen

## Verantwoorde disclosure

We volgen het principe van verantwoorde disclosure:

1. Melder rapporteert privé
2. We bevestigen ontvangst binnen 48 uur
3. We werken aan een fix
4. We releasen een patch
5. We publiceren een advisory (indien van toepassing)
6. Melder mag publiek maken na de fix

## Bekende beperkingen

- De CLI slaat browser sessies lokaal op voor automatische re-authenticatie
- Tokens kunnen maximaal enkele weken geldig blijven (afhankelijk van Magister)
- MCP server draait lokaal en is niet bedoeld voor remote toegang
