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

After installing the requirements:

```bash
cd dbank
python manage.py migrate
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in your browser. The repo already ships a `db.sqlite3`
with one client (`joao`); `migrate` is a no-op against it and only matters if you start
from a fresh database.
