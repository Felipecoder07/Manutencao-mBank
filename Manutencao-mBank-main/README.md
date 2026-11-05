como rodar
1: Abra um terminal e crie uma maquina virtual usando o codigo: 'python -m venv venv' (windows) 'python3 -m venv venv (Mac/Linux).
2: Ative esse ambiente virtual: Windows (cmd): 'venv\Scripts\activate.bat'. Windows (PowerShell): 'venv\Scripts\Activate.ps1'. Mac/Linux: 'source venv/bin/activate'.
3: Use o comando 'cd' para entrar na pasta que esta o arquivos requirements e baixe as dependencias:  'pip install -r requirements.txt'
4: Use o comando 'cd' para entrar na pasta que esta o arquivo manage.py e aplique as migrações: 'python manage.py migrate'
5: Inicie o servidor: 'python manage.py runserver'
6: Abra no navegador: http://127.0.0.1:8000/
