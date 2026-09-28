"""Worker de rastreo: el proceso que consulta las fuentes externas — `TASK-20`.

Corre aparte de la API (`docs/architecture.md` §1.4): con `uvicorn --reload`,
cada guardado reiniciaría la API, y la API nunca llama a una fuente externa.
El único estado que comparten los dos procesos es la base.

    python -m app.workers              # ciclos cada 60 s, hasta Ctrl+C
    python -m app.workers --una-vez    # un solo ciclo, para verificar
"""
