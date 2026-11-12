# dbank

Bank web application for Django - course project.

## Instalation

### If you are running Linux

then create virtual environment and install all the required packages with following commands:

```bash
cd dbank_project
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```


### If your are running Windows

then you are on your own ;) Or you can install [Chocolately](https://chocolatey.org/) (package manager for _Windows_)
and run following commands:

```shell
choco install cmder
choco install python3
```

## Running the project

## SonarCloud analysis

The active GitHub workflow is `.github/workflows/sonarcloud.yml` at the repository
root. Configure the repository Actions secret `SONAR_TOKEN` with a token authorized
for `Felipecoder07_Manutencao-mBank`. Push to `main`, open/update a pull request, or
use **Actions > SonarCloud > Run workflow** after the workflow is on the default
branch. The nested workflow is not executed by GitHub in this repository layout.

The scanner reads `dbank_project/sonar-project.properties`; its existing source
scope is `dbank`. Static analysis does not require a Django `SECRET_KEY`.
Check the Actions run and the SonarCloud dashboard after sending the changes;
passing local tests does not guarantee a passing quality gate.

## Local startup

After installing the requirements:

Set `SECRET_KEY` before running any Django command. There is no default secret;
startup fails if it is missing or empty. `DEBUG` defaults to `False` and is enabled
only with `DEBUG=true`. For a local PowerShell session, from `dbank_project`:

```powershell
$env:SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
$env:DEBUG = 'true'
```

On Linux with the virtual environment active:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export DEBUG=true
```

These commands generate a temporary development key for the current shell. In
production, configure a new persistent key through your hosting secret manager
and keep `DEBUG=false`. Replace the previously committed key in every deployed
environment; removing it from the source does not rotate deployed secrets. Do
not reuse that key or add it to `SECRET_KEY_FALLBACKS`. Rotation can invalidate
existing sessions and signed tokens. Environment files are not loaded automatically.

```bash
cd dbank
python manage.py migrate
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in your browser. The repo already ships a `db.sqlite3`
with one client (`joao`); `migrate` is a no-op against it and only matters if you start
from a fresh database.
