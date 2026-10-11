# omni-one devcontainer

Open this repo in VS Code with Dev Containers (python 3.11 image).

What you get:

- Port 5003 forwarded (API). Open `http://localhost:5003/health`.
- `postCreateCommand` installs seller reqs + editable package.
- Extensions: Python + YAML.

Quickstart:
  1. Reopen in Container.
  2. `PYTHONPATH=src python -m pytest tests/unit -q`
  3. `uvicorn omni_one.api.fastapi_app:create_omni_one_app --factory --reload --port 5003`
