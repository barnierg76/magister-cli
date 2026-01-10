# Bijdragen aan Magister CLI

Bedankt voor je interesse in het bijdragen aan Magister CLI! Dit document beschrijft hoe je kunt bijdragen.

## Hoe bij te dragen

### Bugs melden

1. Controleer eerst of de bug al gemeld is in de [Issues](https://github.com/your-username/magister-cli/issues)
2. Maak een nieuwe issue aan met:
   - Duidelijke titel
   - Stappen om het probleem te reproduceren
   - Verwacht gedrag vs. werkelijk gedrag
   - Python versie en OS

### Feature requests

1. Open een issue met het label `enhancement`
2. Beschrijf de gewenste functionaliteit
3. Leg uit waarom dit nuttig zou zijn

### Code bijdragen

1. Fork de repository
2. Maak een nieuwe branch: `git checkout -b feature/mijn-feature`
3. Maak je wijzigingen
4. Zorg dat tests slagen: `pytest`
5. Format je code: `ruff format .`
6. Check linting: `ruff check .`
7. Commit met duidelijke message
8. Push naar je fork
9. Open een Pull Request

## Development setup

```bash
# Clone je fork
git clone https://github.com/jouw-username/magister-cli.git
cd magister-cli

# Maak virtual environment
uv venv
source .venv/bin/activate

# Installeer met dev dependencies
uv pip install -e ".[dev]"

# Installeer Playwright browser
playwright install chromium
```

## Code stijl

- We gebruiken [ruff](https://github.com/astral-sh/ruff) voor linting en formatting
- Maximale regellengte: 100 karakters
- Type hints waar mogelijk
- Docstrings voor publieke functies

## Tests

```bash
# Alle tests
pytest

# Specifieke test
pytest tests/test_api_client.py

# Met coverage
pytest --cov=magister_cli
```

## Commit messages

Gebruik duidelijke commit messages:

- `feat: beschrijving` - Nieuwe functionaliteit
- `fix: beschrijving` - Bug fix
- `docs: beschrijving` - Documentatie
- `refactor: beschrijving` - Code refactoring
- `test: beschrijving` - Tests toevoegen/aanpassen

## Vragen?

Open een issue met het label `question` of start een discussie.
